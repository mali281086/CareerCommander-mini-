import time
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from job_hunter.scrapers.base_scraper import BaseScraper

class LinkedInScraper(BaseScraper):
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
                        
                        # Clean link (remove query params for storage)
                        if "?" in link: link = link.split("?")[0]
                        
                        # Dedup check in local list
                        if not any(j['link'] == link for j in results):
                            results.append({
                                "title": title,
                                "company": company,
                                "location": location, # Default to search loc if specific element missing
                                "link": link,
                                "platform": "LinkedIn"
                            })
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
