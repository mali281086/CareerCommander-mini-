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

    def search_connections(self, location_name="Germany", limit=10, skip_messaged=True, keywords=None):
        self.driver = self.bm.get_driver(headless=False)

        # Ensure we are logged in by loading cookies if we are on a login page or generic home
        self.bm.load_cookies("https://www.linkedin.com/")

        messaged_list = self.db.load_messaged_contacts() if skip_messaged else []
        messaged_names = {c['name'] for c in messaged_list}

        # Simple approach: Search for people with location and 1st degree connection
        # We use the search results page
        base_url = "https://www.linkedin.com/search/results/people/?"
        # LinkedIn's frontend parser is buggy and drops parameters if quotes are strictly URL-encoded to %22.
        # It expects brackets to be encoded (%5B, %5D) but quotes to be literal (").
        query_parts = [
            'network=%5B"F"%5D',
            'origin=FACETED_SEARCH'
        ]
        
        if location_name.lower() == "germany":
            query_parts.append('geoUrn=%5B"101282230"%5D')
            if keywords:
                query_parts.append(f"keywords={urllib.parse.quote(keywords)}")
        elif location_name:
            if keywords:
                query_parts.append(f"keywords={urllib.parse.quote(keywords + ' ' + location_name)}")
            else:
                query_parts.append(f"keywords={urllib.parse.quote(location_name)}")
        elif keywords:
            query_parts.append(f"keywords={urllib.parse.quote(keywords)}")

        url = base_url + "&".join(query_parts)
        logger.info(f"[LinkedIn Outreach] Navigating to: {url}")
        self.driver.get(url)
        self.random_sleep(4, 7)

        results = []
        scrolled = 0
        while len(results) < limit and scrolled < 3:
            # Look for any list item that contains a button or link meant for messaging
            # This bypasses obfuscated classes
            xpath_msg = "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'message') or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'message')"
            items = self.driver.find_elements(By.XPATH, f"//li[.//button[{xpath_msg}]]")
            
            if not items:
                # Fallback if they are not in li tags
                items = self.driver.find_elements(By.XPATH, f"//div[.//button[{xpath_msg}]]")

            # We might find many nested divs, so we only want the unique buttons. 
            # A cleaner approach is to find the message buttons directly, then traverse up to get the name.
            xpath_msg = "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'message') or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'message')"
            buttons = self.driver.find_elements(By.XPATH, f"//button[{xpath_msg}] | //a[{xpath_msg}]")
            
            for msg_btn in buttons:
                if len(results) >= limit: break
                try:
                    # Ensure the button is actually visible and looks like an action button
                    if not msg_btn.is_displayed():
                        continue
                        
                    aria_label = msg_btn.get_attribute("aria-label") or ""
                    
                    # Extract name
                    full_name = None
                    if "Send a message to " in aria_label:
                        full_name = aria_label.replace("Send a message to ", "").strip()
                    elif "Message " in aria_label:
                        full_name = aria_label.replace("Message ", "").strip()
                    
                    # Traverse up to the container (li or generic div card) to find the profile link and name if missing
                    try:
                        container = msg_btn.find_element(By.XPATH, "./ancestor::li[1]")
                    except:
                        try:
                            # Fallback to the closest div that looks like a card (has a profile link)
                            container = msg_btn.find_element(By.XPATH, "./ancestor::div[.//a[contains(@href, '/in/')]]")
                        except:
                            container = msg_btn

                    if not full_name:
                        try:
                            # Try to find the title text element (aria-hidden=true is common)
                            name_elems = container.find_elements(By.XPATH, ".//a[contains(@href, '/in/')]/span[@aria-hidden='true']")
                            if name_elems:
                                full_name = name_elems[0].text.strip()
                            else:
                                # Grab the first link text
                                profile_links = container.find_elements(By.XPATH, ".//a[contains(@href, '/in/')]")
                                for link in profile_links:
                                    text = link.text.strip()
                                    if text and "\n" not in text and "LinkedIn" not in text:
                                        full_name = text
                                        break
                        except:
                            pass
                    
                    if not full_name:
                        # Absolute fallback, just use the first line of text
                        full_name = container.text.split('\n')[0].strip()

                    # Avoid "Message" as a name
                    if full_name.lower() == "message":
                        continue

                    # Extract Profile URL
                    profile_url = ""
                    try:
                        a_elem = container.find_element(By.XPATH, ".//a[contains(@href, '/in/')]")
                        profile_url = a_elem.get_attribute("href").split('?')[0]
                    except:
                        pass

                    # Avoid duplicates in current session
                    if any(r['name'] == full_name for r in results):
                        continue

                    # Skip if already messaged
                    if full_name in messaged_names:
                        logger.info(f"Skipping {full_name} (Already messaged)")
                        continue

                    results.append({
                        "name": full_name,
                        "first_name": self.get_first_name(full_name),
                        "profile_url": profile_url,
                        "element": msg_btn
                    })

                except Exception as e:
                    logger.info(f"Error parsing connection button: {e}")
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
                    # Case-insensitive and substring match for name in header
                    if full_name.lower() in b.text.lower():
                        already_open = True
                        try: b.click() # Focus it
                        except: self.driver.execute_script("arguments[0].click();", b)
                        break

                if not already_open:
                    try: msg_btn.click()
                    except: self.driver.execute_script("arguments[0].click();", msg_btn)
            except:
                try: msg_btn.click()
                except: self.driver.execute_script("arguments[0].click();", msg_btn)

            random_wait(2, 4)

            # Message box - LinkedIn often has multiple message boxes if multiple are open
            # We look for the active one or the last one
            try:
                # Wait for the message overlay to appear
                wait = WebDriverWait(self.driver, 10)
                # Selectors for the message input area
                msg_box_selectors = [
                    "div[role='textbox']",
                    ".msg-form__contenteditable",
                    "div[aria-label*='Write a message']",
                    "div[aria-label*='Nachricht schreiben']",
                    "div[aria-label*='message']",
                    ".msg-form__message-texteditor"
                ]

                msg_box = None
                for sel in msg_box_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        for el in reversed(elements): # Check from newest/last
                            if el.is_displayed():
                                msg_box = el
                                break
                        if msg_box: break
                    except:
                        continue

                if not msg_box:
                    logger.error(f"Could not find message box for {full_name}")
                    return False

                # Personalize (support both {first_name} and {name})
                first_name = connection['first_name']
                message = message_template.replace("{first_name}", first_name).replace("{name}", full_name)

                # Clear and Type
                msg_box.click()
                msg_box.send_keys(Keys.CONTROL + "a")
                msg_box.send_keys(Keys.BACKSPACE)
                random_wait(0.5, 1)

                # Type message human-like
                lines = [l.strip() for l in message.split('\n') if l.strip()]
                for i, line in enumerate(lines):
                    type_human_like(msg_box, line)
                    if i < len(lines) - 1:
                        msg_box.send_keys(Keys.SHIFT + Keys.ENTER)

                random_wait(1, 2)

                if auto_send:
                    # Send button
                    send_btn = self.driver.find_element(By.CSS_SELECTOR, ".msg-form__send-button")
                    # Only click if not disabled
                    if send_btn.is_enabled():
                        logger.info(f"Sending message to {full_name}")
                        send_btn.click()
                        self.random_sleep(1, 2)
                        
                        # Mark as messaged in our database
                        self.db.save_messaged_contact(full_name, connection.get('profile_url'))

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
                    logger.info(f"Message prepared for {full_name}. Waiting for user to click send manually...")
                    # Wait for user to send (message box becomes empty) or close bubble
                    sent = False
                    max_wait = 300 # 5 minutes timeout per contact
                    elapsed = 0
                    while elapsed < max_wait:
                        try:
                            # If text becomes empty, user hit send
                            if msg_box.text.strip() == "":
                                sent = True
                                break
                            # If bubble is closed manually by user
                            if not msg_box.is_displayed():
                                break
                        except:
                            # StaleElementReferenceException means bubble closed
                            break
                        
                        time.sleep(1)
                        elapsed += 1

                    if sent:
                        logger.info(f"User sent the message for {full_name}.")
                        self.db.save_messaged_contact(full_name, connection.get('profile_url'))
                    else:
                        logger.info(f"User skipped sending message for {full_name}.")

                    # Clean up: close any open bubbles before moving to next
                    try:
                        close_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[class*='msg-overlay-bubble-header__control'][aria-label^='Close']")
                        for btn in close_btns:
                            if btn.is_displayed():
                                btn.click()
                    except:
                        pass
                    
                    return sent

            except Exception as e:
                logger.info(f"Error in message box: {e}")
                return False

        except Exception as e:
            logger.info(f"Error clicking message button: {e}")
            return False

    def close(self):
        if self.driver:
            self.bm.close_driver()
