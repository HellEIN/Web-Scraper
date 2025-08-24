import asyncio
import csv
from playwright.async_api import async_playwright
import datetime as dt 

async def main():
    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://www.casablanca-bourse.com/fr/instruments")  
        await page.fill("input[placeholder='Séance']", 'janvier 1, 2023') # change the date base on your need 
        await page.fill("input[placeholder='Date fin']", 'décembre 31, 2024') # change the date base on your need 
        await page.wait_for_timeout(500) 
        await page.click('button[aria-label="autocomplete"]')
        await page.wait_for_selector('ul[role="listbox"]')
        await page.click('li:has-text("ATTIJARIWAFA BANK")')
        await page.click('button:has-text("Appliquer")')
        await page.wait_for_timeout(500) 
        await page.wait_for_selector("table")
        rows = page.locator("table tbody.whitespace-nowrap tr")

        date = str(dt.datetime.now().strftime("%Y-%m-%d"))
        with open(f"ATW{date}.csv", "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Séance", "Instrument","Ticker","Ouverture","Dernier_Cours","+haut_du_jour","+bas du jour","Nombre_de_titres_échangés","Volume_des_échanges","Nombre_de_transactions","Capitalisation"])

            await page.wait_for_selector("table")
            await page.wait_for_timeout(500)   #  0.5 s pause before pagination

            # Find how many pages there are:
            pagination_buttons = page.locator("nav button.text-sm")
            total_pages = int(await pagination_buttons.last.inner_text())

            # Loop over every page:
            for current_page in range(1, total_pages + 1):
                if current_page > 1:
                    await page.click(f'nav button:has-text("{current_page}")')
                    await page.wait_for_timeout(500)   # ← 0.5 s pause after click
                    await page.wait_for_selector("table")
                    await page.wait_for_timeout(500)   # ← 0.5 s pause before scraping

             
                rows = page.locator("table tbody.whitespace-nowrap tr")
                count = await rows.count()
                for i in range(count):
                    row = rows.nth(i)
                    cells = row.locator("td")
                    data = [await cells.nth(j).inner_text() for j in range(await cells.count())]
                    writer.writerow(data)

#Note: you can icrease the waiting time (wait_for_timeout) if you have a slow internet speed connection 


asyncio.run(main())
