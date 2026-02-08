import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        # Wait for streamlit to be ready
        await page.goto("http://localhost:8501")
        await asyncio.sleep(5)

        # Click on "Current Job Batch"
        await page.click("text=Current Job Batch")
        await asyncio.sleep(3)

        await page.screenshot(path="/home/jules/verification/explorer_v2.png", full_page=True)
        await browser.close()

asyncio.run(run())
