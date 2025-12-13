import json
import time
import os
import datetime
from playwright.sync_api import sync_playwright

class StepstoneJobScraper:
    def __init__(self, search_url, limit=None):
        self.search_url = search_url
        self.limit = int(limit) if limit else None
        self.jobs = []
        self.seen_urls = set()

    def scrape(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            print(f"Navigating to {self.search_url}...")
            page.goto(self.search_url)
            
            # Handle cookies
            try:
                page.wait_for_selector("#cc-banner", timeout=5000)
                page.locator("button#cc-accept-all-btn").first.click()
                print("Cookies accepted.")
            except:
                pass

            try:
                page_number = 1
                while True:
                    if self.limit and len(self.jobs) >= self.limit:
                        print(f"Limit of {self.limit} reached. Stopping.")
                        break

                    print(f"Scraping page {page_number}...")
                    self.collect_job_data(page)
                    
                    if self.limit and len(self.jobs) >= self.limit:
                         break
                    
                    # Pagination
                    # Look for "Next" button. Stepstone often has a 'next' button in pagination.
                    # Or check for url patterns. Stepstone usually uses URL params but also has a next button.
                    try:
                         # Selector for next button might vary. 
                         # Usually aria-label="Nächste" or similar
                         next_button = page.locator("a[aria-label='Nächste']").or_(page.locator("a[rel='next']")).first
                         if next_button.is_visible():
                             next_button.click()
                             time.sleep(3)
                             page_number += 1
                         else:
                             print("No next page found or end of results.")
                             break
                    except:
                        break
                        
            except KeyboardInterrupt:
                print("Scraping interrupted by user.")
            except Exception as e:
                print(f"An error occurred: {e}")
            finally:
                self.save_results()
                browser.close()

    def collect_job_data(self, page):
        # Stepstone job cards are usually articles
        articles = page.locator("article").all()
        
        print(f"Found {len(articles)} articles on this page.")
        
        for article in articles:
            if self.limit and len(self.jobs) >= self.limit:
                return

            try:
                # Job Title
                # Usually in an h2
                h2 = article.locator("h2").first
                if not h2.is_visible(): continue
                
                title = h2.inner_text().strip()
                
                # Link
                # Usually the link is on the h2 or wrapping it
                link = article.locator("a").first
                href = link.get_attribute("href")
                
                if not href: continue
                
                # Stepstone links are usually relative or full
                url = href
                if not url.startswith("http"):
                    url = "https://www.stepstone.de" + url
                
                if url in self.seen_urls:
                    continue

                # Company name and Location
                # Try to find company in the article container
                # Often in specific classes, but let's try text analysis of limits
                company = "Unknown"
                location = "Unknown"
                try:
                    # Get all text lines of article
                    text_content = article.inner_text()
                    lines = [l.strip() for l in text_content.split('\n') if l.strip()]
                    
                    # Heuristic: Title is usually one line. Company is usually next. Location is usually next.
                    
                    # Try getting company from logo alt first
                    logo = article.locator("img[alt]").first
                    if logo.is_visible():
                         alt_text = logo.get_attribute("alt")
                         if alt_text and "Logo" not in alt_text: 
                             company = alt_text
                    
                    if company == "Unknown" and len(lines) > 1:
                        # Fallback to text lines
                        for i, line in enumerate(lines):
                            if title in line:
                                if i + 1 < len(lines):
                                    company = lines[i+1]
                                if i + 2 < len(lines):
                                    location = lines[i+2] 
                                break
                    elif company != "Unknown" and len(lines) > 0:
                        # If company found via logo, location might be in lines
                        found_company_line = False
                        for i, line in enumerate(lines):
                            if company in line:
                                if i + 1 < len(lines):
                                    location = lines[i+1]
                                    break
                except:
                    pass

                self.seen_urls.add(url)
                
                # Check duplication against current list
                if url not in [j["Web Address"] for j in self.jobs]:
                    print(f"Found: {title} at {company} ({location})")
                    self.jobs.append({
                        "Job Title": title,
                        "Company": company,
                        "Location": location,
                        "Web Address": url,
                        "Platform": "Stepstone",
                        "Date Extracted": datetime.datetime.now().strftime("%Y-%m-%d")
                    })
            except:
                continue

    def save_results(self):
        output_file = "data/found_jobs.json"
        
        existing_data = []
        if os.path.exists(output_file):
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except:
                pass
        
        all_data = existing_data + self.jobs
        
        # Deduplication based on URL
        unique_jobs = {job["Web Address"]: job for job in all_data}
        final_list = list(unique_jobs.values())
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_list, f, indent=4, ensure_ascii=False)
        print(f"Saved {len(self.jobs)} jobs to {output_file} (Total in file: {len(final_list)})")
