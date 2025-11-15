"""
SolidWorks API Documentation Spider

This spider crawls the SolidWorks API documentation by:
1. Fetching the table of contents from the JSON API endpoint
2. Recursively extracting all URLs from the children array
3. Downloading each page
"""

import scrapy
from urllib.parse import urlparse, parse_qs
import hashlib
from datetime import datetime
import json
from pathlib import Path


class ApiDocsSpider(scrapy.Spider):
    name = "api_docs"
    allowed_domains = ["help.solidworks.com"]

    # Starting URL - JSON TOC endpoint
    start_urls = [
        "https://help.solidworks.com/expandToc?version=2026&language=english&product=api&queryParam=?id=2"
    ]

    # Custom settings for this spider
    custom_settings = {
        'DEPTH_LIMIT': 0,  # No depth limit, we use URL boundaries instead
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.crawled_urls = set()
        self.base_path = "/2026/english/api/"
        self.base_url = "https://help.solidworks.com"
        self.session_id = datetime.now().strftime("%Y-%m-%d-%H%M%S")

        # Statistics tracking
        self.stats = {
            'start_time': datetime.now().isoformat(),
            'total_pages': 0,
            'successful_pages': 0,
            'failed_pages': 0,
            'skipped_pages': 0,
        }

    def parse(self, response):
        """
        Parse the JSON TOC response and extract all page URLs.

        The JSON structure has a 'children' array where each item may have:
        - url: The page URL to crawl
        - children: Nested array of more pages (recursive)
        """
        try:
            data = json.loads(response.text)

            # Save the JSON response itself
            item = {
                'url': response.url,
                'status_code': response.status,
                'content': response.text,
                'headers': dict(response.headers),
                'timestamp': datetime.now().isoformat(),
                'session_id': self.session_id,
                'content_hash': hashlib.sha256(response.body).hexdigest(),
                'content_length': len(response.body),
                'title': 'expandToc JSON',
            }
            yield item

            # Recursively extract all URLs from the JSON structure
            urls = self.extract_urls_from_json(data)

            self.logger.info(f"Found {len(urls)} URLs in JSON TOC")

            # Create requests for each URL
            for url in urls:
                # Convert relative URL to absolute
                if url.startswith('/'):
                    full_url = self.base_url + url
                else:
                    full_url = url

                # Check if URL is within our allowed boundary
                parsed = urlparse(full_url)
                if not parsed.path.startswith(self.base_path):
                    self.logger.debug(f"Skipping URL outside boundary: {full_url}")
                    continue

                # Yield request for the page itself
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_page,
                    errback=self.handle_error,
                    meta={'original_url': full_url}
                )

                # Extract id parameter and create expandToc request
                query_params = parse_qs(parsed.query)
                if 'id' in query_params:
                    id_value = query_params['id'][0]
                    expand_toc_url = f"{self.base_url}/expandToc?version=2026&language=english&product=api&queryParam=?id={id_value}"

                    self.logger.debug(f"Adding expandToc URL for id={id_value}: {expand_toc_url}")

                    yield scrapy.Request(
                        expand_toc_url,
                        callback=self.parse,
                        errback=self.handle_error,
                        dont_filter=False
                    )

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
        except Exception as e:
            self.logger.error(f"Error processing JSON TOC: {e}")

    def extract_urls_from_json(self, data):
        """
        Recursively extract all URLs from the JSON structure.

        Args:
            data: JSON object or array to process

        Returns:
            List of URLs found in the structure
        """
        urls = []

        # Handle array (list of children)
        if isinstance(data, list):
            for item in data:
                urls.extend(self.extract_urls_from_json(item))

        # Handle object (dict)
        elif isinstance(data, dict):
            # Extract URL if present
            if 'url' in data and data['url']:
                urls.append(data['url'])

            # Recursively process children
            if 'children' in data and data['children']:
                urls.extend(self.extract_urls_from_json(data['children']))

        return urls

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

        # Extract __NEXT_DATA__ JSON from the page
        json_text = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()

        if not json_text:
            self.logger.warning(f"No __NEXT_DATA__ JSON found in {response.url}")
            self.stats['skipped_pages'] += 1
            return

        # Parse JSON and extract only helpContentData
        try:
            data = json.loads(json_text)
            help_content_data = data.get('props', {}).get('pageProps', {}).get('helpContentData')

            if not help_content_data:
                self.logger.warning(f"No helpContentData found in {response.url}")
                self.stats['skipped_pages'] += 1
                return

            # Convert back to JSON string for storage
            content = json.dumps(help_content_data, ensure_ascii=False)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse __NEXT_DATA__ JSON from {response.url}: {e}")
            self.stats['skipped_pages'] += 1
            return

        # Create item with JSON data
        item = {
            'url': response.url,
            'original_url': response.meta.get('original_url', response.url),
            'status_code': response.status,
            'content': content,  # Save only the helpContentData JSON
            'headers': dict(response.headers),
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
        }

        # Calculate content hash for integrity
        item['content_hash'] = hashlib.sha256(content.encode('utf-8')).hexdigest()
        item['content_length'] = len(content.encode('utf-8'))

        # Extract title for better organization
        title = response.xpath('//title/text()').get()
        item['title'] = title.strip() if title else 'Untitled'

        self.stats['successful_pages'] += 1
        self.logger.info(f"Successfully crawled: {response.url} - {item['title']}")

        # Yield the item to be processed by pipelines
        yield item

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
        stats_file = Path(__file__).parent.parent.parent / 'metadata' / 'crawl_stats.json'
        stats_file.parent.mkdir(parents=True, exist_ok=True)

        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)

        self.logger.info(f"Spider closed. Statistics saved to {stats_file}")
        self.logger.info(f"Total pages crawled: {self.stats['successful_pages']}")
        self.logger.info(f"Failed pages: {self.stats['failed_pages']}")
        self.logger.info(f"Skipped pages: {self.stats['skipped_pages']}")