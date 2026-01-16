import asyncio
import csv
import os
from playwright.async_api import async_playwright
import datetime as dt

# ======================================================================================
# FUNCTION: get_all_companies
# PURPOSE:  Clicks the dropdown menu and extracts every company name listed.
# LOGIC:    1. Opens the 'autocomplete' list.
#           2. Loops through the span elements to find company names.
#           3. Closes the dropdown by clicking the 'body' to reset the UI state.
# ======================================================================================
async def get_all_companies(page):
    """
    Scrapes the 'autocomplete' dropdown to retrieve all available company names.
    """
    # .click(): Sends a mouse click event to the specific element found by the CSS selector
    await page.click('button[aria-label="autocomplete"]')
    
    # .wait_for_selector(): Pauses execution until the element appears in the DOM
    await page.wait_for_selector('ul[role="listbox"]')

    # .locator(): Creates a pointer to elements matching the selector (doesn't execute yet)
    options = page.locator('ul[role="listbox"] li span')
    companies = []

    # .count(): Returns the number of elements currently matched by the locator
    count = await options.count()
    for i in range(count):
        # .nth(i): Selects the specific element at index 'i' from the list of matches
        # .inner_text(): Retrieves the visible text inside the element
        name = (await options.nth(i).inner_text()).strip()
        
        if name != "Tous les instruments":
            companies.append(name)
    
    # Clicking the 'body' tag is a trick to click empty space and close the dropdown
    await page.click("body")
    return companies

# ======================================================================================
# FUNCTION: scrape_company
# PURPOSE:  Filters the website data table for a specific company.
# LOGIC:    1. Re-opens the dropdown.
#           2. Uses a text-based selector to click the specific company.
#           3. Clicks 'Appliquer' to trigger the table refresh.
# ======================================================================================
async def scrape_company(page, company_name):
    """
    Interacts with the website UI to select a specific company and refresh the table.
    """
    await page.click('button[aria-label="autocomplete"]')
    
    # state="visible": Ensures the element is not just in the code, but actually seen by the user
    await page.wait_for_selector('ul[role="listbox"]', state="visible")
    
    # :has-text(""): A Playwright pseudo-selector that finds elements containing specific text
    await page.click(f'ul[role="listbox"] li:has-text("{company_name}")')
    
    # Matches a button based on the text it displays
    await page.click('button:has-text("Appliquer")')
    
    # Wait for the table to refresh so we don't scrape old data
    await page.wait_for_selector("table", state="visible")
    
    # .wait_for_timeout(): A hard pause (in milliseconds). Use sparingly!
    await page.wait_for_timeout(1000) 

HEADERS = [
    "Company", "Séance", "Instrument", "Ticker", "Ouverture",
    "Dernier_Cours", "+haut_du_jour", "+bas_du_jour",
    "Nombre_de_titres_échangés", "Volume_des_échanges",
    "Nombre_de_transactions", "Capitalisation"
]

# ======================================================================================
# FUNCTION: main
# PURPOSE:  The core engine that coordinates the entire scraping process.
# LOGIC:    1. Launches the browser and navigates to the URL.
#           2. Clears date filters to get all history.
#           3. Calls 'get_all_companies' to get the loop items.
#           4. Iterates through each company:
#              a. Filters the data.
#              b. Uses a 'while' loop to navigate through pages (1, 2, 3...).
#              c. Saves data to individual and global CSV files.
# ======================================================================================
async def main():
    # async_playwright(): Starts the Playwright driver manager
    async with async_playwright() as p:
        
        # .chromium.launch(): Starts an instance of the Chromium browser
        # slow_mo: Forces Playwright to wait X ms between every single interaction
        browser = await p.chromium.launch(headless=False, slow_mo=1000) 
        
        # .new_page(): Opens a new browser tab
        page = await browser.new_page()
        
        # .goto(): Navigates the current tab to a specific URL
        await page.goto("https://www.casablanca-bourse.com/fr/instruments")

        # .fill(): Clears the input field and types the provided string
        await page.fill("input[placeholder='Séance']", '')
        await page.fill("input[placeholder='Date fin']", '')

        print("Fetching company list...")
        companies = await get_all_companies(page)
        
        date = dt.datetime.now().strftime("%Y-%m-%d")
        os.makedirs("data", exist_ok=True)

        global_path = f"data/all_companies_{date}.csv"
        
        with open(global_path, "w", newline="", encoding="utf-8") as global_file:
            global_writer = csv.writer(global_file)
            global_writer.writerow(HEADERS)

            for company in companies:
                print(f"\n--- Scraping: {company} ---")
                await scrape_company(page, company)

                company_file = f"data/{company.replace(' ', '_')}_{date}.csv"
                with open(company_file, "w", newline="", encoding="utf-8") as f:
                    company_writer = csv.writer(f)
                    company_writer.writerow(HEADERS[1:]) 

                    current_page = 1
                    while True:
                        rows = page.locator("table tbody.whitespace-nowrap tr")
                        row_count = await rows.count()
                        
                        if row_count == 0:
                            print(f"   No data found for {company}")
                            break

                        for i in range(row_count):
                            cells = rows.nth(i).locator("td")
                            
                            # .all_inner_texts(): Returns a list of strings for all matching elements at once
                            cell_texts = await cells.all_inner_texts()
                            if cell_texts:
                                company_writer.writerow(cell_texts)
                                global_writer.writerow([company] + cell_texts)

                        next_page_num = current_page + 1
                        
                        # .get_by_role(): Finds elements by their ARIA role (button, link, heading, etc.)
                        # exact=True: Ensures it only matches "2", not "12" or "20"
                        next_button = page.get_by_role("button", name=str(next_page_num), exact=True)

                        # .is_visible(): Returns True/False immediately without waiting
                        if await next_button.is_visible():
                            print(f"   Moving to page {next_page_num}...")
                            await next_button.click()
                            
                            try:
                                # .wait_for_load_state("networkidle"): Waits until there are no active API/network calls
                                await page.wait_for_load_state("networkidle", timeout=3000)
                            except:
                                await page.wait_for_timeout(1000)
                            
                            current_page = next_page_num
                        else:
                            print(f"   Finished all pages for {company}.")
                            break

        # .close(): Shuts down the browser and cleans up temporary files
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())