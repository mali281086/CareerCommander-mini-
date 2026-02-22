from tools.logger import logger
import os
import json
import undetected_chromedriver as uc
from selenium import webdriver
from tools.logger import logger

class BrowserManager:
    _instance = None
    _driver = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
        return cls._instance

    def get_driver(self, headless=False, profile_name="default"):
        """Returns the existing driver or creates a new one for the specified profile."""
        if self._driver is not None:
            try:
                # Check if alive
                self._driver.title
                return self._driver
            except:
                # Driver died, recreate
                self._driver = None
        
        return self._init_driver(headless, profile_name)

    def _init_driver(self, headless=False, profile_name="default"):
        logger.info(f"Initializing Undetected Browser for profile: {profile_name}...")
        
        # Paths
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        user_data_dir = os.path.join(project_dir, "chrome_profiles", profile_name)
        
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir, exist_ok=True)

        # Options
        options = uc.ChromeOptions()
        # Note: undetected_chromedriver handles user-data-dir differently if passed in constructor
        options.add_argument("--start-maximized")
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-service-autorun")
        options.add_argument("--password-store=basic")
        
        if headless:
            options.add_argument("--headless")

        try:
            # undetected_chromedriver automatically bypasses most bot detection
            # Explicitly passing user_data_dir to constructor as well for redundancy
            driver = uc.Chrome(
                options=options,
                user_data_dir=user_data_dir,
                headless=headless
            )
            
            # Optional: Apply stealth as well for extra protection
            try:
                from selenium_stealth import stealth
                stealth(driver,
                    languages=["en-US", "en", "de"],
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True,
                )
            except ImportError:
                pass
            
            self._driver = driver
            logger.info(f"Undetected Browser launched with profile: {user_data_dir}")
            return driver
        except Exception as e:
            logger.error(f"Failed to launch undetected browser: {e}")
            # Fallback to standard if UC fails
            logger.info("Attempting fallback to standard Chrome...")
            try:
                from selenium.webdriver.chrome.options import Options as StdOptions
                std_options = StdOptions()
                std_options.add_argument(f"user-data-dir={user_data_dir}")
                if headless: std_options.add_argument("--headless=new")
                driver = webdriver.Chrome(options=std_options)
                self._driver = driver
                return driver
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                raise e

    def save_cookies(self):
        """Saves current browser cookies to a file."""
        if not self._driver:
            return

        try:
            cookies = self._driver.get_cookies()
            project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cookie_path = os.path.join(project_dir, "data", "cookies.json")

            os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"Saved {len(cookies)} cookies to {cookie_path}")
        except Exception as e:
            logger.error(f"Failed to save cookies: {e}")

    def load_cookies(self, url=None):
        """Loads cookies from file. If url is provided, navigates there first."""
        if not self._driver:
            return

        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cookie_path = os.path.join(project_dir, "data", "cookies.json")

        if not os.path.exists(cookie_path):
            return

        try:
            with open(cookie_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            if url:
                self._driver.get(url)

            # Group cookies by domain to avoid adding them to wrong pages
            # Selenium only allows adding cookies for the current domain
            current_domain = self._driver.current_url.split("//")[-1].split("/")[0]
            if "www." in current_domain:
                current_domain = current_domain.replace("www.", "")

            count = 0
            for cookie in cookies:
                domain = cookie.get('domain', '')
                # Matching de.indeed.com with .indeed.com or vice-versa
                if current_domain in domain or (domain and domain.strip('.') in current_domain):
                    try:
                        # Selenium can't handle 'expiry' as float in some versions, or if it's in the past
                        if 'expiry' in cookie:
                            cookie['expiry'] = int(cookie['expiry'])
                        self._driver.add_cookie(cookie)
                        count += 1
                    except Exception as e:
                        pass

            if count > 0:
                logger.info(f"Loaded {count} cookies for {current_domain}")
                self._driver.refresh()
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")

    def close_driver(self, profile_name=None):
        """Close the browser. profile_name accepted for compatibility."""
        if self._driver:
            try:
                self.save_cookies()
                self._driver.quit()
            except:
                pass
            self._driver = None

    def close_all_drivers(self):
        """Alias for close_driver — single driver only."""
        self.close_driver()
