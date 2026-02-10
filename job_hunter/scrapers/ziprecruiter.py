import urllib.parse
from selenium.webdriver.common.by import By
from job_hunter.scrapers.base_scraper import BaseScraper

class ZipRecruiterScraper(BaseScraper):
    def __init__(self, profile_name="default"):
        super().__init__(profile_name=profile_name)

    def search(self, keyword, location, limit=10, easy_apply=False):
        results = []
        # User requested: https://www.ziprecruiter.de/jobs/search?q=Data+Analyst&l=Germany&lat=&long=&d=
        base_url = "https://www.ziprecruiter.de/jobs/search?"
        params = {
            "q": keyword,
            "l": location,
            "lat": "",
            "long": "",
            "d": ""
        }
        url = base_url + urllib.parse.urlencode(params)
        
        print(f"[ZipRecruiter] Navigating to: {url}")
        self.driver.get(url)
        self.random_sleep(3, 5)
        
        scrolled = 0
        while len(results) < limit and scrolled < 4:
            # ZipRecruiter DE often uses simple lists
            cards = self.driver.find_elements(By.CLASS_NAME, "job_content_clickable") or \
                    self.driver.find_elements(By.CSS_SELECTOR, "article.job_result") or \
                    self.driver.find_elements(By.CSS_SELECTOR, "li.job-listing")

            print(f"[ZipRecruiter] Found {len(cards)} cards...")
            
            for card in cards:
                if len(results) >= limit: break
                try:
                    # Generic Title Extraction: Try headers, then bold text, then links
                    title = "Zip Job"
                    title_elem = None
                    
                    # Try explicit headers
                    for tag in ["h2", "h3", "h4", "h5", "a"]:
                         try: 
                             elems = card.find_elements(By.TAG_NAME, tag)
                             for el in elems:
                                 txt = el.text.strip()
                                 if txt and len(txt) > 3: # Avoid empty headers
                                     title_elem = el
                                     title = txt
                                     break
                             if title_elem: break
                         except: pass
                    
                    # Company Extraction
                    company = "Unknown"
                    try:
                        # ZipRecruiter often has a class "company_name" or "company_location"
                        # Or it's just the next line after title
                        company_elems = card.find_elements(By.CSS_SELECTOR, ".company_name, .company_location, [class*='company']")
                        if company_elems:
                            company = company_elems[0].text.strip()
                        else:
                            # Fallback: Split card text
                            lines = card.text.split("\n")
                            # Heuristic: Title is usually lines[0], Company lines[1]
                            if len(lines) > 1 and lines[0] in title:
                                company = lines[1]
                            elif len(lines) > 0 and title == "Zip Job":
                                # If title failed, maybe line 0 is title
                                title = lines[0]
                                if len(lines) > 1: company = lines[1]
                    except: pass
                    
                    # Link
                    link = "https://www.ziprecruiter.de"
                    try:
                        link_elems = card.find_elements(By.TAG_NAME, "a")
                        if link_elems: link = link_elems[0].get_attribute("href")
                    except: pass
                    
                    if not any(j['link'] == link for j in results):
                        results.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "link": link,
                            "platform": "ZipRecruiter",
                            "is_easy_apply": False # Default for ZipRecruiter
                        })
                except: continue
                
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.random_sleep(2, 4)
            scrolled += 1
            
        print(f"[ZipRecruiter] Scraped {len(results)} jobs.")
        return results
