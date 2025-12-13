import json
import time
import os
import datetime
from playwright.sync_api import sync_playwright

class IndeedJobScraper:
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
            
            # Handle cookies (if any)
            try:
                print("Checking for Cloudflare/Indeed verification...")
                try:
                    # 'div#mosaic-provider-jobcards' is the main container for Indeed jobs
                    # Wait up to 120s for user to solve CAPTCHA
                    page.wait_for_selector("div#mosaic-provider-jobcards", timeout=120000)
                    print("Results loaded! Proceeding...")
                except:
                    print("Timed out waiting for results. Challenge not solved or blocking persisting.")
                
                # Check for "Accept All" cookies
                page.wait_for_timeout(2000)
                # Indeed cookie banner
                consent_button = page.locator("button#onetrust-accept-btn-handler").first
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
                    # Look for "Next Page" button
                    try:
                        # Indeed pagination usually has aria-label="Next Page" or "Next"
                        next_button = page.locator("a[aria-label='Next Page']").or_(page.locator("a[data-testid='pagination-page-next']")).first
                        if next_button.is_visible():
                            next_button.click()
                            # Wait for new results
                            page.wait_for_timeout(3000) 
                            # Sometimes modal pops up asking for email
                            try:
                                close_modal = page.locator("button[aria-label='close']").first
                                if close_modal.is_visible():
                                    close_modal.click()
                            except:
                                pass
                            
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
        # Indeed job cards
        # Typically have class 'job_seen_beacon' or 'cardOutline'
        
        cards = page.locator("div.job_seen_beacon").all() # Specific enough?
        if not cards:
             cards = page.locator("td.resultContent").all()
        
        print(f"Found {len(cards)} cards on this page.")
             
        for card in cards:
            if self.limit and len(self.jobs) >= self.limit:
                return

            try:
                # Job Title
                # Usually in an h2.jobTitle > a > span
                title_elem = card.locator("h2.jobTitle span").first
                if not title_elem.is_visible():
                    title_elem = card.locator("h2.jobTitle").first
                
                if not title_elem.is_visible(): 
                     continue
                     
                title = title_elem.inner_text().strip()
                
                # Company
                company_elem = card.locator("[data-testid='company-name']").first
                if company_elem.is_visible():
                    company = company_elem.inner_text().strip()
                else:
                    company = "Unknown"
                    
                # Location
                location = "Unknown"
                location_elem = card.locator("[data-testid='text-location']").first
                if not location_elem.is_visible():
                     location_elem = card.locator(".companyLocation").first
                
                if location_elem.is_visible():
                    location = location_elem.inner_text().strip()

                # Link
                # The link is usually on the h2 or a parent 'a'
                link_elem = card.locator("a").first
                # Sometimes the link is 'jcs-JobTitle'
                href = link_elem.get_attribute("href")
                
                # Resolving href
                url = href
                if href:
                    if href.startswith("/"):
                        url = "https://de.indeed.com" + href
                    
                    # Filter out duplicates
                    if url in self.seen_urls:
                        continue
                    
                    self.seen_urls.add(url)
                    
                    print(f"Found: {title} at {company} ({location})")
                    self.jobs.append({
                        "Job Title": title,
                        "Company": company,
                        "Location": location,
                        "Web Address": url,
                        "Platform": "Indeed",
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
