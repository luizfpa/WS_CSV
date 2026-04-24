#!/usr/bin/env python3
"""Wealthsimple Credit Card Transaction Scraper"""

import os
import time
import logging
import re
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
import pandas as pd

OUTPUT_FILE = "output/ws_transactions.csv"
LOGIN_WAIT = 60

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_amount(amount_str):
    if not amount_str:
        return "0.0"
    cleaned = amount_str.replace('"', '').replace("'", "").strip()
    cleaned = cleaned.replace("\xa0", "").replace(" ", "").replace("−", "-").replace("–", "-").replace("$", "")
    cleaned = cleaned.replace("CAD", "").replace("cad", "").replace(",", "")
    try:
        val = float(cleaned)
        return f"-${abs(val)}" if val < 0 else f"${val}"
    except ValueError:
        return amount_str.strip('"').strip()

def parse_date(date_text):
    today = datetime.now()
    date_text = str(date_text).strip()
    if date_text == "Today":
        return today.strftime("%Y-%m-%d")
    elif date_text == "Yesterday":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    for fmt in ["%B %d, %Y", "%b %d, %Y"]:
        try:
            return datetime.strptime(date_text, fmt).strftime("%Y-%m-%d")
        except:
            continue
    return today.strftime("%Y-%m-%d")

def scrape_transactions(driver):
    try:
        driver.get("https://my.wealthsimple.com/app/login")
        
        print("\n" + "=" * 70)
        print(" STEP 1: Log in to Wealthsimple")
        print(" - Go to https://my.wealthsimple.com/app/login")
        print(" - Log in with your credentials")
        print(" - Navigate DIRECTLY to:")
        print("   https://my.wealthsimple.com/app/activity?account_ids=ca-credit-card-GSlRUnSCqQ")
        print("=" * 70)
        print(f"\n>>> Waiting {LOGIN_WAIT} seconds for login...")
        
        time.sleep(LOGIN_WAIT)
        
        logger.info("Navigating to Credit Card transactions...")
        driver.get("https://my.wealthsimple.com/app/activity?account_ids=ca-credit-card-GSlRUnSCqQ")
        time.sleep(5)
        
        for i in range(20):
            driver.execute_script("window.scrollBy(0, 500)")
            time.sleep(0.5)
        
        time.sleep(2)
        
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more')]")
            btn.click()
            time.sleep(3)
        except:
            pass
        
        time.sleep(2)
        
        rows = []
        seen = set()
        
        # Find all transaction containers by searching for elements containing "Credit card"
        all_divs = driver.find_elements(By.XPATH, "//div[contains(., 'Wealthsimple credit card')]")
        logger.info(f"Found {len(all_divs)} transaction containers")
        
        # Step 1: Find all date headers on the page (position-based)
        # Date headers are sections like "April 20, 2026" above transaction groups
        all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '2026')]")
        date_headers = []
        
        for elem in all_elements:
            try:
                text = elem.text.strip()
                # Match format like "April 20, 2026" or "April 24, 2026"
                if re.match(r'^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}$', text):
                    y_pos = elem.location['y']
                    if y_pos > 0:  # visible on page
                        date_headers.append({'text': text, 'y': y_pos})
            except:
                pass
        
        # Sort by Y position (top to bottom)
        date_headers.sort(key=lambda x: x['y'])
        logger.info(f"Found {len(date_headers)} date headers: {[d['text'] for d in date_headers]}")
        
        for div in all_divs:
            try:
                inner_html = div.get_attribute('innerHTML')
                inner_text = div.text
                lines = [l.strip() for l in inner_text.split('\n') if l.strip()]
                
                if len(lines) < 3:
                    continue
                
                # Transaction block format based on website structure:
                # Line 1 (or 2): Merchant name, e.g., "Amazon* Bs53M5Ep1"
                # Line 3: Type "Purchase", "Refund", or "Fee"
                # Last lines: Amount and date
                
                merchant = ""
                amount = ""
                date_text = "Today"
                
                for i, line in enumerate(lines):
                    if '$' in line and ('-' in line or '−' in line):
                        amount = line
                    elif line in ['Purchase', 'Refund', 'Fee']:
                        pass  # type we don't need separately
                    elif re.match(r'^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}$', line):
                        date_text = line
                    elif line and not merchant and len(line) > 2 and len(line) < 50:
                        if not re.search(r'\d{4}', line):  # skip if contains year
                            merchant = line
                
                if not merchant:
                    for i, line in enumerate(lines):
                        if line in ['Purchase', 'Refund', 'Fee']:
                            if i > 0:
                                candidate = lines[i-1]
                                if candidate and candidate not in ['Purchase', 'Refund', 'Fee', 'Credit card', 'Wealthsimple credit card']:
                                    merchant = candidate
                                    break
                
                if not merchant or not amount:
                    continue
                if 'payment' in merchant.lower():
                    continue
                if merchant in ['Tax', 'Activity', 'Scheduled activities', 'Today']:
                    continue
                if 'Credit card' in merchant or 'Wealthsimple credit card' in merchant:
                    continue
                if re.match(r'^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}$', merchant):
                    continue
                
                # Step 2: If no inline date found, find closest date header above this transaction
                if date_text == "Today":
                    try:
                        div_y = div.location['y']
                        # Find the date header that is closest and above this transaction
                        for dh in reversed(date_headers):
                            if dh['y'] < div_y - 20:  # 20px buffer
                                date_text = dh['text']
                                break
                    except:
                        pass
                
                key = merchant + amount
                if key in seen:
                    continue
                seen.add(key)
                
                rows.append({
                    "Date": parse_date(date_text),
                    "Description": merchant,
                    "Amount": parse_amount(amount),
                    "Account": "Wealthsimple Credit Card"
                })
                logger.info(f"  {parse_date(date_text)} | {merchant} | {amount}")
                
            except Exception as e:
                logger.debug(f"Error parsing div: {e}")
                continue
        
        return rows
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    driver = None
    try:
        logger.info("Setting up Chrome driver...")
        options = ChromeOptions()
        options.add_argument("--start-maximized")
        
        for path in ["chromedriver_win64/chromedriver.exe", "chromedriver.exe"]:
            if os.path.exists(path):
                driver = webdriver.Chrome(service=ChromeService(path), options=options)
                break
        if not driver:
            driver = webdriver.Chrome(options=options)
        
        transactions = scrape_transactions(driver)
        
        if transactions:
            df = pd.DataFrame(transactions)
            df.drop_duplicates(inplace=True)
            logger.info(f"Saving {len(df)} transactions")
            os.makedirs("output", exist_ok=True)
            df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
            logger.info(f"Saved to {OUTPUT_FILE}")
        else:
            logger.warning("No transactions found")
            
    except Exception as e:
        logger.critical(f"Failed: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()