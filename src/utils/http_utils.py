#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTTP Utilities Module

Provides utilities for HTTP operations:
- Header manipulation
- Response processing
- Redirect handling
- Response validation
"""

import random
import time
from typing import Dict, Optional, List, Tuple, Union
import logging
import requests
from requests.models import Response

# Configure logging
logger = logging.getLogger('http_utils')

# Common user agent strings for popular browsers
USER_AGENTS = [
    # Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (X11; Linux i686; rv:122.0) Gecko/20100101 Firefox/122.0",
    
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

def get_random_user_agent() -> str:
    """
    Get a random user agent string from common browsers.
    
    Returns:
        Random user agent string
    """
    return random.choice(USER_AGENTS)


def create_headers(
    user_agent: Optional[str] = None,
    accept_language: str = "en-US,en;q=0.9",
    referer: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """
    Create HTTP headers with optional customization.
    
    Args:
        user_agent: User-Agent string (random if None)
        accept_language: Accept-Language header value
        referer: Referer URL
        custom_headers: Additional custom headers
        
    Returns:
        Dictionary of headers
    """
    headers = {
        "User-Agent": user_agent or get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": accept_language,
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "DNT": "1",  # Do Not Track
    }
    
    if referer:
        headers["Referer"] = referer
    
    # Add custom headers
    if custom_headers:
        headers.update(custom_headers)
    
    return headers


def extract_redirect_location(response: Response) -> Optional[str]:
    """
    Extract the redirect location from a response.
    
    Args:
        response: HTTP response object
        
    Returns:
        Redirect URL or None if not a redirect
    """
    if response.status_code in (301, 302, 303, 307, 308):
        return response.headers.get('Location')
    return None


def is_success_response(response: Response) -> bool:
    """
    Check if response indicates success (2xx status code).
    
    Args:
        response: HTTP response object
        
    Returns:
        True if successful
    """
    return 200 <= response.status_code < 300


def is_html_response(response: Response) -> bool:
    """
    Check if response contains HTML content.
    
    Args:
        response: HTTP response object
        
    Returns:
        True if HTML content
    """
    content_type = response.headers.get('Content-Type', '').lower()
    return 'text/html' in content_type


def is_json_response(response: Response) -> bool:
    """
    Check if response contains JSON content.
    
    Args:
        response: HTTP response object
        
    Returns:
        True if JSON content
    """
    content_type = response.headers.get('Content-Type', '').lower()
    return 'application/json' in content_type


def get_retry_after(response: Response) -> Optional[float]:
    """
    Get the Retry-After value from response headers.
    
    Args:
        response: HTTP response object
        
    Returns:
        Number of seconds to wait before retrying, or None if not specified
    """
    retry_after = response.headers.get('Retry-After')
    
    if not retry_after:
        return None
    
    # Try to parse as integer (seconds)
    try:
        return float(retry_after)
    except ValueError:
        pass
    
    # Try to parse as HTTP date
    try:
        from email.utils import parsedate_to_datetime
        retry_date = parsedate_to_datetime(retry_after)
        wait_time = (retry_date - datetime.now()).total_seconds()
        return max(0, wait_time)  # Don't return negative time
    except Exception:
        logger.warning(f"Failed to parse Retry-After header: {retry_after}")
        return None


def handle_rate_limits(response: Response) -> bool:
    """
    Handle rate limiting responses (429 Too Many Requests).
    Waits the appropriate time if Retry-After header is present.
    
    Args:
        response: HTTP response object
        
    Returns:
        True if rate limit was handled, False otherwise
    """
    if response.status_code != 429:
        return False
    
    wait_time = get_retry_after(response) or 30  # Default 30 seconds if not specified
    logger.warning(f"Rate limited. Waiting {wait_time} seconds before retry.")
    time.sleep(wait_time)
    return True


def get_response_size(response: Response) -> int:
    """
    Get the size of the response in bytes.
    
    Args:
        response: HTTP response object
        
    Returns:
        Size in bytes
    """
    # Try Content-Length header first
    content_length = response.headers.get('Content-Length')
    if content_length:
        try:
            return int(content_length)
        except ValueError:
            pass
    
    # Fall back to measuring the actual content
    return len(response.content)


def normalize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Normalize header names to title case for consistency.
    
    Args:
        headers: Dictionary of headers
        
    Returns:
        Dictionary with normalized header names
    """
    return {k.title(): v for k, v in headers.items()}


def extract_cookies(response: Response) -> Dict[str, str]:
    """
    Extract cookies from a response as a simple dictionary.
    
    Args:
        response: HTTP response object
        
    Returns:
        Dictionary of cookies
    """
    return {k: v for k, v in response.cookies.items()}


def check_cloudflare_protection(response: Response) -> bool:
    """
    Check if response indicates Cloudflare protection is active.
    
    Args:
        response: HTTP response object
        
    Returns:
        True if Cloudflare protection detected
    """
    # Check for Cloudflare headers
    cf_ray = 'cf-ray' in response.headers
    server = response.headers.get('server', '').lower().startswith('cloudflare')
    
    # Check for Cloudflare challenge page
    if response.status_code == 403 and (cf_ray or server):
        return True
    
    # Check for Cloudflare CAPTCHA or JavaScript challenge
    if (response.status_code == 503 and
            ('cloudflare' in response.text.lower() or 
             'attention required' in response.text.lower())):
        return True
    
    return False 