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
            # Multi-Platform Concurrency (Ferrari Mode)
            # We use threads to launch search missions in parallel
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def run_scraper(p_name):
                # Search results and logs
                logs = []
                jobs = []
                if p_name in self.scrapers:
                    logs.append(f"🔍 Scouting {p_name} for '{keyword}'...")
                    try:
                        res = self.scrapers[p_name].search(keyword, location, limit, easy_apply=easy_apply)
                        for job in res:
                            job["Found_job"] = keyword
                        jobs.extend(res)
                        logs.append(f"✅ Found {len(res)} jobs on {p_name}")
                    except Exception as e:
                        logs.append(f"⚠️ Error checking {p_name}: {e}")
                else:
                    logs.append(f"⚠️ Platform {p_name} not implemented.")
                return jobs, logs

            # Run search missions in parallel (FERRARI MODE)
            with ThreadPoolExecutor(max_workers=len(platforms)) as executor:
                future_to_platform = {executor.submit(run_scraper, p): p for p in platforms}
                for future in as_completed(future_to_platform):
                    jobs, thread_logs = future.result()
                    all_results.extend(jobs)
                    # Display logs in main thread
                    for msg in thread_logs:
                        log(msg)

            # Integrated Deep Scrape phase (FERRARI MODE)
            if deep_scrape and all_results:
                log(f"🕵️ Deep Scraping {len(all_results)} jobs ( Ferrari Parallel Mode)...")

                # Split jobs by platform to avoid hitting one platform too hard from multiple threads
                from collections import defaultdict
                platform_jobs = defaultdict(list)
                for j in all_results:
                    p = j.get("platform") or j.get("Platform") or "Unknown"
                    platform_jobs[p].append(j)

                def deep_scrape_platform(p_name, jobs):
                    # One fetcher per platform thread with its own profile
                    fetcher = ContentFetcher(profile_name=p_name)
                    thread_logs = []
                    for i, job in enumerate(jobs):
                        url = job.get("link")
                        title = job.get("title") or job.get("Job Title")
                        if url:
                            thread_logs.append(f"  [{p_name}] {i+1}/{len(jobs)} Fetch: {title}")
                            # Add jitter to stay human
                            time.sleep(random.uniform(1, 3))
                            details = fetcher.fetch_details(url, p_name)
                            if details:
                                job["rich_description"] = details.get("description", "")
                                job["language"] = details.get("language", "Unknown")
                                job["is_easy_apply"] = details.get("is_easy_apply", job.get("is_easy_apply", False))
                                if details.get("company") and details.get("company") != job.get("company"):
                                    if "earn up to" not in details.get("company").lower():
                                        job["company"] = details.get("company")
                    fetcher.close()
                    return thread_logs

                # Run deep scrapes for each platform in parallel
                with ThreadPoolExecutor(max_workers=len(platform_jobs)) as executor:
                    future_to_platform_ds = {executor.submit(deep_scrape_platform, p, jobs): p for p, jobs in platform_jobs.items()}
                    for future in as_completed(future_to_platform_ds):
                        try:
                            thread_logs = future.result()
                            for msg in thread_logs:
                                log(msg)
                        except Exception as e:
                            log(f"⚠️ Deep Scrape Thread Error: {e}")

            # Save to DB (Single call ensures deep details are saved)
            log("💾 Saving mission results...")
            self.db.save_scouted_jobs(all_results, append=True)
            log(f"✅ Mission Complete! {len(all_results)} jobs recorded.")

            return all_results
            
        finally:
            # Cleanup - Close Browser
            print("Mission Complete. Closing Browser...")
            BrowserManager().close_driver()
