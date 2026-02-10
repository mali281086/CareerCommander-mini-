import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


import threading

class BrowserManager:
    _instance = None
    # Thread-local storage for drivers
    _local = threading.local()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
        return cls._instance

    def get_driver(self, headless=False, profile_name="default"):
        """Returns a driver for a specific profile."""
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
        print(f"Initializing Browser Profile: {profile_name}...")
        
        # Paths
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_user_data_dir = os.path.join(project_dir, "chrome_data")
        user_data_dir = os.path.join(base_user_data_dir, profile_name)
        
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)

        # Options
        options = Options()

        # Human-like User Agents
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        import random
        options.add_argument(f"user-agent={random.choice(user_agents)}")

        options.add_argument(f"user-data-dir={user_data_dir}")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Performance Optimizations (Ferrari)
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--blink-settings=imagesEnabled=false") # Disable images for speed

        # Exclude automation switches
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        if headless:
            options.add_argument("--headless=new")

        # Service
        try:
            # Selenium 4.6+ manages drivers automatically!
            driver = webdriver.Chrome(options=options)
            self._driver = driver
            print(f"Browser launched with profile: {user_data_dir}")
            return driver
        except Exception as e:
            print(f"Failed to crash browser: {e}")
            raise e

    def close_driver(self, profile_name=None):
        if not hasattr(self._local, 'drivers'):
            return

        if profile_name:
            if profile_name in self._local.drivers and self._local.drivers[profile_name]:
                try:
                    self._local.drivers[profile_name].quit()
                except:
                    pass
                self._local.drivers[profile_name] = None
        else:
            # Close all
            for p in list(self._local.drivers.keys()):
                if self._local.drivers[p]:
                    try:
                        self._local.drivers[p].quit()
                    except:
                        pass
                    self._local.drivers[p] = None
