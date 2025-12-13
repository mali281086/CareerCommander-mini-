import argparse
import urllib.parse
from job_hunter.scrapers.xing import XingJobScraper
from job_hunter.scrapers.stepstone import StepstoneJobScraper
from job_hunter.scrapers.indeed import IndeedJobScraper
from job_hunter.scrapers.ziprecruiter import ZipRecruiterJobScraper

def run_scrapers(keyword, location, platforms, limit=None):
    print(f"Starting search for '{keyword}' in '{location}' on {platforms} (Limit: {limit})")
    
    kw_enc = urllib.parse.quote(keyword)
    loc_enc = urllib.parse.quote(location)
    
    # 1. Xing
    if "Xing" in platforms or "All" in platforms:
        url = f"https://www.xing.com/jobs/search?keywords={kw_enc}&location={loc_enc}"
        print(f"Running Xing Scraper...")
        try:
            scraper = XingJobScraper(url, limit=limit)
            scraper.scrape()
        except Exception as e:
            print(f"Xing failed: {e}")

    # 2. Stepstone
    if "Stepstone" in platforms or "All" in platforms:
        # Stepstone slug logic: jobs/{kw}/in-{loc}
        kw_slug = keyword.replace(" ", "-").lower()
        loc_slug = location.replace(" ", "-").lower()
        if not loc_slug:
             url = f"https://www.stepstone.de/jobs/{kw_slug}"
        else:
             url = f"https://www.stepstone.de/jobs/{kw_slug}/in-{loc_slug}"
             
        print(f"Running Stepstone Scraper...")
        try:
            scraper = StepstoneJobScraper(url, limit=limit)
            scraper.scrape()
        except Exception as e:
            print(f"Stepstone failed: {e}")

    # 3. Indeed
    if "Indeed" in platforms or "All" in platforms:
        url = f"https://de.indeed.com/jobs?q={kw_enc}&l={loc_enc}"
        print(f"Running Indeed Scraper...")
        try:
            scraper = IndeedJobScraper(url, limit=limit)
            scraper.scrape()
        except Exception as e:
            print(f"Indeed failed: {e}")

    # 4. ZipRecruiter
    if "ZipRecruiter" in platforms or "All" in platforms:
        url = f"https://www.ziprecruiter.de/jobs/search?q={kw_enc}&l={loc_enc}"
        print(f"Running ZipRecruiter Scraper...")
        try:
            scraper = ZipRecruiterJobScraper(url, limit=limit)
            scraper.scrape()
        except Exception as e:
            print(f"ZipRecruiter failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Job Scrapers")
    parser.add_argument("--keyword", required=True, help="Job title or keyword")
    parser.add_argument("--location", required=False, default="", help="Location")
    parser.add_argument("--platforms", nargs="+", default=["All"], help="List of platforms to scrape")
    parser.add_argument("--limit", required=False, default=None, help="Max jobs per platform")
    
    args = parser.parse_args()
    
    run_scrapers(args.keyword, args.location, args.platforms, args.limit)
