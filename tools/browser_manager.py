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

    def get_driver(self, headless=False):
        """Returns the existing driver or creates a new one."""
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
            self._driver = driver
            print(f"Browser launched with profile: {user_data_dir}")
            return driver
        except Exception as e:
            print(f"Failed to crash browser: {e}")
            raise e

    def close_driver(self):
        if self._driver:
            try:
                self._driver.quit()
            except:
                pass
            self._driver = None
