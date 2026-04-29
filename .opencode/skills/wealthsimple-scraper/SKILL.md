---
name: wealthsimple-scraper
description: Guidance for improving Wealthsimple transaction scraping with Selenium. Covers project structure, scraping logic, key functions, and improvement suggestions.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: scraping
---

## Project Overview

This project scrapes Wealthsimple transaction data using Selenium and exports to CSV.

### Project Structure
- `script/script_ws_csv.py` - Main scraping script
- `output/` - CSV output directory
- `requirements.txt` - Dependencies (selenium, webdriver-manager, pandas)

### How It Works

1. **Account Selection**: Pass argument `1` (Credit Card) or `2` (Chequing Account)
2. **Login Flow**: Opens Wealthsimple login page, waits 60 seconds for manual login
3. **Navigation**: Direct URL to account activity page
4. **Loading**: Scrolls page and clicks "Load More" twice to load all transactions
5. **Parsing**: Extracts merchant, amount, date from transaction divs
6. **Export**: Saves to CSV with columns: Date, Description, Amount, Account

## Key Functions

### `parse_amount(amount_str)`
- Cleans currency strings: removes $, CAD, handles special dashes (−, –)
- Returns formatted string like `$50.00` or `-$25.00`

### `parse_date(date_text)`
- Handles "Today", "Yesterday", and formats like "April 20, 2026"
- Returns ISO format: YYYY-MM-DD

### `scrape_transactions(driver, account)`
- Main scraping logic using Selenium
- Finds transaction containers with XPath
- Parses date headers and associates with transactions
- Returns list of transaction dicts

### `get_account_selection()`
- Returns account dict with `id` for URL construction

## Known Issues / Improvements Needed

1. **Position-based scraping** - Uses Y-position to associate date headers with transactions; breaks if UI changes
2. **Magic numbers** - LOGIN_WAIT=60, scroll counts (20, 10), sleep times scattered throughout
3. **No type hints** - Function signatures lack annotations
4. **No config management** - Hardcoded values should come from .env or config.py
5. **Limited error handling** - Try/except passes silently on many errors
6. **Fragile XPath** - Transaction container selectors may break with website updates

## Usage

```bash
# Activate virtual environment
.venv\Scripts\activate

# Run for Credit Card
python script/script_ws_csv.py 1

# Run for Chequing Account
python script/script_ws_csv.py 2
```

## When Helping with This Project

- Run the script with account argument to test extraction
- Check output CSV for completeness and accuracy
- Look for parsing errors in logs
- Suggest improvements using the known issues as starting points
- Ensure ChromeDriver is available in PATH or specified in script