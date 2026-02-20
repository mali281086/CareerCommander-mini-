import urllib.parse
from selenium.webdriver.common.by import By
from job_hunter.scrapers.base_scraper import BaseScraper
from job_hunter.models import JobRecord
from tools.browser_manager import BrowserManager
from typing import List, Optional

class StepstoneScraper(BaseScraper):
    def __init__(self, profile_name="default"):
        self.bm = BrowserManager()
        self.profile_name = profile_name
        self.platform_name = "Stepstone"

    @property
    def driver(self):
        return self.bm.get_driver(headless=False, profile_name=self.profile_name)

    def search(self, keyword: str, location: str, limit: int = 10, easy_apply: bool = False) -> List[JobRecord]:
        results = []
        kw_slug = keyword.replace(" ", "-").lower()
        loc_slug = location.replace(" ", "-").lower()
        
        base_url = f"https://www.stepstone.de/jobs/{kw_slug}/in-{loc_slug}?"
        params = {"radius": "30"}
        url = base_url + urllib.parse.urlencode(params)
        
        self.log(f"Navigating to: {url}")
        self.driver.get(url)
        self.random_sleep(3, 5)
        
        scrolled = 0
        while len(results) < limit and scrolled < 3:
            cards = self.driver.find_elements(By.TAG_NAME, "article")
            self.log(f"Found {len(cards)} cards...")
            
            for card in cards:
                if len(results) >= limit: break
                try:
                    title_link = None
                    try:
                        h2 = card.find_element(By.TAG_NAME, "h2")
                        title_link = h2.find_element(By.TAG_NAME, "a")
                    except: pass
                    
                    if not title_link:
                        links = card.find_elements(By.TAG_NAME, "a")
                        for l in links:
                            href = l.get_attribute("href")
                            if href and "stellenangebote--" in href:
                                title_link = l
                                break
                    
                    if not title_link: continue
                    link = title_link.get_attribute("href")
                    if not link: continue
                    
                    bad_signals = ["action=", "facet_", "radius=", "ag=", "wfh=", "am="]
                    if any(sig in link for sig in bad_signals): continue
                    
                    title = title_link.text.strip()
                    if not title:
                         try: title = card.find_element(By.TAG_NAME, "h2").text.strip()
                         except: pass
                    
                    if title in ["Neuer als 24h", "Teilweise Home-Office", "Deutsch", "English"]: continue
                    if "stepstone" in title.lower(): continue

                    lines = [l.strip() for l in card.text.split("\n") if l.strip()]
                    company = "Stepstone Listing"
                    if len(lines) > 1:
                        company = lines[1] if title in lines[0] else lines[0]
                    if "Spons" in company or "neu" in company.lower(): 
                         if len(lines) > 2: company = lines[2]

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

        details = {"description": "", "is_easy_apply": False, "language": "de"}
        desc_selectors = [
            "[data-testid='job-description-content']",
            "[data-testid='job-description']",
            "[data-testing='job-content']",
            "[class*='JobDescription']",
            ".js-app-ld-ContentBlock",
            "section.listing-content",
            ".job-description",
            "article"
        ]

        desc_el = None
        for selector in desc_selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
                if el and len(el.text) > 50:
                    desc_el = el
                    break
            except: continue

        if desc_el:
            details['description'] = desc_el.text
        return details
