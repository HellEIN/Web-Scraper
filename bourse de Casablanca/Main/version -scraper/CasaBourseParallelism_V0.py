import asyncio
import csv
import os
import datetime as dt
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
CONCURRENT_WORKERS = 3  # How many browser tabs to run at once
HEADLESS = False         # Set to False only if you need to debug
# ---------------------

def format_value(val):
	if not val: return val
	cleaned = val.strip().replace(" ", "").replace(",", ".")
	try:
		if cleaned.isdigit(): return int(cleaned)
		return float(cleaned)
	except ValueError: return val.strip()

async def get_all_companies(page):
	await page.goto("https://www.casablanca-bourse.com/fr/instruments")
	await page.click('button[aria-label="autocomplete"]')
	await page.wait_for_selector('ul[role="listbox"]')
	options = await page.locator('ul[role="listbox"] li span').all_inner_texts()
	return [name.strip() for name in options if name.strip() != "Tous les instruments"]

async def scrape_worker(browser, company_queue, global_writer, date, headers):
	"""
	A worker that pulls company names from a queue and scrapes them.
	"""
	# Create a unique context (like an incognito window) for this worker
	context = await browser.new_context()
	# SPEED BOOST: Block images and CSS to save bandwidth and CPU
	await context.route("**/*.{png,jpg,jpeg,gif,css,svg,woff,woff2}", lambda route: route.abort())

	page = await context.new_page()

	while not company_queue.empty():
		company = await company_queue.get()
		print(f"[Worker] Starting: {company}")
		
		try:
			await page.goto("https://www.casablanca-bourse.com/fr/instruments")
			# Clear date filters
			await page.fill("input[placeholder='Séance']", '')
			await page.fill("input[placeholder='Date fin']", '')

			# Select Company
			await page.click('button[aria-label="autocomplete"]')

			await page.wait_for_timeout(2000)
			await page.click(f'ul[role="listbox"] li:has-text("{company}")')
			await page.click('button:has-text("Appliquer")')
			
			# Individual File Setup
			company_file_path = f"data/{company.replace(' ', '_')}_{date}.csv"
			
			with open(company_file_path, "w", newline="", encoding="utf-8") as f:
				writer = csv.writer(f)
				writer.writerow(headers[1:])

				current_page = 1
				while True:
					# Fast-wait for table
					rows_locator = page.locator("table tbody.whitespace-nowrap tr")
					try:
						await rows_locator.first.wait_for(state="attached", timeout=3000)
					except: break

					rows = await rows_locator.all()
					for row in rows:
						cells = await row.locator("td").all_inner_texts()
						if cells:
							processed = [format_value(c) for c in cells]
							writer.writerow(processed)
							global_writer.writerow([company] + processed)

					# Check Pagination
					next_btn = page.get_by_role("button", name=str(current_page + 1), exact=True)
					if await next_btn.is_visible():
						await next_btn.click()
						await page.wait_for_load_state("networkidle")
						current_page += 1
					else: break
		except Exception as e:
			print(f"Error scraping {company}: {e}")
		finally:
			company_queue.task_done()
	
	await context.close()

async def main():
	date = dt.datetime.now().strftime("%Y-%m-%d")
	os.makedirs("data", exist_ok=True)
	
	headers = ["Company", "Séance", "Instrument", "Ticker", "Ouverture", "Dernier_Cours", "+haut_du_jour", "+bas_du_jour", "Nombre_de_titres_échangés", "Volume_des_échanges", "Nombre_de_transactions", "Capitalisation"]

	async with async_playwright() as p:
		browser = await p.chromium.launch(headless=HEADLESS)
		
		# Get list first using a temporary page
		setup_page = await browser.new_page()
		companies = await get_all_companies(setup_page)
		await setup_page.close()

		# Create a queue of companies to scrape
		queue = asyncio.Queue()
		for c in companies:
			await queue.put(c)

		# Global File Setup
		global_path = f"data/all_companies_{date}.csv"
		with open(global_path, "w", newline="", encoding="utf-8") as g_file:
			g_writer = csv.writer(g_file)
			g_writer.writerow(headers)

			# Start the parallel workers
			workers = [
				scrape_worker(browser, queue, g_writer, date, headers) 
				for _ in range(CONCURRENT_WORKERS)
			]
			
			print(f"Running with {CONCURRENT_WORKERS} parallel workers...")
			await asyncio.gather(*workers)

		await browser.close()

if __name__ == "__main__":
	asyncio.run(main())