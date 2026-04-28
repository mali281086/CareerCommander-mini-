import sys, time
sys.path.append('d:/Documents/Study/My Projects/CareerCommander(Mini)')
from tools.browser_manager import BrowserManager
from selenium.webdriver.common.by import By

bm = BrowserManager()
driver = bm.get_driver(headless=False, profile_name='default')

driver.get('https://www.linkedin.com/search/results/people/?network=%5B"F"%5D&origin=FACETED_SEARCH&keywords=Recruiter')
time.sleep(7)

buttons1 = driver.find_elements(By.TAG_NAME, "button")
print(f"Total buttons on page: {len(buttons1)}")
for b in buttons1:
    text = b.text.strip()
    if text:
        print(f"Button: '{text}'")

