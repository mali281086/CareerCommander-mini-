import logging
import os
import datetime
from pathlib import Path

# Paths
LOGS_DIR = Path("logs")
ARTIFACTS_DIR = LOGS_DIR / "debug_artifacts"

def setup_logger(name="CareerCommander"):
    """Sets up a centralized logger for the application."""
    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir()

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if not logger.handlers:
        # File Handler
        fh = logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)

        # Console Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger

logger = setup_logger()

def save_debug_artifact(driver, name_prefix="error"):
    """Saves a screenshot and HTML dump for debugging automation failures."""
    if not ARTIFACTS_DIR.exists():
        ARTIFACTS_DIR.mkdir(parents=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{name_prefix}_{timestamp}"

    # Save Screenshot
    try:
        screenshot_path = ARTIFACTS_DIR / f"{base_name}.png"
        driver.save_screenshot(str(screenshot_path))
        logger.debug(f"Saved screenshot to {screenshot_path}")
    except Exception as e:
        logger.error(f"Failed to save screenshot: {e}")

    # Save HTML
    try:
        html_path = ARTIFACTS_DIR / f"{base_name}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.debug(f"Saved HTML dump to {html_path}")
    except Exception as e:
        logger.error(f"Failed to save HTML dump: {e}")

    return base_name
