# Wealthsimple Transactions to CSV

This Python script uses Selenium to scrape credit card transactions from the Wealthsimple web interface and export them to a CSV file. It navigates the Wealthsimple transactions page, extracts transaction details (date, description, type, account, amount, and status), and saves them to `output/transactions.csv`.

## Features
- Extracts transactions grouped by date.
- Handles dynamic HTML structures with robust selectors.
- Normalizes monetary values (e.g., converts "−$3.49" to `-3.49`).
- Escapes CSV fields to handle commas and quotes correctly.
- Removes duplicate transactions.
- Saves output to a structured CSV file for easy import into financial tools (e.g., Excel, QuickBooks).

## Prerequisites
- **Python 3.6+**: Install from [python.org](https://www.python.org/downloads/).
- **Microsoft Edge Browser**: Ensure it's installed and updated.
- **Edge WebDriver**: Download the version matching your Edge browser from [Microsoft Edge WebDriver](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver?form=MA13LH#installation). Place `msedgedriver.exe` in your system PATH or specify its path in the script.
- **Python Libraries**:
  ```bash
  pip install selenium
  ```
- **Wealthsimple Account**: You need login credentials to access the transactions page.
- A folder named `output` in the project directory to store the generated CSV.

## Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/WS_CSV.git
   cd WS_CSV
   ```
2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   source .venv/bin/activate  # On macOS/Linux
   ```
3. Install dependencies:
   ```bash
   pip install selenium
   ```
4. Ensure the `output` folder exists in the project directory:
   ```bash
   mkdir output
   ```
5. (Optional) If `msedgedriver.exe` is not in PATH, update the script to specify its path:
   ```python
   service = Service("C:/path/to/msedgedriver.exe")
   driver = webdriver.Edge(service=service, options=edge_options)
   ```

## Usage
1. Run the script:
   ```bash
   python script_ws_csv_updated.py
   ```
2. The script opens the Wealthsimple login page in Microsoft Edge. Log in manually.
3. Navigate to the credit card transactions page in the Wealthsimple web interface.
4. Press Enter in the terminal when prompted.
5. The script scrolls the page to load all transactions, extracts them, and saves them to `output/transactions.csv`.

## Expected Output
The script generates a CSV file (`output/transactions.csv`) with the following columns:
- **Date**: Transaction date (YYYY-MM-DD).
- **Description**: Transaction description (e.g., "Real Cdn Superstore #1561").
- **Type**: Transaction type (e.g., "Purchase", "Refund").
- **Account**: Account name (e.g., "Credit card • Wealthsimple credit card").
- **Amount**: Monetary value (positive for refunds, negative for purchases).
- **Status**: Transaction status (e.g., "Pending").

**Example CSV Content:**
```
Date,Description,Type,Account,Amount,Status
2025-07-22,"Hm Hennes Mauritz Inc.",Refund,"Credit card • Wealthsimple credit card",55.97,
2025-07-11,"From: Chequing",,"Credit card • Wealthsimple credit card",1800.0,
```

## Notes
- **Manual Navigation**: The script requires manual login and navigation to the transactions page due to Wealthsimple's authentication.
- **Dynamic HTML**: The script is tailored to the Wealthsimple transactions page structure as of August 2025. If the HTML changes, inspect the page (F12) and update the selectors in the script.
- **Scraping Risks**: Web scraping may violate Wealthsimple's terms of service. Use this script at your own risk and only for your own account data. Consider requesting a native CSV export feature from Wealthsimple support.
- **Debugging**:
  - Ensure a stable internet connection.
  - Verify Edge WebDriver matches your browser version.
  - Check the `output` folder exists and is writable.
  - Review console logs for errors or missing transactions.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.