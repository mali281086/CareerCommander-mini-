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

    def __init__(self, provider="ChatGPT"):
        self.provider = provider if provider in self.PROVIDERS else "ChatGPT"
        self.bm = BrowserManager()
        self.driver = self.bm.get_driver(headless=False)
        self.tab_handle = None

    def _ensure_tab(self):
        """Ensure we have a tab open for the provider."""
        url = self.PROVIDERS[self.provider]

        # 1. Check if we already have a tab for this provider
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if url in self.driver.current_url:
                self.tab_handle = handle
                return

        # 2. Look for ANY blank/new tab to reuse
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if self.driver.current_url in ["about:blank", "data:,", "chrome://newtab/"]:
                self.driver.get(url)
                self.tab_handle = handle
                time.sleep(5)
                return

        # 3. Otherwise, open a new tab
        self.driver.execute_script(f"window.open('{url}', '_blank');")
        time.sleep(2)
        self.tab_handle = self.driver.window_handles[-1]
        self.driver.switch_to.window(self.tab_handle)

        # Initial wait for load
        time.sleep(5)

    def close_tab(self):
        """Closes the tab used for analysis if it's still open."""
        if self.tab_handle and self.tab_handle in self.driver.window_handles:
            try:
                self.driver.switch_to.window(self.tab_handle)
                self.driver.close()
                # Switch back to whatever is left
                if self.driver.window_handles:
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass

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
            self.driver.execute_script("arguments[0].innerText = arguments[1];", text_area, prompt)
            text_area.send_keys(" ") # Trigger event
            text_area.send_keys(Keys.ENTER)

            time.sleep(2)

            # Wait for response to finish
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # Check for send button state
                    send_btn = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='send-button']")
                    if send_btn.is_enabled():
                        # Also ensure the stop button is gone
                        stop_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Stop generating']")
                        if not stop_btns:
                            time.sleep(3)
                            break
                except:
                    pass
                time.sleep(2)

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
                ".textarea_container textarea"
            ]

            prompt_div = None
            for sel in prompt_selectors:
                try:
                    prompt_div = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if prompt_div.is_displayed(): break
                except: continue

            if not prompt_div:
                prompt_div = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.prompt-textarea-wrapper div[contenteditable='true']")))

            self.driver.execute_script("arguments[0].innerText = arguments[1];", prompt_div, prompt)
            prompt_div.send_keys(" ")
            prompt_div.send_keys(Keys.ENTER)

            time.sleep(2)

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # Check for "Share" icon or stop generating state
                    # In Gemini, the "stop" button might be visible during generation
                    stop_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Stop generating']")
                    if not stop_btns:
                        # Check if response tools (copy, share) are visible for the last response
                        tools = self.driver.find_elements(By.CSS_SELECTOR, "div.response-tools")
                        if tools:
                            time.sleep(3)
                            break
                except:
                    pass
                time.sleep(2)

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
                "div[contenteditable='true']"
            ]

            text_area = None
            for sel in prompt_selectors:
                try:
                    text_area = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if text_area.is_displayed(): break
                except: continue

            if not text_area:
                text_area = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea")))

            self.driver.execute_script("arguments[0].value = arguments[1];", text_area, prompt)
            text_area.send_keys(" ")
            text_area.send_keys(Keys.ENTER)

            time.sleep(3)

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # Look for stop button absence or "New Topic" button presence
                    new_topic = self.driver.find_elements(By.CSS_SELECTOR, "button.new-topic-button")
                    stop = self.driver.find_elements(By.CSS_SELECTOR, "button#stop-button")
                    if not stop and new_topic:
                        time.sleep(3)
                        break
                except:
                    pass
                time.sleep(2)

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
