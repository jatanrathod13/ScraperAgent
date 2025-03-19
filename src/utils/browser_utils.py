#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Browser Utilities Module

Provides utilities for browser automation with Playwright:
- Browser setup with various configurations
- Stealth mode for avoiding bot detection
- Screenshot and PDF capture
- Browser profile management
"""

import os
import logging
import random
import json
from typing import Dict, Optional, List, Any, Union, Tuple
from pathlib import Path

from playwright.sync_api import (
    sync_playwright, 
    Browser, 
    BrowserContext, 
    Page, 
    Playwright,
    BrowserType
)

# Configure logging
logger = logging.getLogger('browser_utils')

# Browser options
BROWSER_TYPES = ['chromium', 'firefox', 'webkit']

def setup_browser_page(
    playwright: Playwright,
    browser_type: str = 'chromium',
    headless: bool = True,
    user_agent: Optional[str] = None,
    proxy: Optional[Dict[str, str]] = None,
    viewport: Optional[Dict[str, int]] = None,
    geolocation: Optional[Dict[str, float]] = None,
    locale: str = 'en-US',
    timezone_id: str = 'America/New_York',
    permissions: Optional[List[str]] = None,
    stealth_mode: bool = True,
    ignore_https_errors: bool = True,
    disable_javascript: bool = False,
    user_data_dir: Optional[str] = None,
    slow_mo: int = 0,
    devtools: bool = False
) -> Browser:
    """
    Setup and configure a Playwright browser.
    
    Args:
        playwright: Playwright instance
        browser_type: Type of browser ('chromium', 'firefox', or 'webkit')
        headless: Whether to run in headless mode
        user_agent: Custom user agent string
        proxy: Proxy configuration (e.g. {'server': 'http://myproxy.com:8080'})
        viewport: Viewport size (e.g. {'width': 1280, 'height': 800})
        geolocation: Geolocation (e.g. {'latitude': 37.7749, 'longitude': -122.4194})
        locale: Locale setting
        timezone_id: Timezone identifier
        permissions: List of permissions to grant
        stealth_mode: Whether to enable stealth mode for bot detection avoidance
        ignore_https_errors: Whether to ignore HTTPS errors
        disable_javascript: Whether to disable JavaScript
        user_data_dir: Directory for persistent browser data
        slow_mo: Slow down operations by specified milliseconds
        devtools: Whether to auto-open DevTools
        
    Returns:
        Configured browser instance
    """
    if browser_type not in BROWSER_TYPES:
        logger.warning(f"Invalid browser type {browser_type}, defaulting to chromium")
        browser_type = 'chromium'
    
    # Get browser launcher
    browser_launcher: BrowserType = getattr(playwright, browser_type)
    
    # Prepare launch options
    launch_options = {
        'headless': headless,
        'slow_mo': slow_mo,
        'devtools': devtools,
    }
    
    # Add user data directory if specified (for persistent sessions)
    if user_data_dir:
        os.makedirs(user_data_dir, exist_ok=True)
        launch_options['user_data_dir'] = user_data_dir
    
    # Launch the browser
    browser = browser_launcher.launch(**launch_options)
    
    logger.info(f"Launched {browser_type} browser. Headless: {headless}")
    
    return browser


def create_browser_context(
    browser: Browser,
    user_agent: Optional[str] = None,
    proxy: Optional[Dict[str, str]] = None,
    viewport: Optional[Dict[str, int]] = None,
    geolocation: Optional[Dict[str, float]] = None,
    locale: str = 'en-US',
    timezone_id: str = 'America/New_York',
    permissions: Optional[List[str]] = None,
    stealth_mode: bool = True,
    ignore_https_errors: bool = True,
    disable_javascript: bool = False,
    cookies: Optional[List[Dict[str, Any]]] = None
) -> BrowserContext:
    """
    Create a browser context with the specified configuration.
    
    Args:
        browser: Browser instance
        (Other parameters as in setup_browser_page)
        cookies: Cookies to set in the context
        
    Returns:
        Configured browser context
    """
    context_options = {
        'locale': locale,
        'timezone_id': timezone_id,
        'ignore_https_errors': ignore_https_errors,
    }
    
    if user_agent:
        context_options['user_agent'] = user_agent
    
    if proxy:
        context_options['proxy'] = proxy
    
    if viewport:
        context_options['viewport'] = viewport
    
    if geolocation:
        context_options['geolocation'] = geolocation
    
    # Create the context
    context = browser.new_context(**context_options)
    
    # Apply stealth mode for bot detection avoidance
    if stealth_mode:
        apply_stealth_mode(context)
    
    # Set JavaScript enabled/disabled
    if disable_javascript:
        context.route(
            "**/*",
            lambda route, request: route.continue_(
                headers={**request.headers, "Content-Type": "text/plain"}
            ) if request.resource_type == "script" else route.continue_()
        )
    
    # Grant permissions
    if permissions:
        context.grant_permissions(permissions)
    
    # Set cookies if provided
    if cookies:
        context.add_cookies(cookies)
    
    return context


def apply_stealth_mode(context: BrowserContext) -> None:
    """
    Apply various techniques to make the browser harder to detect as automated.
    
    Args:
        context: Browser context to apply stealth mode to
    """
    # Add script to modify navigator properties
    stealth_script = """
    () => {
        // Overwrite the navigator properties
        const newProto = navigator.__proto__;
        delete newProto.webdriver;
        
        // Modify navigator prototype
        Object.setPrototypeOf(navigator, newProto);
        
        // Add language property
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        
        // Override permissions
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: () => Promise.resolve({ state: 'granted' }),
            }),
        });
        
        // Add plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    {
                        name: "PDF Viewer",
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1
                    },
                    {
                        name: "Chrome PDF Viewer",
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1
                    },
                    {
                        name: "Chromium PDF Viewer",
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1
                    },
                    {
                        name: "Microsoft Edge PDF Viewer",
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1
                    },
                    {
                        name: "WebKit built-in PDF",
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1
                    }
                ];
                return plugins;
            }
        });
        
        // Hide automation features from window object
        window.chrome = {
            runtime: {},
            loadTimes: function() {
                return;
            },
            csi: function() {
                return;
            },
            app: {
                isInstalled: false,
            },
        };
        
        // Hide Playwright-specific objects
        delete window.playwright;
        
        // Add fake notification functionality
        window.Notification = {
            permission: 'default',
            requestPermission: () => Promise.resolve('default'),
        };
    }
    """
    context.add_init_script(stealth_script)
    logger.debug("Applied stealth mode to browser context")


def take_full_page_screenshot(page: Page, path: str, quality: int = 80) -> None:
    """
    Take a full page screenshot and save it to the specified path.
    
    Args:
        page: Page to take screenshot of
        path: Path to save screenshot to
        quality: JPEG quality (0-100)
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    
    # Take screenshot
    page.screenshot(path=path, full_page=True, quality=quality)
    logger.debug(f"Saved full page screenshot to {path}")


def save_page_as_pdf(page: Page, path: str, options: Optional[Dict[str, Any]] = None) -> None:
    """
    Save the page as a PDF.
    
    Args:
        page: Page to save as PDF
        path: Path to save PDF to
        options: PDF options
    """
    default_options = {
        'format': 'A4',
        'printBackground': True,
        'margin': {
            'top': '1cm',
            'bottom': '1cm',
            'left': '1cm',
            'right': '1cm'
        }
    }
    
    pdf_options = {**default_options, **(options or {})}
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    
    # Save as PDF
    page.pdf(path=path, **pdf_options)
    logger.debug(f"Saved page as PDF to {path}")


def execute_js_on_page(page: Page, script: str) -> Any:
    """
    Execute JavaScript code on the page and return the result.
    
    Args:
        page: Page to execute script on
        script: JavaScript code to execute
        
    Returns:
        Result of the script execution
    """
    return page.evaluate(script)


def wait_for_navigation_idle(page: Page, timeout: int = 30000) -> None:
    """
    Wait for the page to become idle (no network activity).
    
    Args:
        page: Page to wait for
        timeout: Timeout in milliseconds
    """
    page.wait_for_load_state('networkidle', timeout=timeout)
    logger.debug("Page navigation complete and idle")


def simulate_human_interaction(page: Page) -> None:
    """
    Simulate human-like interaction with the page.
    
    Args:
        page: Page to interact with
    """
    # Random mouse movements
    for _ in range(random.randint(3, 10)):
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        page.mouse.move(x, y)
        page.wait_for_timeout(random.randint(200, 1000))
    
    # Scroll down and up
    page.evaluate("""
        () => {
            const scrollHeight = document.body.scrollHeight;
            const randomScrolls = Math.floor(Math.random() * 3) + 2;
            
            for (let i = 0; i < randomScrolls; i++) {
                const position = Math.random() * scrollHeight * 0.8;
                window.scrollTo(0, position);
            }
            
            // Scroll back up
            window.scrollTo(0, 0);
        }
    """)
    
    page.wait_for_timeout(random.randint(500, 2000))
    logger.debug("Simulated human-like interaction on page")


def extract_page_metadata(page: Page) -> Dict[str, Any]:
    """
    Extract useful metadata from the page.
    
    Args:
        page: Page to extract metadata from
        
    Returns:
        Dictionary of metadata
    """
    metadata = page.evaluate("""
        () => {
            const result = {};
            
            // Title and meta description
            result.title = document.title;
            const metaDescription = document.querySelector('meta[name="description"]');
            result.description = metaDescription ? metaDescription.getAttribute('content') : null;
            
            // OpenGraph metadata
            result.og = {};
            document.querySelectorAll('meta[property^="og:"]').forEach(meta => {
                const key = meta.getAttribute('property').replace('og:', '');
                result.og[key] = meta.getAttribute('content');
            });
            
            // Twitter metadata
            result.twitter = {};
            document.querySelectorAll('meta[name^="twitter:"]').forEach(meta => {
                const key = meta.getAttribute('name').replace('twitter:', '');
                result.twitter[key] = meta.getAttribute('content');
            });
            
            // Canonical URL
            const canonical = document.querySelector('link[rel="canonical"]');
            result.canonicalUrl = canonical ? canonical.getAttribute('href') : null;
            
            // Structured data
            result.structuredData = [];
            document.querySelectorAll('script[type="application/ld+json"]').forEach(script => {
                try {
                    result.structuredData.push(JSON.parse(script.textContent));
                } catch (e) {
                    // Ignore invalid JSON
                }
            });
            
            return result;
        }
    """)
    
    return metadata 