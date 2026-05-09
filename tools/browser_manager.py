from tools.logger import logger
import os
import json
import undetected_chromedriver as uc
from selenium import webdriver

class BrowserManager:
    _instance = None
    _driver = None
    _is_headless = False
    _current_profile = None

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

                # If the requested mode (headless vs headed) or profile is different,
                # we must close the current one to avoid conflicts or hidden windows.
                if self._is_headless != headless or self._current_profile != profile_name:
                    logger.info(f"Driver mismatch (Headless: {self._is_headless}->{headless}, Profile: {self._current_profile}->{profile_name}). Restarting...")
                    self.close_driver()
                else:
                    return self._driver
            except:
                # Driver died, recreate
                self._driver = None
        
        return self._init_driver(headless, profile_name)

    def _init_driver(self, headless=False, profile_name="default"):
        self._is_headless = headless
        self._current_profile = profile_name
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
            options.add_argument("--window-size=1920,1080")
            
        # Windows stability arguments
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--remote-debugging-port=0") # Auto-assign to avoid conflicts

        try:
            # undetected_chromedriver automatically bypasses most bot detection
            try:
                driver = uc.Chrome(
                    options=options,
                    user_data_dir=user_data_dir,
                    headless=headless,
                    use_subprocess=True
                )
            except Exception as e:
                # If there is a version mismatch, try to extract the user's Chrome version from the error
                import re
                error_msg = str(e)
                logger.warning(f"Failed to launch uc.Chrome initially: {error_msg}")
                match = re.search(r'Current browser version is (\d+)', error_msg)
                
                if match:
                    major_version = int(match.group(1))
                    logger.info(f"Retrying undetected_chromedriver with version_main={major_version}...")
                    
                    # Must recreate options object because uc.Chrome mutates it
                    new_options = uc.ChromeOptions()
                    new_options.add_argument("--start-maximized")
                    new_options.add_argument(f"--user-data-dir={user_data_dir}")
                    new_options.add_argument("--no-first-run")
                    new_options.add_argument("--no-service-autorun")
                    new_options.add_argument("--password-store=basic")
                    if headless:
                        new_options.add_argument("--headless")
                        
                    driver = uc.Chrome(
                        options=new_options,
                        user_data_dir=user_data_dir,
                        headless=headless,
                        version_main=major_version,
                        use_subprocess=True
                    )
                elif any(x in error_msg.lower() for x in ["chrome not reachable", "cannot connect to chrome", "failed to write prefs file", "devtoolsactiveport"]):
                    logger.warning(f"Detected locked or corrupt Chrome process for {profile_name}. Attempting to kill it...")
                    # Automatically hunt and terminate stranded Chrome instances holding this specific profile
                    import subprocess
                    import time
                    ps_cmd = f"Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq 'chrome.exe' -and $_.CommandLine -match '{profile_name}' }} | Invoke-CimMethod -MethodName Terminate"
                    subprocess.run(["powershell", "-command", ps_cmd], capture_output=True, text=True)
                    
                    # Also delete lock files manually
                    lock_files = [
                        os.path.join(user_data_dir, "SingletonLock"),
                        os.path.join(user_data_dir, "DevToolsActivePort"),
                        os.path.join(user_data_dir, "Default", "Preferences"), # Force reset if corrupt
                    ]
                    for lf in lock_files:
                        try:
                            if os.path.exists(lf): os.remove(lf)
                        except: pass
                        
                    time.sleep(2)  # Give OS time to free file locks
                    logger.info("Retrying driver launch after zombie and lock-file cleanup...")
                    
                    new_options = uc.ChromeOptions()
                    new_options.add_argument("--start-maximized")
                    new_options.add_argument(f"--user-data-dir={user_data_dir}")
                    new_options.add_argument("--no-first-run")
                    new_options.add_argument("--no-service-autorun")
                    new_options.add_argument("--password-store=basic")
                    if headless:
                        new_options.add_argument("--headless")
                        
                    driver = uc.Chrome(
                        options=new_options,
                        user_data_dir=user_data_dir,
                        headless=headless
                    )
                else:
                    raise e
                    
            # Stealth removed: selenium-stealth breaks modern Cloudflare (Indeed, Xing, ZipRecruiter)
            
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
        """Saves current browser cookies to a file for all open tabs/domains."""
        if not self._driver:
            return

        try:
            all_cookies = []
            original_handle = self._driver.current_window_handle
            handles = self._driver.window_handles

            for handle in handles:
                try:
                    self._driver.switch_to.window(handle)
                    all_cookies.extend(self._driver.get_cookies())
                except:
                    continue

            # Remove duplicates based on name and domain
            unique_cookies = []
            seen = set()
            for c in all_cookies:
                key = (c.get('name'), c.get('domain'), c.get('path'))
                if key not in seen:
                    unique_cookies.append(c)
                    seen.add(key)

            try:
                self._driver.switch_to.window(original_handle)
            except:
                pass

            project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cookie_path = os.path.join(project_dir, "data", "cookies.json")

            os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(unique_cookies, f, indent=2)
            logger.info(f"Saved {len(unique_cookies)} unique cookies to {cookie_path}")
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

    def is_driver_alive(self):
        """Check if the current driver is still responsive."""
        if self._driver is None:
            return False
        try:
            self._driver.title
            return True
        except:
            return False

    def close_driver(self, profile_name=None):
        """Close the browser. profile_name accepted for compatibility."""
        if self._driver:
            try:
                self.save_cookies()
            except:
                pass
            try:
                self._driver.quit()
            except:
                pass
            self._driver = None
            self._current_profile = None

    def close_all_drivers(self):
        """Alias for close_driver — single driver only."""
        self.close_driver()
