import time
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from job_hunter.scrapers.base_scraper import BaseScraper

class LinkedInScraper(BaseScraper):
    def __init__(self, profile_name="default"):
        super().__init__(profile_name=profile_name)

    def search(self, keyword, location, limit=10, easy_apply=False):
        results = []
        # User requested: https://www.linkedin.com/jobs/search/?currentJobId=...&geoId=...&keywords=...&origin=JOBS_HOME_SEARCH_BUTTON
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
            # Update params for pagination
            current_params = params.copy()
            if offset > 0:
                current_params["start"] = str(offset)
            
            url = base_url + urllib.parse.urlencode(current_params)
            
            print(f"[LinkedIn] Navigating to: {url}")
            self.driver.get(url)
            self.random_sleep(3, 5)
            
            # Verify Easy Apply filter is active in UI if requested
            if easy_apply:
                self._ensure_linkedin_easy_apply_filter()

            # Scroll logic to load jobs (basic implementation)
            # LinkedIn loads jobs in the sidebar (left rail) usually
            try:
                 # WAIT for list to populate
                 WebDriverWait(self.driver, 10).until(
                     EC.presence_of_element_located((By.CLASS_NAME, "jobs-search-results-list"))
                 )
                 
                 # Find result list
                 job_list_container = self.driver.find_element(By.CLASS_NAME, "jobs-search-results-list")
            except:
                 # Maybe full page view?
                 job_list_container = None
            
            # Simple scroll loop
            scrolled = 0
            jobs_found_on_page = 0
            
            while scrolled < 5:
                # Extract Cards
                cards = self.driver.find_elements(By.CSS_SELECTOR, "li.occludable-update-artdeco-list-item") or \
                        self.driver.find_elements(By.CSS_SELECTOR, ".job-card-container")
                
                print(f"[LinkedIn] Found {len(cards)} cards so far on page (Total: {len(results)})...")
                
                for card in cards:
                    if len(results) >= limit: break
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, ".job-card-list__title, .artdeco-entity-lockup__title")
                        company_elem = card.find_element(By.CSS_SELECTOR, ".job-card-container__primary-description, .artdeco-entity-lockup__subtitle")
                        link_elem = card.find_element(By.TAG_NAME, "a")
                        
                        title = title_elem.text.strip()
                        company = company_elem.text.strip()
                        link = link_elem.get_attribute("href")
                        
                        # Better Link Handling for LinkedIn:
                        # 1. Try to get job ID from card attribute (most reliable)
                        job_id = card.get_attribute("data-job-id") or card.get_attribute("data-occludable-job-id")

                        # 2. Try to get job ID from link if attribute missing
                        if not job_id and link:
                            # Matches /jobs/view/12345 or /jobs/search/?currentJobId=12345
                            if "/view/" in link:
                                job_id = link.split("/view/")[1].split("/")[0].split("?")[0]
                            elif "currentJobId=" in link:
                                job_id = link.split("currentJobId=")[1].split("&")[0]

                        if job_id:
                            # Standardize to direct view link
                            link = f"https://www.linkedin.com/jobs/view/{job_id}/"
                        else:
                            # Fallback: Clean link (remove query params for storage) but ONLY if it's a direct view link
                            if link and "/jobs/view/" in link and "?" in link:
                                link = link.split("?")[0]
                        
                        # Check for Easy Apply Badge
                        is_easy = False
                        try:
                            # Easy Apply often has a specific badge or text on the card
                            badge = card.find_element(By.CSS_SELECTOR, ".job-card-container__apply-method, .job-card-list__footer-item")
                            if "Easy Apply" in badge.text or "Einfach bewerben" in badge.text:
                                is_easy = True
                        except:
                            if easy_apply: is_easy = True # Fallback if filter was on

                        # Dedup check in local list
                        if not any(j['link'] == link for j in results):
                            job_data = {
                                "title": title,
                                "company": company,
                                "location": location, # Default to search loc if specific element missing
                                "link": link,
                                "platform": "LinkedIn",
                                "is_easy_apply": is_easy
                            }

                            results.append(job_data)
                            jobs_found_on_page += 1
                    except Exception as e:
                        continue
                        
                if len(results) >= limit: break
                
                # Scroll down
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                # If sidebar exists, scroll that
                if job_list_container:
                     try:
                        self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", job_list_container)
                     except: pass
                
                self.random_sleep(2, 4)
                scrolled += 1
            
            # BREAK if no new jobs were found on this entire page (End of results)
            if jobs_found_on_page == 0:
                print("[LinkedIn] No new jobs found on this page. Stopping.")
                break
                
            # Next Page
            offset += 25
            print(f"[LinkedIn] Moving to next page (Offset {offset})...")
            self.random_sleep(2, 4)

        print(f"[LinkedIn] Scraped {len(results)} jobs.")
        return results

    def _ensure_linkedin_easy_apply_filter(self):
        """Checks if Easy Apply filter is active on the current search page, clicks it if not."""
        try:
            # Common selectors for the Easy Apply filter button/pill
            filter_selectors = [
                "button[aria-label*='Easy Apply']",
                "button[aria-label*='Einfach bewerben']",
                "//button[contains(., 'Easy Apply')]",
                "//button[contains(., 'Einfach bewerben')]"
            ]

            filter_btn = None
            for selector in filter_selectors:
                try:
                    if selector.startswith("//"):
                        filter_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        filter_btn = self.driver.find_element(By.CSS_SELECTOR, selector)

                    if filter_btn and filter_btn.is_displayed():
                        break
                except:
                    continue

            if filter_btn:
                classes = filter_btn.get_attribute("class") or ""
                pressed = filter_btn.get_attribute("aria-pressed") or "false"
                is_active = "selected" in classes.lower() or "active" in classes.lower() or pressed.lower() == "true"

                if not is_active:
                    print(f"[LinkedIn Scraper] Easy Apply filter not active in UI (classes: {classes}), clicking it...")
                    try:
                        self.driver.execute_script("arguments[0].click();", filter_btn)
                    except:
                        filter_btn.click()
                    time.sleep(5)
                    return True
            return False
        except Exception as e:
            print(f"[LinkedIn Scraper] Error ensuring Easy Apply filter: {e}")
            return False
