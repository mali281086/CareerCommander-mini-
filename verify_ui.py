import asyncio
from playwright.async_api import async_playwright
import os
import subprocess
import time

async def run():
    # Start streamlit in background
    proc = subprocess.Popen(["streamlit", "run", "app.py", "--server.port", "8507", "--server.headless", "true"])
    time.sleep(10) # Wait for it to start

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("http://localhost:8507")

        # Wait for streamlit to load
        await page.wait_for_selector(".stApp")

        # Scroll to bottom
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(3)

        await page.screenshot(path="home_verify_bottom.png")

        await browser.close()

    proc.terminate()

if __name__ == "__main__":
    asyncio.run(run())
