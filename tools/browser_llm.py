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

    def __init__(self, provider="ChatGPT", profile_name="default"):
        self.provider = provider if provider in self.PROVIDERS else "ChatGPT"
        self.profile_name = profile_name
        self.bm = BrowserManager()
        self.driver = self.bm.get_driver(headless=False, profile_name=profile_name)
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
        self.driver = self.bm.get_driver(headless=False, profile_name=self.profile_name)

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

    def _wait_for_page_load(self):
        """Waits for the LLM page to load specifically for prompt area."""
        try:
            wait = WebDriverWait(self.driver, 15)
            if self.provider == "ChatGPT":
                wait.until(EC.presence_of_element_located((By.ID, "prompt-textarea")))
            elif self.provider == "Gemini":
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[contenteditable='true']")))
            elif self.provider == "Copilot":
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))

            # Brief pause for animations and cookie banners
            time.sleep(2)
            self._handle_cookies()
        except:
            # Fallback to hard sleep if wait fails
            time.sleep(5)

    def close_tab(self):
        """Closes the tab used for analysis if it's still open.
        If it's the last tab, it stays open to avoid exiting the browser process."""
        try:
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
        except Exception as e:
            logger.info(f"Error closing tab: {e}")

    def quit(self):
        """FORCE closes the entire browser associated with this LLM instance."""
        try:
            self.bm.close_driver(profile_name=self.profile_name)
        except Exception as e:
            logger.info(f"Error quitting browser: {e}")

    def ask(self, prompt, timeout=120):
        """Sends prompt and waits for response."""
        self._ensure_tab()

        if self.provider == "ChatGPT":
            return self._ask_chatgpt(prompt, timeout)
        elif self.provider == "Gemini":
            return self._ask_gemini(prompt, timeout)
        elif self.provider == "Copilot":
            return self._ask_copilot(prompt, timeout)

        return "Provider not implemented."

    def _ask_chatgpt(self, prompt, timeout):
        try:
            # Find prompt area
            wait = WebDriverWait(self.driver, 20)
            text_area = wait.until(EC.presence_of_element_located((By.ID, "prompt-textarea")))

            # Use JS to set value for large prompts (faster and more reliable)
            self.driver.execute_script("""
                var el = arguments[0];
                el.innerText = arguments[1];
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, text_area, prompt)

            time.sleep(1)

            # Try multiple ways to send
            sent = False
            send_selectors = [
                "button[data-testid='send-button']",
                "button[aria-label='Send message']",
                "button.absolute.bottom-1.5"
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

            time.sleep(2)

            # Wait for response to finish
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # If we see the 'Stop generating' button, we are definitely still working
                    stop_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Stop generating']")
                    if stop_btns:
                        time.sleep(2)
                        continue

                    # If send button is visible and enabled, we might be done
                    send_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[data-testid='send-button']")
                    if send_btns and send_btns[0].is_enabled():
                        # Check if the last assistant message has stopped growing
                        responses = self.driver.find_elements(By.CSS_SELECTOR, "div[data-message-author-role='assistant']")
                        if responses:
                            last_text = responses[-1].text
                            time.sleep(3)
                            if responses[-1].text == last_text:
                                break
                except:
                    pass
                time.sleep(1)

            # Extract last response
            selectors = [
                "div[data-message-author-role='assistant']",
                ".markdown.prose",
                "div.agent-turn"
            ]

            for selector in selectors:
                responses = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if responses:
                    text = responses[-1].text
                    if text and len(text) > 10:
                        return text

            return "Failed to extract response from ChatGPT."
        except Exception as e:
            return f"Error interacting with ChatGPT: {e}"

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

            self.driver.execute_script("""
                var el = arguments[0];
                el.innerText = arguments[1];
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, prompt_div, prompt)

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

                    # Check if response tools (copy, share) or new prompt area is ready
                    tools = self.driver.find_elements(By.CSS_SELECTOR, "div.response-tools, div.actions-container")
                    if tools:
                        # Check if text stopped changing
                        responses = self.driver.find_elements(By.CSS_SELECTOR, "model-response")
                        if responses:
                            last_text = responses[-1].text
                            time.sleep(3)
                            if responses[-1].text == last_text:
                                break
                except:
                    pass
                time.sleep(1)

            selectors = [
                "div.message-content",
                "model-response div.content",
                ".markdown",
                "div[class*='response-container']"
            ]

            for selector in selectors:
                responses = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if responses:
                    text = responses[-1].text
                    if text and len(text) > 10:
                        return text

            return "Failed to extract response from Gemini."
        except Exception as e:
            return f"Error interacting with Gemini: {e}"

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
                if (el.tagName === 'TEXTAREA') {
                    el.value = arguments[1];
                } else {
                    el.innerText = arguments[1];
                }
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
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
                        # Ensure content is there
                        responses = self.driver.find_elements(By.CSS_SELECTOR, "div.message-content")
                        if responses:
                            last_text = responses[-1].text
                            time.sleep(4)
                            if responses[-1].text == last_text and len(last_text) > 10:
                                break
                except:
                    pass
                time.sleep(1)

            # Extract Copilot response
            selectors = [
                "div.ac-container",
                "div.message-content",
                "div.attribution-container"
            ]

            for selector in selectors:
                responses = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if responses:
                    # Copilot responses are often in a list
                    for res in reversed(responses):
                        text = res.text
                        if text and len(text) > 50:
                            return text

            return "Failed to extract response from Copilot."
        except Exception as e:
            return f"Error interacting with Copilot: {e}"
