import time
from typing import List, Optional
from selenium.webdriver.common.by import By
from langdetect import detect

from job_hunter.scrapers.base_scraper import BaseScraper
from job_hunter.models import JobRecord
from tools.browser_manager import BrowserManager

class XingScraper(BaseScraper):
    def __init__(self, profile_name="default"):
        self.bm = BrowserManager()
        self.profile_name = profile_name
        self.platform_name = "Xing"

    @property
    def driver(self):
        return self.bm.get_driver(headless=False, profile_name=self.profile_name)

    def search(self, keyword: str, location: str, limit: int = 10, easy_apply: bool = False) -> List[JobRecord]:
        results = []
        search_url = f"https://www.xing.com/jobs/search?keywords={keyword.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
        
        self.log(f"Navigating to: {search_url}")
        self.driver.get(search_url)
        self.random_sleep(4, 6)

        # Xing has no Easy Apply filter in the main search URL easily,
        # so we often have to check cards or filter subsequently.

        processed_links = set()
        page = 1
        
        while len(results) < limit and page < 5:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.random_sleep(2, 3)

            cards = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='job-posting-card']") or \
                    self.driver.find_elements(By.CSS_SELECTOR, ".job-posting-card")
            
            self.log(f"Found {len(cards)} cards on page {page}...")
            
            for card in cards:
                if len(results) >= limit: break
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, "h2")
                    title = title_el.text.strip()
                    
                    company_el = card.find_element(By.CSS_SELECTOR, "p[class*='Company']")
                    company = company_el.text.strip()
                    
                    link_el = card.find_element(By.TAG_NAME, "a")
                    link = link_el.get_attribute("href")
                    
                    if link and "/jobs/" in link and link not in processed_links:
                        processed_links.add(link)
                        
                        # Note: is_easy_apply check on cards is hard for Xing without opening
                        # but we can check for "Schnellbewerbung" text
                        is_easy = "Schnellbewerbung" in card.text or "Easy Apply" in card.text
                        
                        if easy_apply and not is_easy:
                            continue

                        job_rec = JobRecord(
                            title=title,
                            company=company,
                            location=location,
                            link=link.split("?")[0],
                            platform=self.platform_name,
                            is_easy_apply=is_easy
                        )
                        results.append(job_rec)
                except:
                    continue
            
            if len(results) >= limit: break

            # Try to click next page if needed
            try:
                next_btn = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Next'], a[rel='next']")
                self.driver.execute_script("arguments[0].click();", next_btn)
                self.random_sleep(3, 5)
                page += 1
            except:
                break

        return results

    def fetch_details(self, job_url: str) -> Optional[dict]:
        if not job_url: return None
        
        self.driver.get(job_url)
        self.random_sleep(3, 5)

        details = {
            "description": "",
            "is_easy_apply": False,
            "language": "de",
            "company": ""
        }

        # Easy Apply Check
        page_source = self.driver.page_source.lower()
        if "schnellbewerbung" in page_source or "easy apply" in page_source:
            details["is_easy_apply"] = True

        # Company Extraction
        try:
            c_el = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='header-company-name']")
            details['company'] = c_el.text.strip()
        except: pass

        # Description
        try:
            desc_el = self.driver.find_element(By.CSS_SELECTOR, "[class*='html-description'], [data-testid='job-description-content']")
            details['description'] = desc_el.text
        except:
            try:
                main = self.driver.find_element(By.TAG_NAME, "main")
                details['description'] = main.text
            except: pass

        if details["description"]:
            try:
                details["language"] = detect(details["description"])
            except: pass

        return details
