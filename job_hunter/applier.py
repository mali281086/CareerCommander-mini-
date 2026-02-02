import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from tools.browser_manager import BrowserManager
from job_hunter.data_manager import DataManager

class JobApplier:
    """Handles automated Easy Apply for LinkedIn and Xing."""
    
    def __init__(self, resume_path=None, phone_number=None):
        self.bm = BrowserManager()
        self.driver = self.bm.get_driver(headless=False)  # Always visible for safety
        self.resume_path = resume_path
        self.phone_number = phone_number or ""
        self.applied_count = 0
        self.max_applications = 50  # Safety limit per session
        self.db = DataManager()  # For question-answer config
        self.current_job_title = ""  # For logging unknown questions
        self.current_company = ""
    
    def random_sleep(self, min_sec=2, max_sec=5):
        time.sleep(random.uniform(min_sec, max_sec))
    
    def click_element(self, selector, by=By.CSS_SELECTOR, timeout=10):
        """Wait for element and click it."""
        try:
            elem = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )
            elem.click()
            return True
        except TimeoutException:
            print(f"[Applier] Timeout waiting for: {selector}")
            return False
    
    def find_element_safe(self, selector, by=By.CSS_SELECTOR, timeout=5):
        """Find element without throwing exception."""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
        except:
            return None
    
    # ==========================================
    # DETECTION METHODS
    # ==========================================
    def is_easy_apply_linkedin(self, job_url):
        """Check if a LinkedIn job has Easy Apply button."""
        print(f"[LinkedIn] Checking Easy Apply: {job_url}")
        self.driver.get(job_url)
        self.random_sleep(3, 5)  # Wait longer for page to load
        
        # Multiple selector strategies for Easy Apply button
        easy_apply_selectors = [
            # Primary selectors
            "button.jobs-apply-button",
            "button[aria-label*='Easy Apply']",
            ".jobs-apply-button--top-card button",
            # Alternative selectors (LinkedIn changes these often)
            "button.jobs-apply-button--top-card",
            ".jobs-s-apply button",
            "div.jobs-apply-button--top-card button",
            ".jobs-unified-top-card button.jobs-apply-button",
            # Generic fallback
            "button[class*='apply']",
        ]
        
        for selector in easy_apply_selectors:
            try:
                btn = self.find_element_safe(selector, timeout=2)
                if btn:
                    btn_text = btn.text.lower().strip()
                    aria_label = (btn.get_attribute("aria-label") or "").lower()
                    btn_class = (btn.get_attribute("class") or "").lower()
                    
                    print(f"[LinkedIn] Found button: text='{btn_text}', aria='{aria_label}', class='{btn_class}'")
                    
                    # Check if it's Easy Apply (English or German)
                    if "easy" in btn_text or "easy" in aria_label or "einfach" in btn_text or "bewerben" in btn_text:
                        print("[LinkedIn] ✓ Easy Apply detected!")
                        return True
                    
                    # Check if button has jobs-apply-button class (LinkedIn's Easy Apply class)
                    if "jobs-apply-button" in btn_class and "apply" in btn_text:
                        print("[LinkedIn] ✓ Easy Apply detected (via class)!")
                        return True
            except Exception as e:
                print(f"[LinkedIn] Selector {selector} failed: {e}")
                continue
        
        # XPath fallback - search for any button with Easy Apply text (EN or DE)
        try:
            easy_xpath = "//button[contains(translate(., 'EASYAPPLY', 'easyapply'), 'easy apply') or contains(@aria-label, 'Easy Apply') or contains(translate(., 'EINFACH', 'einfach'), 'einfach bewerben')]"
            btn = self.driver.find_element(By.XPATH, easy_xpath)
            if btn:
                print(f"[LinkedIn] ✓ Easy Apply detected via XPath!")
                return True
        except:
            pass
        
        print("[LinkedIn] ✗ Not Easy Apply (external apply required)")
        return False
    
    def is_easy_apply_xing(self, job_url):
        """Check if a Xing job has Easy Apply (not external redirect)."""
        print(f"[Xing] Checking Easy Apply: {job_url}")
        self.driver.get(job_url)
        self.random_sleep(2, 4)
        
        # Keywords that indicate EASY APPLY (internal application)
        easy_apply_keywords = [
            "schnellbewerbung",  # German: Quick Apply
            "easy apply",
            "direkt bewerben",   # German: Apply Directly
            "jetzt bewerben",    # German: Apply Now (on Xing's internal system)
        ]
        
        # Keywords that indicate EXTERNAL APPLY (should skip)
        external_keywords = [
            "visit employer",
            "zur arbeitgeber",   # German: To Employer
            "external",
            "website",
            "karriereseite",     # German: Career Site
        ]
        
        # Look for apply buttons and check their text
        apply_selectors = [
            "button[data-testid='apply-button']",
            "a[data-testid='apply-button']",
            "button.apply-button",
            "a.apply-button",
            "[data-testid='apply-button']"
        ]
        
        for selector in apply_selectors:
            btn = self.find_element_safe(selector, timeout=3)
            if btn:
                btn_text = btn.text.lower().strip()
                print(f"[Xing] Found button with text: '{btn_text}'")
                
                # Check if it's EXTERNAL (should reject)
                if any(ext in btn_text for ext in external_keywords):
                    print("[Xing] ✗ External apply detected - skipping")
                    return False
                
                # Check if it's EASY APPLY
                if any(easy in btn_text for easy in easy_apply_keywords):
                    print("[Xing] ✓ Easy Apply detected!")
                    return True
        
        # XPath fallback - but still check text
        try:
            buttons = self.driver.find_elements(By.XPATH, "//button | //a")
            for btn in buttons:
                try:
                    btn_text = btn.text.lower().strip()
                    if len(btn_text) > 50:  # Skip long text elements
                        continue
                    
                    # Check for external keywords first
                    if any(ext in btn_text for ext in external_keywords):
                        continue
                    
                    # Check for easy apply keywords
                    if any(easy in btn_text for easy in easy_apply_keywords):
                        print(f"[Xing] ✓ Easy Apply detected via XPath: '{btn_text}'")
                        return True
                except:
                    continue
        except:
            pass
        
        print("[Xing] ✗ Not Easy Apply (external or no apply button found)")
        return False
    # ==========================================
    # LINKEDIN EASY APPLY
    # ==========================================
    def apply_linkedin(self, job_url, skip_detection=False):
        """
        Automates LinkedIn Easy Apply.
        Returns: (success: bool, message: str, is_easy_apply: bool)
        """
        if self.applied_count >= self.max_applications:
            return False, "Max applications reached for this session.", False
        
        # Detection step (unless skipped)
        if not skip_detection:
            is_easy = self.is_easy_apply_linkedin(job_url)
            if not is_easy:
                return False, "Not an Easy Apply job. Skipped.", False
        else:
            # Navigate if detection was skipped
            print(f"[LinkedIn] Navigating to: {job_url}")
            self.driver.get(job_url)
            self.random_sleep(3, 5)
        
        # 1. Find and Click "Easy Apply" Button
        easy_apply_selectors = [
            "button.jobs-apply-button",
            "button[aria-label*='Easy Apply']",
            ".jobs-apply-button--top-card button",
            "button.jobs-apply-button--top-card",
            ".jobs-s-apply button",
            "div.jobs-apply-button--top-card button",
            ".jobs-unified-top-card button.jobs-apply-button",
        ]
        
        clicked = False
        for selector in easy_apply_selectors:
            try:
                if self.click_element(selector, timeout=3):
                    clicked = True
                    print(f"[LinkedIn] Clicked Easy Apply button via: {selector}")
                    break
            except:
                continue
        
        # XPath fallback for clicking
        if not clicked:
            try:
                easy_xpath = "//button[contains(translate(., 'EASYAPPLY', 'easyapply'), 'easy apply') or contains(@aria-label, 'Easy Apply') or contains(translate(., 'EINFACH', 'einfach'), 'einfach bewerben')]"
                btn = self.driver.find_element(By.XPATH, easy_xpath)
                btn.click()
                clicked = True
                print("[LinkedIn] Clicked Easy Apply button via XPath")
            except:
                pass
        
        if not clicked:
            return False, "Easy Apply button not found. May require external apply.", False
        
        self.random_sleep(2, 4)
        
        # 2. Process the Modal Steps
        max_steps = 15  # Safety limit
        step = 0
        
        while step < max_steps:
            step += 1
            print(f"[LinkedIn] Processing step {step}...")
            self.random_sleep(1, 2)
            
            # Check for Submit button first (means we're done)
            submit_selectors = [
                "button[aria-label='Submit application']",
                "button[aria-label*='Submit']",
                "footer button[aria-label*='Submit']",
                "button.artdeco-button--primary[aria-label*='Submit']",
            ]
            
            for sel in submit_selectors:
                submit_btn = self.find_element_safe(sel, timeout=2)
                if submit_btn:
                    try:
                        submit_btn.click()
                        self.random_sleep(2, 3)
                        self.applied_count += 1
                        print("[LinkedIn] ✓ Application submitted!")
                        return True, "Application submitted successfully!", True
                    except Exception as e:
                        print(f"[LinkedIn] Submit click failed: {e}")
            
            # Check for Review button
            review_selectors = [
                "button[aria-label='Review your application']",
                "button[aria-label*='Review']",
                "footer button[aria-label*='Review']",
            ]
            
            for sel in review_selectors:
                review_btn = self.find_element_safe(sel, timeout=1)
                if review_btn:
                    try:
                        review_btn.click()
                        print("[LinkedIn] Clicked Review button")
                        self.random_sleep(1, 2)
                        break
                    except:
                        pass
            
            # Handle common fields
            self._linkedin_fill_fields()
            
            # Click Next/Continue
            next_selectors = [
                "button[aria-label='Continue to next step']",
                "button[data-easy-apply-next-button]",
                "footer button.artdeco-button--primary",
                "button.artdeco-button--primary[type='button']",
            ]
            
            next_clicked = False
            for selector in next_selectors:
                try:
                    btn = self.find_element_safe(selector, timeout=2)
                    if btn and btn.is_displayed() and btn.is_enabled():
                        btn_text = btn.text.lower()
                        # Avoid clicking Submit or Review accidentally
                        if "submit" in btn_text or "review" in btn_text:
                            continue
                        btn.click()
                        next_clicked = True
                        print(f"[LinkedIn] Clicked Next via: {selector}")
                        break
                except:
                    continue
            
            if not next_clicked:
                # Check for error messages
                error_msg = self.find_element_safe(".artdeco-inline-feedback--error", timeout=1)
                if error_msg:
                    print(f"[LinkedIn] Error on form: {error_msg.text}")
                    
                # Check for dismiss/close
                close_btn = self.find_element_safe("button[aria-label='Dismiss']", timeout=2)
                if close_btn:
                    close_btn.click()
                    return False, "Got stuck. Modal dismissed.", True
                    
                # Maybe application was already submitted?
                if step > 5:
                    return False, "Unable to proceed. Check manually.", True
            
            self.random_sleep(2, 3)
        
        return False, "Exceeded max steps. Check manually.", True
    
    def _linkedin_fill_fields(self):
        """Fill common fields in LinkedIn Easy Apply modal with smart question detection."""
        
        # 1. Phone Number
        phone_input = self.find_element_safe("input[id*='phoneNumber'], input[name*='phone']", timeout=2)
        if phone_input and not phone_input.get_attribute("value"):
            phone_input.clear()
            phone_input.send_keys(self.phone_number)
            print("[LinkedIn] Filled phone number.")
        
        # 2. Resume Upload
        if self.resume_path:
            file_input = self.find_element_safe("input[type='file']", timeout=2)
            if file_input:
                try:
                    file_input.send_keys(self.resume_path)
                    print("[LinkedIn] Uploaded resume.")
                except Exception as e:
                    print(f"[LinkedIn] Resume upload failed: {e}")
        
        # 3. Handle TEXT INPUTS with labels
        try:
            form_groups = self.driver.find_elements(By.CSS_SELECTOR, ".fb-dash-form-element, .jobs-easy-apply-form-section__grouping")
            for group in form_groups:
                try:
                    # Find label
                    label_el = group.find_element(By.CSS_SELECTOR, "label, .fb-dash-form-element__label, span.t-bold")
                    label_text = label_el.text.strip()
                    
                    if not label_text or len(label_text) < 3:
                        continue
                    
                    # Find input
                    input_el = group.find_element(By.CSS_SELECTOR, "input[type='text'], input[type='number'], input:not([type='file']):not([type='radio']):not([type='checkbox'])")
                    
                    # Skip if already filled
                    if input_el.get_attribute("value"):
                        continue
                    
                    # Try to get answer from config
                    answer = self.db.get_answer_for_question(label_text)
                    
                    if answer is not None and answer != "":
                        input_el.clear()
                        input_el.send_keys(answer)
                        print(f"[LinkedIn] Answered '{label_text}' → '{answer}'")
                    else:
                        # Log as unknown question
                        print(f"[LinkedIn] ❓ Unknown question: '{label_text}'")
                        self.db.log_unknown_question(label_text, self.current_job_title, self.current_company)
                except:
                    continue
        except:
            pass
        
        # 4. Handle DROPDOWNS / SELECT elements
        try:
            selects = self.driver.find_elements(By.CSS_SELECTOR, "select")
            for select in selects:
                try:
                    # Get the label
                    parent = select.find_element(By.XPATH, "./..")
                    label_el = parent.find_element(By.CSS_SELECTOR, "label, span")
                    label_text = label_el.text.strip() if label_el else "dropdown"
                    
                    # Get answer from config
                    answer = self.db.get_answer_for_question(label_text)
                    
                    # Find options
                    options = select.find_elements(By.TAG_NAME, "option")
                    if len(options) <= 1:
                        continue
                    
                    # If we have a configured answer, try to match
                    if answer:
                        for opt in options:
                            if answer.lower() in opt.text.lower():
                                opt.click()
                                print(f"[LinkedIn] Selected '{opt.text}' for '{label_text}'")
                                break
                    else:
                        # Default: select first non-empty option
                        for opt in options[1:]:  # Skip first empty option
                            if opt.text.strip():
                                opt.click()
                                print(f"[LinkedIn] Auto-selected '{opt.text}' for dropdown")
                                break
                except:
                    continue
        except:
            pass
        
        # 5. Handle RADIO BUTTONS with smart Yes/No matching
        try:
            radio_groups = self.driver.find_elements(By.CSS_SELECTOR, "fieldset[data-test-form-builder-radio-button-form-component], fieldset")
            for group in radio_groups:
                try:
                    # Get the question/legend
                    legend = group.find_element(By.CSS_SELECTOR, "legend, span.t-bold")
                    question_text = legend.text.strip() if legend else ""
                    
                    # Get configured answer
                    answer = self.db.get_answer_for_question(question_text) if question_text else None
                    
                    radios = group.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                    if not radios:
                        continue
                    
                    # Check if any radio is already selected
                    any_selected = any(r.is_selected() for r in radios)
                    if any_selected:
                        continue
                    
                    if answer:
                        # Try to find matching option
                        for radio in radios:
                            try:
                                label = radio.find_element(By.XPATH, "./following-sibling::label | ../label | ../../label")
                                if answer.lower() in label.text.lower():
                                    radio.click()
                                    print(f"[LinkedIn] Selected '{label.text}' for '{question_text}'")
                                    break
                            except:
                                continue
                    else:
                        # Default: select first option (usually "Yes")
                        radios[0].click()
                        print(f"[LinkedIn] Auto-selected first option for '{question_text}'")
                        
                        if question_text:
                            self.db.log_unknown_question(question_text, self.current_job_title, self.current_company)
                except:
                    pass
        except:
            pass
        
        # 6. Handle CHECKBOXES (required agreements)
        try:
            checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']:not(:checked)")
            for cb in checkboxes:
                try:
                    # Check if it's a required field
                    parent = cb.find_element(By.XPATH, "./..")
                    label_text = parent.text.lower()
                    
                    # Auto-check consent boxes
                    if "agree" in label_text or "terms" in label_text or "consent" in label_text:
                        cb.click()
                        print("[LinkedIn] Checked consent checkbox")
                except:
                    continue
        except:
            pass

    
    # ==========================================
    # XING EASY APPLY
    # ==========================================
    def apply_xing(self, job_url, skip_detection=False):
        """
        Automates Xing Apply.
        Returns: (success: bool, message: str, is_easy_apply: bool)
        """
        if self.applied_count >= self.max_applications:
            return False, "Max applications reached for this session.", False
        
        # Detection step (unless skipped)
        if not skip_detection:
            is_easy = self.is_easy_apply_xing(job_url)
            if not is_easy:
                return False, "Not a Quick Apply job. Skipped.", False
        else:
            print(f"[Xing] Navigating to: {job_url}")
            self.driver.get(job_url)
            self.random_sleep(3, 5)
        
        # 1. Find and Click Apply Button
        apply_selectors = [
            "button[data-testid='apply-button']",
            "a[data-testid='apply-button']",
            "button.apply-button",
            "a.apply-button",
            "button:contains('Jetzt bewerben')"  # German: Apply Now
        ]
        
        clicked = False
        for selector in apply_selectors:
            if self.click_element(selector, timeout=5):
                clicked = True
                print("[Xing] Clicked Apply button.")
                break
        
        if not clicked:
            # Try XPath for text-based search
            try:
                apply_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'bewerben')] | //a[contains(text(), 'bewerben')]")
                apply_btn.click()
                clicked = True
                print("[Xing] Clicked Apply button (XPath).")
            except:
                pass
        
        if not clicked:
            return False, "Apply button not found.", False
        
        self.random_sleep(2, 3)
        
        # 2. Handle Application Form
        # Upload Resume if prompted
        if self.resume_path:
            file_input = self.find_element_safe("input[type='file']", timeout=3)
            if file_input:
                try:
                    file_input.send_keys(self.resume_path)
                    print("[Xing] Uploaded resume.")
                    self.random_sleep(1, 2)
                except Exception as e:
                    print(f"[Xing] Resume upload failed: {e}")
        
        # 3. Submit
        submit_selectors = [
            "button[type='submit']",
            "button[data-testid='submit-application']",
            "button.submit-button"
        ]
        
        for selector in submit_selectors:
            if self.click_element(selector, timeout=5):
                self.random_sleep(2, 3)
                self.applied_count += 1
                return True, "Application submitted successfully!", True
        
        return False, "Submit button not found. Check manually.", True
    
    # ==========================================
    # MAIN APPLY DISPATCHER
    # ==========================================
    def apply(self, job_url, platform, skip_detection=False, job_title="", company=""):
        """Dispatch to the correct applier based on platform."""
        # Set current job info for logging unknown questions
        self.current_job_title = job_title
        self.current_company = company
        
        platform_lower = platform.lower()
        
        if "linkedin" in platform_lower:
            return self.apply_linkedin(job_url, skip_detection)
        elif "xing" in platform_lower:
            return self.apply_xing(job_url, skip_detection)
        else:
            return False, f"Platform '{platform}' not supported for auto-apply.", False
    
    # ==========================================
    # LIVE APPLY MODE - LinkedIn
    # ==========================================
    def live_apply_linkedin(self, keyword, location, target_count=5, callback=None):
        """
        Browse LinkedIn job search and apply to jobs until target_count is reached.
        Skips: already applied, parked, blacklisted jobs.
        
        Args:
            keyword: Job search keyword
            location: Location to search
            target_count: Number of successful applications to make
            callback: Optional function to call with status updates (for UI)
        
        Returns:
            dict with results: applied_jobs, skipped_jobs, errors
        """
        results = {
            "applied": [],
            "skipped": [],
            "errors": [],
            "checked": 0
        }
        
        # Load filters from data manager
        applied_jobs = self.db.load_applied()
        applied_links = set()
        for v in applied_jobs.values():
            details = v.get('job_details', {})
            lnk = details.get('Web Address') or details.get('link')
            if lnk:
                applied_links.add(lnk)
        
        parked_jobs = self.db.load_parked()
        parked_links = {p.get('link') for p in parked_jobs if p.get('link')}
        
        blacklist = self.db.load_blacklist()
        bl_companies = [c.lower() for c in blacklist.get("companies", []) if c]
        bl_titles = [t.lower() for t in blacklist.get("titles", []) if t]
        safe_phrases = [s.lower() for s in blacklist.get("safe_phrases", []) if s]
        
        def log(msg):
            print(f"[LiveApply] {msg}")
            if callback:
                callback(msg)
        
        def is_blacklisted(title, company):
            """Check if job should be skipped based on blacklist."""
            t_lower = title.lower()
            c_lower = company.lower()
            
            # Company blacklist (always blocks)
            for bl_c in bl_companies:
                if bl_c in c_lower:
                    return True, f"Company '{company}' is blacklisted"
            
            # Title blacklist (can be rescued by safe phrases)
            for bl_t in bl_titles:
                if bl_t in t_lower:
                    # Check safe phrases
                    for safe in safe_phrases:
                        if safe in t_lower:
                            return False, None  # Rescued!
                    return True, f"Title contains blacklisted term '{bl_t}'"
            
            return False, None
        
        # Navigate to LinkedIn Jobs Search
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={keyword.replace(' ', '+')}&location={location.replace(' ', '+')}"
        log(f"Navigating to: {search_url}")
        self.driver.get(search_url)
        self.random_sleep(4, 6)
        
        # Click the Easy Apply filter button (Einfach bewerben / Easy Apply)
        log("🔍 Clicking Easy Apply filter...")
        easy_apply_filter_clicked = False
        
        # Try multiple selectors for the filter button
        filter_selectors = [
            "button[aria-label*='Easy Apply']",
            "button[aria-label*='Einfach bewerben']",
            "button.search-reusables__filter-binary-toggle",
            "//button[contains(text(), 'Easy Apply')]",
            "//button[contains(text(), 'Einfach bewerben')]",
        ]
        
        for selector in filter_selectors:
            try:
                if selector.startswith("//"):
                    # XPath
                    btn = self.driver.find_element(By.XPATH, selector)
                else:
                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                if btn and btn.is_displayed():
                    # Check if it's the Easy Apply filter specifically
                    btn_text = btn.text.lower()
                    aria_label = (btn.get_attribute("aria-label") or "").lower()
                    
                    if "easy" in btn_text or "einfach" in btn_text or "easy" in aria_label or "einfach" in aria_label:
                        btn.click()
                        easy_apply_filter_clicked = True
                        log("✅ Easy Apply filter clicked!")
                        self.random_sleep(2, 3)
                        break
            except:
                continue
        
        # Fallback: Try to find the filter in the "All Filters" modal
        if not easy_apply_filter_clicked:
            try:
                # Look for the filter button directly in the filter bar
                all_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button")
                for btn in all_buttons:
                    try:
                        btn_text = btn.text.lower().strip()
                        if btn_text in ["easy apply", "einfach bewerben"]:
                            btn.click()
                            easy_apply_filter_clicked = True
                            log("✅ Easy Apply filter clicked via text search!")
                            self.random_sleep(2, 3)
                            break
                    except:
                        continue
            except:
                pass
        
        if not easy_apply_filter_clicked:
            log("⚠️ Could not click Easy Apply filter - will check each job individually")
        
        page = 0
        max_pages = 20  # Safety limit
        
        while self.applied_count < target_count and page < max_pages:
            page += 1
            log(f"📄 Scanning page {page}...")
            
            # Find job cards on current page
            try:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, ".jobs-search-results__list-item, .job-card-container, .jobs-search-results-list__list-item")
                log(f"Found {len(job_cards)} job cards")
            except:
                job_cards = []
            
            if not job_cards:
                log("No job cards found, trying to scroll...")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self.random_sleep(2, 3)
                continue
            
            for idx, card in enumerate(job_cards):
                if self.applied_count >= target_count:
                    break
                
                results["checked"] += 1
                
                try:
                    # Click the card to load job details
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                    self.random_sleep(0.5, 1)
                    card.click()
                    self.random_sleep(2, 3)
                    
                    # Get job URL
                    current_url = self.driver.current_url
                    
                    # Extract job title and company from the page
                    try:
                        title_el = self.driver.find_element(By.CSS_SELECTOR, ".jobs-unified-top-card__job-title, .job-details-jobs-unified-top-card__job-title, h1.t-24")
                        title = title_el.text.strip()
                    except:
                        title = "Unknown"
                    
                    try:
                        company_el = self.driver.find_element(By.CSS_SELECTOR, ".jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__subtitle-primary-grouping a")
                        company = company_el.text.strip()
                    except:
                        company = "Unknown"
                    
                    log(f"[{idx+1}/{len(job_cards)}] Checking: {title} @ {company}")
                    
                    # Check if already applied
                    if current_url in applied_links:
                        log(f"   ⏭️ Already applied - skipping")
                        results["skipped"].append({"title": title, "company": company, "reason": "Already applied"})
                        continue
                    
                    # Check if parked
                    if current_url in parked_links:
                        log(f"   ⏭️ In parked jobs - skipping")
                        results["skipped"].append({"title": title, "company": company, "reason": "Parked"})
                        continue
                    
                    # Check blacklist
                    is_blocked, reason = is_blacklisted(title, company)
                    if is_blocked:
                        log(f"   ⏭️ Blacklisted: {reason}")
                        results["skipped"].append({"title": title, "company": company, "reason": reason})
                        continue
                    
                    # Try to apply
                    log(f"   🎯 Attempting to apply...")
                    self.current_job_title = title
                    self.current_company = company
                    
                    success, message, is_easy = self.apply_linkedin(current_url, skip_detection=True)
                    
                    if success:
                        log(f"   ✅ Applied successfully!")
                        results["applied"].append({"title": title, "company": company, "url": current_url})
                        applied_links.add(current_url)  # Add to set so we don't retry
                        
                        # Save to applied jobs
                        jid = f"{title}-{company}"
                        job_data = {"Job Title": title, "Company": company, "Web Address": current_url, "Platform": "LinkedIn"}
                        self.db.save_applied(jid, job_data, {"auto_applied": True})
                    else:
                        log(f"   ❌ Failed: {message}")
                        if is_easy:
                            results["errors"].append({"title": title, "company": company, "error": message})
                        else:
                            results["skipped"].append({"title": title, "company": company, "reason": "Not Easy Apply"})
                    
                    # Navigate back to search results
                    self.driver.get(search_url)
                    self.random_sleep(2, 3)
                    
                except Exception as e:
                    log(f"   ⚠️ Error processing card: {e}")
                    results["errors"].append({"error": str(e)})
                    continue
            
            # Go to next page if needed
            if self.applied_count < target_count:
                try:
                    # Try to click next page
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Page forward'], button[aria-label='Next'], li.artdeco-pagination__indicator--number:not(.active) button")
                    next_btn.click()
                    self.random_sleep(3, 4)
                except:
                    log("No more pages or couldn't navigate to next page")
                    break
        
        log(f"🏁 Live Apply Complete! Applied: {len(results['applied'])} | Skipped: {len(results['skipped'])} | Errors: {len(results['errors'])}")
        return results
    
    # ==========================================
    # LIVE APPLY MODE - Xing
    # ==========================================
    def live_apply_xing(self, keyword, location, target_count=5, callback=None):
        """
        Browse Xing job search and apply to jobs until target_count is reached.
        Xing has no Easy Apply filter, so we check each job individually.
        
        Args:
            keyword: Job search keyword
            location: Location to search
            target_count: Number of successful applications to make
            callback: Optional function to call with status updates
        
        Returns:
            dict with results
        """
        results = {
            "applied": [],
            "skipped": [],
            "errors": [],
            "checked": 0
        }
        
        # Load filters
        applied_jobs = self.db.load_applied()
        applied_links = set()
        for v in applied_jobs.values():
            details = v.get('job_details', {})
            lnk = details.get('Web Address') or details.get('link')
            if lnk:
                applied_links.add(lnk)
        
        parked_jobs = self.db.load_parked()
        parked_links = {p.get('link') for p in parked_jobs if p.get('link')}
        
        blacklist = self.db.load_blacklist()
        bl_companies = [c.lower() for c in blacklist.get("companies", []) if c]
        bl_titles = [t.lower() for t in blacklist.get("titles", []) if t]
        safe_phrases = [s.lower() for s in blacklist.get("safe_phrases", []) if s]
        
        def log(msg):
            print(f"[LiveApply-Xing] {msg}")
            if callback:
                callback(msg)
        
        def is_blacklisted(title, company):
            t_lower = title.lower()
            c_lower = company.lower()
            
            for bl_c in bl_companies:
                if bl_c in c_lower:
                    return True, f"Company '{company}' is blacklisted"
            
            for bl_t in bl_titles:
                if bl_t in t_lower:
                    for safe in safe_phrases:
                        if safe in t_lower:
                            return False, None
                    return True, f"Title contains blacklisted term '{bl_t}'"
            
            return False, None
        
        # Navigate to Xing Jobs Search
        search_url = f"https://www.xing.com/jobs/search?keywords={keyword.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
        log(f"Navigating to: {search_url}")
        self.driver.get(search_url)
        self.random_sleep(4, 6)
        
        page = 0
        max_pages = 20
        
        while self.applied_count < target_count and page < max_pages:
            page += 1
            log(f"📄 Scanning page {page}...")
            
            # Find job cards
            try:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='job-posting-card'], .job-posting-card, a[data-testid='job-search-result']")
                log(f"Found {len(job_cards)} job cards")
            except:
                job_cards = []
            
            if not job_cards:
                log("No job cards found")
                break
            
            for idx, card in enumerate(job_cards):
                if self.applied_count >= target_count:
                    break
                
                results["checked"] += 1
                
                try:
                    # Get job URL from card
                    try:
                        link_el = card.find_element(By.CSS_SELECTOR, "a[href*='/jobs/']")
                        job_url = link_el.get_attribute("href")
                    except:
                        job_url = card.get_attribute("href")
                    
                    if not job_url:
                        continue
                    
                    # Navigate to job page
                    self.driver.get(job_url)
                    self.random_sleep(2, 3)
                    
                    current_url = self.driver.current_url
                    
                    # Extract title and company
                    try:
                        title_el = self.driver.find_element(By.CSS_SELECTOR, "h1, [data-testid='job-title']")
                        title = title_el.text.strip()
                    except:
                        title = "Unknown"
                    
                    try:
                        company_el = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='company-name'], .company-name, a[href*='/company/']")
                        company = company_el.text.strip()
                    except:
                        company = "Unknown"
                    
                    log(f"[{idx+1}/{len(job_cards)}] Checking: {title} @ {company}")
                    
                    # Check if already applied
                    if current_url in applied_links:
                        log(f"   ⏭️ Already applied - skipping")
                        results["skipped"].append({"title": title, "company": company, "reason": "Already applied"})
                        self.driver.get(search_url)
                        self.random_sleep(1, 2)
                        continue
                    
                    # Check if parked
                    if current_url in parked_links:
                        log(f"   ⏭️ In parked jobs - skipping")
                        results["skipped"].append({"title": title, "company": company, "reason": "Parked"})
                        self.driver.get(search_url)
                        self.random_sleep(1, 2)
                        continue
                    
                    # Check blacklist
                    is_blocked, reason = is_blacklisted(title, company)
                    if is_blocked:
                        log(f"   ⏭️ Blacklisted: {reason}")
                        results["skipped"].append({"title": title, "company": company, "reason": reason})
                        self.driver.get(search_url)
                        self.random_sleep(1, 2)
                        continue
                    
                    # Check if this is Easy Apply (no external redirect)
                    is_easy = self.is_easy_apply_xing(current_url)
                    
                    if not is_easy:
                        log(f"   ⏭️ Not Easy Apply - external application required")
                        results["skipped"].append({"title": title, "company": company, "reason": "Not Easy Apply"})
                        self.driver.get(search_url)
                        self.random_sleep(1, 2)
                        continue
                    
                    # Try to apply
                    log(f"   🎯 Attempting to apply...")
                    self.current_job_title = title
                    self.current_company = company
                    
                    success, message, _ = self.apply_xing(current_url, skip_detection=True)
                    
                    if success:
                        log(f"   ✅ Applied successfully!")
                        results["applied"].append({"title": title, "company": company, "url": current_url})
                        applied_links.add(current_url)
                        
                        jid = f"{title}-{company}"
                        job_data = {"Job Title": title, "Company": company, "Web Address": current_url, "Platform": "Xing"}
                        self.db.save_applied(jid, job_data, {"auto_applied": True})
                    else:
                        log(f"   ❌ Failed: {message}")
                        results["errors"].append({"title": title, "company": company, "error": message})
                    
                    # Navigate back
                    self.driver.get(search_url)
                    self.random_sleep(2, 3)
                    
                except Exception as e:
                    log(f"   ⚠️ Error processing card: {e}")
                    results["errors"].append({"error": str(e)})
                    self.driver.get(search_url)
                    self.random_sleep(1, 2)
                    continue
            
            # Next page
            if self.applied_count < target_count:
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Next'], a[rel='next'], [data-testid='pagination-next']")
                    next_btn.click()
                    self.random_sleep(3, 4)
                except:
                    log("No more pages")
                    break
        
        log(f"🏁 Xing Live Apply Complete! Applied: {len(results['applied'])} | Skipped: {len(results['skipped'])} | Errors: {len(results['errors'])}")
        return results
    
    def close(self):
        """Clean up browser."""
        self.bm.close_driver()

