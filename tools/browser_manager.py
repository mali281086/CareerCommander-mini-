import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class BrowserManager:
    _instance = None
    _driver = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
        return cls._instance

    def get_driver(self, headless=False, profile_name="default"):
        """Returns the existing driver or creates a new one.
        profile_name is accepted for compatibility but ignored (single profile)."""
        if self._driver is not None:
            try:
                # Check if alive
                self._driver.title
                return self._driver
            except:
                # Driver died, recreate
                self._driver = None
        
        return self._init_driver(headless)

    def _init_driver(self, headless=False):
        print("Initializing Browser...")
        
        # Paths
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        user_data_dir = os.path.join(project_dir, "chrome_data")
        
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)

        # Options
        options = Options()
        options.add_argument(f"user-data-dir={user_data_dir}")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Exclude automation switches
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        if headless:
            options.add_argument("--headless=new")

        # Service
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # Apply stealth to hide Selenium fingerprint
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
                # selenium_stealth not installed, still works without it
                pass
            
            self._driver = driver
            print(f"Browser launched with profile: {user_data_dir}")
            return driver
        except Exception as e:
            print(f"Failed to launch browser: {e}")
            raise e

    def close_driver(self, profile_name=None):
        """Close the browser. profile_name accepted for compatibility."""
        if self._driver:
            try:
                self._driver.quit()
            except:
                pass
            self._driver = None

    def close_all_drivers(self):
        """Alias for close_driver — single driver only."""
        self.close_driver()
