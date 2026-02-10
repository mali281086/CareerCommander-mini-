import time
import urllib.parse
from selenium.webdriver.common.by import By
from job_hunter.scrapers.base_scraper import BaseScraper

class IndeedScraper(BaseScraper):
    def __init__(self, profile_name="default"):
        super().__init__(profile_name=profile_name)

    def search(self, keyword, location, limit=10, easy_apply=False):
        results = []
        # Indeed URL structure
        # User requested: https://de.indeed.com/jobs?q=Data%20Analyst&l=Germany&from=searchOnHP
        base_url = "https://de.indeed.com/jobs?"
        params = {
            "q": keyword,
            "l": location,
            "from": "searchOnHP"
        }
        url = base_url + urllib.parse.urlencode(params)
        
        print(f"[Indeed] Navigating to: {url}")
        self.driver.get(url)
        self.random_sleep(3, 5)
        
        # Check for Cloudflare/Captcha manually if needed (Selenium usually hits this)
        # Assuming persistent profile helps bypass some, but Indeed is tough.
        
        scrolled = 0
        while len(results) < limit and scrolled < 5:
            # Extract Cards
            # Common classes for Indeed: job_seen_beacon, resultContent
            cards = self.driver.find_elements(By.CLASS_NAME, "job_seen_beacon")
            
            print(f"[Indeed] Found {len(cards)} cards on page...")
            
            for card in cards:
                if len(results) >= limit: break
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, "h2.jobTitle span")
                    company_elem = card.find_element(By.CSS_SELECTOR, "[data-testid='company-name']")
                    link_elem = card.find_element(By.CSS_SELECTOR, "a.jcs-JobTitle")
                    
                    title = title_elem.text.strip()
                    company = company_elem.text.strip()
                    link = link_elem.get_attribute("href")
                    
                    # Clean link
                    if "&" in link and "jk=" in link: 
                         # Try to extract the tracking ID "jk="
                         # Example: .../viewjob?jk=12345&...
                         try:
                             qs = urllib.parse.urlparse(link).query
                             parsed = urllib.parse.parse_qs(qs)
                             jk_val = parsed.get("jk", [None])[0]
                             if jk_val:
                                 # Reconstruct a clean URL
                                 link = f"https://de.indeed.com/viewjob?jk={jk_val}"
                         except:
                             pass

                    # Check for Easy Apply
                    is_easy = False
                    try:
                        # Easily apply badge
                        badge = card.find_element(By.CLASS_NAME, "ialbl") # 'ialbl' is a common class for Indeed Easy Apply
                        if "apply" in badge.text.lower() or "bewerben" in badge.text.lower():
                            is_easy = True
                    except:
                        try:
                            # Secondary check for text
                            if "easily apply" in card.text.lower() or "einfach bewerben" in card.text.lower():
                                is_easy = True
                        except: pass

                    if not any(j['link'] == link for j in results):
                        results.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "link": link,
                            "platform": "Indeed",
                            "is_easy_apply": is_easy
                        })
                except Exception as e:
                    continue
            
            # Pagination / formatting
            # Indeed pagination is usually a "Next" button at bottom
            try:
                next_btn = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='pagination-page-next']")
                next_btn.click()
                self.random_sleep(3, 5)
            except:
                print("[Indeed] No more pages.")
                break
                
            scrolled += 1

        print(f"[Indeed] Scraped {len(results)} jobs.")
        return results
