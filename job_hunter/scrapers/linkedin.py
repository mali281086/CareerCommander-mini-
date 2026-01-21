import time
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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

        url = base_url + urllib.parse.urlencode(params)
        
        print(f"[LinkedIn] Navigating to: {url}")
        self.driver.get(url)
        self.random_sleep(3, 5)
        
        # Scroll logic to load jobs (basic implementation)
        # LinkedIn loads jobs in the sidebar (left rail) usually
        try:
             # Find result list
             # Class names change often, trying strict structure selectors or aria-labels
             # Try locating the scrollable container for job list
             job_list_container = self.driver.find_element(By.CLASS_NAME, "jobs-search-results-list")
        except:
             # Maybe full page view?
             job_list_container = None
        
        # Simple scroll loop
        scrolled = 0
        while len(results) < limit and scrolled < 5:
            # Extract Cards
            cards = self.driver.find_elements(By.CSS_SELECTOR, "li.occludable-update-artdeco-list-item") or \
                    self.driver.find_elements(By.CSS_SELECTOR, ".job-card-container")
            
            print(f"[LinkedIn] Found {len(cards)} cards so far...")
            
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
                except Exception as e:
                    continue
            
            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # If sidebar exists, scroll that
            if job_list_container:
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", job_list_container)
            
            self.random_sleep(2, 4)
            scrolled += 1

        print(f"[LinkedIn] Scraped {len(results)} jobs.")
        return results
