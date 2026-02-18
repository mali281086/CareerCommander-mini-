from tools.logger import logger
import time
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tools.browser_manager import BrowserManager
import random

class LinkedInOutreach:
    def __init__(self):
        self.bm = BrowserManager()
        self.driver = None

    def random_sleep(self, min_s=2, max_s=5):
        time.sleep(random.uniform(min_s, max_s))

    def get_first_name(self, full_name):
        if not full_name:
            return "Sir/Madam"
        parts = full_name.split()
        if parts:
            return parts[0]
        return "Sir/Madam"

    def search_connections(self, location_name="Germany", limit=10):
        self.driver = self.bm.get_driver(headless=False)

        # Simple approach: Search for people with location and 1st degree connection
        # We use the search results page
        base_url = "https://www.linkedin.com/search/results/people/?"
        params = {
            "network": '["F"]', # 1st degree
            "origin": "FACETED_SEARCH",
            "keywords": location_name # Using location as keyword in search is a fallback if geoId is unknown
        }

        # Heuristic for Germany geoId
        if location_name.lower() == "germany":
            params["locationBy"] = '["101282230"]'
            del params["keywords"]

        url = base_url + urllib.parse.urlencode(params)
        logger.info(f"[LinkedIn Outreach] Navigating to: {url}")
        self.driver.get(url)
        self.random_sleep(4, 7)

        results = []
        scrolled = 0
        while len(results) < limit and scrolled < 3:
            items = self.driver.find_elements(By.CSS_SELECTOR, ".reusable-search__result-container")
            for item in items:
                if len(results) >= limit: break
                try:
                    name_elem = item.find_element(By.CSS_SELECTOR, ".entity-result__title-text a span[aria-hidden='true']")
                    full_name = name_elem.text.strip()

                    # Avoid duplicates
                    if any(r['name'] == full_name for r in results):
                        continue

                    # Find Message button
                    try:
                        msg_btn = item.find_element(By.CSS_SELECTOR, "button[aria-label^='Message']")
                        results.append({
                            "name": full_name,
                            "first_name": self.get_first_name(full_name),
                            "element": msg_btn
                        })
                    except:
                        # Maybe it's "Connect" or something else if not actually 1st degree or button hidden
                        continue

                except Exception as e:
                    logger.info(f"Error parsing connection: {e}")
                    continue

            if len(results) < limit:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self.random_sleep(2, 4)
                scrolled += 1
            else:
                break

        return results

    def send_message(self, connection, message_template):
        if not self.driver:
            return False

        try:
            msg_btn = connection['element']
            # Scroll to button
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", msg_btn)
            self.random_sleep(1, 2)
            msg_btn.click()
            self.random_sleep(2, 4)

            # Message box - LinkedIn often has multiple message boxes if multiple are open
            # We look for the active one or the last one
            try:
                # Wait for the message overlay to appear
                wait = WebDriverWait(self.driver, 5)
                msg_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='textbox'], .msg-form__contenteditable")))

                # Personalize
                first_name = connection['first_name']
                message = message_template.replace("{first_name}", first_name)

                # Clear and Type
                msg_box.send_keys(Keys.CONTROL + "a")
                msg_box.send_keys(Keys.BACKSPACE)

                # Type message (could be long, so maybe split by lines)
                for line in message.split('\n'):
                    msg_box.send_keys(line)
                    msg_box.send_keys(Keys.SHIFT + Keys.ENTER)

                self.random_sleep(1, 2)

                # Send button
                send_btn = self.driver.find_element(By.CSS_SELECTOR, ".msg-form__send-button")
                # Only click if not disabled
                if send_btn.is_enabled():
                    # send_btn.click() # COMMENTED OUT FOR SAFETY DURING TESTING, but implementation is there
                    logger.info(f"Would send message to {connection['name']}")
                    # For real use:
                    send_btn.click()
                    self.random_sleep(1, 2)

                    # Close the message bubble to avoid clutter
                    close_btn = self.driver.find_element(By.CSS_SELECTOR, "button[class*='msg-overlay-bubble-header__control'][aria-label^='Close']")
                    close_btn.click()
                    return True
                else:
                    logger.info(f"Send button disabled for {connection['name']}")
                    return False

            except Exception as e:
                logger.info(f"Error in message box: {e}")
                return False

        except Exception as e:
            logger.info(f"Error clicking message button: {e}")
            return False

    def close(self):
        if self.driver:
            self.bm.close_driver()
