import sys, time
sys.path.append('d:/Documents/Study/My Projects/CareerCommander(Mini)')
from tools.browser_manager import BrowserManager
from selenium.webdriver.common.by import By

bm = BrowserManager()
driver = bm.get_driver(headless=False, profile_name='default')

driver.get('https://www.linkedin.com/search/results/people/?network=%5B"F"%5D&origin=FACETED_SEARCH&keywords=Recruiter')
time.sleep(5)

lis = driver.find_elements(By.CSS_SELECTOR, "li")
for i, li in enumerate(lis):
    html = li.get_attribute("outerHTML")
    if "Message" in html:
        with open("linkedin_li_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Dumped li", i)
        break
