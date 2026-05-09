from tools.logger import logger
import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tools.browser_manager import BrowserManager

class BrowserLLM:
    """Automates LLM interaction via browser tabs to save on API costs."""

    PROVIDERS = {
        "ChatGPT": "https://chatgpt.com/",
        "Gemini": "https://gemini.google.com/app",
        "Copilot": "https://copilot.microsoft.com/"
    }

    def __init__(self, provider="ChatGPT", profile_name="llm_profile", headless=False):
        self.provider = provider if provider in self.PROVIDERS else "ChatGPT"
        self.profile_name = profile_name
        self.headless = headless
        self.bm = BrowserManager()
        self.driver = self.bm.get_driver(headless=headless, profile_name=profile_name)
        self.tab_handle = None

    def _handle_cookies(self):
        """Attempts to click 'Accept' on common cookie banners to clear the view."""
        # Common "Accept" button selectors
        selectors = [
            "button[id='onetrust-accept-btn-handler']",
            "button#accept-all",
            "button.accept-all",
            "button[aria-label*='Accept all']",
            "button[aria-label*='Allow all']",
            "#allow-all",
            ".accept-cookies"
        ]
        xpath_selectors = [
            "//button[contains(text(), 'Accept all')]",
            "//button[contains(text(), 'Allow all')]",
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Alle akzeptieren')]",
            "//button[contains(text(), 'Akzeptieren')]"
        ]

        for sel in selectors:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed():
                    btn.click()
                    return True
            except: pass

        for xpath in xpath_selectors:
            try:
                btn = self.driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    btn.click()
                    return True
            except: pass
        return False

    def _ensure_tab(self):
        """Ensure we have a tab open for the provider."""
        url = self.PROVIDERS[self.provider]

        # Ensure we are using the correct driver for this profile
        self.driver = self.bm.get_driver(headless=self.headless, profile_name=self.profile_name)

        # 1. Check if we already have a tab for this provider
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if url in self.driver.current_url:
                self.tab_handle = handle
                self._handle_cookies()
                return

        # 2. Look for ANY blank/new tab to reuse
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if self.driver.current_url in ["about:blank", "data:,", "chrome://newtab/"]:
                self.driver.get(url)
                self.tab_handle = handle
                self._wait_for_page_load()
                return

        # 3. Otherwise, open a new tab
        self.driver.execute_script(f"window.open('{url}', '_blank');")
        time.sleep(1) # Brief pause for tab to open
        self.tab_handle = self.driver.window_handles[-1]
        self.driver.switch_to.window(self.tab_handle)
        self._wait_for_page_load()

    def _handle_overlays(self):
        """Internal helper to clear common ChatGPT/Gemini overlays and banners."""
        try:
            # 1. Cookies
            self._handle_cookies()

            # 2. ChatGPT specific overlays
            if self.provider == "ChatGPT":
                # Handle various guest mode/login prompts
                overlay_selectors = [
                    "//button[contains(., 'Start chatting')]",
                    "//button[contains(., 'Stay in guest mode')]",
                    "//button[contains(., 'Dismiss')]",
                    "//div[@role='dialog']//button[aria-label='Close']",
                    "//button[contains(., 'Maybe later')]"
                ]

                for xpath in overlay_selectors:
                    try:
                        btns = self.driver.find_elements(By.XPATH, xpath)
                        if btns and btns[0].is_displayed():
                            btns[0].click()
                            time.sleep(1)
                    except: pass

                # "Join ChatGPT" Close button (CSS)
                try:
                    join_close = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Close']")
                    if join_close and join_close[0].is_displayed():
                        join_close[0].click()
                        time.sleep(1)
                except: pass

            # 3. Gemini specific overlays
            elif self.provider == "Gemini":
                chat_now = self.driver.find_elements(By.XPATH, "//span[contains(text(), 'Chat now')]")
                if chat_now:
                    chat_now[0].click()
                    time.sleep(1)
        except:
            pass

    def _wait_for_page_load(self):
        """Waits for the LLM page to load specifically for prompt area."""
        try:
            wait = WebDriverWait(self.driver, 20)

            # Detect and handle 431 Request Header Fields Too Large or other browser errors
            for _ in range(2): # Try recovery up to twice
                try:
                    # Check both page text and title for error markers
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    page_title = self.driver.title.lower()

                    if "431" in page_text or "too large" in page_text or "431" in page_title:
                        logger.warning("Detected 431 Error (Headers too large). Performing deep reset...")

                        # 1. Clear everything
                        self.driver.delete_all_cookies()
                        try:
                            self.driver.execute_script("window.localStorage.clear();")
                            self.driver.execute_script("window.sessionStorage.clear();")
                        except: pass # Might fail on native error pages

                        # 2. Hard navigation to about:blank first to truly clear the view
                        self.driver.get("about:blank")
                        time.sleep(1)

                        # 3. Navigate back to provider
                        url = self.PROVIDERS[self.provider]
                        if self.provider == "ChatGPT": url = "https://chatgpt.com/?model=auto"
                        self.driver.get(url)
                        time.sleep(5)
                        continue
                    break
                except Exception as e:
                    # If we can't even read the body, might be a hard browser crash or restricted page
                    if "431" in self.driver.title:
                         self.driver.delete_all_cookies()
                         self.driver.get("about:blank")
                         time.sleep(1)
                         self.driver.get(self.PROVIDERS[self.provider])
                         time.sleep(5)
                         continue
                    break

            self._handle_overlays()

            if self.provider == "ChatGPT":
                wait.until(EC.presence_of_element_located((By.ID, "prompt-textarea")))
            elif self.provider == "Gemini":
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[contenteditable='true']")))
            elif self.provider == "Copilot":
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))

            # Brief extra pause for stable interaction
            time.sleep(2)
        except Exception as e:
            logger.info(f"Page load wait timed out or failed: {e}")
            time.sleep(5)

    def close_tab(self):
        """Closes the tab used for analysis if it's still open.
        If it's the last tab, it stays open to avoid exiting the browser process."""
        try:
            # First check if the driver is still alive
            if not self.bm.is_driver_alive():
                self.tab_handle = None
                return
                
            handles = self.driver.window_handles
            if self.tab_handle and self.tab_handle in handles:
                if len(handles) > 1:
                    self.driver.switch_to.window(self.tab_handle)
                    self.driver.close()
                    # Switch back to whatever is left
                    remaining = self.driver.window_handles
                    if remaining:
                        self.driver.switch_to.window(remaining[0])
                else:
                    # Last tab - navigate to about:blank to clear the view but keep process alive
                    self.driver.get("about:blank")
            self.tab_handle = None
        except Exception as e:
            logger.info(f"Error closing tab: {e}")
            self.tab_handle = None

    def quit(self):
        """FORCE closes the entire browser associated with this LLM instance."""
        try:
            self.bm.close_driver(profile_name=self.profile_name)
        except Exception as e:
            logger.info(f"Error quitting browser: {e}")



    def new_chat(self):
        """Attempts to start a new chat session by navigating the current tab to the base provider URL."""
        try:
            url = self.PROVIDERS[self.provider]
            if self.provider == "ChatGPT":
                url = "https://chatgpt.com/?model=auto"
            
            self._ensure_tab()
            self.driver.switch_to.window(self.tab_handle)
            
            # Navigate to the fresh URL
            self.driver.get(url)
            self._wait_for_page_load()
            return True
        except Exception as e:
            logger.warning(f"Failed to start new chat via navigation: {e}")
            # Fallback to hard refresh
            try:
                self.driver.refresh()
                time.sleep(3)
            except: pass
        return False

    def ask(self, prompt, timeout=120, done_signal=None):
        """Sends prompt and waits for response."""
        self._ensure_tab()

        # Consistent check for overlays before each prompt
        self._handle_overlays()

        # Pre-check for login wall, but only if we can't find the prompt area
        current_url = self.driver.current_url.lower()
        has_prompt = False
        try:
            if self.provider == "ChatGPT":
                has_prompt = len(self.driver.find_elements(By.ID, "prompt-textarea")) > 0
            elif self.provider == "Gemini":
                has_prompt = len(self.driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true']")) > 0
        except: pass

        if not has_prompt and ("login" in current_url or "auth" in current_url or "sign-in" in current_url):
             return f"ERROR: Browser is stuck on a login/auth page ({current_url}). Please log in using the 'Login to AI' button in the sidebar."

        if self.provider == "ChatGPT":
            return self._ask_chatgpt(prompt, timeout, done_signal=done_signal)
        elif self.provider == "Gemini":
            return self._ask_gemini(prompt, timeout)
        elif self.provider == "Copilot":
            return self._ask_copilot(prompt, timeout)

        return "Provider not implemented."

    def _ask_chatgpt(self, prompt, timeout, done_signal=None):
        # Default done_signal for job analysis JSON. Callers can override (e.g. ']' for plain arrays).
        if done_signal is None:
            done_signal = '"status"'
        try:
            # Check for barriers (login walls, rate limits, guest mode blocks)
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                prompt_exists = len(self.driver.find_elements(By.ID, "prompt-textarea")) > 0
                
                if not prompt_exists:
                    if "431" in page_text or "too large" in page_text or "431" in self.driver.title:
                        logger.warning("Detected 431 Error during prompt. Clearing state and reloading...")
                        self.driver.delete_all_cookies()
                        try:
                            self.driver.execute_script("window.localStorage.clear();")
                        except: pass
                        self.driver.get("about:blank")
                        time.sleep(1)
                        self.driver.get("https://chatgpt.com/?model=auto")
                        time.sleep(5)
                        self._wait_for_page_load()
                        # Retry once after clearing
                        prompt_exists = len(self.driver.find_elements(By.ID, "prompt-textarea")) > 0
                        if not prompt_exists:
                             return "ERROR: ChatGPT 431 Header Error persisted after state clear. Please restart the app."

                    if "log in" in page_text and "sign up" in page_text:
                        return "ERROR: ChatGPT is asking for login. Guest mode might be restricted. Please use 'Login to AI' to set up a session."
                    if "too many requests" in page_text or "reached your limit" in page_text:
                        return "ERROR: ChatGPT rate limit reached. Please wait or log in to a ChatGPT Plus account."
                    if "something went wrong" in page_text:
                        self.driver.refresh()
                        time.sleep(5)

                self._handle_overlays()
            except:
                pass
                
            # Find prompt area
            wait = WebDriverWait(self.driver, 20)
            
            prompt_selectors = [
                (By.ID, "prompt-textarea"),
                (By.CSS_SELECTOR, "div[contenteditable='true']"),
                (By.CSS_SELECTOR, "textarea[placeholder*='Message']")
            ]
            
            text_area = None
            for by, sel in prompt_selectors:
                try:
                    text_area = self.driver.find_element(by, sel)
                    if text_area.is_displayed():
                        break
                except:
                    pass
            
            if not text_area:
                text_area = wait.until(EC.presence_of_element_located((By.ID, "prompt-textarea")))

            # Use JS to set value for large prompts (faster and more reliable)
            self.driver.execute_script("""
                var el = arguments[0];
                el.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
                document.execCommand('insertText', false, arguments[1]);
            """, text_area, prompt)

            time.sleep(1)

            # Force focus before sending
            self.driver.execute_script("arguments[0].focus();", text_area)
            time.sleep(0.5)

            # Try to click the send button via JS (immune to interactable errors)
            sent = self.driver.execute_script("""
                var btns = document.querySelectorAll("button[data-testid='send-button'], button[aria-label*='Send']");
                for(var i=0; i<btns.length; i++) {
                    if(!btns[i].disabled) {
                        btns[i].click();
                        return true;
                    }
                }
                return false;
            """)

            if not sent:
                try:
                    text_area.send_keys(Keys.ENTER)
                except:
                    pass # If this fails, we will timeout and retry

            # Wait for response to finish: page text length stops growing for 3 seconds
            start_time = time.time()
            last_len = 0
            stable_count = 0
            while time.time() - start_time < timeout:
                try:
                    # Click 'Continue generating' if it appears
                    continue_btns = self.driver.find_elements(By.XPATH, "//button[contains(., 'Continue generating')]")
                    if continue_btns and continue_btns[0].is_displayed():
                        continue_btns[0].click()
                        time.sleep(2)
                        stable_count = 0
                        continue

                    # Fast exit: ChatGPT generation finishes when the stop button disappears
                    # and either a new send button appears or the response contains our done_signal
                    is_generating = self.driver.execute_script("""
                        return document.querySelector("button[aria-label='Stop generating'], button[data-testid='stop-button']") !== null;
                    """)
                    
                    if not is_generating and stable_count > 0:
                        # Check if done signal is in the last response
                        if done_signal:
                            has_signal = self.driver.execute_script(f"""
                                var resps = document.querySelectorAll('.markdown');
                                if (resps.length > 0) {{
                                    return resps[resps.length - 1].innerText.includes('{done_signal}');
                                }}
                                return false;
                            """)
                            if has_signal:
                                break

                    # Fallback: Get the full visible page text length
                    cur_len = self.driver.execute_script("return document.body.innerText.length;")
                    if cur_len == last_len and cur_len > 200:
                        stable_count += 1
                        if stable_count >= 3:  # Stable for 3 consecutive checks (~6s) → done
                            break
                    else:
                        stable_count = 0
                    last_len = cur_len
                except:
                    pass
                time.sleep(2)

            # Attempt to extract pure code block content first (most reliable for JSON)
            code_text = self.driver.execute_script("""
                var codes = document.querySelectorAll('code');
                if (codes.length > 0) {
                    return codes[codes.length - 1].textContent;
                }
                return "";
            """)
            
            if code_text and len(code_text) > 10 and done_signal in code_text:
                return code_text

            # Fallback to the last markdown response block
            md_text = self.driver.execute_script("""
                var resps = document.querySelectorAll('.markdown');
                if (resps.length > 0) {
                    return resps[resps.length - 1].innerText;
                }
                return "";
            """)
            
            if md_text and len(md_text) > 10:
                return md_text

            # Absolute fallback
            page_text = self.driver.execute_script("return document.body.innerText;")
            if page_text and len(page_text) > 10:
                return page_text

            return "ERROR: Failed to extract response from ChatGPT."
        except Exception as e:
            return f"ERROR: Error interacting with ChatGPT: {e}"

    def _ask_gemini(self, prompt, timeout):
        try:
            wait = WebDriverWait(self.driver, 20)

            # Multiple prompt area selectors for Gemini
            prompt_selectors = [
                "div.prompt-textarea-wrapper div[contenteditable='true']",
                "textarea[aria-label*='Prompt']",
                "div[contenteditable='true'][role='textbox']",
                ".textarea_container textarea",
                "div.input-area [contenteditable='true']"
            ]

            prompt_div = None
            for sel in prompt_selectors:
                try:
                    prompt_div = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if prompt_div.is_displayed(): break
                except: continue

            if not prompt_div:
                prompt_div = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.prompt-textarea-wrapper div[contenteditable='true']")))

            script = """
                var el = arguments[0];
                el.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
                document.execCommand('insertText', false, arguments[1]);
            """
            self.driver.execute_script(script, prompt_div, prompt)

            time.sleep(1)

            # Gemini send button
            sent = False
            send_selectors = [
                "button[aria-label*='Send prompt']",
                "button.send-button",
                "button.send-icon"
            ]
            for sel in send_selectors:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if btn.is_enabled():
                        btn.click()
                        sent = True
                        break
                except: pass

            if not sent:
                prompt_div.send_keys(Keys.ENTER)

            time.sleep(2)

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # Check for stop generating button
                    stop_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Stop generating']")
                    if stop_btns:
                        time.sleep(2)
                        continue

                    # Poll length of last model-response
                    current_len = self.driver.execute_script(
                        "var m = document.querySelectorAll('model-response, message-content'); "
                        "return m.length ? m[m.length-1].textContent.length : 0;"
                    )
                    time.sleep(3)
                    new_len = self.driver.execute_script(
                        "var m = document.querySelectorAll('model-response, message-content'); "
                        "return m.length ? m[m.length-1].textContent.length : 0;"
                    )
                    if current_len == new_len and current_len > 10:
                        break
                except:
                    pass
                time.sleep(1)

            # Extract last response robustly via JS
            script = """
            var responses = Array.from(document.querySelectorAll('model-response, message-content, .markdown, div[class*="response-container"]'));
            if (responses.length > 0) {
                var lastResponse = responses[responses.length - 1];
                var content = lastResponse.querySelector('.content') || lastResponse;
                return content.innerText;
            }
            return "";
            """
            text = self.driver.execute_script(script)
            if text and len(text) > 10:
                return text

            return "ERROR: Failed to extract response from Gemini."
        except Exception as e:
            return f"ERROR: Error interacting with Gemini: {e}"

    def _ask_copilot(self, prompt, timeout):
        try:
            wait = WebDriverWait(self.driver, 20)

            # Copilot UI is inside a shadow DOM often, or just complex
            # Multiple selectors for Copilot textarea
            prompt_selectors = [
                "textarea#searchbox",
                "textarea[placeholder*='Ask']",
                "textarea.searchboxinput",
                "div[contenteditable='true']",
                "textarea"
            ]

            text_area = None
            for sel in prompt_selectors:
                try:
                    text_area = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if text_area.is_displayed(): break
                except: continue

            if not text_area:
                text_area = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))

            self.driver.execute_script("""
                var el = arguments[0];
                el.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
                document.execCommand('insertText', false, arguments[1]);
            """, text_area, prompt)

            time.sleep(1)

            # Send button
            sent = False
            send_selectors = [
                "button[aria-label='Submit']",
                "button.send-button",
                "button[title='Submit query']"
            ]
            for sel in send_selectors:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if btn.is_enabled():
                        btn.click()
                        sent = True
                        break
                except: pass

            if not sent:
                text_area.send_keys(Keys.ENTER)

            time.sleep(3)

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # Look for stop button absence or "New Topic" button presence
                    new_topic = self.driver.find_elements(By.CSS_SELECTOR, "button.new-topic-button")
                    stop = self.driver.find_elements(By.CSS_SELECTOR, "button#stop-button")

                    if not stop and (new_topic or time.time() - start_time > 10):
                        current_len = self.driver.execute_script(
                            "var m = document.querySelectorAll('div.message-content'); "
                            "return m.length ? m[m.length-1].textContent.length : 0;"
                        )
                        time.sleep(4)
                        new_len = self.driver.execute_script(
                            "var m = document.querySelectorAll('div.message-content'); "
                            "return m.length ? m[m.length-1].textContent.length : 0;"
                        )
                        if current_len == new_len and current_len > 10:
                            break
                except:
                    pass
                time.sleep(1)

            # Extract Copilot response via JS
            script = """
            var selectors = ["div.ac-container", "div.message-content", "div.attribution-container"];
            for (var i = 0; i < selectors.length; i++) {
                var responses = Array.from(document.querySelectorAll(selectors[i]));
                if (responses.length > 0) {
                    for (var j = responses.length - 1; j >= 0; j--) {
                        var text = responses[j].innerText;
                        if (text && text.length > 50) return text;
                    }
                }
            }
            return "";
            """
            text = self.driver.execute_script(script)
            if text and len(text) > 10:
                return text

            return "ERROR: Failed to extract response from Copilot."
        except Exception as e:
            return f"ERROR: Error interacting with Copilot: {e}"
