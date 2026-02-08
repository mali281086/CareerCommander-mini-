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

        # Check if we already have a tab for this
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if url in self.driver.current_url:
                self.tab_handle = handle
                return

        # Not found, open new
        self.driver.execute_script(f"window.open('{url}', '_blank');")
        time.sleep(2)
        self.tab_handle = self.driver.window_handles[-1]
        self.driver.switch_to.window(self.tab_handle)

        # Initial wait for load
        time.sleep(5)

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

            # Clear is hard on these rich editors, usually better to just paste
            # But let's try to make sure it's empty
            text_area.send_keys(Keys.CONTROL + "a")
            text_area.send_keys(Keys.BACKSPACE)

            # Use JS to set value for large prompts (faster and more reliable)
            self.driver.execute_script("arguments[0].innerText = arguments[1];", text_area, prompt)
            text_area.send_keys(" ") # Trigger event
            text_area.send_keys(Keys.ENTER)

            time.sleep(2)

            # Wait for response to finish
            # Check for the "Stop generating" or "Regenerate" button
            # Usually when generation is active, there is a stop button.
            # When done, there is a regenerate or the send button is re-enabled.

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # If we see the "Send" button enabled again and NO "Stop" button
                    send_btn = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='send-button']")
                    if send_btn.is_enabled():
                        # Wait a bit more to be sure
                        time.sleep(3)
                        break
                except:
                    pass
                time.sleep(2)

            # Extract last response
            # Multiple possible selectors for ChatGPT messages
            selectors = [
                "div[data-message-author-role='assistant']",
                ".markdown.prose",
                "div.agent-turn"
            ]

            for selector in selectors:
                responses = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if responses:
                    # Get the very last one
                    text = responses[-1].text
                    if text and len(text) > 10:
                        return text

            # Fallback: find any div with significant text that appeared after our prompt
            return "Failed to extract response from ChatGPT."

        except Exception as e:
            return f"Error interacting with ChatGPT: {e}"

    def _ask_gemini(self, prompt, timeout):
        try:
            # Gemini prompt area
            wait = WebDriverWait(self.driver, 20)
            prompt_div = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.prompt-textarea-wrapper div[contenteditable='true']")))

            self.driver.execute_script("arguments[0].innerText = arguments[1];", prompt_div, prompt)
            prompt_div.send_keys(" ")
            prompt_div.send_keys(Keys.ENTER)

            time.sleep(2)

            start_time = time.time()
            while time.time() - start_time < timeout:
                # Gemini shows "stop" button during gen, and "Done" when finished usually.
                # Or we can check for the presence of the last response's "Good response" icons
                try:
                    # Check for "Share" icon which appears when done
                    share_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Share']")
                    if share_btns:
                        time.sleep(2)
                        break
                except:
                    pass
                time.sleep(2)

            # Possible selectors for Gemini
            selectors = [
                "div.message-content",
                "model-response div.content",
                ".markdown"
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
        # Implementation for Copilot would go here
        return "Copilot automation not fully implemented yet. Please use ChatGPT or Gemini."
