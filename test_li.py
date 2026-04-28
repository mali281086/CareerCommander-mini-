import sys, time
sys.path.append('d:/Documents/Study/My Projects/CareerCommander(Mini)')
from tools.browser_manager import BrowserManager
bm = BrowserManager()
driver = bm.get_driver(headless=False, profile_name='default')
driver.get('https://www.linkedin.com/search/results/people/?network=%5B%22F%22%5D&origin=FACETED_SEARCH&geoUrn=%5B%22101282230%22%5D')
time.sleep(5)
print('Current URL:', driver.current_url)
