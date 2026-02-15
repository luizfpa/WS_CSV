import os
import csv
import time
import logging
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_driver():
    """Sets up the Edge WebDriver."""
    logging.info("Setting up Edge WebDriver...")
    options = EdgeOptions()
    options.add_argument("--start-maximized")
    
    # Try using webdriver_manager
    try:
        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=options)
        return driver
    except Exception as e:
        logging.warning(f"WebDriver Manager failed: {e}")
        logging.info("Attempting to use local driver or PATH...")

    # Fallback 1: Check for local msedgedriver.exe in specific folder
    local_driver_path = os.path.join(os.getcwd(), "edgedriver_win64", "msedgedriver.exe")
    if os.path.exists(local_driver_path):
        logging.info(f"Found local driver at {local_driver_path}")
        try:
            service = EdgeService(local_driver_path)
            driver = webdriver.Edge(service=service, options=options)
            return driver
        except Exception as e:
            logging.error(f"Failed to use local driver: {e}")

    # Fallback 2: Try default PATH
    try:
        logging.info("Trying default msedgedriver from PATH...")
        driver = webdriver.Edge(options=options)
        return driver
    except Exception as e:
        logging.critical("Could not setup WebDriver. Please ensure msedgedriver is in your PATH or in 'edgedriver_win64' folder.")
        raise e

def csv_escape(value):
    """Escapes CSV fields to handle commas, quotes, and newlines."""
    value = str(value)
    if ',' in value or '"' in value or '\n' in value:
        return '"{}"'.format(value.replace('"', '""'))
    return value

def parse_amount(amount_str):
    """Normalizes monetary values."""
    if not amount_str:
        return 0.0
    
    # Remove quotes, spaces (including non-breaking), and common currency symbols
    cleaned = amount_str.replace('"', '').replace("'", "").strip()
    cleaned = cleaned.replace("\xa0", "").replace(" ", "")
    cleaned = cleaned.replace("−", "-").replace("–", "-").replace("$", "")
    cleaned = cleaned.replace("CAD", "").replace("cad", "")
    cleaned = cleaned.replace(",", "") # Remove thousands separator
    
    try:
        val = float(cleaned)
        if val < 0:
            return f"-${abs(val)}"
        else:
            return f"${val}"
    except ValueError:
        # If float conversion fails, return the original string but stripped of outer quotes
        return amount_str.strip('"').strip()

def parse_date(date_str):
    """Parses date strings into YYYY-MM-DD format."""
    now = datetime.now()
    if "Today" in date_str:
        return now.strftime("%Y-%m-%d")
    elif "Yesterday" in date_str:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    
    try:
        # wealthsimple often uses "Month Day, Year" format like "October 24, 2023"
        # If year is missing, it might be current year, but usually they include it for past items.
        # Let's assume standard format first.
        return datetime.strptime(date_str, "%B %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
        
    try:
        # Sometimes it might lack the year if it's current year? (Assumption)
        # Verify if needed. For now returning original if fail.
        return datetime.strptime(date_str, "%b %d").replace(year=now.year).strftime("%Y-%m-%d")
    except ValueError:
        return date_str

def scrape_transactions(driver):
    """Scrapes transactions from the Wealthsimple web interface."""
    try:
        # Step 1: Navigate to the login page
        driver.get("https://my.wealthsimple.com/app/login")
        logging.info("Navigated to login page. Please log in manually.")
        
        # We wait for the user to log in and navigate to the activity page manually or we detect it
        # But looking at old script logic, it asks user to press Enter.
        print("\n" + "="*80)
        print(" ACTION REQUIRED: Log in to Wealthsimple and navigate to the 'Activity' or 'Transactions' page.")
        print(" Once the transactions are visible on screen, press ENTER in this terminal to continue.")
        print("="*80 + "\n")
        input("Press Enter to continue...")

        # Step 2: Ensure we are on a page with transactions
        wait = WebDriverWait(driver, 10)
        logging.info("Checking for transaction elements...")
        
        try:
            # Look for common elements that contain transaction data
            # Adjust selectors based on actual page structure if it changes
            # The old script looked for "h2" dates.
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
            logging.info("Date headers found, proceeding...")
        except Exception:
            logging.warning("No date headers (h2) found immediately. Attempting to scroll anyway.")

        # Step 3: Scroll to load all transactions
        logging.info("Scrolling to load all transactions...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2) # Wait for content to load
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # Try one more time to be sure
                time.sleep(2)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
            last_height = new_height
        logging.info("Finished scrolling.")

        # Step 4: Extract transactions
        rows = []
        
        # Strategy: Find the container that holds the dates and transactions.
        # Usually, they are siblings. We find the parent of the first h2.
        try:
            first_date = driver.find_element(By.TAG_NAME, "h2")
            parent_element = first_date.find_element(By.XPATH, "..")
            
            # Get all direct children of the parent
            # This ensures we get h2 (dates) and their following siblings (transactions or groups) in order
            children = parent_element.find_elements(By.XPATH, "./*")
            
            logging.info(f"Found {len(children)} elements in the transaction list container.")
            
            current_date = None
            
            for child in children:
                tag_name = child.tag_name.lower()
                
                # If it's a header, update current date
                if tag_name == "h2":
                    date_text = child.text.strip()
                    current_date = parse_date(date_text)
                    logging.debug(f"Current date set to: {current_date}")
                    continue
                
                # If we have a date, look for transactions in this child
                if current_date:
                    # The child might be a button (transaction) OR a div containing buttons
                    # keys to identify it's a transaction part
                    
                    # Try to find buttons inside
                    buttons = child.find_elements(By.TAG_NAME, "button")
                    
                    # If the child itself is a button (rare but possible in some layouts)
                    if tag_name == "button":
                        buttons.append(child)
                        
                    if not buttons:
                        # If no buttons, maybe it's a div acting as a row?
                        # Check text content. If it has $, likely a transaction.
                        text = child.text
                        if "$" in text or "CAD" in text:
                             # Treat this child as a transaction row container
                             buttons = [child]
                    
                    for button in buttons:
                        try:
                            full_text = button.text.strip()
                            if not full_text:
                                continue
                            
                            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                            
                            description = ""
                            trans_type = ""
                            account = ""
                            amount = ""
                            status = ""
                            
                            remaining_lines = []
                            
                            for line in lines:
                                lower_line = line.lower()
                                
                                is_currency = "$" in line or "CAD" in line or (any(c.isdigit() for c in line) and ("-" in line or "+" in line) and len(line) < 20)
                                
                                if is_currency and not amount:
                                     amount = line
                                     continue
                                     
                                if any(k == lower_line for k in ["purchase", "refund", "deposit", "transfer", "withdrawal", "buy", "sell", "dividend", "interest", "transfer out", "transfer in", "direct deposit", "bill payment", "pre-authorized debit", "check", "cheque"]):
                                     trans_type = line
                                
                                is_account_name = False
                                account_keywords = ["chequing", "dia a dia", "wealthsimple", "tfsa", "rrsp", "crypto", "personal", "spending", "joint account"]
                                if any(k in lower_line for k in account_keywords) or lower_line in ["cash", "save", "account", "card"]:
                                    account = line
                                    is_account_name = True
                                
                                if lower_line in ["pending", "processed", "cancelled", "hold"]:
                                    status = line
                                    continue

                                if not is_account_name and not is_currency:
                                    remaining_lines.append(line)

                            if remaining_lines:
                                candidate = remaining_lines[0]
                                is_candidate_type = any(k == candidate.lower() for k in ["purchase", "refund", "deposit", "transfer", "withdrawal", "buy", "sell", "dividend", "interest", "transfer out", "transfer in", "direct deposit", "bill payment", "pre-authorized debit"])
                                
                                if not is_candidate_type:
                                    description = candidate
                                elif len(remaining_lines) > 1:
                                     description = candidate
                            
                            if not description and trans_type:
                                description = trans_type
                            
                            if not account:
                                account = "Wealthsimple Account"

                            # Ignore "Credit card payment" as requested
                            if "credit card payment" in full_text.lower():
                                logging.info(f"Skipping payment transaction: {current_date} | {description}")
                                continue

                            if amount:
                                # Final cleanup of description
                                if "dia a dia" in description.lower() or "chequing" in description.lower():
                                    if trans_type:
                                        description = trans_type
                                    else:
                                        description = "Transaction"

                                rows.append({
                                    "Date": current_date,
                                    "Description": description,
                                    "Amount": parse_amount(amount),
                                    "Account": "Wealthsimple Account",
                                    "Type": trans_type, 
                                    "Status": status
                                })
                                logging.info(f"Captured: {current_date} | {description} | {amount}")

                        except Exception as e:
                            logging.debug(f"Error parsing transaction item: {e}")
                            continue

        except Exception as e:
            logging.error(f"Could not traverse transaction list: {e}")

        return rows

    except Exception as e:
        logging.error(f"An error occurred during scraping: {e}")
        return []

def main():
    driver = None
    try:
        driver = setup_driver()
        transactions = scrape_transactions(driver)
        
        if not transactions:
            logging.warning("No transactions extracted. Please check the page structure or your login status.")
            return

        logging.info(f"Extracted {len(transactions)} transactions.")

        # Convert to DataFrame
        df = pd.DataFrame(transactions)
        
        # Remove duplicates
        df.drop_duplicates(inplace=True)
        logging.info(f"Unique transactions: {len(df)}")
        
        # Ensure output directory exists
        os.makedirs("output", exist_ok=True)
        
        # Save to CSV
        output_file = "output/ws_transactions.csv"
        # Select columns in requested order: Date, Description, Amount, Account
        # User output example did not show Status or Type, so we stick to these 4.
        cols = ["Date", "Description", "Amount", "Account"]
        
        # Add missing cols if any
        for col in cols:
            if col not in df.columns:
                df[col] = ""
                
        df[cols].to_csv(output_file, index=False, encoding='utf-8-sig')
        logging.info(f"Successfully saved transactions to {output_file}")
        
    except Exception as e:
        logging.critical(f"Critical failure: {e}")
    finally:
        if driver:
            logging.info("Closing browser...")
            driver.quit()

if __name__ == "__main__":
    main()
