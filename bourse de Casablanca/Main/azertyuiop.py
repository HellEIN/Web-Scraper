import asyncio
import csv
import os
import datetime as dt
from playwright.async_api import async_playwright
import schedule
import time

# --- CONFIGURATION ---
CONCURRENT_WORKERS = 4 
HEADLESS = False         
MAX_RETRIES = 10       
# ---------------------

def format_value(val):
    if not val: return val
    cleaned = val.strip().replace(" ", "").replace(",", ".")
    try:
        if cleaned.isdigit(): return int(cleaned)
        return float(cleaned)
    except ValueError: return val.strip()

def get_last_scraped_row(file_path):
    """Reads the local CSV and returns the first data row (most recent)."""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            if len(reader) > 1: # Index 0 is header, Index 1 is most recent data
                return reader[1] 
    except Exception:
        return None
    return None

async def get_all_companies(page):
    await page.goto("https://www.casablanca-bourse.com/fr/instruments", wait_until="domcontentloaded", timeout=60000)
    await page.click('input[role="combobox"]')
    await page.wait_for_selector('ul[role="listbox"]', state="visible")
    options = await page.locator('ul[role="listbox"] li span').all_inner_texts()
    return [name.strip() for name in options if name.strip() != "Tous les instruments"]

async def scrape_worker(browser, company_queue, global_writer, date, headers, stats):
    context = await browser.new_context()
    await context.route("**/*.{png,jpg,jpeg,gif,css,svg,woff,woff2}", lambda route: route.abort())
    page = await context.new_page()
    page.set_default_timeout(60000)

    while not company_queue.empty():
        company = await company_queue.get()
        success = False

        # Define file path to check for existing data
        company_file_path = f"data/{company.replace(' ', '_')}.csv" # Removed date from name to keep history in one file
        last_local_row = get_last_scraped_row(company_file_path)

        for attempt in range(MAX_RETRIES):
            try:
                await page.goto("https://www.casablanca-bourse.com/fr/instruments", wait_until="domcontentloaded")
                await page.fill("input[placeholder='Séance']", '')
                await page.fill("input[placeholder='Date fin']", '')

                # Autocomplete Logic
                combo_input = page.locator('input[role="combobox"]')
                await combo_input.click()
                await page.wait_for_timeout(250)
                await page.keyboard.press("Control+A")
                await page.wait_for_timeout(250)
                await page.keyboard.press("Backspace")
                await combo_input.type(company, delay=100)

                target_item = page.locator('ul[role="listbox"] li').filter(has_text=company).first
                await target_item.wait_for(state="visible", timeout=10000)
                await target_item.click()
                await page.click('button:has-text("Appliquer")')
                
                # Check if we actually need to scrape
                rows_locator = page.locator("table tbody.whitespace-nowrap tr")
                await rows_locator.first.wait_for(state="attached", timeout=10000)
                
                # Compare latest web row with latest local row
                first_web_row_raw = await rows_locator.first.locator("td").all_inner_texts()
                first_web_row = [str(format_value(c)) for c in first_web_row_raw]

                if last_local_row and first_web_row == last_local_row:
                    print(f"[Worker] {company} is already up to date. Skipping...")
                    success = True
                    break

                # If different, append new data
                file_exists = os.path.exists(company_file_path)
                with open(company_file_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(headers[1:])

                    current_page = 1
                    new_rows_count = 0
                    while True:
                        rows = await rows_locator.all()
                        stop_pagination = False
                        
                        for row in rows:
                            cells_raw = await row.locator("td").all_inner_texts()
                            processed = [format_value(c) for c in cells_raw]
                            
                            # If we hit the row we already have, stop scraping for this company
                            if last_local_row and [str(i) for i in processed] == last_local_row:
                                stop_pagination = True
                                break
                            
                            writer.writerow(processed)
                            global_writer.writerow([company] + processed)
                            new_rows_count += 1

                        if stop_pagination: break

                        next_btn = page.get_by_role("button", name=str(current_page + 1), exact=True)
                        if await next_btn.is_visible():
                            await next_btn.click()
                            await page.wait_for_load_state("networkidle", timeout=10000)
                            current_page += 1
                        else: break
                
                print(f"[Worker] {company} updated with {new_rows_count} new entries.")
                success = True
                stats['success'].append(company)
                break

            except Exception as e:
                print(f"   [Error] {company} attempt {attempt+1}: {str(e)[:50]}")
                await asyncio.sleep(2)

        if not success: stats['failed'].append(company)
        company_queue.task_done()
    
    await context.close()

async def main():
    date = dt.datetime.now().strftime("%Y-%m-%d")
    os.makedirs("data", exist_ok=True)
    headers = ["Company", "Séance", "Instrument", "Ticker", "Ouverture", "Dernier_Cours", 
                "+haut_du_jour", "+bas_du_jour", "Nombre_de_titres_échangés", 
                "Volume_des_échanges", "Nombre_de_transactions", "Capitalisation"]
    
    stats = {'success': [], 'failed': []}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        setup_page = await browser.new_page()
        companies = await get_all_companies(setup_page)
        await setup_page.close()

        queue = asyncio.Queue()
        for c in companies: await queue.put(c)

        global_path = f"data/global_update_{date}.csv"
        with open(global_path, "a", newline="", encoding="utf-8") as g_file:
            g_writer = csv.writer(g_file)
            if os.path.getsize(global_path) == 0: g_writer.writerow(headers)

            workers = [scrape_worker(browser, queue, g_writer, date, headers, stats) for _ in range(CONCURRENT_WORKERS)]
            await asyncio.gather(*workers)
        await browser.close()

async def run_task():
    """Wrapper to run the async main function."""
    print(f"[{dt.datetime.now()}] Starting scheduled scrape...")
    await main()
    print(f"[{dt.datetime.now()}] Scrape completed. Waiting for next scheduled run.")

def start_daily_schedule():
    """The function that manages the timing logic."""
    
    # Define the time in 24-hour format
    target_time = "20:00" 
    
    # Schedule the job
    schedule.every().day.at(target_time).do(lambda: asyncio.run(run_task()))
    
    print(f"Scheduler started. The scraper will run every day at {target_time}.")
    print("Keep this terminal window open for the scheduler to work.")

    # Loop forever to keep the script alive
    while True:
        schedule.run_pending()
        time.sleep(60) # Check every minute if it's time to run


if __name__ == "__main__":
    # You can choose to run it once immediately, then start the scheduler
    asyncio.run(main()) 
    
    start_daily_schedule()
    