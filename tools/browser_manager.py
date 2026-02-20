from tools.logger import logger
import os
import undetected_chromedriver as uc
from selenium import webdriver

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
        
        if headless:
            options.add_argument("--headless")

        try:
            # undetected_chromedriver automatically bypasses most bot detection
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
