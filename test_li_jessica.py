import sys, time
sys.path.append('d:/Documents/Study/My Projects/CareerCommander(Mini)')
from tools.browser_manager import BrowserManager
from selenium.webdriver.common.by import By

bm = BrowserManager()
driver = bm.get_driver(headless=False, profile_name='default')

driver.get('https://www.linkedin.com/search/results/people/?network=%5B"F"%5D&origin=FACETED_SEARCH&keywords=Recruiter')
time.sleep(7)

try:
    li = driver.find_element(By.XPATH, "//li[contains(., 'Jessica Sohail')]")
    html = li.get_attribute("outerHTML")
    with open("jessica.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved jessica.html")
except Exception as e:
    print("Error:", e)
