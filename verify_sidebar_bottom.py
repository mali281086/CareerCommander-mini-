
import asyncio
from playwright.async_api import async_playwright
import os

async def verify_sidebar_bottom():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        # Go to app
        await page.goto("http://localhost:8501")
        await page.wait_for_timeout(3000)

        # Scroll sidebar down if possible, or just make viewport taller
        # Streamlit sidebar is a specific div.

        await page.set_viewport_size({"width": 1280, "height": 1200})
        await page.wait_for_timeout(1000)

        await page.screenshot(path="/home/jules/verification/sidebar_bottom.png")
        print("Screenshot saved to /home/jules/verification/sidebar_bottom.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_sidebar_bottom())
