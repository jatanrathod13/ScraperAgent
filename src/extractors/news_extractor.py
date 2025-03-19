#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
News Extractor Module

Specialized extractor for news articles that extracts
structured article information such as headlines, authors, content, etc.
"""

import re
import json
import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from bs4 import BeautifulSoup, Tag

from .base_extractor import BaseExtractor

class NewsExtractor(BaseExtractor):
    """
    Extractor for news article pages.
    
    Extracts detailed article information including:
    - Headline, subheadline
    - Author information
    - Publication date
    - Article content
    - Categories and tags
    - Images and captions
    - Related articles
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the news extractor with optional configuration.
        
        Args:
            config: Configuration dictionary with extraction settings
        """
        super().__init__(config)
        
        # Default config values for news extraction
        self.config.setdefault('extract_related_articles', True)
        self.config.setdefault('extract_comments', False)
        self.config.setdefault('max_images', 10)
        self.config.setdefault('extract_full_content', True)
        
        # Common article content selectors
        self.content_selectors = [
            'article',
            '[itemprop="articleBody"]',
            '.article-content',
            '.article-body',
            '.story-body',
            '.story-content',
            '.news-content',
            '.entry-content',
            '.post-content',
            '#article-body',
            '.content-main',
            '.main-content',
            '.story__content',
            '.wysiwyg'
        ]
        
        # Common author selectors
        self.author_selectors = [
            '[itemprop="author"]',
            '.author',
            '.byline',
            '.article-author',
            '.story-author',
            '.entry-author',
            '.post-author',
            '[rel="author"]',
            '.article__author',
            '.story__author',
            '.c-byline__author'
        ]
        
        # Common date selectors
        self.date_selectors = [
            '[itemprop="datePublished"]',
            '.pub-date',
            '.published-date',
            '.article-date',
            '.post-date',
            '.entry-date',
            '.date',
            '.story-date',
            '.article__date',
            '.c-byline__date',
            'time'
        ]
    
    def can_extract(self, soup: BeautifulSoup, url: str) -> bool:
        """
        Check if this extractor can handle a given page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            url: URL of the page being processed
            
        Returns:
            True if the page is a news article
        """
        # Check for news article schema markup
        json_ld = self.extract_structured_data(soup)
        for data in json_ld:
            if data.get('@type') in ['NewsArticle', 'Article', 'Report', 'BlogPosting']:
                return True
        
        # Check for common article indicators
        # 1. URL patterns
        url_path = urllib.parse.urlparse(url).path.lower()
        if any(segment in url_path for segment in ['/article/', '/story/', '/news/', '/post/']):
            return True
            
        # 2. Content indicators - at least one main article content container
        for selector in self.content_selectors:
            if soup.select(selector):
                # Also check for some substantial text content
                content = soup.select_one(selector)
                if content and len(content.get_text(strip=True)) > 500:  # Reasonable article length
                    return True
        
        # 3. Check for author and date elements typical of news articles
        author_exists = any(soup.select(selector) for selector in self.author_selectors)
        date_exists = any(soup.select(selector) for selector in self.date_selectors)
        
        if author_exists and date_exists:
            return True
            
        # 4. Check for common news site patterns
        # - Social sharing buttons
        if soup.find_all(['a', 'div'], {'class': re.compile(r'share|social', re.I)}):
            # Combined with a headline
            if soup.find('h1') and len(soup.find('h1').get_text(strip=True)) > 20:
                return True
        
        return False
    
    def extract(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract article information from a news page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            url: URL of the page being processed
            
        Returns:
            Dictionary of extracted article data
        """
        result = {
            'type': 'article',
            'url': url,
            'extracted_data': {}
        }
        
        # Try to get structured data first (most reliable)
        result['extracted_data'] = self._extract_from_structured_data(soup)
        
        # If no structured data or incomplete, use HTML extraction
        if not result['extracted_data'] or not result['extracted_data'].get('headline'):
            # Extract article data from HTML
            html_data = self._extract_from_html(soup, url)
            
            # Merge with any structured data, preferring structured data where available
            if result['extracted_data']:
                for key, value in html_data.items():
                    if key not in result['extracted_data'] or not result['extracted_data'][key]:
                        result['extracted_data'][key] = value
            else:
                result['extracted_data'] = html_data
        
        # Add content extraction (may not be in structured data)
        if self.config.get('extract_full_content', True) and not result['extracted_data'].get('content'):
            result['extracted_data']['content'] = self._extract_article_content(soup)
        
        # Extract related articles
        if self.config.get('extract_related_articles', True):
            result['extracted_data']['related_articles'] = self._extract_related_articles(soup, url)
        
        # Extract comments if configured
        if self.config.get('extract_comments', False):
            result['extracted_data']['comments'] = self._extract_comments(soup)
        
        # Clean up empty values
        result['extracted_data'] = {k: v for k, v in result['extracted_data'].items() if v is not None}
        
        return result
    
    def _extract_from_structured_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract article data from JSON-LD structured data.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            Dictionary of extracted article data
        """
        structured_data = self.extract_structured_data(soup)
        
        for data in structured_data:
            if data.get('@type') in ['NewsArticle', 'Article', 'Report', 'BlogPosting']:
                article_data = {}
                
                # Basic article info
                article_data['headline'] = data.get('headline')
                article_data['description'] = data.get('description')
                
                # Author information
                if 'author' in data:
                    authors = []
                    if isinstance(data['author'], list):
                        for author in data['author']:
                            if isinstance(author, dict):
                                name = author.get('name')
                                if name:
                                    authors.append(name)
                            elif isinstance(author, str):
                                authors.append(author)
                    elif isinstance(data['author'], dict):
                        name = data['author'].get('name')
                        if name:
                            authors.append(name)
                    elif isinstance(data['author'], str):
                        authors.append(data['author'])
                    
                    article_data['authors'] = authors
                
                # Publication date
                if 'datePublished' in data:
                    article_data['date_published'] = data['datePublished']
                    
                    # Try to format the date consistently
                    try:
                        date_obj = self._parse_date(data['datePublished'])
                        if date_obj:
                            article_data['date_published_formatted'] = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        pass
                
                # Last modified date
                if 'dateModified' in data:
                    article_data['date_modified'] = data['dateModified']
                
                # Publisher
                if 'publisher' in data and isinstance(data['publisher'], dict):
                    article_data['publisher'] = data['publisher'].get('name')
                
                # Main image
                if 'image' in data:
                    if isinstance(data['image'], dict):
                        article_data['main_image'] = data['image'].get('url')
                    elif isinstance(data['image'], str):
                        article_data['main_image'] = data['image']
                    elif isinstance(data['image'], list) and data['image']:
                        # Take the first image if it's a list
                        if isinstance(data['image'][0], dict):
                            article_data['main_image'] = data['image'][0].get('url')
                        elif isinstance(data['image'][0], str):
                            article_data['main_image'] = data['image'][0]
                
                # Categories/sections
                if 'articleSection' in data:
                    if isinstance(data['articleSection'], list):
                        article_data['categories'] = data['articleSection']
                    else:
                        article_data['categories'] = [data['articleSection']]
                
                # Keywords/tags
                if 'keywords' in data:
                    if isinstance(data['keywords'], str):
                        # Split comma-separated keywords
                        article_data['tags'] = [tag.strip() for tag in data['keywords'].split(',')]
                    elif isinstance(data['keywords'], list):
                        article_data['tags'] = data['keywords']
                
                return article_data
        
        return {}
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse a date string into a datetime object.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            Datetime object or None if parsing fails
        """
        # Try different date formats
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601 with timezone
            "%Y-%m-%dT%H:%M:%SZ",   # ISO 8601 UTC
            "%Y-%m-%dT%H:%M:%S",    # ISO 8601 without timezone
            "%Y-%m-%d %H:%M:%S",    # Common format
            "%Y-%m-%d",             # Just date
            "%B %d, %Y",            # Month name, day, year
            "%b %d, %Y",            # Abbreviated month, day, year
            "%d %B %Y",             # Day, month name, year
            "%d %b %Y",             # Day, abbreviated month, year
            "%B %d, %Y %H:%M",      # Month name, day, year, time
            "%b %d, %Y %H:%M",      # Abbreviated month, day, year, time
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _extract_from_html(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract article data from HTML elements.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            url: URL of the page being processed
            
        Returns:
            Dictionary of extracted article data
        """
        article_data = {}
        
        # Extract headline (usually the main h1)
        h1 = soup.find('h1')
        if h1:
            article_data['headline'] = self.clean_text(h1.get_text())
        
        # Extract subheadline (usually h2 close to h1, or element with specific class)
        subheadline_selectors = [
            '.sub-headline', 
            '.subheadline',
            '.article-subheadline', 
            '.article-subtitle',
            '.article-deck',
            '.article-summary',
            '.article-description',
            '.story-deck',
            '.summary',
            '.kicker'
        ]
        
        for selector in subheadline_selectors:
            subheadline = soup.select_one(selector)
            if subheadline:
                article_data['subheadline'] = self.clean_text(subheadline.get_text())
                break
                
        # If no specific subheadline found, try to find the first paragraph with summary-like properties
        if not article_data.get('subheadline') and h1:
            # Look for paragraphs near the headline
            next_elem = h1.find_next('p')
            if next_elem and 50 <= len(next_elem.get_text()) <= 300:
                article_data['subheadline'] = self.clean_text(next_elem.get_text())
        
        # Extract authors
        authors = []
        
        # Try various author selectors
        for selector in self.author_selectors:
            author_elems = soup.select(selector)
            for author_elem in author_elems:
                # Check if it's a name, not just "By" or other text
                author_text = self.clean_text(author_elem.get_text())
                if author_text and len(author_text) > 2:
                    # Clean up "By Author Name" patterns
                    author_text = re.sub(r'^by\s+', '', author_text, flags=re.I)
                    
                    # Split multiple authors if comma or 'and' separated
                    if ',' in author_text or ' and ' in author_text.lower():
                        for name in re.split(r',\s*|\s+and\s+', author_text):
                            if name and name not in authors:
                                authors.append(name)
                    else:
                        if author_text not in authors:
                            authors.append(author_text)
        
        if authors:
            article_data['authors'] = authors
        
        # Extract publication date
        for selector in self.date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                # Check for datetime attribute first
                date_str = date_elem.get('datetime') or date_elem.get('content')
                
                if not date_str:
                    date_str = self.clean_text(date_elem.get_text())
                
                if date_str:
                    article_data['date_published'] = date_str
                    
                    # Try to parse and format consistently
                    parsed_date = self._parse_date(date_str)
                    if parsed_date:
                        article_data['date_published_formatted'] = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                        
                    break
        
        # Extract categories/sections
        category_selectors = [
            '[itemprop="articleSection"]',
            '.article-category',
            '.article-section',
            '.category',
            '.section',
            '.breadcrumbs',
            '.breadcrumb',
            '.article__section',
            '.story__section'
        ]
        
        categories = []
        for selector in category_selectors:
            category_elems = soup.select(selector)
            for category_elem in category_elems:
                category_text = self.clean_text(category_elem.get_text())
                if category_text and category_text.lower() not in ['home', 'homepage', 'index']:
                    categories.append(category_text)
        
        if categories:
            article_data['categories'] = categories
        
        # Extract tags
        tag_selectors = [
            '.article-tags',
            '.tags',
            '.article-topics',
            '.topics',
            '[rel="tag"]',
            '.article__tags',
            '.story__tags'
        ]
        
        tags = []
        for selector in tag_selectors:
            tag_container = soup.select_one(selector)
            if tag_container:
                # Find individual tag elements
                tag_elems = tag_container.find_all(['a', 'li', 'span'])
                for tag_elem in tag_elems:
                    tag_text = self.clean_text(tag_elem.get_text())
                    if tag_text and tag_text not in tags and len(tag_text) > 1:
                        tags.append(tag_text)
        
        if tags:
            article_data['tags'] = tags
        
        # Extract main image
        main_image_selectors = [
            '[itemprop="image"]',
            '.article-main-image',
            '.article-featured-image',
            '.article-image',
            '.main-image',
            '.featured-image',
            '.article__featured-image',
            '.article-img',
            '.story-img',
            '.primary-image'
        ]
        
        for selector in main_image_selectors:
            img_container = soup.select_one(selector)
            if img_container:
                img = img_container if img_container.name == 'img' else img_container.find('img')
                if img:
                    src = img.get('data-src') or img.get('data-lazy-src') or img.get('src')
                    if src:
                        article_data['main_image'] = urllib.parse.urljoin(url, src)
                        
                        # Try to get image caption
                        caption_elem = img_container.find(['figcaption', '.caption', '.image-caption'])
                        if caption_elem:
                            article_data['main_image_caption'] = self.clean_text(caption_elem.get_text())
                        
                        break
        
        # If no main image found yet, try the first large image in the article
        if not article_data.get('main_image'):
            content_container = None
            for selector in self.content_selectors:
                content_container = soup.select_one(selector)
                if content_container:
                    break
                    
            if content_container:
                img = content_container.find('img')
                if img and (img.get('width') is None or int(img.get('width', '0')) >= 200):
                    src = img.get('data-src') or img.get('data-lazy-src') or img.get('src')
                    if src:
                        article_data['main_image'] = urllib.parse.urljoin(url, src)
        
        # Extract publisher
        publisher_selectors = [
            '[itemprop="publisher"]',
            '.publisher',
            '.site-name',
            '.site-title',
            '.publication',
            '.source'
        ]
        
        for selector in publisher_selectors:
            publisher_elem = soup.select_one(selector)
            if publisher_elem:
                name_elem = publisher_elem.find('[itemprop="name"]') if publisher_elem.name != 'meta' else None
                if name_elem:
                    article_data['publisher'] = self.clean_text(name_elem.get_text())
                else:
                    article_data['publisher'] = self.clean_text(publisher_elem.get_text())
                break
        
        # If no publisher found, try to extract from meta tags
        if not article_data.get('publisher'):
            meta_tags = self.extract_meta_tags(soup)
            for key in ['og:site_name', 'application-name', 'publisher']:
                if key in meta_tags:
                    article_data['publisher'] = meta_tags[key]
                    break
        
        # Get the article word count (if we can extract content)
        if self.config.get('extract_full_content', True):
            content = self._extract_article_content(soup)
            if content:
                article_data['word_count'] = len(content.split())
        
        return article_data
    
    def _extract_article_content(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract the full article content.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            Article content as plain text or None if not found
        """
        content_element = None
        
        # Try to find the main content container
        for selector in self.content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                break
        
        if not content_element:
            return None
        
        # Extract content paragraphs
        paragraphs = []
        
        # Add heading elements in the content
        for heading in content_element.find_all(['h2', 'h3', 'h4']):
            # Skip if it looks like a related article heading or has very short text
            heading_text = self.clean_text(heading.get_text())
            if heading_text and len(heading_text) > 10 and 'related' not in heading_text.lower():
                paragraphs.append(heading_text)
        
        # Add paragraph elements
        for p in content_element.find_all('p'):
            # Skip very short paragraphs (likely not actual content)
            p_text = self.clean_text(p.get_text())
            if p_text and len(p_text) > 20:
                paragraphs.append(p_text)
                
        # Add list items as they might contain content
        for ul in content_element.find_all('ul'):
            # Skip if it looks like a tag list or social links
            if not ul.get('class') or not any(c in ' '.join(ul['class']).lower() for c in ['tag', 'social', 'share']):
                for li in ul.find_all('li'):
                    li_text = self.clean_text(li.get_text())
                    if li_text and len(li_text) > 20:
                        paragraphs.append(f"• {li_text}")
                        
        # Add blockquotes
        for quote in content_element.find_all('blockquote'):
            quote_text = self.clean_text(quote.get_text())
            if quote_text and len(quote_text) > 20:
                paragraphs.append(f'"{quote_text}"')
        
        if not paragraphs:
            return None
            
        return '\n\n'.join(paragraphs)
    
    def _extract_related_articles(self, soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
        """
        Extract related articles/recommended reads.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            url: URL of the page being processed
            
        Returns:
            List of related article dictionaries
        """
        related_articles = []
        
        related_selectors = [
            '.related-articles',
            '.related-posts',
            '.related-stories',
            '.recommended-articles',
            '.recommended-posts',
            '.read-more',
            '.more-stories',
            '.more-articles',
            '#related-articles',
            '.you-might-like',
            '.you-may-also-like',
            '.also-read',
            '.related__articles',
            '.story__related',
            '.further-reading'
        ]
        
        for selector in related_selectors:
            container = soup.select_one(selector)
            if not container:
                continue
                
            # Find article items
            article_items = container.find_all(['div', 'li', 'article'], {'class': re.compile(r'item|article|story|post', re.I)})
            if not article_items and container.find_all('a'):
                # If no specific items found, use all links in the container
                article_items = container.find_all('a')
            
            if not article_items:
                continue
                
            for item in article_items:
                article = {}
                
                # Extract title and URL
                if item.name == 'a':
                    link = item
                else:
                    link = item.find('a')
                    
                if link:
                    article['title'] = self.clean_text(link.get_text())
                    article['url'] = urllib.parse.urljoin(url, link.get('href'))
                else:
                    # Try to find title separately
                    title_elem = item.find(['h2', 'h3', 'h4', '.title', '.headline'])
                    if title_elem:
                        article['title'] = self.clean_text(title_elem.get_text())
                        
                        # Look for link in this title
                        title_link = title_elem.find('a')
                        if title_link:
                            article['url'] = urllib.parse.urljoin(url, title_link.get('href'))
                
                # If no title found, skip this item
                if not article.get('title'):
                    continue
                
                # Extract image
                img = item.find('img')
                if img:
                    src = img.get('data-src') or img.get('data-lazy-src') or img.get('src')
                    if src:
                        article['image'] = urllib.parse.urljoin(url, src)
                
                # Extract description/excerpt
                excerpt_selectors = ['.excerpt', '.description', '.summary', '.teaser', 'p']
                for excerpt_selector in excerpt_selectors:
                    excerpt_elem = item.select_one(excerpt_selector)
                    if excerpt_elem:
                        excerpt = self.clean_text(excerpt_elem.get_text())
                        if excerpt and len(excerpt) > 10:
                            article['excerpt'] = excerpt
                            break
                
                # Extract date if available
                date_elem = item.find(['time', '.date', '.time', '.published'])
                if date_elem:
                    date_str = date_elem.get('datetime') or self.clean_text(date_elem.get_text())
                    if date_str:
                        article['date'] = date_str
                
                related_articles.append(article)
                
                # Limit to reasonable number
                if len(related_articles) >= 8:
                    break
        
        return related_articles
    
    def _extract_comments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract user comments from the article.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            List of comment dictionaries
        """
        comments = []
        
        comment_selectors = [
            '#comments',
            '.comments',
            '.comment-list',
            '.user-comments',
            '.article-comments',
            '.story-comments',
            '#disqus_thread',
            '.commentlist'
        ]
        
        for selector in comment_selectors:
            container = soup.select_one(selector)
            if not container:
                continue
                
            # External comment system detection
            if 'disqus' in str(container).lower():
                return [{'info': 'Comments loaded via Disqus', 'count_available': False}]
                
            if 'facebook' in str(container).lower() and 'comments' in str(container).lower():
                return [{'info': 'Comments loaded via Facebook', 'count_available': False}]
            
            # Find comment items
            comment_items = container.find_all(['div', 'li', 'article'], {'class': re.compile(r'comment|response', re.I)})
            if not comment_items:
                continue
                
            for item in comment_items:
                comment = {}
                
                # Skip comment form elements
                if item.find('form'):
                    continue
                
                # Extract author
                author_elem = item.find(['span', 'div', 'a', 'h3', 'h4'], {'class': re.compile(r'author|name|user', re.I)})
                if author_elem:
                    comment['author'] = self.clean_text(author_elem.get_text())
                
                # Extract date
                date_elem = item.find(['time', 'span', 'div'], {'class': re.compile(r'date|time|when', re.I)})
                if date_elem:
                    date_str = date_elem.get('datetime') or self.clean_text(date_elem.get_text())
                    if date_str:
                        comment['date'] = date_str
                
                # Extract content
                content_elem = item.find(['div', 'p'], {'class': re.compile(r'content|text|body', re.I)})
                if content_elem:
                    comment['content'] = self.clean_text(content_elem.get_text())
                else:
                    # If no specific content element, try to get text from paragraphs
                    paragraphs = item.find_all('p')
                    if paragraphs:
                        comment['content'] = '\n\n'.join(self.clean_text(p.get_text()) for p in paragraphs)
                
                if comment.get('content'):
                    comments.append(comment)
            
        return comments 