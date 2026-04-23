import os
import time
import tempfile
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from job_hunter.data_manager import DataManager
from job_hunter.mission_state import MissionProgress
from job_hunter.vision_core import VisionCore
from tools.logger import logger
from tools.browser_manager import BrowserManager
from tools.human_actions import type_human_like

def random_wait(min_sec=1, max_sec=3):
    time.sleep(random.uniform(min_sec, max_sec))

class JobApplier:
    def __init__(self, resume_path=None, phone_number=None, profile_name="default", headless=False, no_sandbox=False):
        self.resume_path = resume_path
        self.phone_number = phone_number
        self.db = DataManager()
        self.bm = BrowserManager()
        self.driver = self.bm.get_driver(headless=headless, profile_name=profile_name)
        self.vision = VisionCore()
        
        self.resume_text = self._extract_resume_text()
        
    def _extract_resume_text(self):
        if not self.resume_path or not os.path.exists(self.resume_path):
            return "No resume provided."
        try:
            if self.resume_path.lower().endswith('.pdf'):
                import pdfplumber
                with pdfplumber.open(self.resume_path) as pdf:
                    return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            else:
                with open(self.resume_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Failed to read resume: {e}")
            return "Failed to read resume."

    def apply(self, job_url, platform, skip_detection=True, job_title="", company=""):
        logger.info(f"🚀 [Vision] Batch applying to {company} - {job_title} at {job_url}")
        return self._vision_application_loop(job_url)

    def live_apply_linkedin(self, keyword, location, target_count=5, target_role="Auto", callback=None):
        logger.warning("Live Search Apply is not natively supported by the strict Vision API pipeline. Falls back to search UI navigation only.")
        return self._live_apply_vision("LinkedIn", f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}", target_count, callback)

    def live_apply_indeed(self, keyword, location, target_count=5, target_role="Auto", callback=None):
        return self._live_apply_vision("Indeed", f"https://de.indeed.com/jobs?q={keyword}&l={location}", target_count, callback)

    def live_apply_xing(self, keyword, location, target_count=5, target_role="Auto", callback=None):
        return self._live_apply_vision("Xing", f"https://www.xing.com/jobs/search?keywords={keyword}&location={location}", target_count, callback)

    def _live_apply_vision(self, platform, search_url, target_count, callback):
        if callback: callback(f"Starting {platform} live apply with Vision")
        # Opens search UI, delegates strictly to Vision to find job cards
        self.driver.get(search_url)
        random_wait(3, 5)
        # Vision could theoretically loop this, but without DOM it relies heavily on Gemini to detect 
        # unclicked job cards. We will rely on user clicking "submit/next" or the batch run.
        return {"checked": 1, "applied": [], "errors": [], "skipped": [], "unknown_questions": []}

    def _take_screenshot(self):
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        self.driver.save_screenshot(path)
        return path

    def _execute_vision_actions(self, actions):
        window_size = self.driver.get_window_size()
        viewport_w = window_size['width']
        viewport_h = window_size['height']
        
        for act in actions:
            action_type = act.get('type')
            reason = act.get('reason', 'None')
            coords = act.get('coordinates', [500, 500, 500, 500])
            
            # Sometimes models return malformed coords if no strict forcing is used
            if not isinstance(coords, list) or len(coords) != 4:
                logger.error(f"Malformed coords from Gemini: {coords}")
                continue
                
            ymin, xmin, ymax, xmax = coords
            
            y_center_1000 = (ymin + ymax) / 2
            x_center_1000 = (xmin + xmax) / 2
            
            x_px = int((x_center_1000 / 1000) * viewport_w)
            y_px = int((y_center_1000 / 1000) * viewport_h)
            
            # Provide boundary safety
            x_px = max(5, min(viewport_w - 5, x_px))
            y_px = max(5, min(viewport_h - 5, y_px))
            
            logger.info(f"👉 Vision Action [{action_type}]: {reason} at ({x_px}, {y_px})")
            
            try:
                if action_type == 'click':
                    action = ActionBuilder(self.driver)
                    action.pointer_action.move_to_location(x_px, y_px)
                    action.pointer_action.click()
                    action.perform()
                elif action_type == 'type':
                    text_to_type = act.get('text_to_type', '')
                    # Click field first to focus
                    action = ActionBuilder(self.driver)
                    action.pointer_action.move_to_location(x_px, y_px)
                    action.pointer_action.click()
                    action.perform()
                    random_wait(0.5, 1.0)
                    
                    try:
                        active_el = self.driver.switch_to.active_element
                        active_el.send_keys(Keys.CONTROL + "a")
                        active_el.send_keys(Keys.DELETE)
                        type_human_like(active_el, text_to_type)
                    except:
                        # Fallback click and raw JS insert if active element fails
                        action.pointer_action.move_to_location(x_px, y_px)
                        action.pointer_action.click()
                        action.perform()
                        self.driver.execute_script(f"document.activeElement.value = '{text_to_type}';")
                        
                elif action_type == 'scroll':
                    # Native scroll
                    self.driver.execute_script("window.scrollBy(0, window.innerHeight * 0.6);")
                elif action_type == 'pause':
                    logger.info("Vision requested a pause action.")
                    random_wait(2, 4)
                elif action_type == 'upload':
                    file_key = act.get('file_to_upload', 'resume')
                    file_path = ""
                    if file_key == 'cover_letter':
                        file_path = os.path.abspath("data/generated_cover_letter.pdf")
                    else:
                        file_path = os.path.abspath(self.resume_path)

                    if os.path.exists(file_path):
                        # Find the input element at coords or via active element
                        # Usually, clicking the upload button opens a dialog, 
                        # but in Selenium we MUST send keys to the hidden <input type='file'>
                        # Since we are VISION-based, we'll try to find the nearest file input
                        # or just send to the active element if it's the file input.
                        try:
                            # 1. Try to find an input type=file that is "near" the clicked coordinates
                            # For simplicity in Vision, we often just send to the active element if it's an input
                            # OR we find ALL file inputs and send the path to them if there's only one.
                            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                            if len(file_inputs) == 1:
                                file_inputs[0].send_keys(file_path)
                                logger.info(f"📤 Uploaded {file_key} to the only available file input.")
                            else:
                                # Fallback: type path into the focused element (sometimes works with custom dialogs)
                                active_el = self.driver.switch_to.active_element
                                active_el.send_keys(file_path)
                                logger.info(f"📤 Uploaded {file_key} to active element.")
                        except Exception as upload_err:
                            logger.error(f"Upload failed: {upload_err}")
                    else:
                        logger.error(f"Upload file not found: {file_path}")
                    
                random_wait(1, 2)
            except Exception as e:
                logger.error(f"Action {action_type} failed: {e}")

    def _vision_application_loop(self, url):
        self.driver.get(url)
        random_wait(3, 5)
        
        max_steps = 25
        step = 0
        
        while step < max_steps:
            step += 1
            ss_path = self._take_screenshot()
            
            decision = self.vision.get_vision_decision(ss_path, self.resume_text)
            
            try: os.remove(ss_path)
            except: pass
            
            if not decision or decision.get('status') == 'error':
                logger.error("Vision API Error or invalid JSON returned.")
                return False, "Vision API error.", False
                
            logger.info(f"👁️ Vision [Step {step}]: {decision.get('page_purpose')} | Intervention: {decision.get('human_intervention_needed')}")
            
            if decision.get('status') == 'success':
                return True, "Application successful (Vision detected confirmation).", True
                
            if decision.get('human_intervention_needed'):
                reason = decision.get('intervention_reason') or "Manual review needed. Click Submit in browser."
                logger.warning(f"⏸️ Vision paused. Reason: {reason}")
                
                # Signal to UI
                progress = MissionProgress.load()
                if progress.is_active:
                    progress.update(pending_question=reason)
                
                # Halt executing actions until human resolves via UI
                wait_intervals = 0
                max_intervals = 300 # 10 mins
                while progress.pending_question is not None and wait_intervals < max_intervals:
                    random_wait(2, 2)
                    progress = MissionProgress.load()
                    wait_intervals += 1
                    
                if wait_intervals >= max_intervals:
                    return False, "Timed out waiting for human intervention.", False
                    
                logger.info("▶️ Human resolved intervention. Resuming vision loop.")
                continue
                
            actions = decision.get('actions', [])
            if not actions:
                logger.warning("No actions returned but not success. Assuming human intervention required to prevent hang.")
                progress = MissionProgress.load()
                if progress.is_active:
                    progress.update(pending_question="Vision AI got stuck with no actions. Please intervene manually in browser.")
                return False, "Vision AI got stuck.", False
                
            self._execute_vision_actions(actions)
            random_wait(2, 4)
            
        return False, "Vision max steps reached without success.", False

    def close(self):
        pass
