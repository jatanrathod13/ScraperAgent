#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
E-commerce Extractor Module

Specialized extractor for e-commerce product pages that extracts
structured product information such as prices, variants, descriptions, etc.
"""

import re
import json
import urllib.parse
from typing import Dict, Any, List, Optional, Union
from bs4 import BeautifulSoup, Tag

from .base_extractor import BaseExtractor

class EcommerceExtractor(BaseExtractor):
    """
    Extractor for e-commerce product pages.
    
    Extracts detailed product information including:
    - Basic product details (name, price, currency)
    - Variants and options
    - Specifications and attributes
    - Images and media
    - Availability and shipping information
    - Related products
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the e-commerce extractor with optional configuration.
        
        Args:
            config: Configuration dictionary with extraction settings
        """
        super().__init__(config)
        
        # Default config values for e-commerce extraction
        self.config.setdefault('extract_variants', True)
        self.config.setdefault('extract_specifications', True)
        self.config.setdefault('extract_reviews', False)  # Reviews often require additional requests
        self.config.setdefault('extract_related_products', True)
        self.config.setdefault('max_images', 10)
        
        # Common price selectors
        self.price_selectors = [
            '.price', 
            '[itemprop="price"]', 
            '.product-price',
            '.current-price',
            '.product__price',
            '[data-price]',
            'span.amount',
            '.sales-price',
            '.offer-price',
            '.product-meta__price',
            '.product-details__price',
            '.product-single__price'
        ]
        
        # Common product title selectors
        self.name_selectors = [
            'h1', 
            'h1.product-title', 
            '.product-name',
            '[itemprop="name"]',
            '.product__title',
            '.product-meta__title',
            '.product-single__title',
            '.product-details__title'
        ]
    
    def can_extract(self, soup: BeautifulSoup, url: str) -> bool:
        """
        Check if this extractor can handle a given page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            url: URL of the page being processed
            
        Returns:
            True if the page is an e-commerce product page
        """
        # Check for product schema markup
        json_ld = self.extract_structured_data(soup)
        for data in json_ld:
            if data.get('@type') in ['Product', 'IndividualProduct', 'ProductModel']:
                return True
        
        # Check for common product page indicators
        # 1. URL patterns
        url_path = urllib.parse.urlparse(url).path.lower()
        if any(segment in url_path for segment in ['/product/', '/products/', '/item/', '/p/']):
            return True
            
        # 2. Price indicators
        for selector in self.price_selectors:
            if soup.select(selector):
                return True
                
        # 3. Add to cart buttons
        cart_buttons = soup.find_all(['button', 'a'], text=re.compile(r'add to ?(cart|bag|basket)', re.I))
        if cart_buttons:
            return True
            
        # 4. Buy now buttons
        buy_buttons = soup.find_all(['button', 'a'], text=re.compile(r'buy (now|it)', re.I))
        if buy_buttons:
            return True
            
        # 5. Product option selectors (size, color)
        variants = soup.find_all(['select', 'input'], {'name': re.compile(r'variant|option|size|color', re.I)})
        if variants:
            return True
            
        return False
    
    def extract(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract product information from an e-commerce page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            url: URL of the page being processed
            
        Returns:
            Dictionary of extracted product data
        """
        result = {
            'type': 'product',
            'url': url,
            'extracted_data': {}
        }
        
        # Try to get structured data first (most reliable)
        result['extracted_data'] = self._extract_from_structured_data(soup)
        
        # If no structured data or incomplete, use HTML extraction
        if not result['extracted_data'] or not result['extracted_data'].get('name'):
            # Extract product data from HTML
            html_data = self._extract_from_html(soup, url)
            
            # Merge with any structured data, preferring structured data where available
            if result['extracted_data']:
                for key, value in html_data.items():
                    if key not in result['extracted_data'] or not result['extracted_data'][key]:
                        result['extracted_data'][key] = value
            else:
                result['extracted_data'] = html_data
        
        # Extract additional data that might not be in structured data
        result['extracted_data']['variants'] = self._extract_variants(soup)
        result['extracted_data']['specifications'] = self._extract_specifications(soup)
        
        if self.config.get('extract_reviews'):
            result['extracted_data']['reviews'] = self._extract_reviews(soup)
            
        if self.config.get('extract_related_products'):
            result['extracted_data']['related_products'] = self._extract_related_products(soup, url)
        
        # Clean up empty values
        result['extracted_data'] = {k: v for k, v in result['extracted_data'].items() if v}
        
        return result
    
    def _extract_from_structured_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract product data from JSON-LD structured data.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            Dictionary of extracted product data
        """
        structured_data = self.extract_structured_data(soup)
        
        for data in structured_data:
            if data.get('@type') in ['Product', 'IndividualProduct', 'ProductModel']:
                product_data = {}
                
                # Basic product info
                product_data['name'] = data.get('name')
                product_data['description'] = data.get('description')
                product_data['brand'] = self._extract_nested_value(data, 'brand', 'name')
                product_data['sku'] = data.get('sku')
                product_data['mpn'] = data.get('mpn')
                product_data['gtin'] = data.get('gtin13') or data.get('gtin14') or data.get('gtin')
                
                # Price information
                offers = data.get('offers')
                if offers:
                    if isinstance(offers, list):
                        # Multiple offers, take the first one
                        if offers:
                            first_offer = offers[0]
                            product_data['price'] = first_offer.get('price')
                            product_data['currency'] = first_offer.get('priceCurrency')
                            product_data['availability'] = first_offer.get('availability')
                    else:
                        # Single offer
                        product_data['price'] = offers.get('price')
                        product_data['currency'] = offers.get('priceCurrency')
                        product_data['availability'] = offers.get('availability')
                
                # Images
                if 'image' in data:
                    if isinstance(data['image'], list):
                        product_data['images'] = data['image'][:self.config.get('max_images', 10)]
                    else:
                        product_data['images'] = [data['image']]
                
                # Aggregate rating
                if 'aggregateRating' in data:
                    product_data['rating'] = {
                        'value': data['aggregateRating'].get('ratingValue'),
                        'count': data['aggregateRating'].get('reviewCount') or data['aggregateRating'].get('ratingCount')
                    }
                
                return product_data
        
        return {}
    
    def _extract_nested_value(self, data: Dict[str, Any], *keys: str) -> Any:
        """
        Extract a value from a nested dictionary structure.
        
        Args:
            data: Dictionary to extract from
            *keys: Sequence of keys to navigate
            
        Returns:
            Extracted value or None if not found
        """
        if not data or not keys:
            return None
            
        if keys[0] not in data:
            return None
            
        value = data[keys[0]]
        
        if len(keys) == 1:
            return value
            
        if isinstance(value, dict):
            return self._extract_nested_value(value, *keys[1:])
            
        return None
    
    def _extract_from_html(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract product data from HTML elements.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            url: URL of the page being processed
            
        Returns:
            Dictionary of extracted product data
        """
        result = {}
        
        # Extract product name
        name = None
        for selector in self.name_selectors:
            name_elem = soup.select_one(selector)
            if name_elem:
                name = self.clean_text(name_elem.get_text())
                break
        
        if not name:
            # Try h1 or first major heading
            h1 = soup.find('h1')
            if h1:
                name = self.clean_text(h1.get_text())
        
        result['name'] = name
        
        # Extract price
        price_text = None
        price_currency = None
        
        for selector in self.price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text().strip()
                
                # Try to get price from data attribute
                data_price = price_elem.get('data-price') or price_elem.get('content')
                if data_price and re.match(r'^\d+(\.\d+)?$', data_price):
                    price_text = data_price
                    
                # Check for currency symbols
                for symbol, currency in [('$', 'USD'), ('£', 'GBP'), ('€', 'EUR'), ('¥', 'JPY')]:
                    if symbol in price_text:
                        price_currency = currency
                        break
                
                break
        
        if price_text:
            # Extract numeric price
            numeric_price = re.search(r'(\d+[.,]?\d*)', price_text)
            if numeric_price:
                result['price'] = numeric_price.group(1).replace(',', '.')
                result['price_text'] = price_text
                
                if price_currency:
                    result['currency'] = price_currency
        
        # Extract description
        description_selectors = [
            '.product-description',
            '.description',
            '[itemprop="description"]',
            '.product-details__description',
            '#product-description',
            '.product__description'
        ]
        
        for selector in description_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                result['description'] = self.clean_text(desc_elem.get_text())
                break
        
        # If no specific description element found, try to get main content paragraphs
        if not result.get('description'):
            # Get the first few paragraphs of the main content area
            main_content = self.get_main_content(soup)
            if main_content:
                paragraphs = main_content.find_all('p', limit=3)
                if paragraphs:
                    result['description'] = '\n'.join(
                        self.clean_text(p.get_text()) for p in paragraphs
                    )
        
        # Extract images
        images = []
        
        # First check for product image gallery
        gallery_selectors = [
            '.product-gallery img',
            '.product-images img',
            '.product__media-item img',
            '.product-single__media img',
            '.thumbnail-list img'
        ]
        
        for selector in gallery_selectors:
            gallery_imgs = soup.select(selector)
            if gallery_imgs:
                for img in gallery_imgs[:self.config.get('max_images', 10)]:
                    src = img.get('data-src') or img.get('data-srcset') or img.get('src')
                    if src:
                        # Make relative URLs absolute
                        abs_src = urllib.parse.urljoin(url, src)
                        if abs_src not in [i.get('url') for i in images]:
                            images.append({
                                'url': abs_src,
                                'alt': img.get('alt', '')
                            })
        
        # If no gallery found, use any large images on the page
        if not images:
            for img in soup.find_all('img'):
                if img.get('width') and int(img.get('width')) >= 200:
                    src = img.get('data-src') or img.get('data-srcset') or img.get('src')
                    if src:
                        abs_src = urllib.parse.urljoin(url, src)
                        if abs_src not in [i.get('url') for i in images]:
                            images.append({
                                'url': abs_src,
                                'alt': img.get('alt', '')
                            })
        
        result['images'] = images[:self.config.get('max_images', 10)]
        
        # Try to extract brand
        brand_selectors = [
            '[itemprop="brand"]',
            '.product-meta__vendor',
            '.product__vendor',
            '.product-brand',
            '.brand'
        ]
        
        for selector in brand_selectors:
            brand_elem = soup.select_one(selector)
            if brand_elem:
                result['brand'] = self.clean_text(brand_elem.get_text())
                break
        
        # Extract availability
        availability_selectors = [
            '[itemprop="availability"]',
            '.product-availability',
            '.stock-level',
            '.availability',
            '.product__stock'
        ]
        
        for selector in availability_selectors:
            avail_elem = soup.select_one(selector)
            if avail_elem:
                text = self.clean_text(avail_elem.get_text())
                result['availability'] = text
                result['in_stock'] = any(s in text.lower() for s in ['in stock', 'available', 'shipping today'])
                break
        
        return result
    
    def _extract_variants(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract product variants (sizes, colors, etc.).
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            List of variant dictionaries
        """
        if not self.config.get('extract_variants', True):
            return []
            
        variants = []
        
        # Try to find variant scripts (Shopify, WooCommerce, etc.)
        variant_script = soup.find('script', text=re.compile(r'(variants|product_variants)'))
        if variant_script:
            script_text = variant_script.string
            # Look for array of variant objects
            try:
                # Try to extract JSON objects from script
                json_str = re.search(r'variants\s*:\s*(\[.*?\])', script_text, re.DOTALL)
                if json_str:
                    # Clean up the text and parse as JSON
                    variant_data = json.loads(json_str.group(1).replace("'", '"'))
                    if isinstance(variant_data, list):
                        return variant_data
            except (ValueError, json.JSONDecodeError):
                pass
        
        # Extract from select dropdowns
        option_selects = soup.find_all('select', {'name': re.compile(r'variant|option|attribute', re.I)})
        for select in option_selects:
            option_name = select.get('name', '').replace('attribute_', '').replace('option_', '').title()
            if not option_name:
                option_name = self.clean_text(select.find_previous(['label', 'span']).get_text()) if select.find_previous(['label', 'span']) else 'Option'
                
            options = []
            for option in select.find_all('option'):
                if option.get('value') and not option.get('value') == '':
                    option_text = self.clean_text(option.get_text())
                    if option_text.lower() not in ['choose', 'select', 'choose an option']:
                        options.append(option_text)
            
            if options:
                variants.append({
                    'name': option_name,
                    'values': options
                })
        
        # Extract from radio buttons or checkboxes
        option_groups = soup.find_all(['div', 'ul'], {'class': re.compile(r'options|variants|swatches', re.I)})
        for group in option_groups:
            # Find the option name
            option_name = None
            heading = group.find_previous(['h3', 'h4', 'label', 'span'])
            if heading:
                option_name = self.clean_text(heading.get_text())
            
            if not option_name:
                option_name = 'Option'
                
            # Find all options
            options = []
            for option in group.find_all(['input', 'li', 'div', 'a'], {'class': re.compile(r'option|swatch|variant', re.I)}):
                if option.name == 'input':
                    option_text = option.get('value')
                    if not option_text:
                        label = soup.find('label', {'for': option.get('id')})
                        if label:
                            option_text = self.clean_text(label.get_text())
                else:
                    option_text = self.clean_text(option.get_text())
                    
                if option_text and option_text.lower() not in ['choose', 'select', 'choose an option']:
                    options.append(option_text)
            
            if options:
                variants.append({
                    'name': option_name,
                    'values': options
                })
        
        return variants
    
    def _extract_specifications(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract product specifications and attributes.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            Dictionary of specifications
        """
        if not self.config.get('extract_specifications', True):
            return {}
            
        specs = {}
        
        # Try to find specification tables
        spec_selectors = [
            '.product-specifications',
            '.product-attributes',
            '.product-info__specs',
            '#product-specs',
            '.specs-table',
            '.data-table',
            '.definition-list',
            '.product-single__meta table'
        ]
        
        for selector in spec_selectors:
            spec_table = soup.select_one(selector)
            if not spec_table:
                continue
                
            # Try to extract from table
            rows = spec_table.find_all('tr')
            if rows:
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        key = self.clean_text(cells[0].get_text())
                        value = self.clean_text(cells[1].get_text())
                        if key and value:
                            specs[key] = value
                            
                # If we found specs, return them
                if specs:
                    return specs
            
            # Try to extract from definition lists
            dl = spec_table.find('dl')
            if dl:
                dts = dl.find_all('dt')
                dds = dl.find_all('dd')
                
                for i in range(min(len(dts), len(dds))):
                    key = self.clean_text(dts[i].get_text())
                    value = self.clean_text(dds[i].get_text())
                    if key and value:
                        specs[key] = value
                        
                # If we found specs, return them
                if specs:
                    return specs
            
            # Try to extract from div pattern (label-value pairs)
            spec_items = spec_table.find_all(['div', 'li'], {'class': re.compile(r'item|attribute|spec', re.I)})
            if spec_items:
                for item in spec_items:
                    label_elem = item.find(['span', 'div'], {'class': re.compile(r'label|name|key', re.I)})
                    value_elem = item.find(['span', 'div'], {'class': re.compile(r'value|data', re.I)})
                    
                    if label_elem and value_elem:
                        key = self.clean_text(label_elem.get_text())
                        value = self.clean_text(value_elem.get_text())
                        if key and value:
                            specs[key] = value
        
        return specs
    
    def _extract_reviews(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract product reviews from the page.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            
        Returns:
            List of review dictionaries
        """
        # Reviews extraction is complex and often requires JavaScript or separate requests
        # This is a basic implementation to extract reviews directly in the HTML
        reviews = []
        
        review_selectors = [
            '.product-reviews',
            '.review-list',
            '#reviews',
            '.reviews',
            '.user-reviews'
        ]
        
        for selector in review_selectors:
            review_container = soup.select_one(selector)
            if not review_container:
                continue
                
            # Find individual reviews
            review_items = review_container.find_all(['div', 'li'], {'class': re.compile(r'review|testimonial', re.I)})
            if not review_items:
                continue
                
            for item in review_items:
                review = {}
                
                # Extract reviewer name
                author_elem = item.find(['span', 'div', 'a'], {'class': re.compile(r'author|name|user', re.I)})
                if author_elem:
                    review['author'] = self.clean_text(author_elem.get_text())
                
                # Extract rating
                rating_elem = item.find(['meta', 'span', 'div'], {'itemprop': 'ratingValue'}) or \
                              item.find(['span', 'div'], {'class': re.compile(r'rating|stars', re.I)})
                if rating_elem:
                    if rating_elem.name == 'meta':
                        review['rating'] = rating_elem.get('content')
                    else:
                        # Try to extract numeric rating from text or classes
                        rating_text = rating_elem.get_text()
                        rating_match = re.search(r'(\d+(\.\d+)?)', rating_text)
                        if rating_match:
                            review['rating'] = rating_match.group(1)
                        else:
                            # Try to count stars in classes
                            star_classes = [c for c in rating_elem.get('class', []) if 'star' in c.lower()]
                            if star_classes:
                                full_stars = len([c for c in star_classes if 'full' in c.lower()])
                                if full_stars:
                                    review['rating'] = str(full_stars)
                
                # Extract review content
                content_elem = item.find(['div', 'p'], {'class': re.compile(r'content|text|description', re.I)}) or \
                               item.find(['div', 'p'], {'itemprop': 'reviewBody'})
                if content_elem:
                    review['content'] = self.clean_text(content_elem.get_text())
                
                # Extract review date
                date_elem = item.find(['meta', 'span', 'div'], {'itemprop': 'datePublished'}) or \
                            item.find(['span', 'div', 'time'], {'class': re.compile(r'date|time', re.I)})
                if date_elem:
                    if date_elem.name == 'meta':
                        review['date'] = date_elem.get('content')
                    else:
                        review['date'] = self.clean_text(date_elem.get_text())
                
                if review:
                    reviews.append(review)
        
        return reviews
    
    def _extract_related_products(self, soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
        """
        Extract related products or recommendations.
        
        Args:
            soup: BeautifulSoup object representing the parsed HTML
            url: URL of the page being processed
            
        Returns:
            List of related product dictionaries
        """
        related_products = []
        
        related_selectors = [
            '.related-products',
            '.recommendations',
            '.similar-products',
            '.product-recommendations',
            '#related-products',
            '.upsells',
            '.cross-sells'
        ]
        
        for selector in related_selectors:
            container = soup.select_one(selector)
            if not container:
                continue
                
            # Find product items
            product_items = container.find_all(['div', 'li', 'article'], {'class': re.compile(r'product|item', re.I)})
            if not product_items:
                continue
                
            for item in product_items:
                product = {}
                
                # Extract product name
                name_elem = item.find(['h3', 'h4', 'h5', 'a'], {'class': re.compile(r'title|name', re.I)})
                if name_elem:
                    product['name'] = self.clean_text(name_elem.get_text())
                    
                    # Extract URL
                    if name_elem.name == 'a':
                        product_url = name_elem.get('href')
                        if product_url:
                            product['url'] = urllib.parse.urljoin(url, product_url)
                
                # Extract image
                img_elem = item.find('img')
                if img_elem:
                    img_src = img_elem.get('data-src') or img_elem.get('src')
                    if img_src:
                        product['image'] = urllib.parse.urljoin(url, img_src)
                
                # Extract price
                price_elem = item.find(['span', 'div'], {'class': re.compile(r'price', re.I)})
                if price_elem:
                    product['price'] = self.clean_text(price_elem.get_text())
                
                if product.get('name'):
                    related_products.append(product)
                    
                    # Limit to reasonable number
                    if len(related_products) >= 6:
                        break
        
        return related_products 