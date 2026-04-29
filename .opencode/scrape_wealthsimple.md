# Skill: Scrape Wealthsimple Transactions

## Purpose
This skill assists the user in running the Wealthsimple transaction scraper to export their financial data to a CSV file. Since Wealthsimple does not provide a native CSV export for all accounts and requires manual login, this skill guides the agent to execute the script and coordinate with the user.

## Trigger
Use this skill when the user asks to "scrape transactions", "run the wealthsimple scraper", "get my credit card transactions", or "update my wealthsimple CSV".

## Context
The project uses a Python script (`script/script_ws_csv.py`) with Selenium to automate navigating the Wealthsimple web app, scrolling through transactions, extracting the data, and saving it to the `output/` folder.

## Execution Steps

1. **Verify Environment**:
   - Check if `selenium` and `pandas` are installed. If not, inform the user and run `pip install -r requirements.txt` or install them directly.
   - Note: The script uses Chrome WebDriver by default. Ensure the user has Chrome installed.

2. **Determine Extraction Scope**:
   - Confirm with the user if they want to extract the **Credit Card**, **Chequing Account**, or **both**.
   - Note: Since the Chequing account is a recent addition to the workflow, ensure you explicitly ask if they want to run extraction for it.
   - Use `1` for Credit Card and `2` for Chequing Account.

3. **Run the Script(s)**:
   - To run extraction: `python script/script_ws_csv.py <account_number>`
   - Inform the user: *"I have started the scraper for the selected account. A browser window should open shortly. Please log in to your Wealthsimple account manually within the next 60 seconds. The script will automatically navigate to your transactions and begin scraping after the wait time."*
   - **Important**: If the user wants to extract *both* accounts, you must run the script twice sequentially. Wait for the first script to finish completely and save its CSV before starting the second run. The user will need to log in manually each time unless browser session persistence is implemented.

4. **Monitor and Verify**:
   - Wait for the script execution(s) to complete.
   - Verify that the output CSV files were successfully generated in the `output/` directory:
     - `output/ws_transactions_credit_card.csv`
     - `output/ws_transactions_chequing_account.csv`

5. **Report Results and Combine (Optional)**:
   - Read the first few lines of the generated CSV files to confirm the data structure is intact (especially important for the newly added Chequing account).
   - Present a summary of the extracted transactions.
   - *Optional:* If both accounts were extracted, offer to merge them into a single consolidated CSV file using `pandas` for easier financial tracking.
