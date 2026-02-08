import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto("http://localhost:8502")
            await asyncio.sleep(5)

            # Navigate to Current Job Batch
            await page.click("text=Current Job Batch")
            await asyncio.sleep(3)

            await page.screenshot(path="/home/jules/verification/explorer_v3.png", full_page=True)
            print("Screenshot saved to /home/jules/verification/explorer_v3.png")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

asyncio.run(run())
