# ScraperAgent

A powerful and flexible web scraping framework with specialized data extractors for different types of content.

## Features

- **Robust Crawling:** Navigate websites efficiently with respect for robots.txt and rate limiting
- **Specialized Extractors:** Extract structured data from various content types:
  - E-commerce product pages
  - News and article pages
  - Social media profiles and posts
- **Multiple Extraction Modes:**
  - Single URL extraction
  - Batch URL processing
  - Web crawling with customizable depth
- **Browser Automation:** Support for both HTTP requests and headless browser automation via Playwright
- **Caching System:** Smart caching to avoid redundant requests
- **Proxy Support:** Rotate through proxies to avoid IP blocking
- **Flexible Output:** Export data as JSON or CSV

## Architecture

ScraperAgent is organized into several key components:

### Core Components

- **Crawler:** Handles web navigation, URL management, and content fetching
- **Extractors:** Specialized modules that extract structured data from specific types of content
- **Middlewares:** Handle request modification, rate limiting, and proxy rotation
- **Utils:** Provides utility functions for URLs, HTTP requests, browser automation, and caching

### Extractors

- **BaseExtractor:** Abstract base class defining the interface for all extractors
- **EcommerceExtractor:** Extracts product information from e-commerce sites (prices, variants, specifications, etc.)
- **NewsExtractor:** Extracts content from news articles and blogs (headlines, authors, content, etc.)
- **SocialMediaExtractor:** Extracts data from social media platforms (profiles, posts, engagement metrics)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ScraperAgent.git
   cd ScraperAgent
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. (Optional) If you want to use browser automation features:
   ```bash
   pip install playwright
   playwright install chromium
   ```

## Usage

### Command Line Interface

The main script provides a versatile command-line interface:

```bash
python src/main.py [URL] [options]
```

#### Basic Examples

Extract data from a single URL:
```bash
python src/main.py https://example.com/product/123
```

Process multiple URLs from a file:
```bash
python src/main.py --url-file urls.txt
```

Crawl a website with depth of 2:
```bash
python src/main.py https://example.com --depth 2
```

Use specific extractor:
```bash
python src/main.py https://news-site.com/article/123 --extractor news
```

Use browser automation instead of requests:
```bash
python src/main.py https://example.com --browser
```

#### Advanced Options

```
Options:
  -h, --help            Show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Output directory for scraped data (default: output)
  -f {json,csv}, --format {json,csv}
                        Output format for scraped data (default: json)
  --url-file URL_FILE   File containing URLs to scrape (one per line)
  --depth DEPTH         Crawl depth (0 means just the provided URLs) (default: 0)
  --delay DELAY         Delay between requests in seconds (default: 1.0)
  --extractor {auto,ecommerce,news,social}
                        Extractor to use (auto will try to detect the best one) (default: auto)
  --extract-all         Run all extractors on each page
  --browser             Use browser automation (Playwright) instead of requests
  --user-agent USER_AGENT
                        Custom User-Agent string
  --headers HEADERS     Additional headers as JSON string
  --proxy PROXY         Proxy to use (format: protocol://host:port)
  --verbose             Enable verbose output
  --timeout TIMEOUT     Request timeout in seconds (default: 30)
  --cache               Use request caching (default: True)
  --no-cache            Disable request caching
```

### Programmatic Usage

ScraperAgent can also be imported and used in your Python scripts:

```python
from core.crawler import Crawler
from extractors import EcommerceExtractor, NewsExtractor, SocialMediaExtractor

# Initialize a crawler
crawler = Crawler(
    start_urls=["https://example.com"],
    max_depth=2,
    delay=1.0
)

# Add custom parser using an extractor
extractor = EcommerceExtractor()
crawler.add_custom_parser(
    r'.*product.*',  # URL pattern 
    lambda soup, url: extractor.extract(soup, url) if extractor.can_extract(soup, url) else {}
)

# Start crawling
results = crawler.crawl()

# Export results
crawler.export_to_json("output/results.json")
```

## Extending the Framework

### Creating a Custom Extractor

1. Create a new class that inherits from `BaseExtractor`:

```python
from extractors.base_extractor import BaseExtractor

class MyCustomExtractor(BaseExtractor):
    def __init__(self, config=None):
        super().__init__(config)
        # Initialize your extractor

    def can_extract(self, soup, url):
        # Determine if this extractor can handle the page
        return True if suitable_condition else False

    def extract(self, soup, url):
        # Extract data from the page
        data = {}
        # ... extraction logic ...
        return data
```

2. Add custom utility methods for specific extraction tasks.

### Adding a Custom Middleware

Create middlewares for specific tasks like custom rate limiting, proxy rotation, or request modification.

## Responsible Use

Please use this tool responsibly:

- Respect robots.txt directives
- Implement reasonable rate limiting
- Do not scrape personal information
- Follow the terms of service of websites you scrape
- Use the data in compliance with copyright and data protection laws

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
- [Requests](https://requests.readthedocs.io/)
- [Playwright](https://playwright.dev/) 