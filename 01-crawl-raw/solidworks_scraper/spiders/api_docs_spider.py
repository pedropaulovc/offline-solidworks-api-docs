"""
SolidWorks API Documentation Spider

This spider crawls the SolidWorks API documentation starting from the main welcome page,
staying within the /2026/english/api/ boundary.

The start URL (Welcome.htm) is downloaded in its full format to capture the complete
table of contents with all navigation links. All subsequently discovered pages are
saved in print preview format for cleaner, more compact HTML.
"""

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import hashlib
from datetime import datetime
import json
from pathlib import Path


class ApiDocsSpider(CrawlSpider):
    name = "api_docs"
    allowed_domains = ["help.solidworks.com"]

    # Starting URL - main API documentation page
    start_urls = [
        "https://help.solidworks.com/2026/english/api/sldworksapiprogguide/Welcome.htm?id=0"
    ]

    # Custom settings for this spider
    custom_settings = {
        'DEPTH_LIMIT': 0,  # No depth limit, we use URL boundaries instead
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.crawled_urls = set()
        self.base_path = "/2026/english/api/"
        self.session_id = datetime.now().strftime("%Y-%m-%d-%H%M%S")

        # Statistics tracking
        self.stats = {
            'start_time': datetime.now().isoformat(),
            'total_pages': 0,
            'successful_pages': 0,
            'failed_pages': 0,
            'skipped_pages': 0,
        }

    # Define rules for following links
    rules = (
        Rule(
            LinkExtractor(
                allow=r'/2026/english/api/.*',
                deny=[
                    r'.*\.(css|js|jpg|jpeg|png|gif|svg|ico|pdf|zip|exe|msi)$',  # Skip non-HTML files
                    r'.*/print\.html.*',  # Skip if already a print URL
                ],
                unique=True,
            ),
            callback='parse_page',
            follow=True,
            process_links='process_links',
        ),
    )

    def process_links(self, links):
        """Process discovered links to ensure they stay within boundaries"""
        processed_links = []

        for link in links:
            # Check if URL is within our allowed boundary
            parsed = urlparse(link.url)

            # Must be within /2026/english/api/ path
            if not parsed.path.startswith(self.base_path):
                self.logger.debug(f"Skipping URL outside boundary: {link.url}")
                continue

            # Convert to print preview URL
            print_url = self.convert_to_print_preview(link.url)

            # Create new link with print preview URL
            link.url = print_url
            processed_links.append(link)

        return processed_links

    def convert_to_print_preview(self, url):
        """Convert a regular URL to its print preview version"""
        parsed = urlparse(url)

        # Parse existing query parameters
        query_params = parse_qs(parsed.query)

        # Add print preview parameters
        query_params['format'] = ['p']
        query_params['value'] = ['1']

        # Rebuild the URL with new parameters
        new_query = urlencode(query_params, doseq=True)
        print_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

        return print_url

    def start_requests(self):
        """
        Generate initial requests.

        The start URL (Welcome.htm) is downloaded in full format (not print preview)
        because it contains the complete table of contents with all navigation links.
        All subsequent pages discovered will be converted to print preview format.
        """
        for url in self.start_urls:
            # Do NOT convert start URL to print preview - we need the full TOC
            yield scrapy.Request(
                url,
                callback=self.parse_page,
                errback=self.handle_error,
                meta={'original_url': url, 'is_start_page': True}
            )

    def parse_page(self, response):
        """Parse and save a documentation page"""
        # Check if this is actually HTML content
        content_type = response.headers.get('Content-Type', b'').decode('utf-8').lower()
        if 'text/html' not in content_type:
            self.logger.warning(f"Skipping non-HTML content: {response.url}")
            self.stats['skipped_pages'] += 1
            return

        # Check URL boundary again (belt and suspenders)
        parsed = urlparse(response.url)
        if not parsed.path.startswith(self.base_path):
            self.logger.warning(f"URL outside boundary, skipping: {response.url}")
            self.stats['skipped_pages'] += 1
            return

        # Avoid duplicate processing
        if response.url in self.crawled_urls:
            self.logger.debug(f"Already crawled: {response.url}")
            return

        self.crawled_urls.add(response.url)
        self.stats['total_pages'] += 1

        # Create item with page data
        item = {
            'url': response.url,
            'original_url': response.meta.get('original_url', response.url),
            'status_code': response.status,
            'content': response.text,
            'headers': dict(response.headers),
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
        }

        # Calculate content hash for integrity
        item['content_hash'] = hashlib.sha256(response.body).hexdigest()
        item['content_length'] = len(response.body)

        # Extract title for better organization
        title = response.xpath('//title/text()').get()
        item['title'] = title.strip() if title else 'Untitled'

        self.stats['successful_pages'] += 1
        self.logger.info(f"Successfully crawled: {response.url} - {item['title']}")

        # Yield the item to be processed by pipelines
        yield item

        # Follow links in the page
        # The rules will handle link extraction and following

    def handle_error(self, failure):
        """Handle failed requests"""
        self.stats['failed_pages'] += 1
        self.logger.error(f"Failed to crawl {failure.request.url}: {failure.value}")

        # Create error item for logging
        error_item = {
            'type': 'error',
            'url': failure.request.url,
            'error': str(failure.value),
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
        }

        yield error_item

    def closed(self, reason):
        """Called when the spider is closed"""
        self.stats['end_time'] = datetime.now().isoformat()
        self.stats['reason'] = reason

        # Save final statistics
        stats_file = Path(__file__).parent.parent.parent / 'output' / 'metadata' / 'crawl_stats.json'
        stats_file.parent.mkdir(parents=True, exist_ok=True)

        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)

        self.logger.info(f"Spider closed. Statistics saved to {stats_file}")
        self.logger.info(f"Total pages crawled: {self.stats['successful_pages']}")
        self.logger.info(f"Failed pages: {self.stats['failed_pages']}")
        self.logger.info(f"Skipped pages: {self.stats['skipped_pages']}")