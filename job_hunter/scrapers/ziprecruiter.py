import json
import time
import os
import datetime
from playwright.sync_api import sync_playwright

class ZipRecruiterJobScraper:
    def __init__(self, search_url, limit=None):
        self.search_url = search_url
        self.limit = int(limit) if limit else None
        self.jobs = []
        self.seen_urls = set()

    def scrape(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            print(f"Navigating to {self.search_url}...")
            page.goto(self.search_url)
            
            # Handle cookies (if any)
            try:
                page.wait_for_timeout(3000)
                # ZipRecruiter often just has a small banner or none for bots?
                # Check for "Accept All"
                consent_button = page.locator("button").filter(has_text="Accept").first
                if consent_button.is_visible():
                    consent_button.click()
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
                    # Look for "Next" button. 
                    # Often has class 'next_page' or 'pagination__next'
                    next_button = page.locator("a.next_page").or_(
                        page.locator("a[rel='next']")
                    ).or_(
                        page.locator("a[aria-label='Next']")
                    ).first
                    
                    next_class = next_button.get_attribute("class") or ""
                    if next_button.is_visible() and "disabled" not in next_class:
                        next_button.click()
                        time.sleep(3)
                        page_number += 1
                    else:
                        print("No next page found or end of results.")
                        break
                        
            except KeyboardInterrupt:
                print("Scraping interrupted by user.")
            except Exception as e:
                print(f"An error occurred: {e}")
            finally:
                self.save_results()
                try:
                    browser.close()
                except:
                    pass

    def collect_job_data(self, page):
        # ZipRecruiter selectors
        # Cards seem to be wrapped in divs or lis, but 'div.jobList-intro' contains the info
        
        cards = page.locator("div.jobList-intro").all()
        
        print(f"Found {len(cards)} cards on this page.")
             
        for card in cards:
            if self.limit and len(self.jobs) >= self.limit:
                return

            try:
                # Title
                title_elem = card.locator("a.jobList-title").first
                if not title_elem.is_visible(): 
                     continue
                     
                title = title_elem.inner_text().strip()
                
                # Link
                href = title_elem.get_attribute("href")
                if not href: continue

                url = href
                if not url.startswith("http"):
                    # Relative or root
                    url = "https://www.ziprecruiter.de" + url
                
                if url in self.seen_urls:
                    continue

                # Company
                company = "Unknown"
                location = "Unknown"
                
                # Meta usually has Company and Location as adjacent lis
                meta_items = card.locator(".jobList-introMeta li").all()
                if len(meta_items) > 0:
                    company = meta_items[0].inner_text().strip()
                if len(meta_items) > 1:
                    location = meta_items[1].inner_text().strip()
                
                self.seen_urls.add(url)
                
                print(f"Found: {title} at {company} ({location})")
                self.jobs.append({
                    "Job Title": title,
                    "Company": company,
                    "Location": location,
                    "Web Address": url,
                    "Platform": "ZipRecruiter",
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
