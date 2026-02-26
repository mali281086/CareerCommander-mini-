from playwright.sync_api import sync_playwright, expect
import time

def verify_home_stays(page):
    page.goto("http://localhost:8501")
    time.sleep(5) # Wait for Streamlit to load

    # 1. Take a screenshot of the Home view
    page.screenshot(path="/home/jules/verification/home_view_stays_check.png", full_page=True)

    # 2. Check if we are still on Home by looking for Home title or certain elements
    expect(page.get_by_text("🚀 CareerCommander (Mini)")).to_be_visible()

    # Check that we are NOT on Results screen automatically
    expect(page.get_by_text("🔎 Mission Results")).not_to_be_visible()

    print("✅ Verified that Home page stays on Home and does not automatically redirect to Results!")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_home_stays(page)
        except Exception as e:
            print(f"❌ Error during verification: {e}")
        finally:
            browser.close()
