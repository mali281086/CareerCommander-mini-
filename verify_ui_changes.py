from playwright.sync_api import sync_playwright, expect
import time

def verify_career_commander(page):
    page.goto("http://localhost:8501")
    time.sleep(5) # Wait for Streamlit to load

    # 1. Take a screenshot of the Home view
    page.screenshot(path="/home/jules/verification/home_view_check.png", full_page=True)

    # 2. Check if Mission Setup sections exist
    expect(page.get_by_text("🛰️ Mission Setup")).to_be_visible()
    expect(page.get_by_text("Execution Mode")).to_be_visible()

    # 3. Navigate to Explorer
    page.get_by_text("🔎 Explorer / Scouted").click()
    time.sleep(3)
    page.screenshot(path="/home/jules/verification/explorer_view_check.png", full_page=True)

    print("✅ Frontend verification screenshots taken!")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_career_commander(page)
        except Exception as e:
            print(f"❌ Error during verification: {e}")
        finally:
            browser.close()
