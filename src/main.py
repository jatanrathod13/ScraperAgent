#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web Crawler Main Script

This script provides a command-line interface for the web crawler,
supporting various types of content extraction and output formats.
"""

import os
import sys
import logging
import json
import argparse
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup

from src.core.crawler import Crawler
from src.extractors.base_extractor import BaseExtractor
from src.extractors.ecommerce_extractor import EcommerceExtractor
from src.extractors.news_extractor import NewsExtractor
from src.extractors.social_media_extractor import SocialMediaExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraper.log')
    ]
)

logger = logging.getLogger('scraper')

def setup_argparse() -> argparse.ArgumentParser:
    """
    Set up command-line argument parsing.
    
    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Web scraper with specialized extractors for different content types',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Add main arguments
    parser.add_argument('url', nargs='?', help='URL to scrape (or use a file with --url-file)')
    parser.add_argument('-o', '--output', default='output', help='Output directory for scraped data')
    parser.add_argument('-f', '--format', choices=['json', 'csv'], default='json', 
                       help='Output format for scraped data')
    
    # Add crawler related arguments
    parser.add_argument('--url-file', help='File containing URLs to scrape (one per line)')
    parser.add_argument('--depth', type=int, default=0, 
                       help='Crawl depth (0 means just the provided URLs)')
    parser.add_argument('--delay', type=float, default=1.0, 
                       help='Delay between requests in seconds')
    
    # Add extractor related arguments
    parser.add_argument('--extractor', choices=['auto', 'ecommerce', 'news', 'social'], default='auto', 
                       help='Extractor to use (auto will try to detect the best one)')
    parser.add_argument('--extract-all', action='store_true', 
                       help='Run all extractors on each page')
    
    # Add browser/request options
    parser.add_argument('--browser', action='store_true', 
                       help='Use browser automation (Playwright) instead of requests')
    parser.add_argument('--user-agent', 
                       help='Custom User-Agent string')
    parser.add_argument('--headers', 
                       help='Additional headers as JSON string')
    parser.add_argument('--proxy', 
                       help='Proxy to use (format: protocol://host:port)')
    
    # Add other options
    parser.add_argument('--verbose', action='store_true', 
                       help='Enable verbose output')
    parser.add_argument('--timeout', type=int, default=30, 
                       help='Request timeout in seconds')
    parser.add_argument('--cache', action='store_true', default=True, 
                       help='Use request caching')
    parser.add_argument('--no-cache', action='store_false', dest='cache', 
                       help='Disable request caching')
    
    return parser

def get_urls_from_file(filename: str) -> List[str]:
    """
    Read URLs from a file.
    
    Args:
        filename: Path to a file containing URLs (one per line)
        
    Returns:
        List of URLs
    """
    urls = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
    except Exception as e:
        logger.error(f"Error reading URL file: {e}")
        sys.exit(1)
    
    return urls

def extract_data(url: str, args: argparse.Namespace) -> Dict[str, Any]:
    """
    Extract data from a single URL.
    
    Args:
        url: URL to extract data from
        args: Command-line arguments
        
    Returns:
        Dictionary of extracted data
    """
    try:
        # Set up headers
        headers = {'User-Agent': args.user_agent} if args.user_agent else None
        
        if args.headers:
            try:
                additional_headers = json.loads(args.headers)
                if headers:
                    headers.update(additional_headers)
                else:
                    headers = additional_headers
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse headers JSON: {args.headers}")
        
        # Set up proxy
        proxies = None
        if args.proxy:
            proxies = {
                'http': args.proxy,
                'https': args.proxy
            }
        
        # Fetch the page
        if args.verbose:
            logger.info(f"Fetching URL: {url}")
            
        if args.browser:
            # Use Playwright for browser automation
            try:
                from playwright.sync_api import sync_playwright
                
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    page = browser.new_page(
                        user_agent=args.user_agent if args.user_agent else None,
                        proxy={'server': args.proxy} if args.proxy else None
                    )
                    
                    page.goto(url, timeout=args.timeout * 1000)
                    page.wait_for_load_state('networkidle')
                    
                    html = page.content()
                    browser.close()
                    
            except ImportError:
                logger.error("Playwright not installed. Install it with: pip install playwright")
                logger.error("Then run: playwright install")
                sys.exit(1)
                
        else:
            # Use requests
            response = requests.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=args.timeout
            )
            response.raise_for_status()
            html = response.text
        
        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Select extractor
        if args.extract_all:
            # Run all extractors
            results = {}
            for extractor_class in [EcommerceExtractor, NewsExtractor, SocialMediaExtractor]:
                extractor = extractor_class()
                if extractor.can_extract(soup, url):
                    extractor_name = extractor.__class__.__name__.replace('Extractor', '').lower()
                    results[extractor_name] = extractor.extract(soup, url)
            
            if not results:
                logger.warning(f"No suitable extractor found for {url}")
                results = {"raw_html": html}
                
            result = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "extractors": results
            }
            
        else:
            # Use a single extractor
            if args.extractor == 'ecommerce':
                extractor = EcommerceExtractor()
            elif args.extractor == 'news':
                extractor = NewsExtractor()
            elif args.extractor == 'social':
                extractor = SocialMediaExtractor()
            else:  # auto
                # Try each extractor in turn
                extractor = None
                for extractor_class in [EcommerceExtractor, NewsExtractor, SocialMediaExtractor]:
                    potential_extractor = extractor_class()
                    if potential_extractor.can_extract(soup, url):
                        extractor = potential_extractor
                        break
                
                if not extractor:
                    logger.warning(f"No suitable extractor found for {url}")
                    return {
                        "url": url,
                        "timestamp": datetime.now().isoformat(),
                        "error": "No suitable extractor found"
                    }
            
            extractor_name = extractor.__class__.__name__.replace('Extractor', '').lower()
            extracted_data = extractor.extract(soup, url)
            
            result = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "extractor": extractor_name,
                "data": extracted_data
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Error extracting data from {url}: {e}", exc_info=args.verbose)
        return {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

def crawl_and_extract(urls: List[str], args: argparse.Namespace) -> List[Dict[str, Any]]:
    """
    Crawl and extract data from multiple URLs.
    
    Args:
        urls: List of URLs to process
        args: Command-line arguments
        
    Returns:
        List of extracted data
    """
    # Configure crawler
    crawler = Crawler(
        start_urls=urls,
        output_dir=args.output,
        max_depth=args.depth,
        delay=args.delay,
        respect_robots_txt=True,
        playwright_mode=args.browser,
        headers={'User-Agent': args.user_agent} if args.user_agent else None,
        timeout=args.timeout,
        cache_enabled=args.cache,
        verbose=args.verbose
    )
    
    # Add custom parsers based on extractors
    def create_parser(extractor):
        def parser(soup, url):
            try:
                if extractor.can_extract(soup, url):
                    return extractor.extract(soup, url)
            except Exception as e:
                logger.error(f"Error in extractor for {url}: {e}", exc_info=args.verbose)
            return {}
        return parser
    
    # Add parsers for each extractor
    crawler.add_custom_parser('.*', create_parser(EcommerceExtractor()))
    crawler.add_custom_parser('.*', create_parser(NewsExtractor()))
    crawler.add_custom_parser('.*', create_parser(SocialMediaExtractor()))
    
    # Start crawling
    logger.info(f"Starting crawl of {len(urls)} URLs with depth {args.depth}")
    results = crawler.crawl()
    
    logger.info(f"Crawl complete. Processed {len(results)} pages")
    
    return results

def save_results(results: List[Dict[str, Any]], args: argparse.Namespace) -> None:
    """
    Save results to disk.
    
    Args:
        results: Extracted data
        args: Command-line arguments
    """
    os.makedirs(args.output, exist_ok=True)
    
    # Generate filename based on timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if args.format == 'json':
        filename = os.path.join(args.output, f"scraped_data_{timestamp}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    
    elif args.format == 'csv':
        import csv
        
        filename = os.path.join(args.output, f"scraped_data_{timestamp}.csv")
        
        # Flatten results for CSV
        flattened = []
        for item in results:
            flat_item = {'url': item.get('url'), 'timestamp': item.get('timestamp')}
            
            # Get extractor name
            extractor = item.get('extractor')
            if extractor:
                flat_item['extractor'] = extractor
            
            # Extract basic data
            data = item.get('data', {})
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        flat_item[key] = value
            
            flattened.append(flat_item)
        
        if flattened:
            # Get all possible field names
            fieldnames = set()
            for item in flattened:
                fieldnames.update(item.keys())
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
                writer.writeheader()
                writer.writerows(flattened)
    
    logger.info(f"Results saved to {filename}")

def main() -> None:
    """
    Main entry point for the script.
    """
    # Parse command-line arguments
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Get URLs to process
    urls = []
    
    if args.url:
        urls.append(args.url)
    
    if args.url_file:
        file_urls = get_urls_from_file(args.url_file)
        urls.extend(file_urls)
    
    if not urls:
        parser.print_help()
        sys.exit(1)
    
    # Process URLs
    if args.depth > 0:
        # Crawl mode
        results = crawl_and_extract(urls, args)
    else:
        # Single page extraction mode
        results = []
        for url in urls:
            result = extract_data(url, args)
            results.append(result)
            logger.info(f"Extracted data from {url}")
    
    # Save results
    save_results(results, args)

if __name__ == "__main__":
    main() 