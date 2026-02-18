import urllib.parse
import time
from typing import List, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from langdetect import detect

from job_hunter.scrapers.base_scraper import BaseScraper
from job_hunter.models import JobRecord
from tools.browser_manager import BrowserManager
from tools.human_actions import human_scroll, jitter_mouse, random_wait

class LinkedInScraper(BaseScraper):
    def __init__(self, profile_name="default"):
        self.bm = BrowserManager()
        self.profile_name = profile_name
        # Note: driver is fetched lazily or via property in some designs,
        # but here we follow the existing pattern of getting it in init or when needed.
        self.platform_name = "LinkedIn"

    @property
    def driver(self):
        return self.bm.get_driver(headless=False, profile_name=self.profile_name)

    def search(self, keyword: str, location: str, limit: int = 10, easy_apply: bool = False) -> List[JobRecord]:
        results = []
        base_url = "https://www.linkedin.com/jobs/search/?"
        params = {
            "keywords": keyword,
            "location": location,
            "origin": "JOBS_HOME_SEARCH_BUTTON"
        }
        
        if easy_apply:
            params["f_AL"] = "true"

        offset = 0
        while len(results) < limit:
            current_params = params.copy()
            if offset > 0:
                current_params["start"] = str(offset)
            
            url = base_url + urllib.parse.urlencode(current_params)
            self.log(f"Navigating to: {url}")
            self.driver.get(url)
            self.random_sleep(3, 5)
            
            if easy_apply:
                self._ensure_easy_apply_filter()

            try:
                 WebDriverWait(self.driver, 10).until(
                     EC.presence_of_element_located((By.CLASS_NAME, "jobs-search-results-list"))
                 )
                 job_list_container = self.driver.find_element(By.CLASS_NAME, "jobs-search-results-list")
            except:
                 job_list_container = None
            
            scrolled = 0
            jobs_found_on_page = 0
            
            while scrolled < 5:
                cards = self.driver.find_elements(By.CSS_SELECTOR, "li.occludable-update-artdeco-list-item") or \
                        self.driver.find_elements(By.CSS_SELECTOR, ".job-card-container")
                
                self.log(f"Found {len(cards)} cards so far on page (Total: {len(results)})...")
                
                for card in cards:
                    if len(results) >= limit: break
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, ".job-card-list__title, .artdeco-entity-lockup__title")
                        company_elem = card.find_element(By.CSS_SELECTOR, ".job-card-container__primary-description, .artdeco-entity-lockup__subtitle")
                        link_elem = card.find_element(By.TAG_NAME, "a")
                        
                        title = title_elem.text.strip()
                        company = company_elem.text.strip()
                        link = link_elem.get_attribute("href")
                        
                        job_id = card.get_attribute("data-job-id") or card.get_attribute("data-occludable-job-id")
                        if not job_id and link:
                            if "/view/" in link:
                                job_id = link.split("/view/")[1].split("/")[0].split("?")[0]
                            elif "currentJobId=" in link:
                                job_id = link.split("currentJobId=")[1].split("&")[0]

                        if job_id:
                            link = f"https://www.linkedin.com/jobs/view/{job_id}/"
                        elif link and "/jobs/view/" in link:
                            link = link.split("?")[0]
                        
                        is_easy = False
                        try:
                            badge = card.find_element(By.CSS_SELECTOR, ".job-card-container__apply-method, .job-card-list__footer-item")
                            if "Easy Apply" in badge.text or "Einfach bewerben" in badge.text:
                                is_easy = True
                        except:
                            if easy_apply: is_easy = True

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
                            jobs_found_on_page += 1
                    except:
                        continue
                        
                if len(results) >= limit: break
                
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                if job_list_container:
                     try:
                        self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", job_list_container)
                     except: pass
                
                self.random_sleep(2, 4)
                scrolled += 1
            
            if jobs_found_on_page == 0:
                self.log("No new jobs found on this page. Stopping.")
                break
                
            offset += 25
            self.log(f"Moving to next page (Offset {offset})...")
            self.random_sleep(2, 4)

        return results

    def fetch_details(self, job_url: str) -> Optional[dict]:
        """Fetches full job details for a LinkedIn job."""
        if not job_url: return None

        self.driver.get(job_url)
        random_wait(2, 4)

        # Human-like interaction
        human_scroll(self.driver)
        jitter_mouse(self.driver)
        random_wait(1, 2)

        # Expand description if needed
        try:
            expand_btn = self.driver.find_element(By.CSS_SELECTOR, "button.jobs-description__footer-button")
            self.driver.execute_script("arguments[0].click();", expand_btn)
            self.random_sleep(1, 1.5)
        except: pass

        details = {
            "description": "",
            "is_easy_apply": False,
            "language": "en"
        }

        # Easy Apply Check
        try:
            page_source = self.driver.page_source.lower()
            if "easy apply" in page_source or "einfach bewerben" in page_source:
                details["is_easy_apply"] = True
        except: pass

        # Description
        try:
            desc_el = None
            potential_classes = ["jobs-description__content", "job-details-jobs-unified-top-card__primary-description", "job-details"]
            for cls in potential_classes:
                try:
                    el = self.driver.find_element(By.CLASS_NAME, cls)
                    if el and len(el.text) > 100:
                        desc_el = el
                        break
                except: pass

            if not desc_el: desc_el = self.driver.find_element(By.ID, "job-details")
            if desc_el:
                details["description"] = desc_el.text
        except:
            try:
                desc_el = self.driver.find_element(By.CLASS_NAME, "show-more-less-html__markup")
                details["description"] = desc_el.text
            except: pass

        if details["description"]:
            try:
                details["language"] = detect(details["description"])
            except: pass

        return details

    def _ensure_easy_apply_filter(self):
        try:
            filter_selectors = self.selectors.get("linkedin", {}).get("easy_apply_button", ["button[aria-label*='Easy Apply']", "button[aria-label*='Einfach bewerben']"])
            for selector in filter_selectors:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if btn.is_displayed():
                        classes = btn.get_attribute("class") or ""
                        if "selected" not in classes.lower() and "active" not in classes.lower():
                            self.driver.execute_script("arguments[0].click();", btn)
                            self.random_sleep(3, 5)
                            return True
                except: continue
        except: pass
        return False
