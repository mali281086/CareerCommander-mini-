
import asyncio
from playwright.async_api import async_playwright
import os

async def verify_sidebar_ui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        # Go to app
        await page.goto("http://localhost:8501")
        await page.wait_for_timeout(3000)

        # Check if sidebar has the roadmap caption (if a mission is active)
        # We might need to start a mission to see it, but we can at least check if the code doesn't crash

        # Take screenshot of sidebar
        await page.screenshot(path="/home/jules/verification/sidebar_updated.png")
        print("Screenshot saved to /home/jules/verification/sidebar_updated.png")

        # Check for the new Kill button (if active)
        # Since no mission is active by default, let's see if we can trigger one or just check the code

        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_sidebar_ui())
