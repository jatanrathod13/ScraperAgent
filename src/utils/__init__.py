"""
Utility functions and classes for the crawler.
"""

from .url_utils import (
    normalize_url,
    get_domain,
    get_base_url,
    is_same_domain,
    is_subdomain,
    is_valid_url,
    extract_url_components,
    url_join,
    is_same_page
)

from .http_utils import (
    get_random_user_agent,
    create_headers,
    extract_redirect_location,
    is_success_response,
    is_html_response,
    is_json_response,
    get_retry_after,
    handle_rate_limits,
    get_response_size,
    normalize_headers,
    extract_cookies,
    check_cloudflare_protection
)

from .browser_utils import (
    setup_browser_page,
    create_browser_context,
    apply_stealth_mode,
    take_full_page_screenshot,
    save_page_as_pdf,
    execute_js_on_page,
    wait_for_navigation_idle,
    simulate_human_interaction,
    extract_page_metadata
)

from .cache_manager import CacheManager

__all__ = [
    # URL utilities
    'normalize_url', 'get_domain', 'get_base_url', 'is_same_domain',
    'is_subdomain', 'is_valid_url', 'extract_url_components', 'url_join',
    'is_same_page',
    
    # HTTP utilities
    'get_random_user_agent', 'create_headers', 'extract_redirect_location',
    'is_success_response', 'is_html_response', 'is_json_response',
    'get_retry_after', 'handle_rate_limits', 'get_response_size',
    'normalize_headers', 'extract_cookies', 'check_cloudflare_protection',
    
    # Browser utilities
    'setup_browser_page', 'create_browser_context', 'apply_stealth_mode',
    'take_full_page_screenshot', 'save_page_as_pdf', 'execute_js_on_page',
    'wait_for_navigation_idle', 'simulate_human_interaction', 'extract_page_metadata',
    
    # Cache manager
    'CacheManager'
] 