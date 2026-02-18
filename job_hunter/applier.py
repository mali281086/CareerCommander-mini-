from tools.logger import logger, save_debug_artifact
import time
import random
import json
import urllib.parse
import os
import platform
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, ElementClickInterceptedException
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from tools.browser_manager import BrowserManager
from job_hunter.data_manager import DataManager
from job_hunter.mission_state import MissionProgress
from tools.human_actions import human_scroll, jitter_mouse, type_human_like, random_wait

class JobApplier:
    """Handles automated Easy Apply for LinkedIn and Xing."""
    
    # List of localized strings indicating a job has already been applied to
    APPLIED_INDICATORS = [
        "beworben", "candidature confirmée", "postulado",
        "bewerbung ansehen", "view application", "solicitud enviada",
        "già candidato", "aanmelding verzonden", "zaplikowano",
        "candidatado", "already applied", "du hast dich beworben",
        "application submitted", "candidature envoyée", "votre candidature a été envoyée",
        "solicitud confirmada", "candidatura inviata", "postulaste",
        "candidature transmise", "bewerbung gesendet",
        "candidatura inviata", "candidatura enviada", "status della candidatura",
        "sie haben sich beworben", "you applied", "application sent",
        "already applied", "you've applied", "you already applied",
        "applied on", "applied today", "applied yesterday", "applied 2 days ago",
        "bewerbung anzeigen", "view application", "candidatura inviata",
        "postulazione inviata", "candidatura apresentada",
        "status ihrer bewerbung", "application status", "bewerbung am",
        "applied on", "bewerbungsstatus", "bereits beworben", "candidature déjà envoyée",
        "you have submitted applications", "sie haben bewerbungen eingereicht"
    ]

    # List of localized strings indicating a job is no longer accepting applications
    EXPIRED_INDICATORS = [
        "no longer accepting applications",
        "job is closed",
        "this job is no longer available",
        "stelle ist nicht mehr verfügbar",
        "stellenangebot beendet",
        "akzeptiert keine bewerbungen mehr",
        "bewerbung nicht mehr möglich",
        "position filled",
        "besetzt",
        "nicht mehr aktiv",
        "expired",
        "abgelaufen",
        "geschlossen",
        "unavailable",
        "nicht verfügbar",
        "wir nehmen keine bewerbungen mehr an",
        "job has expired",
        "position closed",
        "closed"
    ]

    # CSS selectors for the LinkedIn Easy Apply modal dialog
    MODAL_SELECTORS = [
        ".jobs-easy-apply-modal",
        ".artdeco-modal",
        "div[role='dialog']",
        ".artdeco-modal-overlay .artdeco-modal",
        ".jobs-easy-apply-content",
        ".jpac-modal",
    ]
    MODAL_CSS = ", ".join(MODAL_SELECTORS)

    def __init__(self, resume_path=None, phone_number=None, profile_name="default"):
        self.bm = BrowserManager()
        self.profile_name = profile_name
        # self.driver removed - accessed via property to avoid stale reference
        self.resume_path = resume_path
        self.db = DataManager()  # For question-answer config

        # Pull phone from config if not provided
        if not phone_number:
            bot_config = self.db.load_bot_config()
            ans = bot_config.get("answers", {})
            phone_number = ans.get("mobile phone number") or ans.get("phone number") or ans.get("mobile number") or ""

        self.phone_number = phone_number
        self.applied_count = 0
        self.max_applications = 50  # Safety limit per session
        self.current_job_title = ""  # For logging unknown questions
        self.current_company = ""
        self.session_unknown_questions = []  # Track unknown questions for user prompt
        
    @property
    def driver(self):
        """Get current driver from BrowserManager to avoid stale references."""
        return self.bm.get_driver(headless=False, profile_name=self.profile_name)

    def random_sleep(self, min_sec=2, max_sec=5):
        time.sleep(random.uniform(min_sec, max_sec))
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type((StaleElementReferenceException, NoSuchElementException, ElementClickInterceptedException)),
        reraise=False
    )
    def click_element(self, selector, by=By.CSS_SELECTOR, timeout=5):
        """Wait for element and click it (with JS fallback)."""
        try:
            elem = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )
            elem.click()
            return True
        except Exception as e:
            # Fallback to JS Click
            try:
                elem = self.driver.find_element(by, selector)
                self.driver.execute_script("arguments[0].click();", elem)
                logger.debug(f"[Applier] JS Clicked: {selector}")
                return True
            except:
                logger.warning(f"[Applier] Failed to click: {selector}")
                return False
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(StaleElementReferenceException),
        reraise=False
    )
    def find_element_safe(self, selector, by=By.CSS_SELECTOR, timeout=5):
        """Find element without throwing exception."""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
        except:
            return None

    def handle_cookie_banners(self):
        """Attempts to click 'Accept' on common cookie banners to clear the view."""
        # Common "Accept" button selectors
        selectors = [
            "button[id='onetrust-accept-btn-handler']",
            "button#accept-all",
            "button.accept-all",
            "button[aria-label*='Accept all']",
            "button[aria-label*='Allow all']",
            "#allow-all",
            ".accept-cookies",
            "button[data-testid='uc-accept-all-button']", # Xing/Others
            "button#uc-btn-accept-banner",
        ]
        xpath_selectors = [
            "//button[contains(text(), 'Accept all')]",
            "//button[contains(text(), 'Allow all')]",
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Alle akzeptieren')]",
            "//button[contains(text(), 'Akzeptieren')]",
            "//button[contains(., 'Alles akzeptieren')]"
        ]

        # Fast check
        for sel in selectors:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed():
                    btn.click()
                    logger.info("[Applier] 🍪 Cookie banner handled (CSS)")
                    return True
            except: pass

        for xpath in xpath_selectors:
            try:
                btn = self.driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    btn.click()
                    logger.info("[Applier] 🍪 Cookie banner handled (XPath)")
                    return True
            except: pass
        return False
    
    # ==========================================
    # DETECTION METHODS
    # ==========================================
    def _is_applied_check(self, text=None):
        """Internal helper for robust applied status detection."""
        import re
        if text is None:
            # Check a larger chunk of the page source for modern SPAs
            # LinkedIn pages have large nav/script/ad blocks before job content
            text = self.driver.page_source[:30000].lower()
        else:
            text = text.lower()

        for indicator in self.APPLIED_INDICATORS:
            # Use regex to match as whole words or specific phrases
            pattern = r'\b' + re.escape(indicator) + r'\b'
            if re.search(pattern, text):
                return True, indicator

        # Also check for specific status badges by CSS (LinkedIn, Xing, Indeed)
        status_selectors = [
            ".artdeco-inline-feedback--success",
            ".jobs-s-apply__application-link",
            ".jobs-applied-badge",
            ".hiring-badge--success",
            ".jobs-details__applied-date",
            ".jobs-details-top-card__applied-date",
            ".jobs-company__box .artdeco-inline-feedback",
            ".jobsearch-AlreadyApplied-badge", # Indeed
            "[data-testid='applied-status-bar']", # Xing
            ".x-applied-badge"
        ]
        for sel in status_selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed() and len(el.text.strip()) > 0:
                    return True, f"CSS:{sel}"
            except: pass

        return False, None

    def _is_expired_check(self, text=None):
        """Internal helper to detect if a job is no longer accepting applications."""
        import re
        if text is None:
            # Match the larger scan range used in _is_applied_check
            text = self.driver.page_source[:30000].lower()
        else:
            text = text.lower()

        for indicator in self.EXPIRED_INDICATORS:
            pattern = r'\b' + re.escape(indicator) + r'\b'
            if re.search(pattern, text):
                return True, indicator

        # Check for expired/closed badges by CSS
        expired_selectors = [
            ".artdeco-inline-feedback--error", # Often used for "no longer accepting"
            ".jobs-details__closed-message",
            ".jobsearch-JobComponent-closedMessage", # Indeed
            "[data-testid='closed-message']", # Xing
        ]
        for sel in expired_selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed() and len(el.text.strip()) > 0:
                    # Check if text in the element actually means expired
                    el_text = el.text.lower()
                    if any(ind in el_text for ind in self.EXPIRED_INDICATORS):
                        return True, f"CSS:{sel}"
            except: pass

        return False, None

    def is_easy_apply_linkedin(self, job_url=None):
        """Check if a LinkedIn job has Easy Apply button."""
        if job_url:
            logger.info(f"[LinkedIn] Checking Easy Apply: {job_url}")
            self.driver.get(job_url)
            self.random_sleep(4, 7)  # Wait longer for page to load

        # 1. Check for "Already Applied" or "Expired"
        is_applied, applied_ind = self._is_applied_check()
        if is_applied:
            logger.info(f"[LinkedIn] ⏭️ Job already applied (detected via {applied_ind}).")
            return False

        is_expired, expired_ind = self._is_expired_check()
        if is_expired:
            logger.info(f"[LinkedIn] ⏭️ Job expired/closed (detected via {expired_ind}).")
            return False

        # 2. Find Easy Apply Button
        # Prioritize buttons in the detail area to avoid clicking sidebar jobs
        detail_areas = [
            ".jobs-search__job-details",
            ".scaffold-layout__detail",
            ".jobs-details-jobs-unified-top-card",
            ".jobs-unified-top-card",
            ".jobs-details__main-content",
            ".jobs-details",
            ".job-view-layout",
            "main#main"
        ]

        # Extensive list of selectors for the button itself (Include <a> tags)
        btn_selectors = [
            "button.jobs-apply-button",
            "a.jobs-apply-button",
            "button[aria-label*='Easy Apply']",
            "a[aria-label*='Easy Apply']",
            "button[aria-label*='Einfach bewerben']",
            "button[aria-label*='Einfach Bewerbung']",
            "button[aria-label*='Einfach-Bewerbung']",
            "button[aria-label*='Schnellbewerbung']",
            "button[aria-label*='Simple candidature']",
            "a[aria-label*='Einfach bewerben']",
            "a[aria-label*='Einfach Bewerbung']",
            "a[aria-label*='Einfach-Bewerbung']",
            ".jobs-apply-button--top-card button",
            ".jobs-apply-button--top-card a",
            "button.artdeco-button--primary", # Last resort
            "a.artdeco-button--primary",
        ]
        
        for area in detail_areas:
            try:
                detail_el = self.driver.find_element(By.CSS_SELECTOR, area)
                if not detail_el.is_displayed(): continue
                for sel in btn_selectors:
                    try:
                        btns = detail_el.find_elements(By.CSS_SELECTOR, sel)
                        for btn in btns:
                            if btn.is_displayed():
                                btn_text = btn.text.lower()
                                aria = (btn.get_attribute("aria-label") or "").lower()
                                apply_keywords = ["easy", "apply", "bewerben", "bewerbung", "candidature", "schnellbewerbung"]
                                if any(k in btn_text or k in aria for k in apply_keywords):
                                    if not any(k in btn_text for k in ["website", "extern", "employer", "company site"]):
                                        logger.info(f"[LinkedIn] ✓ Easy Apply detected in {area}")
                                        return True
                    except: continue
            except: continue

        # Global Fallback
        combined = ", ".join(btn_selectors)
        try:
            btns = self.driver.find_elements(By.CSS_SELECTOR, combined)
            for btn in btns:
                if btn.is_displayed():
                    btn_text = btn.text.lower()
                    aria = (btn.get_attribute("aria-label") or "").lower()
                    apply_keywords = ["easy", "apply", "bewerben", "bewerbung", "candidature", "schnellbewerbung"]
                    if any(k in btn_text or k in aria for k in apply_keywords):
                        if not any(k in btn_text for k in ["website", "extern", "employer", "company site"]):
                            logger.info(f"[LinkedIn] ✓ Easy Apply detected via Global Fallback")
                            return True
        except: pass

        logger.info("[LinkedIn] ✗ Not Easy Apply (external apply required)")
        return False
    
    def is_easy_apply_xing(self, job_url=None):
        """Check if a Xing job has Easy Apply (not external redirect)."""
        if job_url:
            logger.info(f"[Xing] Checking Easy Apply: {job_url}")
            self.driver.get(job_url)
            self.random_sleep(2, 4)
        
        # 1. Check for Already Applied or Expired
        is_applied, applied_ind = self._is_applied_check()
        if is_applied:
            logger.info(f"[Xing] ⏭️ Already applied (detected via {applied_ind})")
            return False

        is_expired, expired_ind = self._is_expired_check()
        if is_expired:
            logger.info(f"[Xing] ⏭️ Job expired/closed (detected via {expired_ind}).")
            return False

        # Keywords that indicate EASY APPLY (internal application)
        easy_apply_keywords = [
            "schnellbewerbung",  # German: Quick Apply
            "easy apply",
            "direkt bewerben",   # German: Apply Directly
            "jetzt bewerben",    # German: Apply Now (on Xing's internal system)
            "bewerben",          # Generic apply
            "bewerbung absenden",
            "lebenslauf senden",
            "auf xing bewerben",
            "apply on xing",
            "einfach bewerben",
            "einfach bewerbung"
        ]
        
        # Keywords that indicate EXTERNAL APPLY (should skip)
        external_keywords = [
            "visit employer",
            "visit employer website",
            "zur arbeitgeber",   # German: To Employer
            "external",
            "website",
            "karriereseite",     # German: Career Site
            "zur bewerbung beim arbeitgeber",
            "apply on company site",
            "auf der seite des arbeitgebers bewerben",
            "arbeitgeber-website",
            "offsite",
            "extern"
        ]
        
        # Look for apply buttons and check their text
        apply_selectors = [
            "button[data-testid='apply-button']",
            "a[data-testid='apply-button']",
            "button.apply-button",
            "a.apply-button",
            "[data-testid='apply-button']",
            "button[data-testid='nls-apply-button']",
        ]
        
        for selector in apply_selectors:
            btn = self.find_element_safe(selector, timeout=3)
            if btn:
                btn_text = btn.text.lower().strip()
                logger.info(f"[Xing] Found button with text: '{btn_text}'")
                
                # Check if it's EXTERNAL (should reject)
                if any(ext in btn_text for ext in external_keywords):
                    logger.info("[Xing] ✗ External apply detected - skipping")
                    return False
                
                # Check if it's EASY APPLY
                if any(easy in btn_text for easy in easy_apply_keywords):
                    logger.info("[Xing] ✓ Easy Apply detected!")
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
                        logger.info(f"[Xing] ✓ Easy Apply detected via XPath: '{btn_text}'")
                        return True
                except:
                    continue
        except:
            pass
        
        logger.info("[Xing] ✗ Not Easy Apply (external or no apply button found)")
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
        
        # 1. Navigation & Sanitization
        if "currentJobId=" in job_url:
            import urllib.parse as urlparse
            try:
                parsed = urlparse.urlparse(job_url)
                params = urlparse.parse_qs(parsed.query)
                job_id = params.get('currentJobId', [None])[0]
                if job_id: job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
            except: pass

        logger.info(f"[LinkedIn] Navigating to: {job_url}")
        self.driver.get(job_url)
        self.random_sleep(6, 9) # Give it plenty of time to load and redirect
        self.handle_cookie_banners()

        # 2. Check for "Already Applied" or "Expired"
        is_applied, applied_ind = self._is_applied_check()
        if is_applied:
            logger.info(f"[LinkedIn] ⏭️ Job already applied (detected via {applied_ind}).")
            return True, "Already applied.", True

        is_expired, expired_ind = self._is_expired_check()
        if is_expired:
            logger.info(f"[LinkedIn] ⏭️ Job expired/closed (detected via {expired_ind}).")
            return False, "Job expired or no longer accepting applications.", False

        # 3. Detection step (unless skipped)
        if not skip_detection:
            is_easy = self.is_easy_apply_linkedin()
            if not is_easy:
                # Re-check: is_easy_apply_linkedin returns False for applied/expired too
                is_applied, _ = self._is_applied_check()
                if is_applied:
                    return True, "Already applied.", True
                is_expired, _ = self._is_expired_check()
                if is_expired:
                    return False, "Job expired or no longer accepting applications.", False
                return False, "Not an Easy Apply job. Skipped.", False
            
        # 0. Clear Overlays
        self.handle_cookie_banners()
        
        # 1. Find and Click "Easy Apply" Button
        # Prioritize buttons in the detail area to avoid clicking sidebar jobs
        detail_areas = [
            ".jobs-search__job-details",
            ".scaffold-layout__detail",
            ".jobs-details-jobs-unified-top-card",
            ".jobs-unified-top-card",
            ".jobs-details__main-content",
            ".jobs-details", # Standalone page container
            ".job-view-layout",
            "main#main"
        ]

        # Extensive list of selectors for the button itself
        btn_selectors = [
            "button.jobs-apply-button",
            "a.jobs-apply-button",
            "button[aria-label*='Easy Apply']",
            "a[aria-label*='Easy Apply']",
            "button[aria-label*='Einfach bewerben']", 
            "button[aria-label*='Einfach Bewerbung']",
            "button[aria-label*='Einfach-Bewerbung']",
            "button[aria-label*='Schnellbewerbung']",
            "button[aria-label*='Simple candidature']",
            "a[aria-label*='Einfach bewerben']",
            "a[aria-label*='Einfach Bewerbung']",
            "a[aria-label*='Einfach-Bewerbung']",
            ".jobs-apply-button--top-card button",
            ".jobs-apply-button--top-card a",
            "button.artdeco-button--primary", # Last resort
            "a.artdeco-button--primary",
        ]
        
        clicked = False
        
        # Strategy A: Try to find the button INSIDE the detail area first
        for area in detail_areas:
            try:
                detail_el = self.driver.find_element(By.CSS_SELECTOR, area)
                if not detail_el.is_displayed(): continue

                for sel in btn_selectors:
                    try:
                        btns = detail_el.find_elements(By.CSS_SELECTOR, sel)
                        for btn in btns:
                            if btn.is_displayed():
                                # Check text to avoid "Visit Website" / External apply
                                btn_text = btn.text.lower()
                                aria = (btn.get_attribute("aria-label") or "").lower()

                                apply_keywords = ["easy", "apply", "bewerben", "bewerbung", "candidature", "schnellbewerbung", "einfach"]
                                external_keywords = ["website", "arbeitgeber", "extern", "offsite", "company site", "anwenden"]

                                if any(k in btn_text or k in aria for k in apply_keywords):
                                    if not any(k in btn_text for k in external_keywords):
                                        # Scroll into view before clicking
                                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                        self.random_sleep(0.5, 1.0)
                                        try: btn.click()
                                        except: self.driver.execute_script("arguments[0].click();", btn)
                                        clicked = True
                                        logger.info(f"[LinkedIn] Clicked Easy Apply in Detail Area ({area}) -> {sel}")
                                        break
                        if clicked: break
                    except: continue
                if clicked: break
            except: continue

        # Strategy B: Global CSS fallback
        if not clicked:
            combined = ", ".join(btn_selectors)
            try:
                btns = self.driver.find_elements(By.CSS_SELECTOR, combined)
                for btn in btns:
                    if btn.is_displayed():
                        btn_text = btn.text.lower()
                        aria = (btn.get_attribute("aria-label") or "").lower()
                        if any(k in btn_text or k in aria for k in ["easy", "apply", "bewerben", "bewerbung", "schnellbewerbung", "einfach"]):
                            if not any(k in btn_text for k in ["website", "extern", "employer", "company site"]):
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                self.random_sleep(0.5, 1.0)
                                try: btn.click()
                                except: self.driver.execute_script("arguments[0].click();", btn)
                                clicked = True
                                logger.info(f"[LinkedIn] Clicked Easy Apply via Global CSS")
                                break
            except: pass

        # Strategy C: XPath fallback
        if not clicked:
            lc = "'abcdefghijklmnopqrstuvwxyzäöü'"
            uc = "'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ'"
            xpath_queries = [
                f"//button[contains(translate(., {uc}, {lc}), 'easy apply')]",
                f"//button[contains(translate(., {uc}, {lc}), 'einfach bewerben')]",
                f"//button[contains(translate(., {uc}, {lc}), 'einfach bewerbung')]",
                f"//button[contains(translate(., {uc}, {lc}), 'einfach-bewerbung')]",
                f"//button[contains(translate(., {uc}, {lc}), 'schnellbewerbung')]"
            ]
            
            for xpath in xpath_queries:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    if btn and btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        clicked = True
                        logger.info(f"[LinkedIn] Clicked Easy Apply via XPath: {xpath}")
                        break
                except: pass
        
        if not clicked:
            # Fallback: Re-check if job is applied/expired with FULL page source
            # This catches cases where even 30K chars wasn't enough for initial detection
            full_text = self.driver.page_source.lower()
            is_applied, applied_ind = self._is_applied_check(text=full_text)
            if is_applied:
                logger.info(f"[LinkedIn] ⏭️ Job already applied (late detection via {applied_ind}).")
                return True, "Already applied.", True
            is_expired, expired_ind = self._is_expired_check(text=full_text)
            if is_expired:
                logger.info(f"[LinkedIn] ⏭️ Job expired (late detection via {expired_ind}).")
                return False, "Job expired or no longer accepting applications.", False
            logger.info("[LinkedIn] ❌ Easy Apply button not found (Selectors + XPath failed).")
            return False, "Easy Apply button not found. May require external apply.", False
        
        # Wait briefly for modal to appear (animation)
        time.sleep(3)
        
        # 2. Process the Modal Steps (Unified Logic - Button Driven)
        success = self._process_linkedin_modal()
        
        if success:
            self.applied_count += 1
            return True, "Application submitted successfully!", True
        else:
            return False, "Failed to complete application modal or dismissed due to errors.", True
    
    def _linkedin_fill_fields(self):
        """Fill common fields in LinkedIn Easy Apply modal with smart question detection."""
        
        # 1. Phone Number
        phone_input = self.find_element_safe("input[id*='phoneNumber'], input[name*='phone']", timeout=2)
        if phone_input and not phone_input.get_attribute("value"):
            phone_input.clear()
            phone_input.send_keys(self.phone_number)
            logger.info("[LinkedIn] Filled phone number.")
        
        # 2. Resume Upload
        if self.resume_path:
            file_input = self.find_element_safe("input[type='file']", timeout=2)
            if file_input:
                try:
                    file_input.send_keys(self.resume_path)
                    logger.info("[LinkedIn] Uploaded resume.")
                except Exception as e:
                    logger.info(f"[LinkedIn] Resume upload failed: {e}")
        
        # 3. Handle TEXT INPUTS and COMBOBOXES with labels
        try:
            form_groups = self.driver.find_elements(By.CSS_SELECTOR, ".fb-dash-form-element, .jobs-easy-apply-form-section__grouping, .jobs-easy-apply-form-element, .jobs-easy-apply-form-section__group")
            for group in form_groups:
                try:
                    # Find label
                    label_selectors = [
                        "label",
                        ".fb-dash-form-element__label",
                        "span.t-bold",
                        ".jobs-easy-apply-form-element__label",
                        "p.artdeco-text-input__label",
                        "[data-test-form-element-label]",
                        "span[aria-hidden='true']",
                        "h3"
                    ]
                    label_el = None
                    for sel in label_selectors:
                        try:
                            labels = group.find_elements(By.CSS_SELECTOR, sel)
                            for l in labels:
                                if l.is_displayed() and l.text.strip():
                                    label_el = l
                                    break
                            if label_el: break
                        except: continue

                    if not label_el:
                        continue

                    label_text = label_el.text.strip()
                    
                    if not label_text or len(label_text) < 2:
                        continue
                    
                    # Find input or combobox
                    input_el = None
                    try:
                        input_el = group.find_element(By.CSS_SELECTOR, "input[type='text'], input[type='number'], input[type='tel'], input:not([type='file']):not([type='radio']):not([type='checkbox']), [role='combobox'] input")
                    except:
                        try: input_el = group.find_element(By.TAG_NAME, "textarea")
                        except: pass
                    
                    if not input_el: continue

                    # Skip if already filled (but check if it's just a default placeholder)
                    current_val = input_el.get_attribute("value")
                    if current_val and len(current_val.strip()) > 0:
                        # Optional: Allow overwriting if it matches a "Select" or "Choose" pattern
                        if not any(x in current_val.lower() for x in ["select", "choose", "auswählen"]):
                            continue
                    
                    # Try to get answer from config
                    answer = self.db.get_answer_for_question(label_text)
                    
                    # Fallback: Check placeholder
                    if answer is None:
                        placeholder = input_el.get_attribute("placeholder")
                        if placeholder:
                            answer = self.db.get_answer_for_question(placeholder)

                    if answer is not None and answer != "":
                        # Clear and type
                        try:
                            input_el.clear()
                        except:
                            # If clear fails, try select all + backspace
                            from selenium.webdriver.common.keys import Keys
                            input_el.send_keys(Keys.CONTROL + "a")
                            input_el.send_keys(Keys.BACKSPACE)

                        type_human_like(input_el, answer)
                        logger.info(f"[LinkedIn] Answered '{label_text}' → '{answer}'")

                        # Handle LinkedIn's typeahead/combobox (e.g. City/Location)
                        # These fields require selecting an option from the dropdown even if text is correct
                        try:
                            # Short sleep to let dropdown appear
                            self.random_sleep(0.5, 1.0)

                            # Check if input is likely a combobox
                            role = input_el.get_attribute("role")
                            autocomplete = input_el.get_attribute("aria-autocomplete")
                            is_typeahead = role == "combobox" or autocomplete == "list" or \
                                           "city" in label_text.lower() or "location" in label_text.lower()

                            if is_typeahead:
                                # Try multiple selectors for the first option in the dropdown
                                suggestion_selectors = [
                                    ".artdeco-typeahead__result",
                                    ".artdeco-typeahead__results-list li",
                                    "[role='option']",
                                    ".basic-typeahead__result"
                                ]

                                for sug_sel in suggestion_selectors:
                                    try:
                                        # Use driver.find_elements to avoid waiting too long if not present
                                        options = self.driver.find_elements(By.CSS_SELECTOR, sug_sel)
                                        found = False
                                        for opt in options:
                                            if opt.is_displayed():
                                                # Try clicking directly, then with JS
                                                try: opt.click()
                                                except: self.driver.execute_script("arguments[0].click();", opt)
                                                logger.info(f"[LinkedIn] ✅ Selected dropdown option for '{label_text}'")
                                                found = True
                                                break
                                        if found: break
                                    except:
                                        continue
                        except:
                            pass
                    else:
                        # Handle common questions with safe defaults
                        label_lower = label_text.lower()
                        default_answer = None
                        
                        # Questions that can be answered with N/A or empty
                        skip_questions = [
                            "website", "webseite", "personal website", "portfolio",
                            "linkedin profile", "linkedin",
                            "employee's name", "mitarbeitername", "employee name", "referral",
                            "referred by", "empfehlung", "wer hat sie empfohlen", "who referred"
                        ]
                        
                        for skip_q in skip_questions:
                            if skip_q in label_lower:
                                default_answer = "N/A"
                                break
                        
                        if default_answer:
                            input_el.clear()
                            input_el.send_keys(default_answer)
                            logger.info(f"[LinkedIn] Filled '{label_text}' → '{default_answer}' (default)")

                            # Also handle typeahead for default answers
                            try:
                                self.random_sleep(0.5, 1.0)
                                if "city" in label_text.lower() or "location" in label_text.lower():
                                    options = self.driver.find_elements(By.CSS_SELECTOR, ".artdeco-typeahead__result, [role='option'], .artdeco-typeahead__results-list li")
                                    for opt in options:
                                        if opt.is_displayed():
                                            try: opt.click()
                                            except: self.driver.execute_script("arguments[0].click();", opt)
                                            logger.info(f"[LinkedIn] ✅ Selected dropdown option for default '{label_text}'")
                                            break
                            except:
                                pass
                        else:
                            # Interactive mode: Alert user and wait for them to fill the field
                            logger.info(f"[LinkedIn] 🔔 UNKNOWN QUESTION: '{label_text}'")

                            # Update global mission status
                            progress = MissionProgress.load()
                            if progress.is_active:
                                progress.update(pending_question=label_text)
                            logger.info(f"[LinkedIn] ⏳ Please fill this field on LinkedIn. Bot will capture your answer...")
                            
                            # Interactive mode: Alert user and wait for them to fill the field
                            logger.info(f"[LinkedIn] 🔔 UNKNOWN QUESTION: '{label_text}'")
                            
                            # 1. Beep
                            try:
                                if platform.system() == "Windows":
                                    import winsound
                                    winsound.Beep(1000, 1000)
                                else:
                                    logger.info('\a') # Terminal beep
                            except: pass
                            
                            # 2. Log to file
                            try:
                                q_file = "unanswered_questions.json"
                                if not os.path.exists(q_file):
                                    with open(q_file, "w", encoding="utf-8") as f: json.dump([], f)
                                
                                with open(q_file, "r", encoding="utf-8") as f:
                                    qs = json.load(f)
                                
                                if label_text not in qs:
                                    qs.append(label_text)
                                    with open(q_file, "w", encoding="utf-8") as f:
                                        json.dump(qs, f, indent=2, ensure_ascii=False)
                            except Exception as e:
                                logger.info(f"Failed to log question: {e}")

                            # Inject a highly visible prompt and beep logic into the browser
                            try:
                                self.driver.execute_script(f"""
                                    (function() {{
                                        // 1. Create Audio context and beep function
                                        var context = new (window.AudioContext || window.webkitAudioContext)();
                                        function beep() {{
                                            var osc = context.createOscillator();
                                            var gain = context.createGain();
                                            osc.type = 'sine';
                                            osc.frequency.setValueAtTime(880, context.currentTime);
                                            gain.gain.setValueAtTime(0.5, context.currentTime);
                                            osc.connect(gain);
                                            gain.connect(context.destination);
                                            osc.start();
                                            osc.stop(context.currentTime + 0.3);
                                        }}

                                        // 2. Initial attempt to beep
                                        if (context.state === 'suspended') {{
                                            console.log('Audio suspended, waiting for interaction');
                                        }} else {{
                                            beep();
                                        }}

                                        // 3. Create Overlay
                                        var msg = document.getElementById('bot-prompt-overlay');
                                        if (!msg) {{
                                            msg = document.createElement('div');
                                            msg.id = 'bot-prompt-overlay';
                                            document.body.appendChild(msg);
                                        }}

                                        msg.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,0,0,0.3); border: 10px solid #ff4b4b; z-index: 10000; pointer-events: none; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; text-shadow: 2px 2px 4px black; font-family: sans-serif;';

                                        msg.innerHTML = `
                                            <div style="background: #262730; padding: 30px; border-radius: 15px; border: 3px solid #ff4b4b; pointer-events: auto; text-align: center; max-width: 80%;">
                                                <h1 style="margin: 0 0 15px 0; color: #ff4b4b;">🤖 ACTION REQUIRED</h1>
                                                <p style="font-size: 20px; margin-bottom: 20px;">The bot encountered a question it cannot answer:</p>
                                                <div style="background: #1e1e1e; padding: 15px; border-radius: 8px; font-size: 24px; color: yellow; margin-bottom: 25px; border: 1px solid #444;">
                                                    ${{JSON.stringify(label_text)}}
                                                </div>
                                                <p style="font-size: 18px;">Please <b>type your answer</b> in the LinkedIn field below.</p>
                                                <button id="bot-beep-btn" style="background: #ff4b4b; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 16px; margin-top: 10px;">🔊 Test Sound</button>
                                            </div>
                                        `;

                                        document.getElementById('bot-beep-btn').onclick = function() {{
                                            context.resume().then(() => beep());
                                        }};

                                        // 4. Repeated beep every 5 seconds until removed
                                        var beepInterval = setInterval(function() {{
                                            if (document.getElementById('bot-prompt-overlay')) {{
                                                if (context.state !== 'suspended') beep();
                                            }} else {{
                                                clearInterval(beepInterval);
                                            }}
                                        }}, 5000);
                                    }})();
                                """)
                            except: pass

                            # Also try terminal beep as fallback
                            logger.info('\a')
                            
                            # Wait for user to fill the field (poll every 2 seconds, max 120 seconds for user comfort)
                            max_wait = 120
                            poll_interval = 2
                            waited = 0
                            user_answer = None
                            
                            while waited < max_wait:
                                try:
                                    current_value = input_el.get_attribute("value")
                                    if current_value and current_value.strip():
                                        user_answer = current_value.strip()
                                        logger.info(f"[LinkedIn] ✅ Captured answer: '{user_answer}'")
                                        
                                        # Save to Q&A config automatically
                                        self.db.save_qa_answer(label_text, user_answer)
                                        logger.info(f"[LinkedIn] 💾 Saved Q&A: '{label_text}' → '{user_answer}'")

                                        # Clear pending question in state
                                        progress = MissionProgress.load()
                                        if progress.is_active:
                                            progress.update(pending_question=None)

                                        # Remove overlay
                                        try: self.driver.execute_script("var el = document.getElementById('bot-prompt-overlay'); if(el) el.remove();")
                                        except: pass
                                        break
                                except StaleElementReferenceException:
                                    break  # Element gone, page changed
                                except:
                                    pass
                                
                                time.sleep(poll_interval)
                                waited += poll_interval
                            
                            if not user_answer:
                                # Remove overlay
                                try: self.driver.execute_script("var el = document.getElementById('bot-prompt-overlay'); if(el) el.remove();")
                                except: pass
                                logger.info(f"[LinkedIn] ⚠️ No answer provided, logging as unknown...")
                                self.db.log_unknown_question(label_text, self.current_job_title, self.current_company)
                                q_entry = {"question": label_text, "type": "text", "job": self.current_job_title}
                                if q_entry not in self.session_unknown_questions:
                                    self.session_unknown_questions.append(q_entry)
                except:
                    continue
        except:
            pass
        
        # 4. Handle DROPDOWNS / SELECT elements
        try:
            selects = self.driver.find_elements(By.CSS_SELECTOR, "select")
            for select in selects:
                try:
                    # Check if already has a valid selection
                    from selenium.webdriver.support.ui import Select
                    sel_obj = Select(select)
                    current_selected = sel_obj.first_selected_option.text.strip()
                    if current_selected and current_selected.lower() not in ["", "select", "auswählen", "bitte wählen", "please select", "--"]:
                        continue  # Already has a valid selection
                    
                    # Try multiple patterns to find the label
                    label_text = ""
                    try:
                        # Pattern 1: label element with for attribute
                        select_id = select.get_attribute("id")
                        if select_id:
                            label_el = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{select_id}']")
                            label_text = label_el.text.strip()
                    except:
                        pass
                    
                    if not label_text:
                        try:
                            # Pattern 2: label in parent div
                            parent = select.find_element(By.XPATH, "./ancestor::div[1]")
                            label_el = parent.find_element(By.CSS_SELECTOR, "label, legend, span.t-bold, .fb-dash-form-element__label, .jobs-easy-apply-form-element__label")
                            label_text = label_el.text.strip()
                        except:
                            pass
                    
                    if not label_text:
                        try:
                            # Pattern 3: preceding sibling text
                            label_el = select.find_element(By.XPATH, "./preceding-sibling::label | ./preceding::label[1]")
                            label_text = label_el.text.strip()
                        except:
                            label_text = "dropdown"
                    
                    logger.info(f"[LinkedIn] Dropdown found: '{label_text}'")
                    
                    # Get answer from config
                    answer = self.db.get_answer_for_question(label_text)
                    
                    # Find options
                    options = select.find_elements(By.TAG_NAME, "option")
                    if len(options) <= 1:
                        continue
                    
                    # If we have a configured answer, try to match
                    if answer:
                        matched = False
                        for opt in options:
                            if answer.lower() in opt.text.lower():
                                sel_obj.select_by_visible_text(opt.text)
                                logger.info(f"[LinkedIn] ✅ Selected saved answer '{opt.text}' for '{label_text}'")
                                matched = True
                                break
                        if matched:
                            continue
                    
                    # No saved answer - use smart selection and log the question
                    logger.info(f"[LinkedIn] ⚠️ No saved answer for: '{label_text}', using smart selection...")
                    self.db.log_unknown_question(label_text, self.current_job_title, self.current_company)
                    
                    # Smart selection: prefer higher values, avoid "Gar nicht", "Keine", "0"
                    negative_terms = ['gar nicht', 'keine', 'kein', 'nicht', 'nein', 'überhaupt nicht', 'never', 'none', 'not at all', '0 ', 'nein']
                    prefer_terms = ['5+', '10+', '3+', '4+', 'more than', 'über', 'ja', 'yes', 'expert', 'erfahren', 'native', 'muttersprache', 'fließend', 'bilingual', 'immer', 'always', 'einverstanden', 'bereit']
                    
                    selected = False
                    # First try to find a preferred option
                    for opt in options[1:]:
                        opt_text = opt.text.lower().strip()
                        if any(p in opt_text for p in prefer_terms):
                            sel_obj.select_by_visible_text(opt.text)
                            logger.info(f"[LinkedIn] Selected preferred '{opt.text}' for dropdown")
                            selected = True
                            break
                    
                    # If no preferred, select last non-negative option (usually highest value)
                    if not selected:
                        for opt in reversed(list(options[1:])):  # Reverse to get highest first
                            opt_text = opt.text.lower().strip()
                            if opt_text and not any(n in opt_text for n in negative_terms):
                                sel_obj.select_by_visible_text(opt.text)
                                logger.info(f"[LinkedIn] Selected '{opt.text}' for dropdown (highest)")
                                selected = True
                                break
                    
                    # Fallback: just select first if nothing else worked
                    if not selected and len(options) > 1:
                        sel_obj.select_by_index(1)
                        logger.info(f"[LinkedIn] Selected fallback '{options[1].text}' for dropdown")
                except Exception as e:
                    logger.info(f"[LinkedIn] Dropdown error: {str(e)[:50]}")
                    continue
        except:
            pass
        
        # 5. Handle RADIO BUTTONS and BUTTON GROUPS with smart Yes/No matching
        try:
            # Look for fieldsets or groups with radio role
            radio_groups = self.driver.find_elements(By.CSS_SELECTOR, "fieldset, [role='radiogroup'], .fb-dash-form-element")
            for group in radio_groups:
                try:
                    # Get the question/legend
                    legend = None
                    legend_selectors = ["legend", "span.t-bold", ".fb-dash-form-element__label", ".jobs-easy-apply-form-element__label"]
                    for sel in legend_selectors:
                        try:
                            legend = group.find_element(By.CSS_SELECTOR, sel)
                            if legend and legend.text.strip():
                                break
                        except: continue
                    
                    question_text = legend.text.strip() if legend else ""
                    if not question_text:
                        continue

                    # Get configured answer
                    answer = self.db.get_answer_for_question(question_text)
                    
                    # 5a. Try actual radio inputs
                    radios = group.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                    if radios:
                        # Check if any radio is already selected
                        if any(r.is_selected() for r in radios):
                            continue

                        options_found = False
                        if answer:
                            for radio in radios:
                                try:
                                    label_el = radio.find_element(By.XPATH, "./following-sibling::label | ../label")
                                    if answer.lower() in label_el.text.lower():
                                        self.driver.execute_script("arguments[0].click();", radio)
                                        logger.info(f"[LinkedIn] Selected '{label_el.text}' for '{question_text}'")
                                        options_found = True
                                        break
                                except: continue

                        if not options_found:
                            # Smart selection: prefer "Ja/Yes" over "Nein/No"
                            yes_labels = ['ja', 'yes', 'agree', 'willing', 'immer', 'einverstanden', 'bereit', 'zustimmen', 'verstanden']
                            for radio in radios:
                                try:
                                    label_el = radio.find_element(By.XPATH, "./following-sibling::label | ../label")
                                    if any(y in label_el.text.lower() for y in yes_labels):
                                        self.driver.execute_script("arguments[0].click();", radio)
                                        logger.info(f"[LinkedIn] Selected 'Yes' option for '{question_text}'")
                                        options_found = True
                                        break
                                except: continue

                            if not options_found:
                                # Fallback to first option
                                self.driver.execute_script("arguments[0].click();", radios[0])
                                logger.info(f"[LinkedIn] Auto-selected first option for '{question_text}'")
                                self.db.log_unknown_question(question_text, self.current_job_title, self.current_company)
                        continue # Done with this group

                    # 5b. Try Button Groups (often used for Yes/No)
                    buttons = group.find_elements(By.CSS_SELECTOR, "button")
                    if buttons and len(buttons) >= 2:
                        # Check if any is already 'selected' (often indicated by class or aria-pressed)
                        if any("active" in b.get_attribute("class").lower() or b.get_attribute("aria-pressed") == "true" for b in buttons):
                            continue

                        btn_clicked = False
                        if answer:
                            for btn in buttons:
                                if answer.lower() in btn.text.lower():
                                    btn.click()
                                    logger.info(f"[LinkedIn] Clicked button '{btn.text}' for '{question_text}'")
                                    btn_clicked = True
                                    break
                        
                        if not btn_clicked:
                            yes_labels = ['ja', 'yes', 'agree', 'willing', 'immer', 'einverstanden', 'bereit', 'zustimmen', 'verstanden']
                            for btn in buttons:
                                if any(y in btn.text.lower() for y in yes_labels):
                                    btn.click()
                                    logger.info(f"[LinkedIn] Clicked 'Yes' button for '{question_text}'")
                                    btn_clicked = True
                                    break

                            if not btn_clicked:
                                buttons[0].click()
                                logger.info(f"[LinkedIn] Clicked first button for '{question_text}'")
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
                    # Check if it's a required/consent field
                    parent = cb.find_element(By.XPATH, "./..")
                    label_text = parent.text.lower()
                    
                    # Auto-check consent boxes
                    if any(t in label_text for t in ["agree", "terms", "consent", "einwillig", "zustimm", "akzeptier"]):
                        self.driver.execute_script("arguments[0].click();", cb)
                        logger.info("[LinkedIn] Checked consent checkbox")
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
        
        # 1. Navigation
        logger.info(f"[Xing] Navigating to: {job_url}")
        self.driver.get(job_url)
        self.random_sleep(4, 7)

        # 2. Check for Already Applied or Expired
        is_applied, applied_ind = self._is_applied_check()
        if is_applied:
            logger.info(f"[Xing] ⏭️ Already applied (detected via {applied_ind})")
            return True, "Already applied.", True

        is_expired, expired_ind = self._is_expired_check()
        if is_expired:
            logger.info(f"[Xing] ⏭️ Job expired/closed (detected via {expired_ind}).")
            return False, "Job expired or no longer accepting applications.", False

        # 3. Detection step (unless skipped)
        if not skip_detection:
            is_easy = self.is_easy_apply_xing() # No URL means no re-navigation
            if not is_easy:
                return False, "Not a Quick Apply job. Skipped.", False
            
        # 0. Clear Overlays
        self.handle_cookie_banners()
        
        # 1. Find and Click Apply Button
        # Optimized: Combined selector
        combined_selector = "button[data-testid='apply-button'], a[data-testid='apply-button'], button.apply-button, a.apply-button, button[data-testid='nls-apply-button'], a[data-testid='nls-apply-button'], .apply-button-container button, div[class*='ApplyButton'] button, button[class*='apply-button']"
        
        clicked = self.click_element(combined_selector, timeout=5)
        
        if not clicked:
            # Try XPath for text-based search (EN and DE)
            xpath_queries = [
                "//button[contains(translate(., 'BEWERBEN', 'bewerben'), 'bewerben')]",
                "//a[contains(translate(., 'BEWERBEN', 'bewerben'), 'bewerben')]",
                "//button[contains(translate(., 'APPLY', 'apply'), 'apply')]",
                "//a[contains(translate(., 'APPLY', 'apply'), 'apply')]"
            ]
            for query in xpath_queries:
                try:
                    apply_btn = self.driver.find_element(By.XPATH, query)
                    if apply_btn.is_displayed():
                        apply_btn.click()
                        clicked = True
                        logger.info(f"[Xing] Clicked Apply button via XPath: {query}")
                        break
                except:
                    continue
        
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
                    logger.info("[Xing] Uploaded resume.")
                    self.random_sleep(1, 2)
                except Exception as e:
                    logger.info(f"[Xing] Resume upload failed: {e}")
        
        # 3. Submit
        submit_selectors = [
            "button[type='submit']",
            "button[data-testid='submit-application']",
            "button.submit-button",
            "button[data-testid='nls-submit-button']",
            "button[class*='SubmitButton']",
            "//button[contains(translate(., 'ABSENDEN', 'absenden'), 'absenden')]",
            "//button[contains(translate(., 'BESTÄTIGEN', 'bestätigen'), 'bestätigen')]",
            "//button[contains(translate(., 'SUBMIT', 'submit'), 'submit')]",
            "//button[contains(translate(., 'CONFIRM', 'confirm'), 'confirm')]",
            "//button[contains(., 'Send application')]",
            "//button[contains(., 'Bewerbung absenden')]",
            "//button[contains(., 'Antrag stellen')]"
        ]
        
        for selector in submit_selectors:
            try:
                if selector.startswith("//"):
                    btn = self.driver.find_element(By.XPATH, selector)
                    btn.click()
                    clicked = True
                else:
                    clicked = self.click_element(selector, timeout=5)

                if clicked:
                    self.random_sleep(2, 3)
                    self.applied_count += 1
                    return True, "Application submitted successfully!", True
            except:
                continue
        
        return False, "Submit button not found. Check manually.", True
    
    # ==========================================
    # INDEED EASY APPLY (SCHNELLBEWERBUNG)
    # ==========================================
    def is_easy_apply_indeed(self, job_url=None):
        """Check if an Indeed job has Schnellbewerbung."""
        if job_url:
            logger.info(f"[Indeed] Checking Easy Apply: {job_url}")
            self.driver.get(job_url)
            self.random_sleep(3, 5)

        # 1. Check for Already Applied or Expired
        is_applied, applied_ind = self._is_applied_check()
        if is_applied:
            logger.info(f"[Indeed] ⏭️ Already applied (detected via {applied_ind})")
            return False

        is_expired, expired_ind = self._is_expired_check()
        if is_expired:
            logger.info(f"[Indeed] ⏭️ Job expired/closed (detected via {expired_ind}).")
            return False

        # Look for buttons that say "Schnellbewerbung" or "Easily Apply"
        try:
            page_source = self.driver.page_source.lower()
            if any(phrase in page_source for phrase in ["easily apply", "einfach bewerben", "einfach bewerbung", "schnellbewerbung"]):
                return True
        except: pass
        return False

    def apply_indeed(self, job_url, skip_detection=False):
        """Automates Indeed Schnellbewerbung."""
        if self.applied_count >= self.max_applications:
            return False, "Max applications reached.", False

        # 1. Navigation
        logger.info(f"[Indeed] Navigating to: {job_url}")
        self.driver.get(job_url)
        self.random_sleep(4, 7)

        # 2. Check for Already Applied or Expired
        is_applied, applied_ind = self._is_applied_check()
        if is_applied:
            logger.info(f"[Indeed] ⏭️ Already applied (detected via {applied_ind})")
            return True, "Already applied.", True

        is_expired, expired_ind = self._is_expired_check()
        if is_expired:
            logger.info(f"[Indeed] ⏭️ Job expired/closed (detected via {expired_ind}).")
            return False, "Job expired or no longer accepting applications.", False

        # 3. Detection step (unless skipped)
        if not skip_detection:
            if not self.is_easy_apply_indeed(): # No URL means no re-navigation
                return False, "Not an Indeed Easy Apply job.", False

        # 0. Clear Overlays
        self.handle_cookie_banners()

        # 1. Find and Click Apply Button
        logger.info("[Indeed] Looking for Apply Button...")
        
        # New robust selectors list
        apply_selectors = [
            "button.jobsearch-IndeedApplyButton-button", 
            "#indeedApplyButton", 
            "button[id*='indeedApplyButton']",
            ".jobsearch-IndeedApplyButton-contentWrapper button",
            "div[class*='apply-button'] button",
            "button[aria-label*='Apply']",
            "button[aria-label*='Bewerben']"
        ]
        
        clicked = False
        for sel in apply_selectors:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed():
                    logger.info(f"[Indeed] Found Apply Button via CSS: {sel}")
                    btn.click()
                    clicked = True
                    break
            except: continue
            
        if not clicked:
            # Fallback to XPath
            xpath_selectors = [
                "//button[contains(., 'Schnellbewerbung')]",
                "//button[contains(., 'Easily apply')]",
                "//button[contains(., 'Einfach bewerben')]",
                "//button[contains(., 'Einfach Bewerbung')]",
                "//span[contains(., 'Schnellbewerbung')]/parent::button"
            ]
            for sel in xpath_selectors:
                try:
                    btn = self.driver.find_element(By.XPATH, sel)
                    if btn.is_displayed():
                        logger.info(f"[Indeed] Found Apply Button via XPath: {sel}")
                        btn.click()
                        clicked = True
                        break
                except: continue

        if not clicked:
            logger.error("[Indeed] ❌ Apply button NOT found.")
            save_debug_artifact(self.driver, "indeed_apply_failed")
            return False, "Indeed Apply button not found.", False

        logger.info("[Indeed] Apply button clicked. Waiting for modal/iframe...")
        self.random_sleep(3, 5)

        # Indeed often uses an IFRAME for the application form
        # We need to switch to it if present
        # WAIT for iframe
        iframe_found = False
        try:
            WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                src = (iframe.get_attribute("src") or "").lower()
                title = (iframe.get_attribute("title") or "").lower()
                if "indeed" in src or "apply" in title or "bewerbung" in title:
                    self.driver.switch_to.frame(iframe)
                    logger.info(f"[Indeed] Switched to application iframe (src: {src[:30]}...)")
                    iframe_found = True
                    break
        except Exception as e:
            logger.info(f"[Indeed] Iframe check warning: {e}")

        if not iframe_found:
             logger.info("[Indeed] No specific application iframe found. Assuming form is in main window or new tab.")

        # 2. Fill Fields (Multi-step form)
        max_steps = 15
        for step in range(max_steps):
            logger.info(f"[Indeed] processing step {step+1}...")
            self.random_sleep(2, 3)

            # Check for success indicators
            page_source_lower = self.driver.page_source.lower()
            success_indicators = [
                "bewerbung ist unterwegs", "application submitted", 
                "gelungen", "great, you're done", "application sent"
            ]
            if any(s in page_source_lower for s in success_indicators):
                logger.info("[Indeed] ✓ Application submitted successfully!")
                self.applied_count += 1
                try: self.driver.switch_to.default_content()
                except: pass
                return True, "Applied!", True

            # Handle Resume
            if self.resume_path:
                try:
                    resume_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                    resume_input.send_keys(self.resume_path)
                    logger.info("[Indeed] Uploaded resume.")
                    self.random_sleep(2, 3) # Wait for upload
                except: pass

            # Fill Text Fields (Standard & Floating Labels)
            try:
                inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='tel'], input[type='email'], textarea")
                for inp in inputs:
                    try:
                        if not inp.is_displayed(): continue
                        
                        # Check exist value
                        val = inp.get_attribute("value")
                        if val and len(val) > 1: continue

                        # Try to find label/ID
                        label_text = ""
                        inp_id = inp.get_attribute("id")
                        if inp_id:
                            try:
                                label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{inp_id}']")
                                label_text = label.text
                            except: pass
                        
                        # If no label tag, check aria-label or placeholder
                        if not label_text:
                            label_text = inp.get_attribute("aria-label") or inp.get_attribute("placeholder") or ""

                        if label_text:
                            # Use DB for answer mapping
                            answer = self.db.get_answer_for_question(label_text)
                            if answer:
                                logger.info(f"[Indeed] Filling '{label_text}' with '{answer}'")
                                inp.clear()
                                inp.send_keys(answer)
                    except: pass
            except: pass
            
            # Click "Continue", "Review", or "Submit"
            # Indeed buttons change: "Weiter", "Continue", "Review your application", "Submit application"
            
            button_found = False
            
            # 1. Try Primary Action Buttons
            action_selectors = [
                "button[type='submit']",
                ".ia-continue-button",
                ".ia-submit-button",
                "button.css-1i08qff", # Common Indeed generated class
                "button.css-kyg8or"   # Another common one
            ]
            
            possible_btns = []
            for sel in action_selectors:
                possible_btns.extend(self.driver.find_elements(By.CSS_SELECTOR, sel))
            
            # Also text based search for buttons
            possible_btns.extend(self.driver.find_elements(By.TAG_NAME, "button"))
            
            target_actions = ["continue", "weieter", "weiter", "review", "überprüfen", "submit", "senden", "apply", "bewerbung absenden"]
            
            for btn in possible_btns:
                try:
                    if not btn.is_displayed(): continue
                    txt = btn.text.lower().strip()
                    if any(t in txt for t in target_actions):
                        logger.info(f"[Indeed] Clicking Action Button: '{txt}'")
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        button_found = True
                        break
                except: continue
                
            if not button_found:
                logger.info(f"[Indeed] No obvious 'Next/Submit' button found in step {step+1}. Checking for success again next loop or stopping.")
                # Sometimes it's just loading?
                self.random_sleep(2, 3)
            
            # Check for "Return to job search" or close popup
            try:
                close_btn = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Close']")
                if close_btn.is_displayed():
                     # Only click close if we think we are done? 
                     # Or if it's a "Save your resume" popup?
                     pass
            except: pass

        try: self.driver.switch_to.default_content()
        except: pass
        
        return False, "Stopped loop without confirmed success.", True

    # ==========================================
    # MAIN APPLY DISPATCHER
    # ==========================================
    def apply(self, job_url, platform, skip_detection=False, job_title="", company="", target_role=None):
        """Dispatch to the correct applier based on platform."""
        # Set current job info for logging unknown questions
        self.current_job_title = job_title
        self.current_company = company
        self.target_role = target_role or job_title
        
        platform_lower = platform.lower()
        
        if "linkedin" in platform_lower:
            return self.apply_linkedin(job_url, skip_detection)
        elif "xing" in platform_lower:
            return self.apply_xing(job_url, skip_detection)
        elif "indeed" in platform_lower:
            return self.apply_indeed(job_url, skip_detection)
        else:
            return False, f"Platform '{platform}' not supported for auto-apply.", False
    
    # ==========================================
    # LIVE APPLY MODE - LinkedIn
    # ==========================================
    def live_apply_linkedin(self, keyword, location, target_count=5, target_role=None, callback=None):
        """
        Browse LinkedIn job search and apply to jobs until target_count is reached.
        Workflow:
        1. Search with keyword, location, Easy Apply filter (ONCE)
        2. Click each job card to load details in side panel
        3. Check for 'Beworben' (already applied) status
        4. If not applied, click Easy Apply and complete form
        5. Move to next card (no navigation away from search)
        
        Returns:
            dict with results: applied, skipped, errors
        """
        applied_count = 0
        results = {
            "applied": [],
            "skipped": [],
            "errors": [],
            "checked": 0
        }
        
        # Set target_role if not provided
        if not target_role:
            target_role = keyword

        # Load filters
        blacklist = self.db.load_blacklist()
        bl_companies = [c.lower() for c in blacklist.get("companies", []) if c]
        bl_titles = [t.lower() for t in blacklist.get("titles", []) if t]
        safe_phrases = [s.lower() for s in blacklist.get("safe_phrases", []) if s]
        
        def log(msg):
            logger.info(f"[LiveApply] {msg}")
            if callback:
                callback(msg)
        
        def is_blacklisted(title, company):
            t_lower = title.lower()
            c_lower = company.lower()
            
            for bl_c in bl_companies:
                if bl_c in c_lower:
                    return True, f"Company blacklisted"
            
            for bl_t in bl_titles:
                if bl_t in t_lower:
                    for safe in safe_phrases:
                        if safe in t_lower:
                            return False, None
                    return True, f"Title blacklisted"
            
            return False, None
        
        # Navigate to LinkedIn Jobs Search with Easy Apply filter
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={keyword.replace(' ', '+')}&location={location.replace(' ', '+')}&f_AL=true"
        log(f"🔍 Navigating to: {search_url}")
        self.driver.get(search_url)
        self.random_sleep(4, 6)
        
        # Verify Easy Apply filter is active (f_AL=true in URL should work)
        log("✅ Easy Apply filter applied via URL parameter")
        self._ensure_linkedin_easy_apply_filter()
        
        page = 0
        max_pages = 20
        processed_jobs = set()  # Track processed jobs by title+company to avoid duplicates
        
        while applied_count < target_count and page < max_pages:
            if self.applied_count >= self.max_applications:
                log(f"🛑 Session limit ({self.max_applications}) reached!")
                break

            page += 1
            log(f"📄 Page {page} - Applied: {applied_count}/{target_count}")
            
            # Scroll to load all job cards
            job_list = self.find_element_safe(".jobs-search-results-list, .scaffold-layout__list", timeout=5)
            if job_list:
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", job_list)
                self.random_sleep(1, 2)
            
            # Use index-based iteration to avoid stale elements
            card_index = 0
            max_cards_per_page = 50
            
            while applied_count < target_count and card_index < max_cards_per_page:
                jitter_mouse(self.driver)
                # Always re-fetch the job cards list (DOM may have changed)
                try:
                    job_cards = self.driver.find_elements(By.CSS_SELECTOR, 
                        ".jobs-search-results__list-item, .job-card-container, .scaffold-layout__list-item")
                except:
                    job_cards = []
                
                if card_index == 0:
                    log(f"Found {len(job_cards)} job cards")
                
                if card_index >= len(job_cards):
                    break  # No more cards on this page
                
                card = job_cards[card_index]
                card_index += 1
                results["checked"] += 1
                
                try:
                    # Quick check if already applied on card text
                    try:
                        card_text = card.text.lower()
                        is_applied, indicator = self._is_applied_check(card_text)
                        if is_applied:
                            log(f"   ⏭️ Already applied (via card text: {indicator})")
                            results["skipped"].append({"title": "Unknown", "company": "Unknown", "reason": f"Already applied ({indicator})"})
                            continue
                    except:
                        pass

                    # Click card with retry for stale elements
                    card_clicked = False
                    for retry in range(3):
                        try:
                            # Re-fetch card if we're retrying
                            if retry > 0:
                                job_cards = self.driver.find_elements(By.CSS_SELECTOR, 
                                    ".jobs-search-results__list-item, .job-card-container, .scaffold-layout__list-item")
                                if card_index - 1 < len(job_cards):
                                    card = job_cards[card_index - 1]
                                else:
                                    break
                            
                            # Scroll card into view and click using JavaScript
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                            self.random_sleep(0.3, 0.5)
                            # Try regular click first, then JS
                            try:
                                card.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", card)
                            card_clicked = True
                            break
                        except StaleElementReferenceException:
                            self.random_sleep(0.5, 1.0)
                            continue
                    
                    if not card_clicked:
                        log(f"   ⚠️ Card stale after retries, skipping...")
                        continue
                    
                    self.random_sleep(1.5, 2.5)
                    
                    # Extract job title and company from side panel
                    try:
                        title_el = self.driver.find_element(By.CSS_SELECTOR, 
                            ".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, h2.t-24")
                        title = title_el.text.strip()
                    except:
                        title = "Unknown"
                    
                    try:
                        company_el = self.driver.find_element(By.CSS_SELECTOR, 
                            ".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name")
                        company = company_el.text.strip()
                    except:
                        company = "Unknown"
                    
                    # Track by job title+company to avoid processing same job twice
                    job_key = f"{title}_{company}".lower()
                    if job_key in processed_jobs:
                        continue  # Skip duplicate job
                    processed_jobs.add(job_key)
                    
                    log(f"[{card_index}] {title} @ {company}")
                    
                    # CHECK 1: Already applied?
                    try:
                        # Scope to detail panel
                        detail_panel = self.find_element_safe(".jobs-search__job-details, .scaffold-layout__detail, .jobs-search-two-pane__details", timeout=3)
                        if detail_panel:
                            # Wait slightly for text to populate (Async React)
                            time.sleep(1.5)
                            
                            is_applied, indicator = self._is_applied_check(detail_panel.text)
                            if is_applied:
                                log(f"   ⏭️ Already applied (detected in details: {indicator})")
                                results["skipped"].append({"title": title, "company": company, "reason": f"Already applied ({indicator})"})
                                continue
                    except: pass
                    
                    # CHECK 2: Blacklist check
                    is_blocked, reason = is_blacklisted(title, company)
                    if is_blocked:
                        log(f"   ⏭️ {reason}")
                        results["skipped"].append({"title": title, "company": company, "reason": reason})
                        continue
                    
                    # APPLY: Click Easy Apply button in side panel
                    log(f"   🎯 Attempting to apply...")
                    
                    # First scroll the job description (like EAB does)
                    try:
                        job_desc_area = self.driver.find_element(By.CLASS_NAME, "jobs-search__job-details--container")
                        self.driver.execute_script("arguments[0].scrollTo(0, 800)", job_desc_area)
                        self.random_sleep(0.5, 1.0)
                        self.driver.execute_script("arguments[0].scrollTo(0, 0)", job_desc_area)
                    except:
                        pass
                    
                    # Check if this is an EXTERNAL apply job (not Easy Apply)
                    # Use a broader set of external indicators
                    is_external = False
                    try:
                        # Common labels for external apply buttons in EN/DE/FR/ES
                        external_labels = ["Anwenden", "Apply", "Bewerben", "Postuler", "Solicitar", "Candidatarsi"]
                        for label in external_labels:
                            try:
                                btn = self.driver.find_element(By.XPATH, f"//button[contains(., '{label}')] | //a[contains(., '{label}')]")
                                if btn and btn.is_displayed():
                                    # Double check it is NOT Easy Apply
                                    txt = btn.text.lower()
                                    if "easy" not in txt and "einfach" not in txt and "schnell" not in txt:
                                        is_external = True
                                        break
                            except: continue
                    except: pass

                    if is_external:
                        log(f"   ⚠️ External apply job detected. Skipping...")
                        results["skipped"].append({"title": title, "company": company, "reason": "External apply"})
                        continue
                    
                    # Find Easy Apply button (Robust)
                    easy_apply_btn = None
                    
                    # Strategy A: Use the existing logic from is_easy_apply_linkedin
                    # but localized to the current side panel
                    try:
                        detail_panel = self.find_element_safe(".jobs-search__job-details, .scaffold-layout__detail", timeout=2)
                        if detail_panel:
                            # Search for button with apply keywords
                            # These selectors match what we use in apply_linkedin
                            apply_selectors = [
                                "button.jobs-apply-button", "a.jobs-apply-button",
                                "button[aria-label*='Easy Apply']", "button[aria-label*='Einfach bewerben']",
                                "button[aria-label*='Einfach Bewerbung']", "button[aria-label*='Schnellbewerbung']"
                            ]
                            for sel in apply_selectors:
                                try:
                                    btns = detail_panel.find_elements(By.CSS_SELECTOR, sel)
                                    for b in btns:
                                        if b.is_displayed():
                                            easy_apply_btn = b
                                            break
                                    if easy_apply_btn: break
                                except: continue
                    except: pass
                    
                    # Strategy B: Global CSS fallback (from apply_linkedin)
                    if not easy_apply_btn:
                        btn_selectors = [
                            "button.jobs-apply-button", "a.jobs-apply-button",
                            "button[aria-label*='Easy Apply']", "a[aria-label*='Easy Apply']",
                            "button.artdeco-button--primary"
                        ]
                        for sel in btn_selectors:
                            try:
                                btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                                for b in btns:
                                    if b.is_displayed():
                                        txt = b.text.lower()
                                        if any(k in txt for k in ["easy", "apply", "bewerben", "bewerbung", "schnellbewerbung", "einfach"]):
                                            if not any(k in txt for k in ["website", "extern", "employer", "company site"]):
                                                easy_apply_btn = b
                                                break
                                if easy_apply_btn: break
                            except: continue

                    # Strategy C: XPath fallback
                    if not easy_apply_btn:
                        xpath_queries = [
                            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'easy apply')]",
                            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'einfach bewerben')]",
                            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'schnellbewerbung')]"
                        ]
                        for xpath in xpath_queries:
                            try:
                                btn = self.driver.find_element(By.XPATH, xpath)
                                if btn and btn.is_displayed():
                                    easy_apply_btn = btn
                                    break
                            except: pass
                    
                    if not easy_apply_btn:
                        log(f"   ⚠️ Easy Apply button not found (may be external)")
                        results["skipped"].append({"title": title, "company": company, "reason": "No Easy Apply"})
                        continue
                    
                    # Click Easy Apply button (with retry for stale element)
                    clicked = False
                    max_retries = 3
                    for retry in range(max_retries):
                        try:
                            easy_apply_btn.click()
                            clicked = True
                            break
                        except StaleElementReferenceException:
                            self.random_sleep(0.5, 1.0)
                            try:
                                easy_apply_btn = self.driver.find_element(By.CLASS_NAME, 'jobs-apply-button')
                            except:
                                pass
                        except Exception:
                            # Fallback to JavaScript click
                            try:
                                self.driver.execute_script("arguments[0].click();", easy_apply_btn)
                                clicked = True
                                break
                            except:
                                pass
                    
                    if not clicked:
                        log(f"   ⚠️ Could not click Easy Apply button")
                        results["errors"].append({"title": title, "company": company, "error": "Click failed"})
                        continue
                    
                    self.random_sleep(2, 3)
                    
                    # Process the modal
                    self.current_job_title = title
                    self.current_company = company
                    
                    apply_success = self._process_linkedin_modal()
                    
                    if apply_success:
                        applied_count += 1
                        self.applied_count += 1
                        log(f"   ✅ Applied! ({applied_count}/{target_count})")
                        results["applied"].append({"title": title, "company": company})
                        
                        # Save to applied jobs with timestamp
                        jid = f"{title}-{company}"
                        job_url = self.driver.current_url
                        from datetime import datetime
                        job_data = {
                            "Job Title": title,
                            "Company": company,
                            "Web Address": job_url,
                            "Platform": "LinkedIn",
                            "Found_job": target_role,
                            "Location": location,
                            "created_at": datetime.now().isoformat()
                        }
                        self.db.save_applied(jid, job_data, {"auto_applied": True})
                        log(f"   💾 Saved to database: {jid}")
                        
                        # After successful application, wait a bit for DOM to stabilize
                        self.random_sleep(2, 3)
                    else:
                        log(f"   ❌ Failed to complete application")
                        results["errors"].append({"title": title, "company": company, "error": "Modal failed"})
                    
                except StaleElementReferenceException:
                    log(f"   ⚠️ Stale element, retrying...")
                    continue
                except Exception as e:
                    log(f"   ⚠️ Error: {str(e)[:50]}")
                    results["errors"].append({"error": str(e)})
                    continue
            
            # Go to next page if needed
            if applied_count < target_count:
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, 
                        "button[aria-label='Weiter'], button[aria-label='Next'], li.artdeco-pagination__indicator--number button")
                    next_btn.click()
                    log("➡️ Moving to next page...")
                    self.random_sleep(3, 4)
                    # Re-verify filter on new page to be sure
                    self._ensure_linkedin_easy_apply_filter()
                except:
                    log("📄 No more pages available")
                    break
        
        log(f"🏁 Complete! Applied: {applied_count} | Checked: {results['checked']} | Skipped: {len(results['skipped'])}")
        
        # Include unknown questions for user to answer
        results["unknown_questions"] = self.session_unknown_questions
        
        return results
    
    def _recursive_iframe_search(self, keywords, depth=0, max_depth=3):
        """
        Recursively search for a button with keywords in visible text.
        Returns the WebElement if found, else None.
        """
        if depth > max_depth:
            return None

        # 1. Check current frame
        try:
            btns = self.driver.find_elements(By.TAG_NAME, "button")
            for b in btns:
                try:
                    if b.is_displayed():
                        txt = b.text.lower().strip()
                        # Exclude 'Easy Apply' (background button)
                        if "easy apply" in txt or "einfach bewerben" in txt:
                            continue
                        
                        if any(k in txt for k in keywords):
                            logger.info(f"[LinkedIn] Recursive Found: '{b.text}' in Depth {depth}")
                            return b
                except: pass
        except: pass

        # 2. Recurse children
        try:
            frames = self.driver.find_elements(By.TAG_NAME, "iframe")
            for i, frame in enumerate(frames):
                try:
                    self.driver.switch_to.frame(frame)
                    found = self._recursive_iframe_search(keywords, depth + 1, max_depth)
                    if found:
                        return found
                    self.driver.switch_to.parent_frame()
                except Exception as e:
                    logger.info(f"[LinkedIn] Frame switch error: {e}")
                    try: self.driver.switch_to.parent_frame()
                    except: pass
        except: pass
        
        return None

    def _process_linkedin_modal(self):
        """
        Process the LinkedIn Easy Apply modal using robust button-driven loop.
        Matches logic from reference project 'linkedin-easyapply-ai-main' but with added safety checks.
        """
        import time
        logger.info("[LinkedIn] Entering Button-Driven Application Loop...")
        
        # 0. Check for New Tab/Window (Crucial!)
        try:
            current_handle = self.driver.current_window_handle
            all_handles = self.driver.window_handles
            if len(all_handles) > 1:
                # If a new window appeared recently, switch to it
                if current_handle != all_handles[-1]:
                    logger.info(f"[LinkedIn] ⚠️ New window detected. Switching from {current_handle} to {all_handles[-1]}")
                    self.driver.switch_to.window(all_handles[-1])
        except Exception as e:
            logger.info(f"[LinkedIn] Window handle check failed: {e}")

        # 0.5 WAIT FOR MODAL TO APPEAR
        try:
            logger.info("[LinkedIn] Waiting for application modal to render...")
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".artdeco-modal, [role='dialog'], .jobs-easy-apply-modal"))
            )
            logger.info("[LinkedIn] Modal detected.")
        except:
            logger.info("[LinkedIn] ⚠️ Modal not detected after 5s wait. Proceeding anyway but might fail.")

        max_attempts = 25
        attempts = 0
        submitted_clicked = False
        
        while attempts < max_attempts:
            attempts += 1
            self.random_sleep(2.0, 3.5)
            
            # 1. Check for success indicators FIRST
            try:
                success_keywords = [
                    "bewerbung gesendet", "application sent", "successfully submitted",
                    "erfolgreich", "bewerbung wurde gesendet", "votre candidature a été envoyée",
                    "candidatura inviata", "candidatura enviada"
                ]
                page_text = self.driver.page_source.lower()
                if any(kw in page_text for kw in success_keywords) or "application was sent" in page_text or "sent to" in page_text:
                    logger.info("[LinkedIn] ✅ Application success detected via page text.")
                    try:
                        # Try to find "Done" or "Dismiss"
                        done_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Done'], button.artdeco-button--primary, button[aria-label*='Dismiss'], .artdeco-modal__dismiss")
                        for db in done_btns:
                            if any(k in db.text.lower() for k in ['done', 'fertig', 'close', 'schließen']) or "dismiss" in db.get_attribute("aria-label").lower():
                                self.driver.execute_script("arguments[0].click();", db)
                                break
                    except: pass
                    return True
            except: pass

            # 2. Find PRIMARY BUTTONS (Generic class, any tag)
            # Use .artdeco-button--primary instead of button.artdeco-button--primary
            found_action = False
            
            # Contexts to check: Main Document + Iframes
            # We will gather all potential buttons from Main Doc first, if none, check Iframes
            
            potential_buttons = []
            
            # A. Main Document Scan
            try:
                btns = self.driver.find_elements(By.CSS_SELECTOR, ".artdeco-button--primary")
                visible_btns = []
                for b in btns:
                    try:
                        if b.is_displayed():
                            visible_btns.append(b)
                            # DEBUG LOG
                            logger.info(f"[LinkedIn DEBUG] Found visible btn: Tag={b.tag_name}, Text='{b.text}'")
                    except: pass
                
                if visible_btns:
                    potential_buttons = visible_btns
            except: pass
            
            # B. Iframe Scan (if no buttons in main doc)
            if not potential_buttons:
                try:
                    iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                    if iframes:
                        logger.info(f"[LinkedIn DEBUG] Checking {len(iframes)} iframes...")
                        for frame in iframes:
                            try:
                                self.driver.switch_to.frame(frame)
                                f_btns = self.driver.find_elements(By.CSS_SELECTOR, ".artdeco-button--primary")
                                for b in f_btns:
                                    if b.is_displayed():
                                        potential_buttons.append(b)
                                        logger.info(f"[LinkedIn DEBUG] Found iframe btn: Tag={b.tag_name}, Text='{b.text}'")
                                if potential_buttons:
                                    # Stay in this frame if we found buttons!
                                    break 
                                self.driver.switch_to.default_content()
                            except:
                                self.driver.switch_to.default_content()
                except: pass
            
            if not potential_buttons:
                logger.info(f"[LinkedIn] No visible primary buttons found in Main or Iframes. Attempt {attempts}/{max_attempts}")
                
                # Dump logic moved to end of loop to cover all failure cases
                if attempts > 10:
                    logger.info("[LinkedIn] ⚠️ No buttons found for 10+ steps and no success msg. Assuming failed/closed.")
                    return False
                continue
            
            # Pick the action button
            action_btn = None
            target_keywords = ['next', 'weiter', 'submit', 'senden', 'review', 'überprüfen', 'continue', 'suivant', 'absenden', 'bewerben', 'einreichen', 'done', 'fertig']
            
            # If we already clicked submit, we should look for Close/Dismiss buttons as signs of success
            if submitted_clicked:
                target_keywords.extend(['close', 'schließen', 'dismiss'])
            
            # First pass: look for exact keywords
            for b in potential_buttons:
                txt = b.text.lower().strip()
                if any(k in txt for k in target_keywords):
                    action_btn = b
                    logger.info(f"[LinkedIn] Matched Action Button: '{txt}'")
                    break
            
            # Fallback: take any primary button that is NOT 'Easy Apply'
            if not action_btn:
                for b in potential_buttons:
                    txt = b.text.lower()
                    if "easy apply" not in txt and "einfach bewerben" not in txt:
                        action_btn = b
                        logger.info(f"[LinkedIn] Matched Fallback Button: '{txt}'")
                        break
            
            # STRATEGY C: Search ALL buttons by text (if Primary Class failed)
            if not action_btn:
                logger.info("[LinkedIn] Strategy C: Searching ALL visible buttons for keywords...")
                try:
                    all_btns = self.driver.find_elements(By.TAG_NAME, "button")
                    for b in all_btns:
                        if b.is_displayed():
                            txt = b.text.lower().strip()
                            if any(k in txt for k in target_keywords):
                                action_btn = b
                                logger.info(f"[LinkedIn] Strategy C Matched: '{b.text}' (Tag: {b.tag_name})")
                                break
                except Exception as e:
                    logger.info(f"[LinkedIn] Strategy C failed: {e}")

            # STRATEGY D: Recursive Iframe Search (Python)
            if not action_btn:
                logger.info("[LinkedIn] Strategy D: Recursive Iframe Search...")
                self.driver.switch_to.default_content()
                
                # Check for fields first
                try: self._linkedin_fill_fields()
                except: pass
                
                recurse_btn = self._recursive_iframe_search(target_keywords, depth=0, max_depth=3)
                if recurse_btn:
                    logger.info(f"[LinkedIn] Strategy D Success: Found '{recurse_btn.text}'")
                    try: recurse_btn.click()
                    except: self.driver.execute_script("arguments[0].click();", recurse_btn)
                    found_action = True
                    
                    # Check if we clicked "Done" -> Success!
                    if any(x in recurse_btn.text.lower() for x in ['done', 'fertig', 'close', 'schließen']):
                         logger.info("[LinkedIn] ✅ 'Done' button clicked via Strategy D. Application Complete!")
                         return True

                    time.sleep(4)
                    continue
                else:
                    self.driver.switch_to.default_content()

            # STRATEGY E: ULTIMATE JS SEARCH (Shadow DOM + Iframes Combined)
            if not action_btn and not found_action:
                logger.info("[LinkedIn] Strategy E: Ultimate JS Search (Shadow+Iframe)...")
                
                # Check for fields first
                try: self._linkedin_fill_fields()
                except: pass
                
                js_script = """
                function findDeep(root, keywords) {
                    if (!root) return null;
                    
                    // Check logic
                    if (root.tagName === 'BUTTON' || (root.tagName === 'A' && root.className.includes('button')) || 
                        (root.tagName === 'SPAN' && root.className.includes('button')) ||
                        (root.tagName === 'DIV' && (root.className.includes('button') || root.getAttribute('role') === 'button'))) {
                        try {
                            let text = (root.innerText || '').toLowerCase();
                            let aria = (root.getAttribute('aria-label') || '').toLowerCase();
                            let isMatch = keywords.some(k => text.includes(k) || aria.includes(k));
                            
                            // Blacklist "edit", "bearbeiten", "change" to avoid loops
                            let isBlacklisted = ["edit", "bearbeiten", "change", "ändern"].some(b => text.includes(b) || aria.includes(b));
                            
                            if (isMatch && !isBlacklisted && !text.includes('easy apply') && !text.includes('bewerben')) {
                                let style = window.getComputedStyle(root);
                                if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                                    return root;
                                }
                            }
                        } catch(e){}
                    }
                    
                    // Shadow Root
                    if (root.shadowRoot) {
                        let res = findDeep(root.shadowRoot, keywords);
                        if (res) return res;
                    }
                    
                    // Children
                    if (root.children) {
                        for (let child of root.children) {
                            let res = findDeep(child, keywords);
                            if (res) return res;
                        }
                    }
                    
                    // Iframes
                    if (root.tagName === 'IFRAME') {
                        try {
                            let doc = root.contentDocument || root.contentWindow.document;
                            if (doc) {
                                let res = findDeep(doc.body, keywords);
                                if (res) return res;
                            }
                        } catch(e){}
                    }
                    return null;
                }
                
                let kw = arguments[0];
                let btn = findDeep(document.body, kw);
                if (btn) {
                    btn.click();
                    return "Clicked: " + (btn.innerText || btn.getAttribute('aria-label'));
                }
                return "NotFound";
                """
                try:
                    res = self.driver.execute_script(js_script, target_keywords)
                    if res and res.startswith("Clicked"):
                        logger.info(f"[LinkedIn] Strategy E Success: {res}")
                        found_action = True
                        
                        # Check if we clicked "Done" -> Success!
                        if any(x in res.lower() for x in ['done', 'fertig', 'close', 'schließen']):
                            logger.info("[LinkedIn] ✅ 'Done' button clicked via Strategy E. Application Complete!")
                            return True
                        
                        time.sleep(4)
                        continue
                except Exception as e:
                    logger.info(f"[LinkedIn] Strategy E Error: {e}")

            if not action_btn and not found_action:
                logger.warning("[LinkedIn] Visible buttons found but none matched Action or Fallback logic.")
                try:
                    logger.debug([b.text for b in potential_buttons])
                except:
                    logger.debug("[LinkedIn] (Some buttons became stale during printing)")
                
                # DUMP HTML FOR DEBUGGING
                if attempts == 1 or attempts == 5:
                    save_debug_artifact(self.driver, f"linkedin_modal_step_{attempts}")

            if action_btn:
                btn_text = action_btn.text.strip()
                
                # 3. Fill Fields (We must ensure we are in the correct context if iframe was used)
                try:
                    self._linkedin_fill_fields()
                except: pass
                
                # 4. Click Button
                try:
                    action_btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", action_btn)
                
                # If we clicked "Done", we are successful!
                if any(k in btn_text.lower() for k in ['done', 'fertig']):
                     logger.info("[LinkedIn] ✅ Clicked Done/Fertig. Application Complete.")
                     return True
                
                # If we clicked "Close" AND we previously submitted, that's also success!
                if submitted_clicked and any(k in btn_text.lower() for k in ['close', 'schließen', 'dismiss']):
                     logger.info("[LinkedIn] ✅ Clicked Close after Submit. Application Complete.")
                     return True
                
                # 5. Check for Errors (Blocking)
                self.random_sleep(1.5, 2.0)
                try:
                    errors = self.driver.find_elements(By.CSS_SELECTOR, ".artdeco-inline-feedback__message")
                    visible_errors = [e for e in errors if e.is_displayed()]
                    if visible_errors:
                        logger.info(f"[LinkedIn] ❌ Blocking Form Error: {visible_errors[0].text}")
                        return False
                except: pass
                
                # If button was 'Submit', we might be done next loop
                submit_hints = ['submit', 'senden', 'absenden', 'bewerben', 'einreichen']
                if any(s in btn_text.lower() for s in submit_hints):
                    logger.info("[LinkedIn] Clicked Submit. Waiting for success...")
                    submitted_clicked = True
                    time.sleep(4)
                    
            else:
                logger.info("[LinkedIn] Visible buttons found but none matched Action or Fallback logic.")
                logger.info([b.text for b in potential_buttons])
            
        # Switch back to default content just in case
        try: self.driver.switch_to.default_content()
        except: pass
        
        return False
    
    # ==========================================
    # LIVE APPLY MODE - Xing
    # ==========================================
    def live_apply_xing(self, keyword, location, target_count=5, target_role=None, callback=None):
        """
        Browse Xing job search and apply to jobs until target_count is reached.
        Xing has no Easy Apply filter, so we check each job individually.
        
        Args:
            keyword: Job search keyword
            location: Location to search
            target_count: Number of successful applications to make
            target_role: The role name this application is for
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
        
        if not target_role:
            target_role = keyword

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
            logger.info(f"[LiveApply-Xing] {msg}")
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
        applied_in_call = 0
        
        while applied_in_call < target_count and page < max_pages:
            if self.applied_count >= self.max_applications:
                log(f"🛑 Session limit ({self.max_applications}) reached!")
                break

            page += 1
            log(f"📄 Scanning page {page} - Applied {applied_in_call}/{target_count}...")
            
            # Find job cards
            try:
                # Expanded selectors for Xing job cards
                card_selectors = [
                    "article[data-testid='job-posting-card']",
                    ".job-posting-card",
                    "a[data-testid='job-search-result']",
                    "article[class*='JobPostingCard']",
                    "div[data-testid='job-search-result-container'] article"
                ]
                job_cards = []
                for sel in card_selectors:
                    found = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if found:
                        job_cards = found
                        break
                log(f"Found {len(job_cards)} job cards")
            except:
                job_cards = []
            
            if not job_cards:
                log("No job cards found")
                break
            
            search_handle = self.driver.current_window_handle

            for idx, card in enumerate(job_cards):
                if applied_in_call >= target_count:
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
                    
                    # Open in new tab
                    self.driver.execute_script(f"window.open('{job_url}', '_blank');")
                    self.random_sleep(1, 2)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
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
                    
                    # Check if already applied (via DB)
                    if current_url in applied_links:
                        log(f"   ⏭️ Already applied (DB) - skipping")
                        results["skipped"].append({"title": title, "company": company, "reason": "Already applied"})
                        self.driver.close()
                        self.driver.switch_to.window(search_handle)
                        continue

                    # Check if already applied (via UI)
                    # Check only the prefix of the page to avoid false positives in description
                    source_prefix = self.driver.page_source[:2000].lower()
                    if any(ind in source_prefix for ind in self.APPLIED_INDICATORS):
                        log(f"   ⏭️ Already applied (UI prefix) - skipping")
                        results["skipped"].append({"title": title, "company": company, "reason": "Already applied"})
                        self.driver.close()
                        self.driver.switch_to.window(search_handle)
                        continue
                    
                    # Check if parked
                    if current_url in parked_links:
                        log(f"   ⏭️ In parked jobs - skipping")
                        results["skipped"].append({"title": title, "company": company, "reason": "Parked"})
                        self.driver.close()
                        self.driver.switch_to.window(search_handle)
                        continue
                    
                    # Check blacklist
                    is_blocked, reason = is_blacklisted(title, company)
                    if is_blocked:
                        log(f"   ⏭️ Blacklisted: {reason}")
                        results["skipped"].append({"title": title, "company": company, "reason": reason})
                        self.driver.close()
                        self.driver.switch_to.window(search_handle)
                        continue
                    
                    # Check if this is Easy Apply (no external redirect)
                    is_easy = self.is_easy_apply_xing()
                    
                    if not is_easy:
                        log(f"   ⏭️ Not Easy Apply - external application required")
                        results["skipped"].append({"title": title, "company": company, "reason": "Not Easy Apply"})
                        self.driver.close()
                        self.driver.switch_to.window(search_handle)
                        continue
                    
                    # Try to apply
                    log(f"   🎯 Attempting to apply...")
                    self.current_job_title = title
                    self.current_company = company
                    
                    success, message, _ = self.apply_xing(current_url, skip_detection=True)
                    
                    if success:
                        log(f"   ✅ Applied successfully!")
                        applied_in_call += 1
                        results["applied"].append({"title": title, "company": company, "url": current_url})
                        applied_links.add(current_url)
                        
                        jid = f"{title}-{company}"
                        job_data = {
                            "Job Title": title,
                            "Company": company,
                            "Web Address": current_url,
                            "Platform": "Xing",
                            "Found_job": target_role
                        }
                        self.db.save_applied(jid, job_data, {"auto_applied": True})
                    else:
                        log(f"   ❌ Failed: {message}")
                        results["errors"].append({"title": title, "company": company, "error": message})
                    
                    # Close tab and switch back
                    self.driver.close()
                    self.driver.switch_to.window(search_handle)
                    self.random_sleep(1, 2)
                    
                except Exception as e:
                    log(f"   ⚠️ Error processing card: {e}")
                    results["errors"].append({"error": str(e)})
                    # Make sure to close tab and switch back even on error
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                    self.driver.switch_to.window(search_handle)
                    continue
            
            # Next page
            if applied_in_call < target_count:
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Next'], a[rel='next'], [data-testid='pagination-next']")
                    next_btn.click()
                    self.random_sleep(3, 4)
                except:
                    log("No more pages")
                    break
        
        log(f"🏁 Xing Live Apply Complete! Applied: {len(results['applied'])} | Skipped: {len(results['skipped'])} | Errors: {len(results['errors'])}")
        return results
    
    def _ensure_linkedin_easy_apply_filter(self):
        """Checks if Easy Apply filter is active on the current search page, clicks it if not."""
        try:
            # Wait for filter bar to load
            self.random_sleep(1, 2)

            # Common selectors for the Easy Apply filter button/pill
            # LinkedIn often uses artdeco-pill components for these filters
            filter_selectors = [
                "button[aria-label*='Easy Apply']",
                "button[aria-label*='Einfach bewerben']",
                "//button[contains(., 'Easy Apply filter')]",
                "//button[contains(., 'Filter für Einfach bewerben')]",
                "//button[contains(., 'Easy Apply')]",
                "//button[contains(., 'Einfach bewerben')]"
            ]

            filter_btn = None
            for selector in filter_selectors:
                try:
                    if selector.startswith("//"):
                        filter_btn = self.driver.find_element(By.XPATH, selector)
                    else:
                        filter_btn = self.driver.find_element(By.CSS_SELECTOR, selector)

                    if filter_btn and filter_btn.is_displayed():
                        break
                except:
                    continue

            if filter_btn:
                # Check state
                classes = filter_btn.get_attribute("class") or ""
                pressed = filter_btn.get_attribute("aria-pressed") or "false"

                # Active pills usually have a 'selected' class or aria-pressed="true"
                # LinkedIn specifically uses 'artdeco-pill--selected'
                is_active = "selected" in classes.lower() or "active" in classes.lower() or pressed.lower() == "true"

                if not is_active:
                    logger.info(f"[LinkedIn] Easy Apply filter not active in UI (classes: {classes}, pressed: {pressed}), clicking it...")
                    try:
                        # Sometimes clicking the button itself doesn't work if it's a pill with an inner span
                        self.driver.execute_script("arguments[0].click();", filter_btn)
                    except Exception as e:
                        logger.info(f"[LinkedIn] JS click failed: {e}")
                        filter_btn.click()

                    self.random_sleep(4, 6) # Wait for results to refresh

                    # Double check if it became active
                    try:
                        classes_after = filter_btn.get_attribute("class") or ""
                        if "selected" in classes_after.lower() or "active" in classes_after.lower():
                            logger.info("[LinkedIn] Easy Apply filter successfully activated.")
                        else:
                            logger.info(f"[LinkedIn] Warning: Easy Apply filter still doesn't look active after click (classes: {classes_after})")
                    except: pass

                    return True
                else:
                    logger.info("[LinkedIn] Easy Apply filter is already active in UI.")
                    return True
            else:
                logger.info("[LinkedIn] Could not find Easy Apply filter button in UI.")
                return False
        except Exception as e:
            logger.info(f"[LinkedIn] Error ensuring Easy Apply filter: {e}")
            return False

    def live_apply_indeed(self, keyword, location, target_count=5, target_role=None, callback=None):
        """
        Browse Indeed job search and apply to jobs until target_count is reached.
        Indeed Schnellbewerbung only.
        
        Args:
            keyword: Job search keyword
            location: Location to search
            target_count: Max number of jobs to apply to in this call
            target_role: The role name from resume (for tracking)
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
        
        if not target_role:
            target_role = keyword

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
            logger.info(f"[LiveApply-Indeed] {msg}")
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
        
        # Navigate to Indeed Jobs Search
        domain = "de.indeed.com" 
        search_url = f"https://{domain}/jobs?q={keyword.replace(' ', '+')}&l={location.replace(' ', '+')}"
        log(f"Navigating to: {search_url}")
        self.driver.get(search_url)
        self.random_sleep(4, 6)
        
        page = 0
        max_pages = 20
        applied_in_call = 0
        
        while applied_in_call < target_count and page < max_pages:
            if self.applied_count >= self.max_applications:
                log(f"🛑 Session limit ({self.max_applications}) reached!")
                break

            page += 1
            log(f"📄 Scanning page {page} - Applied {applied_in_call}/{target_count}...")
            
            self.handle_cookie_banners()
            
            # Find job cards using updated selectors
            try:
                card_selectors = [
                    "div.job_seen_beacon",
                    "td.resultContent",
                    "div.cardOutline",
                    ".jobsearch-SerpJobCard"
                ]
                job_cards = []
                for sel in card_selectors:
                    found = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if found:
                        job_cards = found
                        break
                log(f"Found {len(job_cards)} job cards via selector: {sel if job_cards else 'None'}")
            except:
                job_cards = []
            
            if not job_cards:
                log("No job cards found")
                break
            
            search_handle = self.driver.current_window_handle

            for idx, card in enumerate(job_cards):
                if applied_in_call >= target_count:
                    break
                
                results["checked"] += 1
                
                try:
                    # Extract Data
                    title = "Unknown"
                    try:
                        title_el = card.find_element(By.CSS_SELECTOR, "h2.jobTitle span[title]")
                        title = title_el.text.strip()
                    except:
                        try:
                            title_el = card.find_element(By.CSS_SELECTOR, "h2.jobTitle")
                            title = title_el.text.strip()
                        except: pass
                    
                    company = "Unknown"
                    try:
                        company_el = card.find_element(By.CSS_SELECTOR, "[data-testid='company-name']")
                        company = company_el.text.strip()
                    except: pass
                        
                    # Get Link (Crucial Fix: Look for the link inside the title element or covering the card)
                    job_url = None
                    try:
                        link_el = card.find_element(By.CSS_SELECTOR, "a[id^='job_'], a.jcs-JobTitle")
                        raw_href = link_el.get_attribute("href")
                        
                        # Clean URL to match Batch/Scout logic (viewjob?jk=...)
                        if raw_href:
                            try:
                                if "jk=" in raw_href:
                                    qs = urllib.parse.urlparse(raw_href).query
                                    parsed = urllib.parse.parse_qs(qs)
                                    jk_val = parsed.get("jk", [None])[0]
                                    if jk_val:
                                        job_url = f"https://de.indeed.com/viewjob?jk={jk_val}"
                                else:
                                    # Fallback to raw if no jk found (rare)
                                    job_url = raw_href
                            except:
                                job_url = raw_href
                    except: 
                        pass

                    if not job_url:
                        continue
                        
                    log(f"[{idx+1}/{len(job_cards)}] Checking: {title} @ {company}")

                    if job_url in applied_links:
                        log(f"   ⏭️ Already applied (DB) - skipping")
                        results["skipped"].append({"title": title, "company": company, "reason": "Already applied"})
                        continue

                    if job_url in parked_links:
                          log(f"   ⏭️ In parked jobs - skipping")
                          results["skipped"].append({"title": title, "company": company, "reason": "Parked"})
                          continue
                          
                    is_blocked, reason = is_blacklisted(title, company)
                    if is_blocked:
                        log(f"   ⏭️ Blacklisted: {reason}")
                        results["skipped"].append({"title": title, "company": company, "reason": reason})
                        continue

                    # Open in new tab
                    self.driver.execute_script(f"window.open('{job_url}', '_blank');")
                    self.random_sleep(3, 4)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    
                    current_url = self.driver.current_url
                    
                    is_applied, applied_ind = self._is_applied_check()
                    if is_applied:
                        log(f"   ⏭️ Already applied (UI detection: {applied_ind})")
                        results["skipped"].append({"title": title, "company": company, "reason": "Already applied"})
                        self.driver.close()
                        self.driver.switch_to.window(search_handle)
                        continue
                        
                    # Check if Easy Apply (Robust Retry)
                    is_easy = False
                    for _ in range(3):
                        try:
                            # 1. Check metadata/badge first (most reliable on viewjob)
                            try:
                                badge = self.driver.find_element(By.CSS_SELECTOR, ".ialbl, [data-testid='indeedApply'], #indeedApplyButton")
                                if badge.is_displayed():
                                    is_easy = True
                                    break
                            except: pass
                            
                            # 2. Check page source text
                            page_source = self.driver.page_source.lower()
                            if any(phrase in page_source for phrase in ["easily apply", "einfach bewerben", "einfach bewerbung", "schnellbewerbung"]):
                                is_easy = True
                                break
                            
                            self.random_sleep(1, 1.5)
                        except: pass
                    
                    if not is_easy:
                        log(f"   ⏭️ Not Indeed Easy Apply")
                        results["skipped"].append({"title": title, "company": company, "reason": "Not Easy Apply"})
                        self.driver.close()
                        self.driver.switch_to.window(search_handle)
                        continue
                        
                    # Apply
                    log(f"   🎯 Live Apply Mode: Attempting to apply...")
                    self.current_job_title = title
                    self.current_company = company
                    
                    # Call apply_indeed directly with SKIPPED detection because we verified it above
                    # Use the clean job_url we constructed, not current_url (which might be redirect/tracking mess)
                    success, message, _ = self.apply_indeed(job_url, skip_detection=True)
                    
                    if success:
                        log(f"   ✅ Applied successfully!")
                        applied_in_call += 1
                        results["applied"].append({"title": title, "company": company, "url": current_url})
                        applied_links.add(current_url)
                        
                        jid = f"{title}-{company}"
                        job_data = {
                            "Job Title": title,
                            "Company": company,
                            "Web Address": current_url,
                            "Platform": "Indeed",
                            "Found_job": target_role
                        }
                        self.db.save_applied(jid, job_data, {"auto_applied": True})
                    else:
                        log(f"   ❌ Failed: {message}")
                        results["errors"].append({"title": title, "company": company, "error": message})
                    
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                    self.driver.switch_to.window(search_handle)
                    self.random_sleep(1, 2)
                    
                except Exception as e:
                    log(f"   ⚠️ Error processing card: {e}")
                    results["errors"].append({"error": str(e)})
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                    self.driver.switch_to.window(search_handle)
                    continue
            
            # Next Page
            if applied_in_call < target_count:
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='pagination-page-next'], a[aria-label='Next'], a[aria-label='Weiter']")
                    next_btn.click()
                    self.random_sleep(4, 6)
                    try:
                        close_popup = self.find_element_safe("button[aria-label='Close']", timeout=2)
                        if close_popup: close_popup.click()
                    except: pass
                except:
                    log("No more pages")
                    break
        
        log(f"🏁 Indeed Live Apply Complete! Applied: {len(results['applied'])} | Skipped: {len(results['skipped'])} | Errors: {len(results['errors'])}")
        return results

    def close(self):
        """Clean up browser."""
        self.bm.close_driver(profile_name=self.profile_name)

