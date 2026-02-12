import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth
import threading

class BrowserManager:
    _instance = None
    # Thread-local storage for drivers
    _local = threading.local()
    # Global registry for ALL active drivers across all threads
    _all_drivers = []
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
        return cls._instance

    def get_driver(self, headless=False, profile_name="default"):
        """Returns a driver. Reverted to always using 'default' to avoid login issues."""
        # Force default profile for everything (Normal Mode)
        profile_name = "default"

        # We store drivers in a dict per thread
        if not hasattr(self._local, 'drivers'):
            self._local.drivers = {}

        if profile_name not in self._local.drivers or self._local.drivers[profile_name] is None:
            self._local.drivers[profile_name] = self._init_driver(headless, profile_name)
        else:
            try:
                self._local.drivers[profile_name].title
            except:
                self._local.drivers[profile_name] = self._init_driver(headless, profile_name)
        
        return self._local.drivers[profile_name]

    def _init_driver(self, headless=False, profile_name="default"):
        # Check for system profile override
        system_user_data = os.getenv("SYSTEM_CHROME_USER_DATA")
        system_profile = os.getenv("SYSTEM_CHROME_PROFILE")
        
        if system_user_data and system_profile:
            print(f"Using System Chrome Profile: {system_user_data} | {system_profile}")
            user_data_dir = system_user_data
            profile_dir = system_profile
        else:
            print(f"Initializing Local Browser Profile: {profile_name}...")
            # Paths
            project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            user_data_dir = os.path.join(project_dir, "chrome_data", profile_name)
            profile_dir = "Default"

            if not os.path.exists(user_data_dir):
                os.makedirs(user_data_dir)

        # Options
        options = Options()

        # Human-like User Agents
        user_agents = [
            {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "plt": "Win32"},
            {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "plt": "MacIntel"},
            {"ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "plt": "Linux x86_64"}
        ]
        import random
        agent = random.choice(user_agents)
        options.add_argument(f"user-agent={agent['ua']}")

        options.add_argument(f"user-data-dir={user_data_dir}")
        options.add_argument(f"--profile-directory={profile_dir}")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Performance Optimizations
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # options.add_argument("--blink-settings=imagesEnabled=false") # Enabled images back for better stability/human-like

        # Exclude automation switches
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        if headless:
            options.add_argument("--headless=new")

        # Service
        try:
            # Selenium 4.6+ manages drivers automatically!
            driver = webdriver.Chrome(options=options)

            # Apply Stealth
            stealth(driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform=agent['plt'],
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )

            # Register globally
            with self._lock:
                self._all_drivers.append(driver)

            print(f"Browser launched with profile: {user_data_dir} (Total active: {len(self._all_drivers)})")
            return driver
        except Exception as e:
            print(f"Failed to launch browser: {e}")
            raise e

    def close_driver(self, profile_name=None):
        """Closes drivers associated with the current thread."""
        if not hasattr(self._local, 'drivers'):
            return

        if profile_name:
            if profile_name in self._local.drivers and self._local.drivers[profile_name]:
                driver = self._local.drivers[profile_name]
                try:
                    driver.quit()
                    with self._lock:
                        if driver in self._all_drivers:
                            self._all_drivers.remove(driver)
                except:
                    pass
                self._local.drivers[profile_name] = None
        else:
            # Close all in THIS thread
            for p in list(self._local.drivers.keys()):
                if self._local.drivers[p]:
                    driver = self._local.drivers[p]
                    try:
                        driver.quit()
                        with self._lock:
                            if driver in self._all_drivers:
                                self._all_drivers.remove(driver)
                    except:
                        pass
                    self._local.drivers[p] = None

    def close_all_drivers(self):
        """FORCE closes EVERY browser opened by any thread."""
        print(f"Force closing all {len(self._all_drivers)} active drivers...")
        with self._lock:
            for driver in list(self._all_drivers):
                try:
                    driver.quit()
                except:
                    pass
            self._all_drivers.clear()

        # Also clear thread-local references if we are in a thread that has them
        if hasattr(self._local, 'drivers'):
            self._local.drivers = {}
