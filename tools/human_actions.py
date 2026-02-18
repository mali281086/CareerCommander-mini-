import time
import random
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from tools.logger import logger

def jitter_mouse(driver):
    """Slightly moves the mouse to simulate human presence."""
    try:
        actions = ActionChains(driver)
        # Move by small random amounts
        x = random.randint(-5, 5)
        y = random.randint(-5, 5)
        actions.move_by_offset(x, y).perform()
        logger.debug(f"Mouse jittered by ({x}, {y})")
    except Exception as e:
        logger.debug(f"Failed to jitter mouse: {e}")

def human_scroll(driver):
    """Scrolls the page in small, variable increments."""
    try:
        total_height = driver.execute_script("return document.body.scrollHeight")
        current_scroll = driver.execute_script("return window.pageYOffset")

        # Scroll down a bit
        target = min(current_scroll + random.randint(200, 500), total_height)

        # Incremental scroll
        temp_scroll = current_scroll
        while temp_scroll < target:
            step = random.randint(20, 50)
            temp_scroll += step
            driver.execute_script(f"window.scrollTo(0, {temp_scroll});")
            time.sleep(random.uniform(0.01, 0.05))

        logger.debug(f"Human scrolled to {temp_scroll}")
    except Exception as e:
        logger.debug(f"Failed to scroll human-like: {e}")

def type_human_like(element, text):
    """Types text into an element with variable delays between keystrokes."""
    try:
        for char in text:
            element.send_keys(char)
            # Sleep between 0.05 and 0.2 seconds per character
            time.sleep(random.uniform(0.05, 0.2))
        logger.debug(f"Typed '{text}' human-like")
    except Exception as e:
        logger.error(f"Failed to type human-like: {e}")

def random_wait(min_sec=1, max_sec=3):
    """Waits for a random amount of time."""
    wait_time = random.uniform(min_sec, max_sec)
    time.sleep(wait_time)
