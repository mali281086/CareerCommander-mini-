import urllib.parse
from selenium.webdriver.common.by import By
from job_hunter.scrapers.base_scraper import BaseScraper
import time

class StepstoneScraper(BaseScraper):
    def search(self, keyword, location, limit=10, easy_apply=False):
        results = []
        # User requested: https://www.stepstone.de/jobs/data-analyst/in-germany?radius=30
        
        # Slugify keys (basic)
        kw_slug = keyword.replace(" ", "-").lower()
        loc_slug = location.replace(" ", "-").lower()
        
        base_url = f"https://www.stepstone.de/jobs/{kw_slug}/in-{loc_slug}?"
        params = {
            "radius": "30"
        }
        url = base_url + urllib.parse.urlencode(params)
        
        print(f"[Stepstone] Navigating to: {url}")
        self.driver.get(url)
        self.random_sleep(3, 5)
        
        scrolled = 0
        while len(results) < limit and scrolled < 3:
            # Articles with class 'res-1t0q73n' or similar dynamic hashes
            # Use 'article' tag
            cards = self.driver.find_elements(By.TAG_NAME, "article")
            
            print(f"[Stepstone] Found {len(cards)} cards...")
            
            for card in cards:
                if len(results) >= limit: break
                if len(results) >= limit: break
                try:
                    # Strategy: Find the Job Title link specifically
                    # Usually inside an <h2> or has 'stellenangebote--' in href
                    title_link = None
                    
                    # 1. Try finding link inside h2
                    try:
                        h2 = card.find_element(By.TAG_NAME, "h2")
                        title_link = h2.find_element(By.TAG_NAME, "a")
                    except: pass
                    
                    # 2. If not found, iterate all links and find the one with 'stellenangebote'
                    if not title_link:
                        links = card.find_elements(By.TAG_NAME, "a")
                        for l in links:
                            href = l.get_attribute("href")
                            if href and "stellenangebote--" in href:
                                title_link = l
                                break
                    
                    # 3. Fallback: First link that is NOT a company profile
                    if not title_link:
                         links = card.find_elements(By.TAG_NAME, "a")
                         for l in links:
                             href = l.get_attribute("href")
                             if href and "/cmp/" not in href and "stellenangebote" in href:
                                 title_link = l
                                 break

                    if not title_link: continue

                    link = title_link.get_attribute("href")
                    if not link: continue
                    
                    # --- FILTERING BAD LINKS (Facets/Nav) ---
                    bad_signals = ["action=", "facet_", "radius=", "ag=", "wfh=", "am="]
                    if any(sig in link for sig in bad_signals): continue
                    
                    title = title_link.text.strip()
                    if not title:
                         # Try getting text from h2 parent if link text is hidden
                         try: title = card.find_element(By.TAG_NAME, "h2").text.strip()
                         except: pass
                    
                    # Filter out generic titles
                    if title in ["Neuer als 24h", "Teilweise Home-Office", "Deutsch", "English"]: continue
                    if "stepstone" in title.lower(): continue # generic breadcrumb

                    context_text = card.text
                    lines = [l.strip() for l in context_text.split("\n") if l.strip()]
                    
                    company = "Stepstone Listing"
                    # Heuristic: Company is often 2nd line, or first line if title not in first
                    if len(lines) > 1:
                        # If line[0] is title, line[1] is company?
                        if title in lines[0]: company = lines[1]
                        else: company = lines[0] # Fallback
                        
                    # Cleanup Company
                    if "Spons" in company or "neu" in company.lower(): 
                         if len(lines) > 2: company = lines[2]

                    if not any(j['link'] == link for j in results):
                        results.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "link": link,
                            "platform": "Stepstone",
                            "is_easy_apply": False # Default for Stepstone
                        })
                except: continue
            
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.random_sleep(2, 3)
            scrolled += 1
            
        print(f"[Stepstone] Scraped {len(results)} jobs.")
        return results
