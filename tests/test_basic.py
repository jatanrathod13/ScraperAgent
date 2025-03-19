"""
Basic tests for ScraperAgent.
"""

import unittest
from src.core.crawler import Crawler
from src.extractors.base_extractor import BaseExtractor

class TestBasic(unittest.TestCase):
    """Basic test cases."""

    def test_crawler_initialization(self):
        """Test that crawler can be initialized."""
        crawler = Crawler(start_urls=["https://example.com"])
        self.assertIsNotNone(crawler)
        self.assertEqual(len(crawler.start_urls), 1)

    def test_base_extractor(self):
        """Test that base extractor exists."""
        extractor = BaseExtractor()
        self.assertIsNotNone(extractor)

if __name__ == '__main__':
    unittest.main() 