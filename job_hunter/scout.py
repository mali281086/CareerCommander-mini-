from job_hunter.scrapers.linkedin import LinkedInScraper
from job_hunter.scrapers.indeed import IndeedScraper
from job_hunter.scrapers.stepstone import StepstoneScraper
from job_hunter.scrapers.xing import XingScraper
from job_hunter.scrapers.ziprecruiter import ZipRecruiterScraper
from job_hunter.data_manager import DataManager
from job_hunter.content_fetcher import ContentFetcher
from tools.browser_manager import BrowserManager
import time
import random

class Scout:
    def __init__(self):
        self.db = DataManager()
        self.scrapers = {
            "LinkedIn": LinkedInScraper(profile_name="LinkedIn"),
            "Indeed": IndeedScraper(profile_name="Indeed"),
            "Stepstone": StepstoneScraper(profile_name="Stepstone"),
            "Xing": XingScraper(profile_name="Xing"),
            "ZipRecruiter": ZipRecruiterScraper(profile_name="ZipRecruiter")
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
            # Sequential Scouting (Normal Mode - to avoid login issues)
            for p_name in platforms:
                if p_name in self.scrapers:
                    log(f"🔍 Scouting {p_name} for '{keyword}'...")
                    try:
                        res = self.scrapers[p_name].search(keyword, location, limit, easy_apply=easy_apply)
                        for job in res:
                            job["Found_job"] = keyword
                        all_results.extend(res)
                        log(f"✅ Found {len(res)} jobs on {p_name}")
                    except Exception as e:
                        log(f"⚠️ Error checking {p_name}: {e}")
                else:
                    log(f"⚠️ Platform {p_name} not implemented.")

            # Integrated Deep Scrape phase (Sequential)
            if deep_scrape and all_results:
                log(f"🕵️ Deep Scraping {len(all_results)} jobs...")

                # Single fetcher for all jobs to keep it stable
                fetcher = ContentFetcher(profile_name="default")
                try:
                    for i, job in enumerate(all_results):
                        url = job.get("link")
                        p_name = job.get("platform") or job.get("Platform") or "Unknown"
                        title = job.get("title") or job.get("Job Title")
                        if url:
                            log(f"  [{i+1}/{len(all_results)}] Fetching {p_name}: {title}")
                            # Add jitter to stay human
                            time.sleep(random.uniform(2, 4))
                            details = fetcher.fetch_details(url, p_name)
                            if details:
                                job["rich_description"] = details.get("description", "")
                                job["language"] = details.get("language", "Unknown")
                                job["is_easy_apply"] = details.get("is_easy_apply", job.get("is_easy_apply", False))
                                if details.get("company") and details.get("company") != job.get("company"):
                                    if "earn up to" not in details.get("company").lower():
                                        job["company"] = details.get("company")
                finally:
                    fetcher.close()

            # Save to DB (Single call ensures deep details are saved)
            log("💾 Saving mission results...")
            self.db.save_scouted_jobs(all_results, append=True)
            log(f"✅ Mission Complete! {len(all_results)} jobs recorded.")

            return all_results
            
        finally:
            # Cleanup - Close ALL Browsers (Ferrari: ensures no leaks)
            print("Mission Complete. Force closing all browsers...")
            BrowserManager().close_all_drivers()
