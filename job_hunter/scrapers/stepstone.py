import urllib.parse
from selenium.webdriver.common.by import By
from job_hunter.scrapers.base_scraper import BaseScraper
from job_hunter.models import JobRecord
from tools.browser_manager import BrowserManager
from typing import List, Optional
import time

class StepstoneScraper(BaseScraper):
    def __init__(self, profile_name="default"):
        self.bm = BrowserManager()
        self.profile_name = profile_name
        self.platform_name = "Stepstone"

    # Stepstone UI badge texts that should NOT be treated as company names
    BADGE_NOISE = [
        "passt hervorragend", "passt gut", "gute übereinstimmung",
        "neuer als 24h", "neu", "gesponsert", "sponsored", "spons",
        "teilweise home-office", "home-office", "remote",
        "deutsch", "english", "vollzeit", "teilzeit",
        "befristet", "unbefristet", "festanstellung",
    ]

    @property
    def driver(self):
        return self.bm.get_driver(headless=False, profile_name=self.profile_name)

    def _is_badge_noise(self, text: str) -> bool:
        """Returns True if the text is a Stepstone UI badge, not a company name."""
        t = text.strip().lower()
        return any(noise in t for noise in self.BADGE_NOISE) or len(t) < 2

    def search(self, keyword: str, location: str, limit: int = 10, easy_apply: bool = False) -> List[JobRecord]:
        results = []
        kw_slug = keyword.replace(" ", "-").lower()
        loc_slug = location.replace(" ", "-").lower()
        
        base_url = f"https://www.stepstone.de/jobs/{kw_slug}/in-{loc_slug}?"
        params = {"radius": "30"}
        url = base_url + urllib.parse.urlencode(params)
        
        self.log(f"Navigating to: {url}")
        self.driver.get(url)
        self.random_sleep(3, 5)
        
        scrolled = 0
        while len(results) < limit and scrolled < 3:
            cards = self.driver.find_elements(By.TAG_NAME, "article")
            self.log(f"Found {len(cards)} cards on Stepstone. Processing up to {limit - len(results)} more to reach limit...")
            
            for card in cards:
                if len(results) >= limit: break
                try:
                    title_link = None
                    try:
                        h2 = card.find_element(By.TAG_NAME, "h2")
                        title_link = h2.find_element(By.TAG_NAME, "a")
                    except: pass
                    
                    if not title_link:
                        links = card.find_elements(By.TAG_NAME, "a")
                        for l in links:
                            href = l.get_attribute("href")
                            if href and "stellenangebote--" in href:
                                title_link = l
                                break
                    
                    if not title_link: continue
                    link = title_link.get_attribute("href")
                    if not link: continue
                    
                    bad_signals = ["action=", "facet_", "radius=", "ag=", "wfh=", "am="]
                    if any(sig in link for sig in bad_signals): continue
                    
                    title = title_link.text.strip()
                    if not title:
                         try: title = card.find_element(By.TAG_NAME, "h2").text.strip()
                         except: pass
                    
                    if title in ["Neuer als 24h", "Teilweise Home-Office", "Deutsch", "English"]: continue
                    if "stepstone" in title.lower(): continue

                    # --- COMPANY EXTRACTION (Robust) ---
                    company = "Stepstone Listing"
                    
                    # Strategy 1: Try data-at attribute (Stepstone's company element)
                    try:
                        co_el = card.find_element(By.CSS_SELECTOR, "[data-at='job-item-company-name']")
                        if co_el and co_el.text.strip():
                            company = co_el.text.strip()
                    except: pass
                    
                    # Strategy 2: Try span/div near company area
                    if company == "Stepstone Listing":
                        try:
                            spans = card.find_elements(By.TAG_NAME, "span")
                            for span in spans:
                                txt = span.text.strip()
                                if txt and not self._is_badge_noise(txt) and txt != title and len(txt) > 2:
                                    company = txt
                                    break
                        except: pass

                    # Strategy 3: Fall back to line parsing but filter badges
                    if company == "Stepstone Listing":
                        lines = [l.strip() for l in card.text.split("\n") if l.strip()]
                        for line in lines:
                            if line == title: continue
                            if self._is_badge_noise(line): continue
                            company = line
                            break

                    if not any(j.link == link for j in results):
                        results.append(JobRecord(
                            title=title,
                            company=company,
                            location=location,
                            link=link,
                            platform=self.platform_name,
                            is_easy_apply=False
                        ))
                except: continue
            
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.random_sleep(2, 3)
            scrolled += 1
            
        return results

    def fetch_details(self, job_url: str) -> Optional[dict]:
        if not job_url: return None
        self.driver.get(job_url)
        self.random_sleep(2, 4)

        details = {"description": "", "is_easy_apply": False, "language": "de"}
        
        # --- EXTRACT COMPANY NAME from detail page header ---
        company_selectors = [
            "[data-at='header-company-name']",
            "[data-testid='company-name']",
            "a[data-at='job-header-company-name']",
            ".at-header-company-name",
            "[class*='CompanyName']",
        ]
        for sel in company_selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el and el.text.strip():
                    details['company'] = el.text.strip()
                    break
            except: continue

        # --- SCROLL DOWN to trigger lazy-loaded JD content ---
        for i in range(3):
            self.driver.execute_script(f"window.scrollTo(0, {(i + 1) * 800});")
            time.sleep(0.5)
        self.random_sleep(1, 2)

        # --- EXTRACT JOB DESCRIPTION ---
        desc_selectors = [
            "[data-testid='job-description-content']",
            "[data-testid='job-description']",
            "[data-testing='job-content']",
            "[data-at='job-ad-content']",
            "[class*='JobDescription']",
            ".js-app-ld-ContentBlock",
            "section.listing-content",
            ".job-description",
            "article"
        ]

        desc_el = None
        for selector in desc_selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
                if el and len(el.text) > 50:
                    desc_el = el
                    break
            except: continue

        if desc_el:
            details['description'] = desc_el.text
        else:
            # Last resort: grab all visible text from the page body
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                if len(body_text) > 200:
                    details['description'] = body_text
                    self.log("Used full body text as fallback for JD", level="warning")
            except: pass

        return details

