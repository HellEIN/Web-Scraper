
# Casablanca Stock Exchange Web Scraper

This Python project automates the extraction of historical stock data from the Casablanca Stock Exchange (Bourse de Casablanca) website. It uses **Playwright** to navigate the site, handle dynamic content, and export structured data into CSV files for further analysis.

## Features

* Automatically scrape historical stock data for a selected instrument and date range
* Handles dynamic page elements including dropdowns and pagination
* Exports collected data into CSV format with proper column headers
* Built with asynchronous programming for faster and efficient scraping

## Technologies Used

* **Python** – Core programming language
* **Playwright** – Web automation and browser control
* **CSV** – Data export format
* **asyncio** – Asynchronous programming for concurrent tasks

## How to Use

1. Clone the repository:

   ```bash
   git clone https://github.com/HellEIN/Web-Scraper.git
   cd bourse de Casablanca
   ```

2. Install dependencies:

   ```bash
   pip install playwright asyncio
   playwright install
   ```

3. Update the date range and instrument in `main.py`:

   ```python
   await page.fill("input[placeholder='Séance']", 'janvier 1, 2023')
   await page.fill("input[placeholder='Date fin']", 'décembre 31, 2024')
   await page.click('li:has-text("ATTIJARIWAFA BANK")')
   ```

4. Run the scraper:

   ```bash
   python CasaBourse_scraper.py
   ```

5. The scraped data will be saved as a CSV file in the format: `ATWYYYY-MM-DD.csv`

## Benefits

* Quickly gather structured financial data without manual effort
* Enables further analysis for research, trading insights, or reporting
* Learn and practice asynchronous web automation and data extraction

## Learning Outcomes

* Mastered **Playwright** for automated browser interactions
* Implemented **pagination handling** and dynamic element selection
* Applied **asynchronous programming** in real-world scraping tasks


