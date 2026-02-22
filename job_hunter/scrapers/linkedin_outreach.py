from tools.logger import logger
import time
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tools.browser_manager import BrowserManager
from job_hunter.data_manager import DataManager
import random
from tools.human_actions import type_human_like, random_wait

class LinkedInOutreach:
    def __init__(self):
        self.bm = BrowserManager()
        self.db = DataManager()
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

    def search_connections(self, location_name="Germany", limit=10, skip_messaged=True):
        self.driver = self.bm.get_driver(headless=False)

        # Ensure we are logged in by loading cookies if we are on a login page or generic home
        self.bm.load_cookies("https://www.linkedin.com/")

        messaged_list = self.db.load_messaged_contacts() if skip_messaged else []
        messaged_names = {c['name'] for c in messaged_list}

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

                    link_elem = item.find_element(By.CSS_SELECTOR, ".entity-result__title-text a")
                    profile_url = link_elem.get_attribute("href").split('?')[0]

                    # Avoid duplicates in current session
                    if any(r['name'] == full_name for r in results):
                        continue

                    # Skip if already messaged
                    if full_name in messaged_names:
                        logger.info(f"Skipping {full_name} (Already messaged)")
                        continue

                    # Find Message button
                    try:
                        msg_btn = item.find_element(By.CSS_SELECTOR, "button[aria-label^='Message']")
                        results.append({
                            "name": full_name,
                            "first_name": self.get_first_name(full_name),
                            "profile_url": profile_url,
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

    def send_message(self, connection, message_template, auto_send=False):
        if not self.driver:
            return False

        full_name = connection['name']
        try:
            msg_btn = connection['element']
            # Scroll to button
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", msg_btn)
            random_wait(1, 2)

            # Check if message overlay is already open for this person
            # (LinkedIn often opens them automatically if you recently chatted)
            try:
                # Look for an open bubble with this person's name
                bubbles = self.driver.find_elements(By.CSS_SELECTOR, ".msg-overlay-bubble-header")
                already_open = False
                for b in bubbles:
                    if full_name in b.text:
                        already_open = True
                        b.click() # Focus it
                        break

                if not already_open:
                    msg_btn.click()
            except:
                msg_btn.click()

            random_wait(2, 4)

            # Message box - LinkedIn often has multiple message boxes if multiple are open
            # We look for the active one or the last one
            try:
                # Wait for the message overlay to appear
                wait = WebDriverWait(self.driver, 5)
                # Selectors for the message input area
                msg_box_selectors = [
                    "div[role='textbox']",
                    ".msg-form__contenteditable",
                    "div[aria-label^='Write a message']",
                    "div[aria-label^='Nachricht schreiben']"
                ]

                msg_box = None
                for sel in msg_box_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        if elements:
                            # Use the last one (usually the most recently opened)
                            msg_box = elements[-1]
                            break
                    except:
                        continue

                if not msg_box:
                    logger.error(f"Could not find message box for {full_name}")
                    return False

                # Personalize (support both {first_name} and {name})
                first_name = connection['first_name']
                message = message_template.replace("{first_name}", first_name).replace("{name}", full_name)

                # Clear
                msg_box.click()
                msg_box.send_keys(Keys.CONTROL + "a")
                msg_box.send_keys(Keys.BACKSPACE)
                random_wait(0.5, 1)

                # Type message human-like
                lines = message.split('\n')
                for i, line in enumerate(lines):
                    type_human_like(msg_box, line)
                    if i < len(lines) - 1:
                        msg_box.send_keys(Keys.SHIFT + Keys.ENTER)

                random_wait(1, 2)

                # Mark as messaged in our database
                self.db.save_messaged_contact(full_name, connection.get('profile_url'))

                if auto_send:
                    # Send button
                    send_btn = self.driver.find_element(By.CSS_SELECTOR, ".msg-form__send-button")
                    # Only click if not disabled
                    if send_btn.is_enabled():
                        logger.info(f"Sending message to {full_name}")
                        send_btn.click()
                        self.random_sleep(1, 2)

                        # Close the message bubble to avoid clutter
                        try:
                            close_btn = self.driver.find_element(By.CSS_SELECTOR, "button[class*='msg-overlay-bubble-header__control'][aria-label^='Close']")
                            close_btn.click()
                        except:
                            pass
                        return True
                    else:
                        logger.info(f"Send button disabled for {full_name}")
                        return False
                else:
                    logger.info(f"Message prepared for {full_name} (Auto-send is OFF)")
                    return True

            except Exception as e:
                logger.info(f"Error in message box: {e}")
                return False

        except Exception as e:
            logger.info(f"Error clicking message button: {e}")
            return False

    def close(self):
        if self.driver:
            self.bm.close_driver()
