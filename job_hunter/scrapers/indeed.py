import urllib.parse
from typing import List, Optional
from selenium.webdriver.common.by import By
from langdetect import detect

from job_hunter.scrapers.base_scraper import BaseScraper
from job_hunter.models import JobRecord
from tools.browser_manager import BrowserManager

class IndeedScraper(BaseScraper):
    def __init__(self, profile_name="default"):
        self.bm = BrowserManager()
        self.profile_name = profile_name
        self.platform_name = "Indeed"

    @property
    def driver(self):
        return self.bm.get_driver(headless=False, profile_name=self.profile_name)

    def search(self, keyword: str, location: str, limit: int = 10, easy_apply: bool = False) -> List[JobRecord]:
        self.bm.load_cookies("https://de.indeed.com/")
        results = []
        domain = "de.indeed.com"
        
        # If easy_apply is on, Indeed can filter by "schnellbewerbung" in the query
        search_kw = keyword
        if easy_apply:
            search_kw += " schnellbewerbung"

        base_url = f"https://{domain}/jobs?q={urllib.parse.quote(search_kw)}&l={urllib.parse.quote(location)}"
        
        self.log(f"Navigating to: {base_url}")
        self.driver.get(base_url)
        self.random_sleep(4, 6)
        
        start = 0
        while len(results) < limit:
            url = base_url + f"&start={start}"
            if start > 0:
                self.driver.get(url)
                self.random_sleep(3, 5)

            cards = self.driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon") or \
                    self.driver.find_elements(By.CSS_SELECTOR, "td.resultContent")
            
            self.log(f"Found {len(cards)} cards on page...")
            if not cards: break
            
            found_on_page = 0
            for card in cards:
                if len(results) >= limit: break
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, "h2.jobTitle")
                    title = title_el.text.strip()
                    
                    company_el = card.find_element(By.CSS_SELECTOR, "[data-testid='company-name']")
                    company = company_el.text.strip()

                    link_el = card.find_element(By.TAG_NAME, "a")
                    href = link_el.get_attribute("href")

                    if href and "jk=" in href:
                        jk = href.split("jk=")[1].split("&")[0]
                        link = f"https://{domain}/viewjob?jk={jk}"
                    else:
                        link = href
                    
                    is_easy = False
                    try:
                        badge = card.find_element(By.CSS_SELECTOR, ".ialbl, [data-testid='indeedApply']")
                        if badge: is_easy = True
                    except:
                        if "schnellbewerbung" in card.text.lower(): is_easy = True

                    if not any(j.link == link for j in results):
                        job_rec = JobRecord(
                            title=title,
                            company=company,
                            location=location,
                            link=link,
                            platform=self.platform_name,
                            is_easy_apply=is_easy
                        )
                        results.append(job_rec)
                        found_on_page += 1
                except:
                    continue
            
            if found_on_page == 0: break
            start += 10

        return results

    def fetch_details(self, job_url: str) -> Optional[dict]:
        if not job_url: return None

        self.bm.load_cookies("https://de.indeed.com/")
        self.driver.get(job_url)
        self.random_sleep(3, 5)

        details = {
            "description": "",
            "is_easy_apply": False,
            "language": "en"
        }

        # Easy Apply Check
        try:
            page_source = self.driver.page_source.lower()
            if any(phrase in page_source for phrase in ["easily apply", "einfach bewerben", "schnellbewerbung"]):
                details["is_easy_apply"] = True
        except: pass

        # Description
        desc_selectors = ["#jobDescriptionText", "[id*='jobDescription']", ".jobsearch-JobComponent-description"]
        for selector in desc_selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
                if el and len(el.text) > 50:
                    details["description"] = el.text
                    break
            except: continue

        if details["description"]:
            try:
                details["language"] = detect(details["description"])
            except: pass

        return details
