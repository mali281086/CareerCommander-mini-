import urllib.parse
from selenium.webdriver.common.by import By
from job_hunter.scrapers.base_scraper import BaseScraper
import time

class XingScraper(BaseScraper):
    def search(self, keyword, location, limit=10, easy_apply=False):
        results = []
        # Reverting to standard search URL.
        # The user-requested '/ki' path seems to require a session-specific 'id' and redirects to a landing page without it.
        base_url = "https://www.xing.com/jobs/search?"
        params = {
            "keywords": keyword,
            "location": location
        }
        url = base_url + urllib.parse.urlencode(params)
        
        print(f"[Xing] Navigating to: {url}")
        self.driver.get(url)
        self.random_sleep(3, 5)
        
        scrolled = 0
        while len(results) < limit and scrolled < 5:
            # Strategy 3: Link-First Discovery (Most Robust)
            # Find all links that look like job postings
            links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/jobs/')]")
            
            print(f"[Xing] Found {len(links)} potential job links...")
            
            for a_tag in links:
                if len(results) >= limit: break
                try:
                    href = a_tag.get_attribute("href")
                    # Filter out non-job links (e.g. nav, search, login)
                    if not href: continue
                    
                    # Blacklist of generic Xing paths
                    bad_patterns = [
                        "search?", "login", "/jobs/find", "/jobs/my-jobs", "/jobs/search", 
                        "/recruiting", "pro.", "xref="
                    ]
                    if any(bad in href for bad in bad_patterns): continue

                    # Title is usually the link text
                    title = a_tag.text.strip()
                    if not title or len(title) < 5: 
                         # Sometimes title is inside a div inside the a
                         title = a_tag.get_attribute("textContent").strip()
                    
                    # Fallback: Parse URL slug if text is still empty
                    if not title:
                        # href format: .../jobs/location-title-id or .../jobs/title-location-id
                        # e.g. .../jobs/berlin-business-data-analyst-12345
                        try:
                            slug = href.split("/jobs/")[-1]
                            # Remove trailing query params
                            slug = slug.split("?")[0]
                            # Split by hyphen
                            parts = slug.split("-")
                            # Remove the last part if it's a number (ID)
                            if parts[-1].isdigit(): parts.pop()
                            
                            # Reconstruct
                            title = " ".join(parts).title()
                        except: pass
                    
                    # Ignore generic titles
                    if title.lower() in ["jobs", "search", "find jobs", "create a job ad", "your jobs"]: continue
                    if not title: continue # Skip empty links
                    
                    # Company extraction: Look at parent text
                    company = "Unknown"
                    try:
                        # Go up to the card container (likely li or article or div)
                        # We try going up 1-3 levels
                        parent = a_tag.find_element(By.XPATH, "./..")
                        grandparent = parent.find_element(By.XPATH, "./..")
                        
                        # Get full text of the card
                        card_text = grandparent.text
                        lines = [l.strip() for l in card_text.split("\n") if l.strip()]
                        
                        # Heuristic: If Title is line X, Company is usually X+1
                        # Find title in lines (fuzzy match)
                        for i, line in enumerate(lines):
                            # The slug-derived title might not match text exactly
                            # So just take the first line that isn't the title or "New" badge
                            if len(line) > 3 and line.lower() not in title.lower() and "new" not in line.lower():
                                 company = line
                                 # If company is "Kununu", skip
                                 if "kununu" in company.lower(): continue
                                 break
                    except: pass
                    
                    if company == "Unknown": company = "Xing Employer"
                    
                    if not any(j['link'] == href for j in results):
                        results.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "link": href,
                            "platform": "Xing"
                        })
                except: continue
            
            # Scroll logic
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.random_sleep(2, 4)
            scrolled += 1

        print(f"[Xing] Scraped {len(results)} jobs.")
        
        if easy_apply and results:
            print(f"[Xing] 🕵️ Filtering {len(results)} jobs for 'Easy Apply'...")
            easy_apply_results = []
            for i, job in enumerate(results):
                try:
                    print(f"   [{i+1}/{len(results)}] Checking: {job['title']}...")
                    self.driver.get(job['link'])
                    self.random_sleep(2, 4)
                    
                    # Logic: Check for indicators of Easy Apply
                    # Indicators: "Schnellbewerbung" text, or specific internal application buttons.
                    # We check page text for simplicity and speed.
                    page_source = self.driver.page_source.lower()
                    
                    # "schnellbewerbung" is the German term for Easy Apply on Xing
                    # "easy apply" might appear in English interface
                    if "schnellbewerbung" in page_source or "easy apply" in page_source:
                        print(f"      ✅ Found Easy Apply!")
                        easy_apply_results.append(job)
                    else:
                        print(f"      ❌ Standard Apply only.")
                        
                except Exception as e:
                    print(f"      ⚠️ Error checking job: {e}")
            
            print(f"[Xing] Filtered down to {len(easy_apply_results)} Easy Apply jobs.")
            return easy_apply_results

        return results