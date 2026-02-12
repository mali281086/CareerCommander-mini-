import time
import random
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from tools.browser_manager import BrowserManager
from job_hunter.data_manager import DataManager

class JobApplier:
    """Handles automated Easy Apply for LinkedIn and Xing."""
    
    # List of localized strings indicating a job has already been applied to
    APPLIED_INDICATORS = [
        "beworben", "applied", "candidature confirmée", "postulado",
        "bewerbung ansehen", "view application", "solicitud enviada",
        "già candidato", "aanmelding verzonden", "zaplikowano",
        "candidatado", "already applied", "du hast dich beworben",
        "application submitted", "candidature envoyée", "votre candidature a été envoyée",
        "solicitud confirmada", "candidatura inviata"
    ]

    def __init__(self, resume_path=None, phone_number=None, profile_name="default"):
        self.bm = BrowserManager()
        self.profile_name = profile_name
        self.driver = self.bm.get_driver(headless=False, profile_name=profile_name)  # Always visible for safety
        self.resume_path = resume_path
        self.phone_number = phone_number or ""
        self.applied_count = 0
        self.max_applications = 50  # Safety limit per session
        self.db = DataManager()  # For question-answer config
        self.current_job_title = ""  # For logging unknown questions
        self.current_company = ""
        self.session_unknown_questions = []  # Track unknown questions for user prompt
    
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
    
    def is_easy_apply_xing(self, job_url=None):
        """Check if a Xing job has Easy Apply (not external redirect)."""
        if job_url:
            print(f"[Xing] Checking Easy Apply: {job_url}")
            self.driver.get(job_url)
            self.random_sleep(2, 4)
        
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
            "apply on xing"
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
            # Ferrari: Shorter wait if we already know it's a valid link
            self.random_sleep(1.5, 3)
        
        # 1. Find and Click "Easy Apply" Button
        # Optimized: Use a combined selector for all patterns to find it in one go
        combined_selector = "button.jobs-apply-button, button[aria-label*='Easy Apply'], .jobs-apply-button--top-card button, button.jobs-apply-button--top-card, .jobs-s-apply button, div.jobs-apply-button--top-card button, .jobs-unified-top-card button.jobs-apply-button"
        
        clicked = self.click_element(combined_selector, timeout=5)
        
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
                                                print(f"[LinkedIn] ✅ Selected dropdown option for '{label_text}'")
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
                            "website", "personal website", "portfolio",
                            "linkedin profile", "linkedin",
                            "employee's name", "employee name", "referral",
                            "referred by", "who referred"
                        ]
                        
                        for skip_q in skip_questions:
                            if skip_q in label_lower:
                                default_answer = "N/A"
                                break
                        
                        if default_answer:
                            input_el.clear()
                            input_el.send_keys(default_answer)
                            print(f"[LinkedIn] Filled '{label_text}' → '{default_answer}' (default)")

                            # Also handle typeahead for default answers
                            try:
                                self.random_sleep(0.5, 1.0)
                                if "city" in label_text.lower() or "location" in label_text.lower():
                                    options = self.driver.find_elements(By.CSS_SELECTOR, ".artdeco-typeahead__result, [role='option'], .artdeco-typeahead__results-list li")
                                    for opt in options:
                                        if opt.is_displayed():
                                            try: opt.click()
                                            except: self.driver.execute_script("arguments[0].click();", opt)
                                            print(f"[LinkedIn] ✅ Selected dropdown option for default '{label_text}'")
                                            break
                            except:
                                pass
                        else:
                            # Interactive mode: Alert user and wait for them to fill the field
                            print(f"[LinkedIn] 🔔 UNKNOWN QUESTION: '{label_text}'")
                            print(f"[LinkedIn] ⏳ Please fill this field on LinkedIn. Bot will capture your answer...")
                            
                            # Interactive mode: Alert user and wait for them to fill the field
                            print(f"[LinkedIn] 🔔 UNKNOWN QUESTION: '{label_text}'")

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
                            print('\a')
                            
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
                                        print(f"[LinkedIn] ✅ Captured answer: '{user_answer}'")
                                        
                                        # Save to Q&A config automatically
                                        self.db.save_qa_answer(label_text, user_answer)
                                        print(f"[LinkedIn] 💾 Saved Q&A: '{label_text}' → '{user_answer}'")

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
                                print(f"[LinkedIn] ⚠️ No answer provided, logging as unknown...")
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
                            label_el = parent.find_element(By.CSS_SELECTOR, "label, legend, span.t-bold")
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
                    
                    print(f"[LinkedIn] Dropdown found: '{label_text}'")
                    
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
                                print(f"[LinkedIn] ✅ Selected saved answer '{opt.text}' for '{label_text}'")
                                matched = True
                                break
                        if matched:
                            continue
                    
                    # No saved answer - use smart selection and log the question
                    print(f"[LinkedIn] ⚠️ No saved answer for: '{label_text}', using smart selection...")
                    self.db.log_unknown_question(label_text, self.current_job_title, self.current_company)
                    
                    # Smart selection: prefer higher values, avoid "Gar nicht", "Keine", "0"
                    negative_terms = ['gar nicht', 'keine', 'kein', 'never', 'none', 'not at all', '0 ']
                    prefer_terms = ['5+', '10+', '3+', '4+', 'more than', 'über', 'ja', 'yes', 'expert', 'erfahren', 'native', 'bilingual', 'immer', 'always']
                    
                    selected = False
                    # First try to find a preferred option
                    for opt in options[1:]:
                        opt_text = opt.text.lower().strip()
                        if any(p in opt_text for p in prefer_terms):
                            sel_obj.select_by_visible_text(opt.text)
                            print(f"[LinkedIn] Selected preferred '{opt.text}' for dropdown")
                            selected = True
                            break
                    
                    # If no preferred, select last non-negative option (usually highest value)
                    if not selected:
                        for opt in reversed(list(options[1:])):  # Reverse to get highest first
                            opt_text = opt.text.lower().strip()
                            if opt_text and not any(n in opt_text for n in negative_terms):
                                sel_obj.select_by_visible_text(opt.text)
                                print(f"[LinkedIn] Selected '{opt.text}' for dropdown (highest)")
                                selected = True
                                break
                    
                    # Fallback: just select first if nothing else worked
                    if not selected and len(options) > 1:
                        sel_obj.select_by_index(1)
                        print(f"[LinkedIn] Selected fallback '{options[1].text}' for dropdown")
                except Exception as e:
                    print(f"[LinkedIn] Dropdown error: {str(e)[:50]}")
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
                    try:
                        legend = group.find_element(By.CSS_SELECTOR, "legend, span.t-bold, .fb-dash-form-element__label")
                    except:
                        pass
                    
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
                                        print(f"[LinkedIn] Selected '{label_el.text}' for '{question_text}'")
                                        options_found = True
                                        break
                                except: continue

                        if not options_found:
                            # Smart selection: prefer "Ja/Yes" over "Nein/No"
                            yes_labels = ['ja', 'yes', 'agree', 'willing', 'immer']
                            for radio in radios:
                                try:
                                    label_el = radio.find_element(By.XPATH, "./following-sibling::label | ../label")
                                    if any(y in label_el.text.lower() for y in yes_labels):
                                        self.driver.execute_script("arguments[0].click();", radio)
                                        print(f"[LinkedIn] Selected 'Yes' option for '{question_text}'")
                                        options_found = True
                                        break
                                except: continue

                            if not options_found:
                                # Fallback to first option
                                self.driver.execute_script("arguments[0].click();", radios[0])
                                print(f"[LinkedIn] Auto-selected first option for '{question_text}'")
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
                                    print(f"[LinkedIn] Clicked button '{btn.text}' for '{question_text}'")
                                    btn_clicked = True
                                    break
                        
                        if not btn_clicked:
                            yes_labels = ['ja', 'yes', 'agree', 'willing', 'immer']
                            for btn in buttons:
                                if any(y in btn.text.lower() for y in yes_labels):
                                    btn.click()
                                    print(f"[LinkedIn] Clicked 'Yes' button for '{question_text}'")
                                    btn_clicked = True
                                    break

                            if not btn_clicked:
                                buttons[0].click()
                                print(f"[LinkedIn] Clicked first button for '{question_text}'")
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
        # Optimized: Combined selector
        combined_selector = "button[data-testid='apply-button'], a[data-testid='apply-button'], button.apply-button, a.apply-button, button[data-testid='nls-apply-button'], a[data-testid='nls-apply-button'], .apply-button-container button, div[class*='ApplyButton'] button"
        
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
                        print(f"[Xing] Clicked Apply button via XPath: {query}")
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
                    print("[Xing] Uploaded resume.")
                    self.random_sleep(1, 2)
                except Exception as e:
                    print(f"[Xing] Resume upload failed: {e}")
        
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
            "//button[contains(translate(., 'CONFIRM', 'confirm'), 'confirm')]"
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
            print(f"[Indeed] Checking Easy Apply: {job_url}")
            self.driver.get(job_url)
            self.random_sleep(3, 5)

        # Look for buttons that say "Schnellbewerbung" or "Easily Apply"
        try:
            page_source = self.driver.page_source.lower()
            if any(phrase in page_source for phrase in ["easily apply", "einfach bewerben", "schnellbewerbung"]):
                return True
        except: pass
        return False

    def apply_indeed(self, job_url, skip_detection=False):
        """Automates Indeed Schnellbewerbung."""
        if self.applied_count >= self.max_applications:
            return False, "Max applications reached.", False

        if not skip_detection:
            if not self.is_easy_apply_indeed(job_url):
                return False, "Not an Indeed Easy Apply job.", False
        else:
            self.driver.get(job_url)
            self.random_sleep(3, 5)

        # 1. Find and Click Apply Button
        # Optimized: Combined selector for non-xpath
        css_selector = "button.jobsearch-IndeedApplyButton-button, #indeedApplyButton, button[class*='IndeedApplyButton']"
        clicked = self.click_element(css_selector, timeout=5)

        if not clicked:
            # Fallback to XPath
            xpath_selectors = ["//button[contains(., 'Schnellbewerbung')]", "//button[contains(., 'Easily apply')]"]
            for sel in xpath_selectors:
                try:
                    btn = self.driver.find_element(By.XPATH, sel)
                    btn.click()
                    clicked = True
                    break
                except: continue

        if not clicked:
            return False, "Indeed Apply button not found.", False

        self.random_sleep(3, 5)

        # Indeed often uses an IFRAME for the application form
        # We need to switch to it if present
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                if "indeed" in (iframe.get_attribute("src") or "").lower():
                    self.driver.switch_to.frame(iframe)
                    print("[Indeed] Switched to application iframe.")
                    break
        except: pass

        # 2. Fill Fields (Multi-step form)
        max_steps = 10
        for step in range(max_steps):
            self.random_sleep(1, 2)

            # Check for success
            if "gelungen" in self.driver.page_source.lower() or "submitted" in self.driver.page_source.lower():
                print("[Indeed] ✓ Application submitted!")
                self.applied_count += 1
                self.driver.switch_to.default_content()
                return True, "Applied!", True

            # Handle Resume
            if self.resume_path:
                resume_btn = self.find_element_safe("input[type='file']")
                if resume_btn:
                    try:
                        resume_btn.send_keys(self.resume_path)
                        print("[Indeed] Uploaded resume.")
                    except: pass

            # Fill Text Fields
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='tel'], textarea")
            for inp in inputs:
                try:
                    if not inp.get_attribute("value"):
                        # Try to find label
                        label_text = ""
                        try:
                            label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{inp.get_attribute('id')}']")
                            label_text = label.text
                        except: pass

                        answer = self.db.get_answer_for_question(label_text) if label_text else None
                        if answer:
                            inp.send_keys(answer)
                except: pass

            # Click Continue / Submit
            continue_btn = self.find_element_safe("button[type='submit'], .ia-continue-button, //button[contains(., 'Weiter')]")
            if continue_btn:
                continue_btn.click()
                print(f"[Indeed] Step {step+1} continued.")
            else:
                break

        self.driver.switch_to.default_content()
        return False, "Stopped during form filling.", True

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
            print(f"[LiveApply] {msg}")
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
                        if any(ind in card_text for ind in self.APPLIED_INDICATORS):
                            log(f"   ⏭️ Already applied (via card text)")
                            results["skipped"].append({"title": "Unknown", "company": "Unknown", "reason": "Already applied"})
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
                    
                    # CHECK 1: Is "Beworben" (already applied) shown in the detail panel?
                    try:
                        # Scope to detail panel to avoid finding other cards' badges
                        detail_panel = self.find_element_safe(".jobs-search__job-details, .scaffold-layout__detail, .jobs-search-two-pane__details", timeout=3)
                        if detail_panel:
                            # Check for common "Applied" indicators in various languages
                            found_applied = False
                            panel_text = detail_panel.text.lower()
                            for indicator in self.APPLIED_INDICATORS:
                                if indicator in panel_text:
                                    found_applied = True
                                    break

                            if found_applied:
                                log(f"   ⏭️ Already applied (detected in details)")
                                results["skipped"].append({"title": title, "company": company, "reason": "Already applied"})
                                continue
                    except:
                        pass  # Not applied - good!
                    
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
                    try:
                        external_btn = self.driver.find_element(By.XPATH, 
                            "//button[contains(text(), 'Anwenden')] | //a[contains(text(), 'Anwenden')] | //span[text()='Anwenden']/ancestor::button")
                        if external_btn and external_btn.is_displayed():
                            log(f"   ⚠️ External apply job detected (filter might have dropped). Re-verifying Easy Apply filter...")
                            if self._ensure_linkedin_easy_apply_filter():
                                log("   ♻️ Filter re-applied. Skipping this job as it was likely a leftover.")

                            results["skipped"].append({"title": title, "company": company, "reason": "External apply"})
                            continue
                    except:
                        pass  # Not external - continue to Easy Apply
                    
                    # Find Easy Apply button with retry logic (EAB pattern)
                    easy_apply_btn = None
                    max_retries = 3
                    
                    for retry in range(max_retries):
                        try:
                            # Try by class name first (most reliable per EAB)
                            easy_apply_btn = self.driver.find_element(By.CLASS_NAME, 'jobs-apply-button')
                            if easy_apply_btn and easy_apply_btn.is_displayed():
                                break
                        except (StaleElementReferenceException, NoSuchElementException):
                            pass
                        
                        # Try other selectors
                        for sel in ["button[aria-label*='Easy Apply']", "button[aria-label*='Einfach bewerben']"]:
                            try:
                                easy_apply_btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                                if easy_apply_btn and easy_apply_btn.is_displayed():
                                    break
                            except:
                                continue
                        
                        if easy_apply_btn:
                            break
                        self.random_sleep(0.5, 1.0)
                    
                    if not easy_apply_btn:
                        log(f"   ⚠️ Easy Apply button not found (may be external)")
                        results["skipped"].append({"title": title, "company": company, "reason": "No Easy Apply"})
                        continue
                    
                    # Click Easy Apply button (with retry for stale element)
                    clicked = False
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
    
    def _process_linkedin_modal(self):
        """
        Process the LinkedIn Easy Apply modal and submit application.
        Based on EAB patterns: loop until submit button text found, use primary button class.
        """
        max_steps = 15
        # German + English submit button texts
        submit_texts = [
            'submit application', 'bewerbung senden', 'absenden', 
            'submit', 'senden', 'abschicken', 'bewerben'
        ]
        # German + English next/continue button texts (for recognition, not action)
        next_button_texts = [
            'next', 'weiter', 'further', 'continue', 'fortfahren',
            'review', 'überprüfen', 'prüfen', 'nächster', 'nächste'
        ]
        had_errors = False  # Track if we encountered errors
        consecutive_errors = 0  # Track consecutive validation errors
        last_step_with_error = -1
        
        for step in range(max_steps):
            self.random_sleep(1.0, 2.0)
            
            # Check for success message first
            try:
                success_indicators = [
                    "//*[contains(text(), 'Bewerbung gesendet')]",
                    "//*[contains(text(), 'Application sent')]",
                    "//*[contains(text(), 'successfully submitted')]",
                    "//*[contains(text(), 'erfolgreich')]",
                    "//*[contains(text(), 'Bewerbung wurde gesendet')]",
                    "//*[contains(text(), 'Ihre Bewerbung')]",
                    "//*[contains(text(), 'Your application')]",
                    "//*[contains(text(), 'wurde übermittelt')]"
                ]
                for xpath in success_indicators:
                    try:
                        self.driver.find_element(By.XPATH, xpath)
                        print("[LinkedIn] ✅ Application submitted successfully!")
                        # Close any confirmation modal
                        try:
                            dismiss = self.driver.find_element(By.CLASS_NAME, 'artdeco-modal__dismiss')
                            dismiss.click()
                        except:
                            pass
                        return True
                    except:
                        continue
            except:
                pass
            
            # Check if modal is still open
            modal_open = False
            try:
                modal = self.driver.find_element(By.CLASS_NAME, "jobs-easy-apply-modal__content")
                modal_open = True
            except:
                try:
                    modal = self.driver.find_element(By.CSS_SELECTOR, ".artdeco-modal")
                    modal_open = True
                except:
                    pass
            
            if not modal_open:
                # Modal closed - check if we had errors
                if had_errors:
                    print("[LinkedIn] ❌ Modal closed after errors - application likely failed")
                    return False
                else:
                    print("[LinkedIn] Modal closed, assuming success")
                    return True
            
            # Fill form fields on current page
            self._linkedin_fill_fields()
            
            # Find the primary action button (Next / Submit / Review)
            try:
                primary_btn = self.driver.find_element(By.CLASS_NAME, "artdeco-button--primary")
                button_text = primary_btn.text.lower()
                
                print(f"[LinkedIn] Step {step+1}: Button text = '{button_text}'")
                
                # Check if this is the submit button
                if any(submit_text in button_text for submit_text in submit_texts):
                    # Try to unfollow company first
                    try:
                        follow_checkbox = self.driver.find_element(By.XPATH,
                            "//label[contains(.,'to stay up to date with their page.') or contains(.,'folgen')]")
                        follow_checkbox.click()
                        print("[LinkedIn] Unfollowed company")
                    except:
                        pass
                    
                    # Click submit
                    self.random_sleep(0.5, 1.0)
                    primary_btn.click()
                    self.random_sleep(2.0, 3.0)
                    
                    # Check for errors after submit
                    error_messages = [
                        'enter a valid', 'file is required', 'make a selection',
                        'whole number', 'pflichtfeld', 'erforderlich', 'required'
                    ]
                    page_source = self.driver.page_source.lower()
                    if any(err in page_source for err in error_messages):
                        print("[LinkedIn] ⚠️ Form validation error detected")
                        had_errors = True
                        consecutive_errors += 1
                        if consecutive_errors >= 3:
                            print("[LinkedIn] ❌ Too many consecutive errors, giving up")
                            break
                        continue  # Try to fill again
                    
                    # Close confirmation dialogs
                    self.random_sleep(1.0, 2.0)
                    for dismiss_class in ['artdeco-modal__dismiss', 'artdeco-toast-item__dismiss']:
                        try:
                            self.driver.find_element(By.CLASS_NAME, dismiss_class).click()
                        except:
                            pass
                    
                    return True
                else:
                    # Click Next/Continue/Review
                    primary_btn.click()
                    self.random_sleep(1.5, 2.5)
                    
                    # Check for errors after clicking
                    error_messages = [
                        'enter a valid', 'file is required', 'make a selection',
                        'whole number', 'pflichtfeld', 'erforderlich'
                    ]
                    page_source = self.driver.page_source.lower()
                    if any(err in page_source for err in error_messages):
                        print("[LinkedIn] ⚠️ Validation error, filling fields again...")
                        had_errors = True
                        
                        # Track consecutive errors on same step
                        if step == last_step_with_error:
                            consecutive_errors += 1
                        else:
                            consecutive_errors = 1
                            last_step_with_error = step
                        
                        # If stuck on same step, give up
                        if consecutive_errors >= 3:
                            print("[LinkedIn] ❌ Stuck on validation errors, cannot proceed")
                            break
                        
                        self._linkedin_fill_fields()  # Try to fill again
                    else:
                        consecutive_errors = 0  # Reset on success
                        
            except Exception as e:
                print(f"[LinkedIn] No primary button found: {str(e)[:50]}")
                had_errors = True
                
                # Try to dismiss and fail
                if step > 5:
                    try:
                        dismiss = self.driver.find_element(By.CLASS_NAME, 'artdeco-modal__dismiss')
                        dismiss.click()
                        self.random_sleep(0.5, 1.0)
                        try:
                            confirm = self.driver.find_elements(By.CLASS_NAME, 'artdeco-modal__confirm-dialog-btn')
                            if confirm:
                                confirm[0].click()
                        except:
                            pass
                        return False
                    except:
                        pass
        
        # Max steps reached or gave up - try to dismiss
        print("[LinkedIn] ⚠️ Max steps reached or errors, dismissing modal")
        try:
            self.driver.find_element(By.CLASS_NAME, 'artdeco-modal__dismiss').click()
            self.random_sleep(0.5, 1.0)
            # Click confirm if discard dialog appears
            try:
                confirm = self.driver.find_elements(By.CLASS_NAME, 'artdeco-modal__confirm-dialog-btn')
                if confirm:
                    confirm[0].click()
            except:
                pass
        except:
            pass
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
                    page_text = self.driver.page_source.lower()
                    if any(ind in page_text for ind in self.APPLIED_INDICATORS):
                        log(f"   ⏭️ Already applied (UI) - skipping")
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
                    print(f"[LinkedIn] Easy Apply filter not active in UI (classes: {classes}, pressed: {pressed}), clicking it...")
                    try:
                        # Sometimes clicking the button itself doesn't work if it's a pill with an inner span
                        self.driver.execute_script("arguments[0].click();", filter_btn)
                    except Exception as e:
                        print(f"[LinkedIn] JS click failed: {e}")
                        filter_btn.click()

                    self.random_sleep(4, 6) # Wait for results to refresh

                    # Double check if it became active
                    try:
                        classes_after = filter_btn.get_attribute("class") or ""
                        if "selected" in classes_after.lower() or "active" in classes_after.lower():
                            print("[LinkedIn] Easy Apply filter successfully activated.")
                        else:
                            print(f"[LinkedIn] Warning: Easy Apply filter still doesn't look active after click (classes: {classes_after})")
                    except: pass

                    return True
                else:
                    print("[LinkedIn] Easy Apply filter is already active in UI.")
                    return True
            else:
                print("[LinkedIn] Could not find Easy Apply filter button in UI.")
                return False
        except Exception as e:
            print(f"[LinkedIn] Error ensuring Easy Apply filter: {e}")
            return False

    def close(self):
        """Clean up browser."""
        self.bm.close_driver(profile_name=self.profile_name)

