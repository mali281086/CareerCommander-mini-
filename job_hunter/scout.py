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

    def launch_mission(self, keyword, location, limit, platforms, easy_apply=False, deep_scrape=True, status_callback=None):
        """
        Launches a job scouting mission.
        - easy_apply: If True, filters for Easy Apply jobs.
        - deep_scrape: If True, fetches full JD and language subsequently (Integrated).
        - status_callback: Optional function(msg) for UI progress updates.
        """
        all_results = []
        
        def log(msg):
            print(msg)
            if status_callback:
                status_callback(msg)

        try:
            for p_name in platforms:
                if p_name in self.scrapers:
                    log(f"🔍 Scouting {p_name} for '{keyword}'...")
                    try:
                        results = self.scrapers[p_name].search(keyword, location, limit, easy_apply=easy_apply)
                        # Inject keyword for tracking
                        for job in results:
                            job["Found_job"] = keyword
                        all_results.extend(results)
                    except Exception as e:
                        log(f"⚠️ Error checking {p_name}: {e}")
                else:
                    log(f"⚠️ Platform {p_name} not implemented.")

            # Integrated Deep Scrape phase
            if deep_scrape and all_results:
                # Deduplicate before deep scraping to save time
                # We only want to deep scrape jobs that aren't already in DB with a description
                # But for now, let's just do it for the new batch

                log(f"🕵️ Deep Scraping {len(all_results)} jobs...")
                fetcher = ContentFetcher()
                for i, job in enumerate(all_results):
                    url = job.get("link")
                    platform = job.get("platform") or job.get("Platform")
                    title = job.get("title") or job.get("Job Title")

                    if url and platform:
                        log(f"  [{i+1}/{len(all_results)}] Detail Fetch: {title}")
                        details = fetcher.fetch_details(url, platform)
                        if details:
                            job["rich_description"] = details.get("description", "")
                            job["language"] = details.get("language", "Unknown")
                            # Update company if found better name
                            if details.get("company") and details.get("company") != job.get("company"):
                                if "earn up to" not in details.get("company").lower():
                                    job["company"] = details.get("company")
                fetcher.close()

            # Save to DB (Single call ensures deep details are saved)
            log("💾 Saving mission results...")
            saved_data = self.db.save_scouted_jobs(all_results, append=True)
            log(f"✅ Mission Complete! {len(all_results)} jobs recorded.")

            return saved_data
            
        finally:
            # Cleanup - Close Browser
            print("Mission Complete. Closing Browser...")
            BrowserManager().close_driver()
