import sys, time
sys.path.append('d:/Documents/Study/My Projects/CareerCommander(Mini)')
from tools.browser_manager import BrowserManager
from selenium.webdriver.common.by import By

bm = BrowserManager()
driver = bm.get_driver(headless=False, profile_name='default')

driver.get('https://www.linkedin.com/search/results/people/?network=%5B"F"%5D&origin=FACETED_SEARCH&keywords=Recruiter')
time.sleep(5)

buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label^='Message']")
print(f"Found {len(buttons)} Message buttons")
for btn in buttons:
    print("Label:", btn.get_attribute("aria-label"))
    # Also find profile URL
    try:
        # traverse up to find the closest 'a' tag or search within the parent 'li'
        # Since button is deep, let's find the closest li
        li = btn.find_element(By.XPATH, "./ancestor::li")
        a = li.find_element(By.CSS_SELECTOR, "a[href*='/in/']")
        print("URL:", a.get_attribute("href").split('?')[0])
    except Exception as e:
        print("Could not find URL:", e)
