#!/usr/bin/env python3
"""Wealthsimple Transaction Scraper"""

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

LOGIN_WAIT = 60

ACCOUNTS = {
    "1": {"name": "Credit Card", "id": "ca-credit-card-GSlRUnSCqQ"},
    "2": {"name": "Chequing Account", "id": "ca-cash-msb-p5o8bu"}
}

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

def get_account_selection():
    import sys
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
        if choice in ACCOUNTS:
            return ACCOUNTS[choice]
    
    print("\n" + "=" * 50)
    print(" Select Account to Extract:")
    print("=" * 50)
    for key, account in ACCOUNTS.items():
        print(f"  {key}. {account['name']}")
    print("=" * 50)
    print(f"Usage: python script.py [1|2]")
    print(f"  1 = Credit Card")
    print(f"  2 = Chequing Account")
    sys.exit(1)

def scrape_transactions(driver, account):
    try:
        driver.get("https://my.wealthsimple.com/app/login")
        
        url = f"https://my.wealthsimple.com/app/activity?account_ids={account['id']}&timeframe=last-90-days"
        
        print("\n" + "=" * 70)
        print(" STEP 1: Log in to Wealthsimple")
        print(" - Go to https://my.wealthsimple.com/app/login")
        print(" - Log in with your credentials")
        print(" - Navigate DIRECTLY to:")
        print(f"   {url}")
        print("=" * 70)
        print(f"\n>>> Waiting {LOGIN_WAIT} seconds for login...")
        
        time.sleep(LOGIN_WAIT)
        
        logger.info(f"Navigating to {account['name']} transactions...")
        driver.get(url)
        time.sleep(5)
        
        for i in range(20):
            driver.execute_script("window.scrollBy(0, 500)")
            time.sleep(0.5)
        
        time.sleep(2)
        
        # Click Load More first time
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more')]")
            btn.click()
            time.sleep(3)
        except:
            pass
        
        time.sleep(2)
        
        # Scroll more to load additional transactions
        for i in range(10):
            driver.execute_script("window.scrollBy(0, 500)")
            time.sleep(0.5)
        
        time.sleep(2)
        
        # Click Load More second time
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more')]")
            btn.click()
            time.sleep(3)
        except:
            pass
        
        time.sleep(2)
        
        rows = []
        seen = set()
        
        # Find transaction containers - Credit Card uses 'Wealthsimple' divs
        all_divs = driver.find_elements(By.XPATH, "//div[contains(., 'Wealthsimple')]")
        logger.info(f"Found {len(all_divs)} transaction containers (Credit Card method)")
        
        # If no transactions found, try Chequing Account method
        if len(all_divs) == 0:
            all_divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'Transaction') or contains(@data-testid, 'transaction') or contains(@data-track, 'transaction')]")
            logger.info(f"Found {len(all_divs)} transaction containers (Chequing method 1)")
        
        # Fallback: search for any clickable transaction elements
        if len(all_divs) == 0:
            all_divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'item') or contains(@class, 'row')][.//text()[contains(., '$')]]")
            logger.info(f"Found {len(all_divs)} transaction containers (Chequing method 2)")
        
        # Fallback: find elements containing dollar amounts with negative sign
        if len(all_divs) == 0:
            all_divs = driver.find_elements(By.XPATH, "//div[.//text()[contains(., '-$') or contains(., '-$')]]")
            logger.info(f"Found {len(all_divs)} transaction containers (Chequing method 3)")
        
        # Fallback: find all divs containing currency pattern
        if len(all_divs) == 0:
            all_divs = driver.find_elements(By.XPATH, "//div[contains(text(), '$') and contains(text(), '-')]")
            logger.info(f"Found {len(all_divs)} transaction containers (Chequing method 4)")
        
        # Fallback: use any element containing transaction amounts (not just divs)
        if len(all_divs) == 0:
            all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '-$')]")
            logger.info(f"Found {len(all_elements)} elements with negative amounts")
        
        # Step 1: Find all date headers on the page (position-based)
        # Date headers are sections like "April 20, 2026" above transaction groups
        current_year = datetime.now().year
        all_elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{current_year}')]")
        date_headers = []
        
        for elem in all_elements:
            try:
                text = elem.text.strip()
                # Match format like "April 20, 2026" or "Apr 20, 2026"
                if re.match(r'^[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4}$', text):
                    y_pos = elem.location['y']
                    if y_pos > 0:  # visible on page
                        date_headers.append({'text': text, 'y': y_pos})
            except:
                pass
        
        # Fallback: find date headers by looking for month names
        if not date_headers:
            months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
            for month in months:
                elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{month}') and contains(text(), ',')]")
                for elem in elements:
                    try:
                        text = elem.text.strip()
                        if re.match(r'^[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4}$', text):
                            y_pos = elem.location['y']
                            if y_pos > 0:
                                date_headers.append({'text': text, 'y': y_pos})
                    except:
                        pass
        
        # Sort by Y position (top to bottom)
        date_headers.sort(key=lambda x: x['y'])
        logger.info(f"Found {len(date_headers)} date headers: {[d['text'] for d in date_headers]}")
        
        # If no transaction containers found, try alternative approach
        # Scan all elements on page for transaction-like content
        if len(all_divs) == 0 and len(date_headers) > 0:
            logger.info("Using alternative element scanning approach...")
            # Search for any element containing dollar amounts (various formats)
            all_elements = driver.find_elements(By.XPATH, 
                "//*[contains(text(), '$') and not(contains(text(), 'Wealthsimple')) and not(contains(text(), 'credit'))]"
            )
            logger.info(f"Found {len(all_elements)} elements with dollar signs")
            
            for elem in all_elements:
                try:
                    elem_y = elem.location['y']
                    text = elem.text.strip()
                    
                    if not text or '$' not in text:
                        continue
                    
                    # Filter out non-transaction amounts (balance, available, etc.)
                    text_lower = text.lower()
                    if any(x in text_lower for x in ['available', 'balance', 'total', 'account', 'interest', 'earned', 'pending']):
                        continue
                    
                    # Only process lines that look like transaction amounts
                    # Format: -$XX.XX or $XX.XX or XX.XX CAD
                    if not re.search(r'[\$\-]?\d+\.\d{2}', text):
                        continue
                    
                    # Find closest date header above this element
                    date_text = "Today"
                    for dh in reversed(date_headers):
                        if dh['y'] < elem_y - 20:
                            date_text = dh['text']
                            break
                    
                    # Try to find merchant from parent/sibling elements
                    merchant = ""
                    parent = None
                    try:
                        # Go up to grandparent to find transaction container
                        parent = elem.find_element(By.XPATH, "./..")
                        grandparent = parent.find_element(By.XPATH, "./..")
                        
                        # Get all text from grandparent container
                        container_text = grandparent.text
                        if container_text:
                            lines = [l.strip() for l in container_text.split('\n') if l.strip()]
                            # Look for a line that is NOT the amount and NOT a date
                            for line in lines:
                                # Skip lines that are just amounts or dates or "CAD"
                                if '$' in line or 'CAD' in line:
                                    continue
                                if re.match(r'^[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4}$', line):
                                    continue
                                if line in ['−', '-', '']:
                                    continue
                                if len(line) > 1 and len(line) < 50:
                                    merchant = line
                                    break
                    except:
                        pass
                    
                    # If no merchant found, try parent
                    if not merchant and parent is not None:
                        try:
                            parent_text = parent.text
                            if parent_text:
                                lines = [l.strip() for l in parent_text.split('\n') if l.strip()]
                                for line in lines:
                                    if '$' in line or 'CAD' in line:
                                        continue
                                    if re.match(r'^[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4}$', line):
                                        continue
                                    if len(line) > 1 and len(line) < 50:
                                        merchant = line
                                        break
                        except:
                            pass
                    
                    # If still no merchant, look for siblings
                    if not merchant and parent is not None:
                        try:
                            siblings = parent.find_elements(By.XPATH, "./preceding-sibling::* | ./following-sibling::*")
                            for sib in siblings:
                                sib_text = sib.text.strip()
                                if sib_text and '$' not in sib_text and 'CAD' not in sib_text:
                                    if len(sib_text) > 1 and len(sib_text) < 50:
                                        merchant = sib_text
                                        break
                        except:
                            pass
                    
                    # If still no merchant, use element text without amount as fallback
                    if not merchant:
                        # Extract from text by removing the amount pattern
                        cleaned = text.replace('CAD', '').replace('−', '').replace('-', '').strip()
                        amount_match = re.search(r'[\$\−]?\s*[\d,]+\.\d{2}', cleaned)
                        if amount_match:
                            merchant = cleaned.replace(amount_match.group(), '').strip()
                        if not merchant or len(merchant) < 2:
                            merchant = "Unknown"
                    
                    if not merchant or len(merchant) < 2:
                        continue
                    
                    key = merchant + text
                    if key in seen:
                        continue
                    seen.add(key)
                    
                    rows.append({
                        "Date": parse_date(date_text),
                        "Description": merchant,
                        "Amount": parse_amount(text),
                        "Account": f"Wealthsimple {account['name']}"
                    })
                    logger.info(f"  {parse_date(date_text)} | {merchant} | {text}")
                    
                except Exception as e:
                    logger.debug(f"Error parsing element: {e}")
                    continue
            
            if rows:
                return rows
        
        # Original approach - iterate through div containers
        for div in all_divs:
            try:
                inner_html = div.get_attribute('innerHTML')
                inner_text = div.text
                lines = [l.strip() for l in inner_text.split('\n') if l.strip()]
                
                logger.debug(f"Div lines ({len(lines)}): {lines[:10]}")
                
                if len(lines) < 2:
                    logger.debug(f"Skipping div - only {len(lines)} lines")
                    continue
                
                merchant = ""
                amount = ""
                date_text = "Today"
                
                # Log the lines for debugging
                logger.debug(f"Processing {len(lines)} lines: {lines}")
                
                # First pass: look for specific merchant patterns (lines with * are likely merchants)
                for i, line in enumerate(lines):
                    if '*' in line and len(line) > 3 and len(line) < 50:
                        if not any(x in line for x in ['Purchase', 'Refund', 'Fee', 'Credit card']):
                            merchant = line
                            break
                
                # Second pass: if no merchant found, try line before Purchase/Refund/Fee
                if not merchant:
                    for i, line in enumerate(lines):
                        if line in ['Purchase', 'Refund', 'Fee']:
                            if i > 0:
                                candidate = lines[i-1]
                                # Valid merchant: not empty, not a keyword, reasonable length
                                if candidate and len(candidate) > 2 and len(candidate) < 50:
                                    if not any(x in candidate.lower() for x in ['purchase', 'refund', 'fee', 'credit card', 'today', 'scheduled', 'activity']):
                                        merchant = candidate
                                        break
                
                # Third pass: any reasonable text line that's not amount/date/type
                if not merchant:
                    for line in lines:
                        if '$' not in line and 'CAD' not in line and '-' not in line[:2]:
                            if line and len(line) > 2 and len(line) < 50:
                                if not re.match(r'^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}$', line):
                                    if 'purchase' not in line.lower() and 'refund' not in line.lower():
                                        merchant = line
                                        break
                
                # Get amount - Chequing account may have different format
                for line in lines:
                    if '$' in line or 'CAD' in line:
                        if '-' in line or '−' in line:
                            amount = line
                            break
                        # Also capture positive amounts (deposits/transfers)
                        if re.search(r'\d+\.\d{2}', line):
                            amount = line
                            break
                
                # Get inline date if present
                for line in lines:
                    if re.match(r'^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}$', line):
                        date_text = line
                        break
                
                logger.debug(f"Merchant: '{merchant}', Amount: '{amount}', Date: '{date_text}'")
                
                if not merchant or not amount:
                    logger.debug("Skipping - no merchant or amount")
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
                    "Account": f"Wealthsimple {account['name']}"
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
        account = get_account_selection()
        account_name_safe = account['name'].lower().replace(" ", "_")
        output_file = f"output/ws_transactions_{account_name_safe}.csv"
        
        logger.info("Setting up Chrome driver...")
        options = ChromeOptions()
        options.add_argument("--start-maximized")
        
        for path in ["chromedriver_win64/chromedriver.exe", "chromedriver.exe"]:
            if os.path.exists(path):
                driver = webdriver.Chrome(service=ChromeService(path), options=options)
                break
        if not driver:
            driver = webdriver.Chrome(options=options)
        
        transactions = scrape_transactions(driver, account)
        
        if transactions:
            df = pd.DataFrame(transactions)
            df.drop_duplicates(inplace=True)
            logger.info(f"Saving {len(df)} transactions")
            os.makedirs("output", exist_ok=True)
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            logger.info(f"Saved to {output_file}")
        else:
            logger.warning("No transactions found")
            
    except Exception as e:
        logger.critical(f"Failed: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()