import sys, time
sys.path.append('d:/Documents/Study/My Projects/CareerCommander(Mini)')
from tools.browser_manager import BrowserManager
from selenium.webdriver.common.by import By

bm = BrowserManager()
driver = bm.get_driver(headless=False, profile_name='default')

driver.get('https://www.linkedin.com/search/results/people/?network=%5B%22F%22%5D&origin=FACETED_SEARCH&keywords=Berlin')
time.sleep(5)

items = driver.find_elements(By.CSS_SELECTOR, ".reusable-search__result-container")
print(f"Found {len(items)} items using .reusable-search__result-container")

if len(items) == 0:
    print("Trying alternative selectors...")
    # Print the class names of the first few elements that look like search results
    search_results = driver.find_elements(By.CSS_SELECTOR, "li")
    for li in search_results[:10]:
        print("li classes:", li.get_attribute("class"))
else:
    for item in items[:2]:
        try:
            name_elem = item.find_element(By.CSS_SELECTOR, ".entity-result__title-text a span[aria-hidden='true']")
            print("Name:", name_elem.text.strip())
        except Exception as e:
            print("Could not find name:", e)
