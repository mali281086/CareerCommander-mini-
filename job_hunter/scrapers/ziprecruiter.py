import urllib.parse
from selenium.webdriver.common.by import By
from job_hunter.scrapers.base_scraper import BaseScraper
from job_hunter.models import JobRecord
from tools.browser_manager import BrowserManager
from typing import List, Optional

class ZipRecruiterScraper(BaseScraper):
    def __init__(self, profile_name="default"):
        self.bm = BrowserManager()
        self.profile_name = profile_name
        self.platform_name = "ZipRecruiter"

    @property
    def driver(self):
        return self.bm.get_driver(headless=False, profile_name=self.profile_name)

    def search(self, keyword: str, location: str, limit: int = 10, easy_apply: bool = False) -> List[JobRecord]:
        results = []
        base_url = f"https://www.ziprecruiter.com/candidate/search?search={urllib.parse.quote(keyword)}&location={urllib.parse.quote(location)}"
        
        self.log(f"Navigating to: {base_url}")
        self.driver.get(base_url)
        self.random_sleep(3, 5)
        
        scrolled = 0
        while len(results) < limit and scrolled < 3:
            cards = self.driver.find_elements(By.CSS_SELECTOR, "div.job_content") or \
                    self.driver.find_elements(By.CSS_SELECTOR, ".job_result_container")

            self.log(f"Found {len(cards)} cards...")
            
            for card in cards:
                if len(results) >= limit: break
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, "h2.title, .job_title")
                    title = title_el.text.strip()
                    
                    company_el = card.find_element(By.CSS_SELECTOR, ".name, .company_name")
                    company = company_el.text.strip()
                    
                    link_el = card.find_element(By.TAG_NAME, "a")
                    link = link_el.get_attribute("href")
                    
                    if not any(j.link == link for j in results):
                        results.append(JobRecord(
                            title=title,
                            company=company,
                            location=location,
                            link=link,
                            platform=self.platform_name,
                            is_easy_apply=False
                        ))
                except: continue

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.random_sleep(2, 3)
            scrolled += 1
            
        return results

    def fetch_details(self, job_url: str) -> Optional[dict]:
        if not job_url: return None
        self.driver.get(job_url)
        self.random_sleep(2, 4)

        details = {"description": "", "is_easy_apply": False, "language": "en"}
        try:
            desc_selectors = [".job_description", "[class*='jobDescription']", "#job_desc"]
            desc_el = None
            for s in desc_selectors:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, s)
                    if el and len(el.text) > 50:
                        desc_el = el
                        break
                except: continue

            if desc_el:
                details['description'] = desc_el.text
            else:
                details['description'] = self.driver.find_element(By.TAG_NAME, "body").text
        except: pass
        return details
