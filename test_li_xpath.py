import sys, time
sys.path.append('d:/Documents/Study/My Projects/CareerCommander(Mini)')
from tools.browser_manager import BrowserManager
from selenium.webdriver.common.by import By

bm = BrowserManager()
driver = bm.get_driver(headless=False, profile_name='default')

# Start from connections page
driver.get("https://www.linkedin.com/mynetwork/invite-connect/connections/")
time.sleep(3)

# Then go to the search with filters page
driver.get('https://www.linkedin.com/search/results/people/?origin=MEMBER_PROFILE_CANNED_SEARCH&network=%5B"F"%5D&keywords=Recruiter')
time.sleep(5)

buttons = driver.find_elements(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'message') or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'message')] | //a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'message') or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'message')]")

print(f"Found {len(buttons)} message buttons")
for btn in buttons:
    try:
        print("Found:", btn.text.strip(), "| Aria:", btn.get_attribute("aria-label"))
    except:
        pass
