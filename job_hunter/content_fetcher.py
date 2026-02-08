
import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tools.browser_manager import BrowserManager

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from langdetect import detect

class ContentFetcher:
    def __init__(self):
        self.bm = BrowserManager()
        # Use visible browser to avoid detection if possible, or headless if preferred.
        # User implies visible might be better for manual intervention, but "Fetch Details" implies automation.
        # We'll use headless=False to be safe with auth/blocks, or reuse existing session.
        self.driver = self.bm.get_driver(headless=False) 

    def _handle_popups(self, driver):
        """Attempts to close popups (like Indeed Google Login) via ESC or Clicks."""
        try:
            # 1. Blind ESC key
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5)
            
            # 2. Indeed Google Login Close Button
            try:
                # Often in an iframe or just a div
                close_btns = driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Close'], button[class*='close'], button[id*='close']")
                for btn in close_btns:
                    if btn.is_displayed():
                        btn.click()
            except: pass
        except: pass

    def _expand_content(self, driver):
        """Attempts to click 'See more' / 'Read more' type buttons."""
        try:
            # Common patterns for expand buttons
            expand_selectors = [
                "button[class*='show-more']", 
                "button[class*='read-more']",
                ".job-description-toggle", 
                "[aria-label*='Click to see more']",
                ".file-text-icon" # Sometimes icons
            ]
            for sel in expand_selectors:
                try:
                    btns = driver.find_elements(By.CSS_SELECTOR, sel)
                    for btn in btns:
                        if btn.is_displayed():
                            driver.execute_script("arguments[0].click();", btn)
                            time.sleep(1) # Wait for expansion
                except: pass
        except: pass

        # Text-based approach (Robust for "Mehr", "See more")
        try:
             expand_texts = ["see more", "show more", "mehr anzeigen", "weiterlesen", "read more", "more", "mehr"]
             elements = driver.find_elements(By.TAG_NAME, "button")
             
             for el in elements:
                 try:
                     if not el.is_displayed(): continue
                     txt = el.text.strip().lower()
                     
                     # Check exact or contained match
                     if any(ex == txt or (len(txt) < 20 and ex in txt) for ex in expand_texts):
                          driver.execute_script("arguments[0].click();", el)
                          time.sleep(0.5)
                 except: pass
        except: pass

    def fetch_details(self, job_url, platform):
        """
        Navigates to the URL and attempts to scrape:
        - Full Description (Rich Description)
        """
        if not job_url or "http" not in job_url:
            return None

        # Reuse existing driver
        driver = self.bm.get_driver(headless=False)
        
        try:
            driver.get(job_url)
            # Randomized sleep to mimic human behavior
            time.sleep(random.uniform(2, 4))
            
            # Handle Popups (Indeed especially)
            self._handle_popups(driver)
            
            # Attempt to expand content
            self._expand_content(driver)
            
            data = {
                "description": ""
            }
            
            p_lower = platform.lower()
            
            # --- LinkedIn ---
            if "linkedin" in p_lower:
                try:
                    # Description
                    desc_el = None
                    potential_classes = ["jobs-description__content", "job-details-jobs-unified-top-card__primary-description", "job-details"]
                    for cls in potential_classes:
                        try:
                            el = driver.find_element(By.CLASS_NAME, cls)
                            if el and len(el.text) > 100: 
                                desc_el = el
                                break
                        except: pass
                    
                    if not desc_el: desc_el = driver.find_element(By.ID, "job-details")
                    if desc_el: data["description"] = desc_el.text
                except:
                    # Public View Fallback
                    try:
                        desc_el = driver.find_element(By.CLASS_NAME, "show-more-less-html__markup")
                        if desc_el: data["description"] = desc_el.text
                    except: pass
            
            # --- Indeed ---
            elif "indeed" in p_lower:
                try:
                    # Wait for page to fully load
                    time.sleep(3)
                    
                    # Try multiple selectors - Indeed changes these frequently
                    desc_selectors = [
                        "#jobDescriptionText",
                        "[id*='jobDescription']",
                        ".jobsearch-JobComponent-description",
                        ".jobsearch-jobDescriptionText",
                        "[data-testid='job-description']",
                        ".job-description"
                    ]
                    
                    desc_el = None
                    for selector in desc_selectors:
                        try:
                            el = driver.find_element(By.CSS_SELECTOR, selector)
                            if el and len(el.text) > 50:
                                desc_el = el
                                print(f"[Indeed] Found description with selector: {selector}")
                                break
                        except:
                            continue
                    
                    # Fallback: try to find any large text block
                    if not desc_el:
                        try:
                            # Sometimes the description is in the main content area
                            main_area = driver.find_element(By.CSS_SELECTOR, "main, [role='main'], #main-content")
                            if main_area and len(main_area.text) > 100:
                                desc_el = main_area
                                print("[Indeed] Using main content area as fallback")
                        except:
                            pass
                    
                    if desc_el:
                        data['description'] = desc_el.text
                    else:
                        print("[Indeed] Could not find job description element")
                except Exception as e:
                    print(f"[Indeed] Error fetching details: {e}")
                
            # --- Stepstone ---
            elif "stepstone" in p_lower:
                try:
                    # Description
                    desc_selectors = [
                        "[data-testid='job-description-content']",
                        "[data-testid='job-description']",
                        ".js-app-ld-ContentBlock",
                        "section.listing-content",
                        ".job-description",
                        "article"
                    ]

                    desc_el = None
                    for selector in desc_selectors:
                        try:
                            el = driver.find_element(By.CSS_SELECTOR, selector)
                            if el and len(el.text) > 50:
                                desc_el = el
                                print(f"[Stepstone] Found description with selector: {selector}")
                                break
                        except:
                            continue

                    if desc_el:
                        data['description'] = desc_el.text
                    else:
                        # Fallback to article or body
                        try:
                            article = driver.find_element(By.TAG_NAME, "article")
                            data['description'] = article.text
                        except:
                            body = driver.find_element(By.TAG_NAME, "body")
                            data['description'] = body.text
                except Exception as e:
                    print(f"[Stepstone] Error fetching details: {e}")
            
            # --- ZipRecruiter ---
            elif "zip" in p_lower:
                try:
                    # Description
                    try:
                        desc_container = driver.find_element(By.CLASS_NAME, "job_description")
                        data['description'] = desc_container.text
                    except:
                        data['description'] = driver.find_element(By.TAG_NAME, "body").text
                except: pass

            # --- Xing ---
            elif "xing" in p_lower:
                try:
                    # Company Extraction (Priority)
                    try:
                        # 1. Header Company Name (best)
                        c_el = driver.find_element(By.CSS_SELECTOR, "[data-testid='header-company-name']")
                        data['company'] = c_el.text.strip()
                    except:
                        try:
                            # 2. Link with /pages/
                            company_link = driver.find_element(By.XPATH, "//a[contains(@href, '/pages/') or contains(@href, '/companies/')]")
                            c_name = company_link.text.strip()
                            if len(c_name) > 2 and "kununu" not in c_name.lower():
                                data['company'] = c_name
                        except: pass

                    # Description
                    try:
                        # 1. Specific container
                        desc_el = driver.find_element(By.CSS_SELECTOR, "[class*='html-description'], [data-testid='job-description-content']")
                        data['description'] = desc_el.text
                    except:
                        try:
                            # 2. Main fallback
                            main = driver.find_element(By.TAG_NAME, "main")
                            data['description'] = main.text
                        except:
                            data['description'] = driver.find_element(By.TAG_NAME, "body").text
                except: pass

            # --- Universal Fallbacks ---
            
            # 1. Content Fallback
            if not data["description"] or len(data["description"]) < 50:
                try:
                    main = driver.find_element(By.TAG_NAME, "main")
                    data['description'] = main.text
                except:
                    try:
                         body = driver.find_element(By.TAG_NAME, "body")
                         data['description'] = body.text[:8000]
                    except: pass


            # --- CLEANING ---
            data['description'] = self._clean_text(data['description'], platform)

            # --- LANGUAGE DETECTION ---
            data['language'] = "en" # Default
            try:
                if data['description'] and len(data['description']) > 50:
                     lang = detect(data['description'])
                     data['language'] = lang
            except: pass

            return data

        except Exception as e:
            print(f"Error fetching {job_url}: {e}")
            return None

    def _clean_text(self, text, platform):
        """Removes common garbage text from scraped content."""
        if not text: return ""
        
        # General Cleaning
        text = text.strip()
        
        # --- LinkedIn Specifics ---
        if "linkedin" in platform.lower():
            # 1. Remove Top Noise
            # "About the job" usually marks the start of real content
            if "About the job" in text:
                text = text.split("About the job")[-1]
            elif "Job description" in text:
                text = text.split("Job description")[-1]
                
            # 2. Remove Bottom Noise / Footer
            # "About the company" usually marks the end
            if "About the company" in text:
                text = text.split("About the company")[0]
            
            # 3. Remove specific phrases
            garbage_phrases = [
                "See how you compare to", 
                "Promoted by hirer", 
                "Responses managed off LinkedIn", 
                "Apply", 
                "Save", 
                "\u2026 more", # Ellipsis
                "... more",
                "Show more", 
                "Show less",
                "Try Premium for",
                "Access exclusive applicant insights",
                "Set alert for similar jobs"
            ]
            
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if not line: continue
                
                is_garbage = False
                for phrase in garbage_phrases:
                    if phrase.lower() in line.lower():
                        is_garbage = True
                        break
                
                if not is_garbage:
                    cleaned_lines.append(line)
            
            text = "\n".join(cleaned_lines)
            


        # --- Xing Specifics ---
        if "xing" in platform.lower():
            start_markers = ["About this job", "Über diesen Job", "Stellenbeschreibung", "Aufgaben:"]
            end_markers = ["About the company", "Über das Unternehmen", "Salary forecast", "Similar jobs", "Das bieten wir", "Got these skills, too?", "Skills", "Dein Profil"]
            noise_phrases = [
                "Earn up to", "Posted", "Salary", "Be an early applicant", "Visit employer website", 
                "Save job", "Data Analysis", "Salary expectations", "Employment type:",
                "Full-time", "On-site", "Home office", " €", "(XING estimate)", "Apply", "Bewerben"
            ]
            
            lines = text.split('\n')
            cleaned_lines = []
            started = False
            has_start_marker = any(m in text for m in start_markers)
            
            for line in lines:
                line = line.strip()
                if not line: continue
                
                if not started and has_start_marker:
                    if any(m in line for m in start_markers):
                        started = True
                        cleaned_lines.append(line)
                    continue
                
                if any(m in line for m in end_markers):
                    if "About the company" in line or "Salary forecast" in line or "Similar jobs" in line or "Got these skills, too?" in line:
                        break
                
                is_noise = False
                if len(line) < 3: is_noise = True
                if any(p in line for p in noise_phrases): is_noise = True
                if not has_start_marker and ("Yesterday" in line or "Posted" in line): is_noise = True
                
                if not is_noise:
                    cleaned_lines.append(line)
            
            text = "\n".join(cleaned_lines)
            
        return text



    def close(self):
        """Closes the browser instance explicitly."""
        self.bm.close_driver()
