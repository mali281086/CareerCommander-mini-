import sys, time
sys.path.append('d:/Documents/Study/My Projects/CareerCommander(Mini)')
from tools.browser_manager import BrowserManager
from selenium.webdriver.common.by import By

bm = BrowserManager()
driver = bm.get_driver(headless=False, profile_name='default')

driver.get('https://www.linkedin.com/search/results/people/?network=%5B"F"%5D&origin=FACETED_SEARCH&keywords=Recruiter')
time.sleep(7)

try:
    lis = driver.find_elements(By.CSS_SELECTOR, "li")
    for li in lis:
        html = li.get_attribute("outerHTML")
        if "Recruiter" in html or "1st" in html:
            with open("first_li.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Saved first_li.html")
            break
except Exception as e:
    print("Error:", e)
