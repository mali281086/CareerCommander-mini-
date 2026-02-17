import logging
import os
from datetime import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # Console Handler
        c_handler = logging.StreamHandler()
        c_handler.setLevel(logging.INFO)
        c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)

        # File Handler
        f_handler = logging.FileHandler(os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log"))
        f_handler.setLevel(logging.DEBUG)
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)

    return logger

def move_debug_artifact(filepath):
    if not os.path.exists(filepath):
        return

    DEBUG_DIR = os.path.join(LOG_DIR, "debug_artifacts")
    os.makedirs(DEBUG_DIR, exist_ok=True)

    filename = os.path.basename(filepath)
    new_path = os.path.join(DEBUG_DIR, f"{datetime.now().strftime('%H%M%S')}_{filename}")

    os.rename(filepath, new_path)
    return new_path
