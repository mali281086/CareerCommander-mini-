from abc import ABC, abstractmethod
from typing import List, Optional
from job_hunter.models import JobRecord
from tools.logger import logger
from job_hunter.data_manager import DataManager

class BaseScraper(ABC):
    """Abstract base class for all job scrapers."""

    def __init__(self, driver=None):
        self._driver = driver
        self.platform_name = "Base"
        self.db = DataManager()
        self.selectors = self.db.load_selectors()

    @abstractmethod
    def search(self, keyword: str, location: str, limit: int = 10) -> List[JobRecord]:
        """Search for jobs on the platform."""
        pass

    @abstractmethod
    def fetch_details(self, job_url: str) -> Optional[str]:
        """Fetch the full description for a job URL."""
        pass

    def random_sleep(self, min_sec=2, max_sec=5):
        import time
        import random
        time.sleep(random.uniform(min_sec, max_sec))

    def log(self, msg, level="info"):
        full_msg = f"[{self.platform_name}] {msg}"
        if level == "info":
            logger.info(full_msg)
        elif level == "error":
            logger.error(full_msg)
        elif level == "warning":
            logger.warning(full_msg)
        elif level == "debug":
            logger.debug(full_msg)
