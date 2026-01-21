import time
from selenium.webdriver.common.by import By
from tools.browser_manager import BrowserManager
from job_hunter.data_manager import DataManager

class ApplicationAgent:
    def __init__(self):
        self.browser_manager = BrowserManager()
        self.driver = self.browser_manager.get_driver(headless=False) # Must be headed for applying
        self.db = DataManager()

    def run_apply_cycle(self, jobs_list):
        """
        Iterates through the provided list of jobs (from Scouted jobs).
        Performs Deep Scrape + Apply Logic.
        """
        log = []
        for i, job in enumerate(jobs_list):
            job_id = f"{job.get('title')}-{job.get('company')}"
            
            # Skip if already in 'applied.json' (Simple check)
            # ideally handle this at UI level or DB level
            
            print(f"[Agent] Processing: {job.get('title')}")
            result = self.process_single_job(job)
            log.append(result)
            
            # Update 'Applied' status in DB immediately if applied
            if result['status'] == 'applied':
                self.db.save_applied(job_id, job, analysis_data={"notes": "Auto-Applied via Agent"})
            
            time.sleep(2) # Breath between jobs

        return log

    def process_single_job(self, job):
        """
        1. Navigate
        2. Deep Scrape JD
        3. Check Easy Apply
        4. Apply or Mark Manual
        """
        link = job.get('link')
        if not link: return {"status": "skipped", "reason": "No link"}

        try:
            self.driver.get(link)
            time.sleep(3)
            
            # --- DEEP SCRAPE JD ---
            # Try generic selectors or platform specific
            full_description = self._extract_job_description(job.get('platform', 'Unknown'))
            job['Job Description'] = full_description
            
            # --- APPLY LOGIC ---
            # Check for "Easy Apply" / "Quick Apply"
            if self._is_easy_apply_available():
                success = self._attempt_easy_apply()
                if success:
                    return {"status": "applied", "job_title": job.get('title')}
                else:
                    return {"status": "manual_check", "reason": "Easy Apply Failed"}
            else:
                return {"status": "manual_required", "reason": "No Easy Apply"}

        except Exception as e:
            print(f"Error processing {job.get('title')}: {e}")
            return {"status": "error", "error": str(e)}

    def _extract_job_description(self, platform):
        # Very basic universal scraper attempt
        # Ideally split by platform
        try:
            # LinkedIn
            if "LinkedIn" in platform or "linkedin" in self.driver.current_url:
                 # "Click to see more" sometimes needed
                 try:
                     see_more = self.driver.find_element(By.CSS_SELECTOR, ".jobs-description__footer-button")
                     see_more.click()
                     time.sleep(1)
                 except: pass
                 
                 desc_box = self.driver.find_element(By.ID, "job-details")
                 return desc_box.text
            
            return "N/A - Scraper not implemented for this platform yet."
        except:
            return "Failed to extract description."

    def _is_easy_apply_available(self):
        # Look for typical buttons
        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            txt = btn.text.lower()
            if "easy apply" in txt or "bewerben" in txt or "solliciteren" in txt:
                return True
        return False

    def _attempt_easy_apply(self):
        """
        Attempts to click 'Easy Apply' and navigate the modal.
        Returns True if 'Submit' was clicked, False otherwise.
        """
        try:
            # 1. Click the main button (Easy Apply)
            # Try multiple selectors
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            apply_btn = None
            for btn in buttons:
                text = btn.text.lower()
                if "easy apply" in text or "einfach bewerben" in text:
                    apply_btn = btn
                    break
            
            if not apply_btn: return False
            
            apply_btn.click()
            time.sleep(2)
            
            # 2. Modal Navigation Loop
            # We look for "Next" or "Review" or "Submit"
            max_steps = 5
            for _ in range(max_steps):
                # Check for Submit
                submit_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Submit application'], button[aria-label='Bewerbung absenden']")
                if submit_btns:
                    # found submit!
                    # UNCOMMENT TO ACTUALLY SUBMIT
                    # submit_btns[0].click()
                    print("[Agent] Found SUBMIT button! (Simulation Mode: Not clicking)")
                    return True # simulated success
                
                # Check for Next
                next_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Continue to next step'], button[aria-label='Weiter zum nächsten Schritt']")
                if next_btns:
                    next_btns[0].click()
                    time.sleep(1)
                    continue

                # If we are here, we might be stuck or manual review needed
                # Check for "Review"
                review_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Review your application']")
                if review_btns:
                    review_btns[0].click()
                    time.sleep(1)
                    continue
                
                # If neither, break
                break
                
            return False
            
        except Exception as e:
            print(f"Easy Apply Error: {e}")
            return False
