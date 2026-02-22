import unittest
from tools.internet import is_internet_available

class TestInternet(unittest.TestCase):
    def test_connectivity(self):
        # This assumes the sandbox has internet access as per Guiding Principles
        self.assertTrue(is_internet_available())

if __name__ == '__main__':
    unittest.main()
