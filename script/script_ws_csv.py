from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
import csv
import time
from datetime import datetime
from datetime import timedelta

 # Function to escape CSV fields
def csv_escape(value):
    value = str(value)  # Convert to string to avoid errors with floats
    if isinstance(value, str) and (',' in value or '"' in value or '\n' in value):
        return '"{}"'.format(value.replace('"', '""'))
    return value

 # Function to normalize monetary values
def parse_amount(amount_str):
    cleaned = amount_str.replace("−", "-").replace("$", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return amount_str

 # Function to format dates
def parse_date(date_str):
    if "Today" in date_str:
        return datetime.now().strftime("%Y-%m-%d")
    elif "Yesterday" in date_str:
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        return datetime.strptime(date_str, "%B %d, %Y").strftime("%Y-%m-%d")
    except:
        return date_str

 # Microsoft Edge WebDriver setup
edge_options = webdriver.EdgeOptions()
edge_options.add_argument("--start-maximized")
 # Specify the path to msedgedriver.exe if necessary
 # service = Service("C:/WebDriver/msedgedriver.exe")
 # driver = webdriver.Edge(service=service, options=edge_options)
driver = webdriver.Edge(options=edge_options)  # Use if msedgedriver.exe is in PATH

try:
    # Step 1: Navigate to the login page
    driver.get("https://my.wealthsimple.com/app/login")
    print("Navigated to the login page. Please log in manually.")
    input("Press Enter after you have manually navigated to the credit card transactions page...")

    # Step 2: Check if the transactions page has loaded
    wait = WebDriverWait(driver, 30)
    print("Waiting for the transactions page to load...")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Transaction') or contains(text(), 'Recent Activity')]")))
        print("Transactions page detected.")
    except:
        print("WARNING: No element indicating transactions was found. Make sure you are on the correct page.")

    # Step 3: Scroll to the bottom of the page
    print("Scrolling the page to load all transactions...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    print("Scrolling completed.")

    # Step 4: Extract transactions by date
    rows = []
    dates = driver.find_elements(By.TAG_NAME, "h2")
    print(f"Found {len(dates)} dates.")

    for date_el in dates:
        date = parse_date(date_el.text.strip())
        
        # Find the next div after h2 (transaction group) and extract buttons inside
        try:
            group_div = date_el.find_element(By.XPATH, "following-sibling::div[1]")
            transaction_buttons = group_div.find_elements(By.TAG_NAME, "button")
            print(f"For date '{date}': Found {len(transaction_buttons)} transaction buttons.")
        except:
            continue

        for button in transaction_buttons:
            # Sub-elements (p, span, div)
            sub_elements = button.find_elements(By.XPATH, ".//*[self::p or self::span or self::div]")
            
            description = None
            trans_type = None
            account = None
            amount = None
            status = None
            
            for sub in sub_elements:
                text = sub.text.strip()
                if not description and text and not "$" in text and not any(word in text.lower() for word in ["purchase", "refund", "credit card"]):
                    description = text
                elif "Purchase" in text or "Refund" in text:
                    trans_type = text
                elif "Credit card" in text:
                    account = text
                elif "$" in text and any(char.isdigit() for char in text):
                    amount = text.replace("−", "-")
                elif text.lower() == "pending":
                    status = text

            if date and description and amount:
                rows.append([date, description, trans_type or "", account or "", parse_amount(amount), status or ""])
                print(f"Transaction found: {date}, {description}, {amount}")

    if not rows:
        print("WARNING: No transactions found. Check the HTML or the transactions page.")

    # Step 5: Remove duplicates
    unique_rows = [list(t) for t in set(tuple(row) for row in rows)]
    print(f"Total unique transactions: {len(unique_rows)}")

    # Step 6: Save CSV
    csv_header = ["Date", "Description", "Type", "Account", "Amount", "Status"]
    csv_rows = [csv_header] + unique_rows
    with open("output/transactions.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in csv_rows:
            writer.writerow([csv_escape(cell) for cell in row])

    print("CSV file successfully generated: transactions.csv")

except Exception as e:
    print(f"Error during execution: {e}")
    print("Debugging tips:")
    print("- Make sure you are on the correct transactions page after login.")
    print("- Inspect the HTML (F12) to confirm the tags (h2 for dates, button for transactions, p for descriptions/amounts).")
    print("- Make sure Edge WebDriver is up to date and in the PATH.")
    print("- Test with a stable internet connection.")

finally:
    driver.quit()