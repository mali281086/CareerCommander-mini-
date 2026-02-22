import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://localhost:8501")
        await page.wait_for_timeout(5000)

        # Check Home
        await page.screenshot(path="frontend_home.png")

        # Check Networking
        await page.click("text=Networking")
        await page.wait_for_timeout(2000)
        await page.screenshot(path="frontend_networking.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
