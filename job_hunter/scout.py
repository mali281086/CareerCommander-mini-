from tools.logger import logger
import time
import random
from job_hunter.scrapers.linkedin import LinkedInScraper
from job_hunter.scrapers.indeed import IndeedScraper
from job_hunter.scrapers.stepstone import StepstoneScraper
from job_hunter.scrapers.xing import XingScraper
from job_hunter.scrapers.ziprecruiter import ZipRecruiterScraper
from job_hunter.data_manager import DataManager
from tools.browser_manager import BrowserManager

class Scout:
    def __init__(self):
        self.db = DataManager()
        self.scrapers = {
            "LinkedIn": LinkedInScraper(profile_name="default"),
            "Indeed": IndeedScraper(profile_name="default"),
            "Stepstone": StepstoneScraper(profile_name="default"),
            "Xing": XingScraper(profile_name="default"),
            "ZipRecruiter": ZipRecruiterScraper(profile_name="default")
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
            logger.info(msg)
            if status_callback:
                status_callback(msg)

        try:
            # Sequential Scouting (Normal Mode - to avoid login issues)
            for p_name in platforms:
                if p_name in self.scrapers:
                    log(f"🔍 Scouting {p_name} for '{keyword}'...")
                    try:
                        # Scrapers now return JobRecord objects
                        records = self.scrapers[p_name].search(keyword, location, limit, easy_apply=easy_apply)

                        # Convert to dictionaries for legacy compatibility
                        res = []
                        for rec in records:
                            job_dict = rec.to_dict()
                            job_dict["Found_job"] = keyword
                            res.append(job_dict)

                        all_results.extend(res)
                        log(f"✅ Found {len(res)} jobs on {p_name}")
                    except Exception as e:
                        log(f"⚠️ Error checking {p_name}: {e}")
                else:
                    log(f"⚠️ Platform {p_name} not implemented.")

            # Integrated Deep Scrape phase (Sequential)
            if deep_scrape and all_results:
                log(f"🕵️ Deep Scraping {len(all_results)} jobs...")

                # Integrated Deep Scrape phase (using unified scraper methods)
                for i, job in enumerate(all_results):
                    url = job.get("link")
                    p_name = job.get("platform")
                    title = job.get("title")

                    if url and p_name in self.scrapers:
                        log(f"  [{i+1}/{len(all_results)}] Fetching {p_name}: {title}")
                        time.sleep(random.uniform(2, 4)) # Jitter

                        try:
                            details = self.scrapers[p_name].fetch_details(url)
                            if details:
                                job["rich_description"] = details.get("description", "")
                                job["language"] = details.get("language", "Unknown")
                                job["is_easy_apply"] = details.get("is_easy_apply", job.get("is_easy_apply", False))
                                if details.get("company") and details.get("company") != job.get("company"):
                                    if "earn up to" not in details.get("company").lower():
                                        job["company"] = details.get("company")
                        except Exception as e:
                            log(f"  ⚠️ Error fetching details for {title}: {e}")

            # Save to DB (Single call ensures deep details are saved)
            log("💾 Saving mission results...")
            self.db.save_scouted_jobs(all_results, append=True)
            log(f"✅ Mission Complete! {len(all_results)} jobs recorded.")

            return all_results
            
        finally:
            # Cleanup - Close ALL Browsers (Ferrari: ensures no leaks)
            logger.info("Mission Complete. Force closing all browsers...")
            BrowserManager().close_all_drivers()
