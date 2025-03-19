#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced Web Crawler Core Module

A high-performance web crawler with advanced features:
- Parallel processing with configurable workers
- Sophisticated throttling and rate limiting
- Comprehensive error handling and retry mechanisms
- Proxy rotation support
- Cache support for respecting revisit rules
- Enhanced JavaScript rendering capabilities
"""

import os
import time
import json
import logging
import random
import re
import urllib.parse
from datetime import datetime
from typing import List, Dict, Set, Optional, Callable, Any, Union, Tuple, Generator
from urllib.robotparser import RobotFileParser
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue
import hashlib
from pathlib import Path
import traceback

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError
from tqdm import tqdm

from src.middlewares.proxy_middleware import ProxyMiddleware
from src.middlewares.rate_limiter import RateLimiter
from src.utils.url_utils import normalize_url, is_same_domain, get_domain
from src.utils.cache_manager import CacheManager
from src.utils.http_utils import extract_redirect_location
from src.utils.browser_utils import setup_browser_page

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('crawler')

class Crawler:
    """
    Enhanced web crawler with advanced features for performance, resilience and flexibility.
    """
    
    def __init__(
        self,
        start_urls: List[str],
        output_dir: str = 'crawled_data',
        max_depth: int = 3,
        delay: float = 1.0,
        respect_robots_txt: bool = True,
        playwright_mode: bool = False,
        headers: Optional[Dict[str, str]] = None,
        allowed_domains: Optional[List[str]] = None,
        url_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        custom_parsers: Optional[Dict[str, Callable[[BeautifulSoup, str], Dict[str, Any]]]] = None,
        max_pages: int = 100,
        timeout: int = 30,
        screenshot_dir: Optional[str] = None,
        max_workers: int = 5,
        proxies: Optional[List[str]] = None,
        retry_count: int = 3,
        retry_delay: float = 2.0,
        cache_enabled: bool = True,
        cache_expiry: int = 3600,  # 1 hour in seconds
        verbose: bool = False,
        cookies: Optional[Dict[str, str]] = None,
        follow_redirects: bool = True,
        verify_ssl: bool = True,
        preserve_cookies: bool = True
    ):
        """
        Initialize the crawler with the given parameters.
        
        Args:
            start_urls: List of URLs to start crawling from
            output_dir: Directory to save crawled data
            max_depth: Maximum depth to crawl (0 means only crawl start_urls)
            delay: Delay between requests in seconds
            respect_robots_txt: Whether to respect robots.txt rules
            playwright_mode: Whether to use Playwright for JavaScript rendering
            headers: Custom headers to use for requests
            allowed_domains: List of domains to restrict crawling to
            url_patterns: List of regex patterns that URLs must match to be crawled
            exclude_patterns: List of regex patterns that URLs must NOT match to be crawled
            custom_parsers: Dictionary mapping URL patterns to custom parser functions
            max_pages: Maximum number of pages to crawl
            timeout: Timeout for requests in seconds
            screenshot_dir: Directory to save screenshots (only used in playwright_mode)
            max_workers: Maximum number of concurrent workers for parallel processing
            proxies: List of proxy URLs to rotate through
            retry_count: Number of times to retry failed requests
            retry_delay: Delay between retries in seconds
            cache_enabled: Whether to enable HTTP cache
            cache_expiry: Time in seconds until cached responses expire
            verbose: Whether to print verbose output
            cookies: Cookies to include in requests
            follow_redirects: Whether to follow HTTP redirects
            verify_ssl: Whether to verify SSL certificates
            preserve_cookies: Whether to maintain cookies between requests to the same domain
        """
        self.start_urls = [normalize_url(url) for url in start_urls]
        self.output_dir = output_dir
        self.max_depth = max_depth
        self.base_delay = delay
        self.respect_robots_txt = respect_robots_txt
        self.playwright_mode = playwright_mode
        self.ua = UserAgent()
        self.allowed_domains = allowed_domains
        self.url_patterns = [re.compile(pattern) for pattern in url_patterns] if url_patterns else None
        self.exclude_patterns = [re.compile(pattern) for pattern in exclude_patterns] if exclude_patterns else None
        self.custom_parsers = custom_parsers or {}
        self.max_pages = max_pages
        self.timeout = timeout
        self.screenshot_dir = screenshot_dir
        self.max_workers = max_workers
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.cache_enabled = cache_enabled
        self.verbose = verbose
        self.cookies = cookies or {}
        self.follow_redirects = follow_redirects
        self.verify_ssl = verify_ssl
        self.preserve_cookies = preserve_cookies
        
        # Set default headers if none provided
        if headers is None:
            self.headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'DNT': '1',  # Do Not Track request header
            }
        else:
            self.headers = headers
        
        # Initialize middleware components
        self.proxy_middleware = ProxyMiddleware(proxies) if proxies else None
        self.rate_limiter = RateLimiter(base_delay=delay, per_domain_rules={})
        self.cache_manager = CacheManager(
            enabled=cache_enabled,
            expiry=cache_expiry,
            cache_dir=os.path.join(output_dir, '.cache')
        )
        
        # Create output directories
        os.makedirs(self.output_dir, exist_ok=True)
        if self.playwright_mode and self.screenshot_dir:
            os.makedirs(self.screenshot_dir, exist_ok=True)
            
        # Initialize variables
        self.visited_urls: Set[str] = set()
        self.robots_parsers: Dict[str, RobotFileParser] = {}
        self.crawl_results: List[Dict[str, Any]] = []
        self.domain_cookies: Dict[str, Dict[str, str]] = {}
        
        # Thread synchronization
        self.lock = threading.Lock()
        self.result_queue = queue.Queue()
        self.pages_crawled = 0
        
        logger.info(f"Initialized crawler with {len(start_urls)} start URLs")
    
    def _is_allowed_by_robots(self, url: str) -> bool:
        """Check if URL is allowed to be crawled according to robots.txt"""
        if not self.respect_robots_txt:
            return True
            
        domain = get_domain(url)
        
        # Create and cache robots parser for this domain if not already done
        if domain not in self.robots_parsers:
            with self.lock:  # For thread safety
                if domain not in self.robots_parsers:  # Double-check after acquiring lock
                    robots_url = f"{urllib.parse.urlparse(url).scheme}://{domain}/robots.txt"
                    parser = RobotFileParser()
                    parser.set_url(robots_url)
                    try:
                        with requests.get(robots_url, timeout=self.timeout, headers=self.headers) as response:
                            if response.status_code == 200:
                                parser.parse(response.text.splitlines())
                            else:
                                logger.warning(f"No robots.txt found at {domain} (status code: {response.status_code})")
                    except Exception as e:
                        logger.warning(f"Error reading robots.txt for {domain}: {e}")
                        return True  # Assume allowed if robots.txt can't be read
                    
                    self.robots_parsers[domain] = parser
        
        return self.robots_parsers[domain].can_fetch(self.headers['User-Agent'], url)
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid for crawling based on various rules"""
        # Basic URL validation
        if not url or not url.startswith(('http://', 'https://')):
            return False
            
        # Check if URL should be excluded
        if self.exclude_patterns:
            for pattern in self.exclude_patterns:
                if pattern.search(url):
                    return False
        
        # Check if URL matches required patterns
        if self.url_patterns:
            matches_pattern = False
            for pattern in self.url_patterns:
                if pattern.search(url):
                    matches_pattern = True
                    break
            if not matches_pattern:
                return False
        
        # Check domain restrictions
        if self.allowed_domains:
            domain = get_domain(url)
            if domain not in self.allowed_domains:
                return False
        
        # Check if URL has been visited already
        if url in self.visited_urls:
            return False
            
        # Check robots.txt rules
        if not self._is_allowed_by_robots(url):
            return False
            
        return True
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract and normalize links from HTML content"""
        links = []
        
        # Get base URL for resolving relative links
        base_tag = soup.find('base', href=True)
        if base_tag:
            base_href = base_tag['href']
            base_url = urllib.parse.urljoin(base_url, base_href)
        
        # Extract links from a, area, and other tags
        for tag in soup.find_all(['a', 'area'], href=True):
            href = tag.get('href')
            if href and not href.startswith(('javascript:', 'mailto:', 'tel:')):
                absolute_url = urllib.parse.urljoin(base_url, href)
                normalized_url = normalize_url(absolute_url)
                links.append(normalized_url)
        
        return links
    
    def _default_parser(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Default parser for web pages when no custom parser matches"""
        result = {}
        result['url'] = url
        result['crawl_time'] = datetime.now().isoformat()
        
        # Extract metadata
        result['title'] = soup.title.text.strip() if soup.title else "No title found"
        
        # Extract meta description and keywords
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        result['description'] = meta_desc['content'] if meta_desc and 'content' in meta_desc.attrs else "No description found"
        
        meta_kw = soup.find('meta', attrs={'name': 'keywords'})
        result['keywords'] = meta_kw['content'] if meta_kw and 'content' in meta_kw.attrs else "No keywords found"
        
        # Extract canonical URL if present
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        result['canonical_url'] = canonical['href'] if canonical and 'href' in canonical.attrs else url
        
        # Calculate page size
        result['page_size_bytes'] = len(str(soup))
        
        # Extract main text content
        text_content = []
        for p in soup.find_all('p'):
            text = p.get_text().strip()
            if text:
                text_content.append(text)
        result['text_content'] = '\n'.join(text_content)
        
        # Extract headers
        headers = {}
        for i in range(1, 7):
            headers[f'h{i}'] = [h.get_text().strip() for h in soup.find_all(f'h{i}')]
        result['headers'] = headers
        
        # Extract links
        result['links'] = self._extract_links(soup, url)
        
        return result
    
    def _get_custom_parser(self, url: str) -> Optional[Callable[[BeautifulSoup, str], Dict[str, Any]]]:
        """Find the appropriate custom parser for a URL"""
        for pattern_str, parser_func in self.custom_parsers.items():
            pattern = re.compile(pattern_str)
            if pattern.search(url):
                return parser_func
        return None
    
    def _make_request(self, url: str, retry: int = 0) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Make HTTP request with retries and proxy support"""
        err_msg = None
        
        # Check if cached response exists and is valid
        if self.cache_enabled:
            cached_response = self.cache_manager.get_response(url)
            if cached_response:
                return cached_response, None
        
        # Apply rate limiting
        if self.rate_limiter:
            domain = get_domain(url)
            self.rate_limiter.wait_for_rate_limit(domain)
        
        # Get proxy if configured
        proxy = None
        if self.proxy_middleware:
            proxy = self.proxy_middleware.get_proxy()
        
        # Get domain-specific cookies if preserving cookies
        domain_cookies = {}
        if self.preserve_cookies:
            domain = get_domain(url)
            with self.lock:
                domain_cookies = self.domain_cookies.get(domain, {})
        
        # Merge cookies
        all_cookies = {**self.cookies, **domain_cookies}
        
        try:
            # Rotate user agent for each request to avoid bot detection
            if 'User-Agent' in self.headers:
                self.headers['User-Agent'] = self.ua.random
            
            # Make the request
            proxies = {"http": proxy, "https": proxy} if proxy else None
            
            response = requests.get(
                url,
                headers=self.headers,
                cookies=all_cookies,
                proxies=proxies,
                timeout=self.timeout,
                allow_redirects=self.follow_redirects,
                verify=self.verify_ssl
            )
            
            # Update domain cookies if needed
            if self.preserve_cookies and response.cookies:
                domain = get_domain(url)
                with self.lock:
                    if domain not in self.domain_cookies:
                        self.domain_cookies[domain] = {}
                    for key, value in response.cookies.items():
                        self.domain_cookies[domain][key] = value
            
            # Cache the response if enabled
            if self.cache_enabled and response.status_code == 200:
                self.cache_manager.cache_response(url, response)
            
            return response, None
            
        except requests.exceptions.SSLError as e:
            err_msg = f"SSL Error: {str(e)}"
        except requests.exceptions.ConnectionError as e:
            err_msg = f"Connection Error: {str(e)}"
        except requests.exceptions.Timeout as e:
            err_msg = f"Timeout Error: {str(e)}"
        except requests.exceptions.RequestException as e:
            err_msg = f"Request Error: {str(e)}"
        except Exception as e:
            err_msg = f"Unexpected Error: {str(e)}"
            
        # Retry logic
        if retry < self.retry_count:
            logger.warning(f"Error fetching {url}: {err_msg}. Retrying ({retry + 1}/{self.retry_count})...")
            time.sleep(self.retry_delay * (retry + 1))  # Exponential backoff
            return self._make_request(url, retry + 1)
        else:
            logger.error(f"Failed to fetch {url} after {self.retry_count} attempts: {err_msg}")
            return None, err_msg
    
    def _process_page_with_requests(self, url: str) -> Tuple[Optional[BeautifulSoup], List[str], Optional[str]]:
        """Process a page using requests library"""
        response, error = self._make_request(url)
        
        if error or not response:
            return None, [], error
            
        # Handle redirects if not following automatically
        if not self.follow_redirects and response.status_code in (301, 302, 303, 307, 308):
            redirect_url = extract_redirect_location(response)
            if redirect_url:
                logger.info(f"Following redirect from {url} to {redirect_url}")
                return self._process_page_with_requests(redirect_url)
        
        # Only process pages with 200 status code and HTML content
        if response.status_code != 200:
            return None, [], f"HTTP Error: {response.status_code}"
            
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type:
            return None, [], f"Not HTML content: {content_type}"
            
        try:
            # Parse HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract links
            links = self._extract_links(soup, url)
            
            return soup, links, None
        except Exception as e:
            return None, [], f"Error parsing HTML: {str(e)}"
    
    def _process_page_with_playwright(self, url: str, page: Page) -> Tuple[Optional[BeautifulSoup], List[str], Optional[str]]:
        """Process a page using Playwright for JavaScript rendering"""
        try:
            # Navigate to the URL
            response = page.goto(
                url,
                timeout=self.timeout * 1000,  # Playwright uses milliseconds
                wait_until="networkidle"
            )
            
            if not response:
                return None, [], "Failed to get response from page"
                
            if response.status != 200:
                return None, [], f"HTTP Error: {response.status}"
                
            # Wait for content to load
            page.wait_for_load_state("networkidle")
            
            # Take screenshot if enabled
            if self.screenshot_dir:
                url_hash = hashlib.md5(url.encode()).hexdigest()
                screenshot_path = os.path.join(self.screenshot_dir, f"{url_hash}.png")
                page.screenshot(path=screenshot_path, full_page=True)
            
            # Get the HTML content
            html_content = page.content()
            
            # Parse the HTML
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract links
            links = self._extract_links(soup, url)
            
            return soup, links, None
            
        except PlaywrightTimeoutError:
            return None, [], "Timeout while loading page"
        except Exception as e:
            logger.error(f"Error processing {url} with Playwright: {str(e)}\n{traceback.format_exc()}")
            return None, [], f"Error with Playwright: {str(e)}"
    
    def _process_url(self, url: str, depth: int, page: Optional[Page] = None) -> Dict[str, Any]:
        """Process a single URL and return extracted data"""
        logger.info(f"Processing URL: {url} (depth: {depth})")
        
        # Mark URL as visited
        with self.lock:
            self.visited_urls.add(url)
        
        # Process page with appropriate method
        if self.playwright_mode and page:
            soup, links, error = self._process_page_with_playwright(url, page)
        else:
            soup, links, error = self._process_page_with_requests(url)
        
        # Return error result if processing failed
        if error or not soup:
            return {
                'url': url,
                'crawl_time': datetime.now().isoformat(),
                'status': 'error',
                'error': error or 'Unknown error',
                'links': [],
                'depth': depth
            }
        
        # Parse the page
        custom_parser = self._get_custom_parser(url)
        if custom_parser:
            try:
                result = custom_parser(soup, url)
            except Exception as e:
                logger.error(f"Error in custom parser for {url}: {str(e)}")
                result = self._default_parser(soup, url)
        else:
            result = self._default_parser(soup, url)
        
        # Add depth and found links to the result
        result['depth'] = depth
        result['links'] = links
        result['status'] = 'success'
        
        # Queue child URLs if not at max depth
        if depth < self.max_depth:
            with self.lock:
                queue_count = 0
                for link in links:
                    if self._is_valid_url(link):
                        self.result_queue.put((link, depth + 1))
                        queue_count += 1
                
                logger.debug(f"Queued {queue_count} new URLs from {url}")
        
        # Update crawl metrics
        with self.lock:
            self.pages_crawled += 1
            
        return result
    
    def _worker(self, urls_to_process: List[Tuple[str, int]]):
        """Worker function for threaded crawling"""
        with sync_playwright() as playwright:
            # Create a new browser and page for this worker if using Playwright
            page = None
            if self.playwright_mode:
                browser = setup_browser_page(playwright)
                page = browser.new_page(user_agent=self.ua.random)
                
                # Configure page
                page.set_default_timeout(self.timeout * 1000)
                if self.cookies:
                    for name, value in self.cookies.items():
                        page.add_cookie({"name": name, "value": value, "url": self.start_urls[0]})
            
            try:
                for url, depth in urls_to_process:
                    # Check if max pages has been reached
                    with self.lock:
                        if self.pages_crawled >= self.max_pages:
                            break
                        
                        # Check if URL has been visited (another thread might have processed it)
                        if url in self.visited_urls:
                            continue
                    
                    # Process the URL
                    result = self._process_url(url, depth, page)
                    
                    # Add result to results list
                    with self.lock:
                        self.crawl_results.append(result)
            
            finally:
                # Close browser if using Playwright
                if self.playwright_mode and page:
                    page.close()
                    if browser:
                        browser.close()
    
    def crawl(self) -> List[Dict[str, Any]]:
        """Crawl starting from the provided URLs"""
        start_time = time.time()
        logger.info(f"Starting crawl with {len(self.start_urls)} URLs, max depth {self.max_depth}, max pages {self.max_pages}")
        
        # Reset state for new crawl
        self.visited_urls = set()
        self.crawl_results = []
        self.pages_crawled = 0
        
        # Initialize the queue with start URLs
        urls_to_process = [(url, 0) for url in self.start_urls]
        for url in self.start_urls:
            self.result_queue.put((url, 0))
        
        # Process URLs in parallel with ThreadPoolExecutor
        if self.max_workers > 1 and not self.playwright_mode:
            # For non-Playwright mode, use ThreadPoolExecutor for parallelism
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Create initial batch of tasks
                futures = []
                for _ in range(min(self.max_workers, self.result_queue.qsize())):
                    if not self.result_queue.empty():
                        urls_batch = []
                        urls_batch.append(self.result_queue.get())
                        futures.append(executor.submit(self._worker, urls_batch))
                
                # Process the queue as items are added
                while futures and self.pages_crawled < self.max_pages:
                    # Wait for at least one task to complete
                    completed, futures = as_completed(futures, timeout=None), []
                    
                    # For each completed task, potentially add a new one
                    for future in completed:
                        try:
                            future.result()  # Get the result (or exception)
                        except Exception as e:
                            logger.error(f"Worker error: {str(e)}")
                        
                        # If queue is not empty and we haven't reached max pages, add a new task
                        if not self.result_queue.empty() and self.pages_crawled < self.max_pages:
                            urls_batch = []
                            urls_batch.append(self.result_queue.get())
                            futures.append(executor.submit(self._worker, urls_batch))
        else:
            # For Playwright mode or single worker, process sequentially
            self._worker([(url, 0) for url in self.start_urls])
            
            # Process any additional URLs added to the queue
            while not self.result_queue.empty() and self.pages_crawled < self.max_pages:
                url, depth = self.result_queue.get()
                if url not in self.visited_urls:
                    self._worker([(url, depth)])
        
        elapsed_time = time.time() - start_time
        logger.info(f"Crawl completed in {elapsed_time:.2f} seconds. Processed {self.pages_crawled} pages.")
        
        return self.crawl_results
    
    def export_to_json(self, filename: Optional[str] = None) -> str:
        """Export crawl results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.output_dir, f"crawl_results_{timestamp}.json")
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.crawl_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results exported to JSON: {filename}")
        return filename
    
    def export_to_csv(self, filename: Optional[str] = None) -> str:
        """Export crawl results to CSV file"""
        import pandas as pd
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.output_dir, f"crawl_results_{timestamp}.csv")
        
        # Flatten the results for CSV export
        flattened_results = []
        for result in self.crawl_results:
            flat_result = {}
            for key, value in result.items():
                if key == 'links':
                    flat_result[key] = ';'.join(value)
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, list):
                            flat_result[f"{key}_{sub_key}"] = ';'.join(sub_value)
                        else:
                            flat_result[f"{key}_{sub_key}"] = sub_value
                elif isinstance(value, list):
                    flat_result[key] = ';'.join(value)
                else:
                    flat_result[key] = value
            flattened_results.append(flat_result)
        
        # Create DataFrame and export to CSV
        df = pd.DataFrame(flattened_results)
        df.to_csv(filename, index=False, encoding='utf-8')
        
        logger.info(f"Results exported to CSV: {filename}")
        return filename
    
    def add_custom_parser(self, url_pattern: str, parser_func: Callable[[BeautifulSoup, str], Dict[str, Any]]) -> None:
        """Add a custom parser function for URLs matching the given pattern"""
        self.custom_parsers[url_pattern] = parser_func
        logger.info(f"Added custom parser for pattern: {url_pattern}")
    
    def clear_cache(self) -> None:
        """Clear the HTTP cache"""
        if self.cache_manager:
            self.cache_manager.clear_cache()
            logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Return statistics about the crawl"""
        stats = {
            'pages_crawled': self.pages_crawled,
            'unique_domains': len(set(get_domain(url) for url in self.visited_urls)),
            'total_urls_discovered': len(self.visited_urls),
            'success_count': sum(1 for r in self.crawl_results if r.get('status') == 'success'),
            'error_count': sum(1 for r in self.crawl_results if r.get('status') == 'error'),
            'content_size_total': sum(r.get('page_size_bytes', 0) for r in self.crawl_results),
        }
        return stats 