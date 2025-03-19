#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base Extractor Module

Provides the base class for all data extractors. Extractors are responsible for
extracting structured data from web pages based on their content type.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set
from bs4 import BeautifulSoup

class BaseExtractor(ABC):
    """
    Base class for all data extractors.
    
    All specific extractors should inherit from this class and implement
    the extract method to extract data from a particular type of content.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the extractor with optional configuration.
        
        Args:
            config: Configuration dictionary for customizing extraction behavior
        """
        self.config = config or {}
    
    @abstractmethod
    def extract(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract data from a web page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            url: URL of the page being processed
            
        Returns:
            Dictionary of extracted data
        """
        pass
    
    @abstractmethod
    def can_extract(self, soup: BeautifulSoup, url: str) -> bool:
        """
        Check if this extractor can extract data from a given page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            url: URL of the page being processed
            
        Returns:
            True if the extractor can process this page
        """
        pass
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize a text string.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove extra whitespace
        cleaned = ' '.join(text.split())
        
        return cleaned.strip()
    
    def extract_meta_tags(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extract meta tags from a web page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            Dictionary of meta tag name/property to content
        """
        meta_tags = {}
        
        # Extract standard meta tags
        for meta in soup.find_all('meta'):
            if 'name' in meta.attrs and 'content' in meta.attrs:
                meta_tags[meta['name']] = meta['content']
            elif 'property' in meta.attrs and 'content' in meta.attrs:
                meta_tags[meta['property']] = meta['content']
        
        return meta_tags
    
    def extract_structured_data(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract JSON-LD structured data from a web page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            List of parsed JSON-LD objects
        """
        import json
        
        structured_data = []
        
        # Find all JSON-LD script tags
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                structured_data.append(data)
            except (json.JSONDecodeError, TypeError):
                continue
        
        return structured_data
    
    def get_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """
        Try to extract the main content area of a web page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            BeautifulSoup object for the main content or None if not found
        """
        # Look for common main content containers
        main_content_selectors = [
            'main',
            'article',
            '#content',
            '#main',
            '.content',
            '.main',
            '.post',
            '.entry',
            '[role="main"]'
        ]
        
        for selector in main_content_selectors:
            content = soup.select_one(selector)
            if content:
                return content
        
        return None
    
    def extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """
        Extract images from a web page with their relevant attributes.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            base_url: Base URL for resolving relative image URLs
            
        Returns:
            List of dictionaries with image information
        """
        import urllib.parse
        
        images = []
        
        for img in soup.find_all('img'):
            image_info = {}
            
            # Get source URL
            src = img.get('src') or img.get('data-src')
            if not src:
                continue
                
            # Handle relative URLs
            image_info['url'] = urllib.parse.urljoin(base_url, src)
            
            # Get alt text
            image_info['alt'] = img.get('alt', '')
            
            # Get caption
            if img.parent.name == 'figure':
                figcaption = img.parent.find('figcaption')
                if figcaption:
                    image_info['caption'] = self.clean_text(figcaption.get_text())
            
            # Get dimensions if available
            if 'width' in img.attrs:
                image_info['width'] = img['width']
            if 'height' in img.attrs:
                image_info['height'] = img['height']
            
            images.append(image_info)
        
        return images
    
    def get_text_blocks(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract text blocks (paragraphs) from a web page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            List of text blocks
        """
        blocks = []
        
        # Try to get main content first
        content = self.get_main_content(soup) or soup
        
        # Extract paragraphs
        for p in content.find_all('p'):
            text = self.clean_text(p.get_text())
            if text and len(text) > 20:  # Skip very short paragraphs
                blocks.append(text)
        
        return blocks 