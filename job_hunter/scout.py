from job_hunter.scrapers.linkedin import LinkedInScraper
from job_hunter.scrapers.indeed import IndeedScraper
from job_hunter.scrapers.stepstone import StepstoneScraper
from job_hunter.scrapers.xing import XingScraper
from job_hunter.scrapers.ziprecruiter import ZipRecruiterScraper
from job_hunter.data_manager import DataManager
from job_hunter.content_fetcher import ContentFetcher
from tools.browser_manager import BrowserManager

class Scout:
    def __init__(self):
        self.db = DataManager()
        self.scrapers = {
            "LinkedIn": LinkedInScraper(),
            "Indeed": IndeedScraper(),
            "Stepstone": StepstoneScraper(),
            "Xing": XingScraper(),
            "ZipRecruiter": ZipRecruiterScraper()
        }

    def launch_mission(self, keyword, location, limit, platforms, easy_apply=False, deep_scrape=False):
        all_results = []
        
        try:
            for p_name in platforms:
                if p_name in self.scrapers:
                    print(f"Scouting {p_name}...")
                    try:
                        results = self.scrapers[p_name].search(keyword, location, limit, easy_apply=easy_apply)
                        # Inject keyword for tracking
                        for job in results:
                            job["Found_job"] = keyword
                        all_results.extend(results)
                    except Exception as e:
                        print(f"Error checking {p_name}: {e}")
                else:
                    print(f"Platform {p_name} not yet implemented.")
            
            # Deep Scrape if requested
            if deep_scrape and all_results:
                print(f"Starting Deep Scrape for {len(all_results)} jobs...")
                fetcher = ContentFetcher()
                for i, job in enumerate(all_results):
                    url = job.get("link")
                    platform = job.get("platform")
                    if url and platform:
                        print(f"  [{i+1}/{len(all_results)}] Fetching details: {job.get('title')}")
                        details = fetcher.fetch_details(url, platform)
                        if details:
                            job["rich_description"] = details.get("description", "")
                            job["language"] = details.get("language", "Unknown")
                            # Update company if found better name
                            if details.get("company") and details.get("company") != job.get("company"):
                                if "earn up to" not in details.get("company").lower():
                                    job["company"] = details.get("company")
                fetcher.close()

            # Save to DB (Single call to avoid duplicates and ensure deep details are saved)
            saved_data = self.db.save_scouted_jobs(all_results, append=True)

            return saved_data
            
        finally:
            # Cleanup - Close Browser
            print("Mission Complete. Closing Browser...")
            BrowserManager().close_driver()
