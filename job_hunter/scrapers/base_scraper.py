from abc import ABC, abstractmethod
import time
from tools.browser_manager import BrowserManager

class BaseScraper(ABC):
    def __init__(self):
        self.browser_manager = BrowserManager()

    @property
    def driver(self):
        return self.browser_manager.get_driver()

    @abstractmethod
    def search(self, keyword, location, limit=10, easy_apply=False):
        """
        Scrape jobs.
        :param keyword: Job title or keyword
        :param location: Location
        :param limit: Max number of jobs to fetch
        :param easy_apply: If True, filter for Easy Apply jobs
        :return: List of dictionaries
        """
        raise NotImplementedError

    def random_sleep(self, min_s=2, max_s=5):
        import random
        time.sleep(random.uniform(min_s, max_s))
