#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
URL Utilities Module

Provides utilities for manipulating and validating URLs:
- URL normalization
- Domain extraction
- URL comparison
- URL parsing and validation
"""

import re
import urllib.parse
from typing import Optional, Tuple, List
from urllib.parse import urlparse, urlunparse, ParseResult, parse_qs, urlencode


def normalize_url(url: str) -> str:
    """
    Normalize a URL by removing fragments, normalizing path,
    sorting query parameters, and ensuring consistent scheme.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL
    """
    # Parse the URL
    parsed = urlparse(url)
    
    # Force lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Sort query parameters and rebuild query string
    if parsed.query:
        query_params = parse_qs(parsed.query)
        # Sort the params by key and then values
        sorted_query = {k: sorted(v) for k, v in sorted(query_params.items())}
        # Rebuild the query string
        query = urlencode(sorted_query, doseq=True)
    else:
        query = ''
    
    # Remove default ports (80 for http, 443 for https)
    if ':' in netloc:
        host, port = netloc.split(':', 1)
        if (scheme == 'http' and port == '80') or (scheme == 'https' and port == '443'):
            netloc = host
    
    # Remove trailing slashes from path if it's not the root path
    path = parsed.path
    if path != '/' and path.endswith('/'):
        path = path.rstrip('/')
    
    # Handle case where path is empty
    if not path:
        path = '/'
    
    # Rebuild the URL without the fragment
    normalized = urlunparse((scheme, netloc, path, parsed.params, query, ''))
    
    return normalized


def get_domain(url: str) -> str:
    """
    Extract the domain from a URL.
    
    Args:
        url: URL to extract domain from
        
    Returns:
        Domain name
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Remove port if present
    if ':' in domain:
        domain = domain.split(':', 1)[0]
    
    return domain


def get_base_url(url: str) -> str:
    """
    Get the base URL (scheme + domain) from a full URL.
    
    Args:
        url: URL to extract base from
        
    Returns:
        Base URL (scheme + domain)
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Check if two URLs belong to the same domain.
    
    Args:
        url1: First URL
        url2: Second URL
        
    Returns:
        True if URLs belong to the same domain
    """
    return get_domain(url1) == get_domain(url2)


def is_subdomain(domain: str, parent_domain: str) -> bool:
    """
    Check if domain is a subdomain of parent_domain.
    
    Args:
        domain: Domain to check
        parent_domain: Potential parent domain
        
    Returns:
        True if domain is a subdomain of parent_domain
    """
    if domain == parent_domain:
        return False
    
    return domain.endswith(f".{parent_domain}")


def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def extract_url_components(url: str) -> Tuple[str, str, str, dict, str]:
    """
    Extract components from a URL.
    
    Args:
        url: URL to extract components from
        
    Returns:
        Tuple of (scheme, domain, path, query_params, fragment)
    """
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    return (
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        query_params,
        parsed.fragment
    )


def url_join(*parts: str) -> str:
    """
    Join URL parts together, handling trailing and leading slashes.
    
    Args:
        *parts: URL parts to join
        
    Returns:
        Joined URL
    """
    base = parts[0]
    
    for part in parts[1:]:
        if base.endswith('/'):
            if part.startswith('/'):
                base = base + part[1:]
            else:
                base = base + part
        else:
            if part.startswith('/'):
                base = base + part
            else:
                base = base + '/' + part
    
    return base


def is_same_page(url1: str, url2: str) -> bool:
    """
    Check if two URLs point to the same page, ignoring query parameters and fragments.
    
    Args:
        url1: First URL
        url2: Second URL
        
    Returns:
        True if URLs point to the same page
    """
    parsed1 = urlparse(url1)
    parsed2 = urlparse(url2)
    
    # Compare scheme, netloc and path
    return (
        parsed1.scheme.lower() == parsed2.scheme.lower() and
        parsed1.netloc.lower() == parsed2.netloc.lower() and
        parsed1.path.rstrip('/') == parsed2.path.rstrip('/')
    ) 