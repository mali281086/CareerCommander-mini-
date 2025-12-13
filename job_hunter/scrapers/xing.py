import json
import time
import os
import datetime
from playwright.sync_api import sync_playwright

class XingJobScraper:
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
            
            # Handle cookies (Usercentrics)
            try:
                page.wait_for_selector("#usercentrics-root", state="attached", timeout=5000)
                root = page.locator("#usercentrics-root")
                accept_btn = root.locator("button[data-testid='uc-accept-all-button']").first
                if accept_btn.is_visible():
                    accept_btn.click()
                    print("Cookies accepted.")
            except:
                pass

            try:
                while True:
                    self.collect_job_data(page)
                    
                    if self.limit and len(self.jobs) >= self.limit:
                        print(f"Limit of {self.limit} reached. Stopping.")
                        break

                    # "Show more" button handling
                    try:
                        more_button = page.locator("button[data-testid='search-load-more-button']").first
                        if more_button.is_visible():
                            more_button.click()
                            time.sleep(3) # Wait for content
                        else:
                            print("No more results.")
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
        # Existing Logic
        # Try generic article first, as data-testid might have changed
        cards = page.locator("article").all()
        
        print(f"Found {len(cards)} articles.")
        
        for card in cards:
            if self.limit and len(self.jobs) >= self.limit:
                return

            try:
                # Title
                # Try h3 first (common in Xing)
                title_elem = card.locator("h3 a").first
                if not title_elem.is_visible():
                     title_elem = card.locator("a[href*='/jobs/']").first
                
                if not title_elem.is_visible(): continue
                link = title_elem
                
                title = title_elem.inner_text().strip()
                href = link.get_attribute("href")
                
                # Fallback if title is empty (happens if link wraps strict structure)
                card_text = card.inner_text()
                lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                
                if not title and len(lines) > 0:
                    title = lines[0]
                
                # Resolve URL
                url = href
                if not url.startswith("http"):
                    url = "https://www.xing.com" + url
                
                # Deduplication logic
                if url in self.seen_urls:
                    continue

                company = "Unknown"
                location = "Unknown"
                
                # Heuristic parsing of lines
                # Lines usually: [ "Be an early applicant", "Data Analyst", "Company", "Location" ]
                # OR: [ "Data Analyst", "Company", "Location" ]
                
                parsed_title = title
                parsed_company = "Unknown"
                parsed_location = "Unknown"
                
                clean_lines = []
                for line in lines:
                    # Filter out the garbage label immediately
                    if "be an early applicant" not in line.lower() and "neu" != line and "new" != line:
                        clean_lines.append(line)
                
                if len(clean_lines) > 0:
                    parsed_title = clean_lines[0]
                if len(clean_lines) > 1:
                    parsed_company = clean_lines[1]
                if len(clean_lines) > 2:
                    parsed_location = clean_lines[2]
                    
                # Assign back
                title = parsed_title
                company = parsed_company
                location = parsed_location

                # Final cleanup just in case
                if title.lower().startswith("be an early applicant"):
                     title = "Unknown" 
                
                self.seen_urls.add(url)
                print(f"Found: {title} at {company} ({location})") 

                self.seen_urls.add(url)
                print(f"Found: {title} at {company} ({location})") 
                
                self.jobs.append({
                    "Job Title": title,
                    "Company": company,
                    "Location": location,
                    "Web Address": url,
                    "Platform": "Xing",
                    "Date Extracted": datetime.datetime.now().strftime("%Y-%m-%d")
                })
            except Exception as e:
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
