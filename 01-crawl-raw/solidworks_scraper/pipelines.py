"""
Pipelines for processing and storing crawled SolidWorks API documentation.
"""

import json
import jsonlines
from pathlib import Path
from urllib.parse import urlparse
import re
from datetime import datetime
from itemadapter import ItemAdapter
import hashlib


class HtmlSavePipeline:
    """Pipeline to save HTML content to organized file structure"""

    def __init__(self):
        self.output_dir = Path(__file__).parent.parent / 'output' / 'html'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_item(self, item, spider):
        """Save HTML content to file"""
        # Skip error items
        if item.get('type') == 'error':
            return item

        adapter = ItemAdapter(item)

        # Get the URL and content
        url = adapter.get('url')
        content = adapter.get('content')

        if not url or not content:
            spider.logger.warning(f"Missing URL or content for item")
            return item

        # Generate file path from URL
        file_path = self.url_to_file_path(url)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Save HTML content
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Add file path to item for metadata
            item['file_path'] = str(file_path.relative_to(self.output_dir.parent.parent))
            spider.logger.debug(f"Saved HTML to {file_path}")

        except Exception as e:
            spider.logger.error(f"Failed to save HTML for {url}: {e}")
            item['save_error'] = str(e)

        return item

    def url_to_file_path(self, url):
        """Convert URL to organized file path (deterministic)"""
        parsed = urlparse(url)
        path = parsed.path.strip('/')

        # Remove the base path prefix
        if path.startswith('2026/english/api/'):
            path = path[len('2026/english/api/'):]

        # Remove query parameters from filename but keep them for uniqueness
        # by appending a deterministic hash if query params exist
        if parsed.query:
            # Create a deterministic hash from query params for uniqueness
            # Using MD5 for deterministic hashing (not for security)
            query_hash = hashlib.md5(parsed.query.encode('utf-8')).hexdigest()[:8]
            path = path.replace('.htm', f'_{query_hash}.htm')
            path = path.replace('.html', f'_{query_hash}.html')

        # Ensure it ends with .html
        if not path.endswith(('.html', '.htm')):
            path += '.html'

        # Clean up the path - replace unsafe characters
        path = re.sub(r'[<>:"|?*]', '_', path)

        # Create full file path
        file_path = self.output_dir / path

        return file_path


class MetadataLogPipeline:
    """Pipeline to log metadata about crawled pages"""

    def __init__(self):
        self.metadata_dir = Path(__file__).parent.parent / 'metadata'
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        # File paths for different metadata
        self.urls_file = self.metadata_dir / 'urls_crawled.jsonl'
        self.errors_file = self.metadata_dir / 'errors.jsonl'
        self.manifest_file = self.metadata_dir / 'manifest.json'

        # Initialize manifest
        self.init_manifest()

    def init_manifest(self):
        """Initialize or update the manifest file"""
        manifest = {
            'crawler_version': '1.0.0',
            'last_updated': datetime.now().isoformat(),
            'start_url': 'https://help.solidworks.com/2026/english/api/sldworksapiprogguide/Welcome.htm?id=0',
            'boundary': '/2026/english/api/',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'respect_robots_txt': True,
            'crawl_delay_seconds': 2,
        }

        with open(self.manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

    def process_item(self, item, spider):
        """Log metadata for the crawled item"""
        adapter = ItemAdapter(item)

        # Handle error items separately
        if adapter.get('type') == 'error':
            self.log_error(item)
            return item

        # Prepare metadata entry
        metadata = {
            'url': adapter.get('url'),
            'timestamp': adapter.get('timestamp'),
            'file_path': adapter.get('file_path'),
            'content_hash': adapter.get('content_hash'),
            'content_length': adapter.get('content_length'),
            'status_code': adapter.get('status_code'),
            'title': adapter.get('title'),
            'session_id': adapter.get('session_id'),
        }

        # Log to URLs file
        try:
            with jsonlines.open(self.urls_file, mode='a') as writer:
                writer.write(metadata)
            spider.logger.debug(f"Logged metadata for {metadata['url']}")

        except Exception as e:
            spider.logger.error(f"Failed to log metadata: {e}")

        return item

    def log_error(self, error_item):
        """Log error information"""
        error_data = {
            'url': error_item.get('url'),
            'error': error_item.get('error'),
            'timestamp': error_item.get('timestamp'),
            'session_id': error_item.get('session_id'),
        }

        try:
            with jsonlines.open(self.errors_file, mode='a') as writer:
                writer.write(error_data)

        except Exception as e:
            # Can't log to spider here, just print
            print(f"Failed to log error: {e}")


class DuplicateCheckPipeline:
    """Pipeline to check for and skip duplicate URLs"""

    def __init__(self):
        self.seen_urls = set()
        self.load_existing_urls()

    def load_existing_urls(self):
        """Load already crawled URLs from metadata"""
        urls_file = Path(__file__).parent.parent / 'metadata' / 'urls_crawled.jsonl'

        if urls_file.exists():
            try:
                with jsonlines.open(urls_file) as reader:
                    for obj in reader:
                        if obj.get('url'):
                            self.seen_urls.add(obj['url'])

            except Exception as e:
                print(f"Could not load existing URLs: {e}")

    def process_item(self, item, spider):
        """Check if URL has already been processed"""
        # Skip error items
        if item.get('type') == 'error':
            return item

        url = item.get('url')

        if url in self.seen_urls:
            spider.logger.debug(f"Duplicate URL, skipping: {url}")
            raise DropItem(f"Duplicate URL: {url}")

        self.seen_urls.add(url)
        return item


class ValidationPipeline:
    """Pipeline to validate crawled content"""

    def process_item(self, item, spider):
        """Validate that the item has required fields and content"""
        # Skip error items
        if item.get('type') == 'error':
            return item

        adapter = ItemAdapter(item)

        # Check required fields
        required_fields = ['url', 'content', 'timestamp', 'content_hash']
        for field in required_fields:
            if not adapter.get(field):
                spider.logger.warning(f"Missing required field '{field}' for {adapter.get('url')}")

        # Validate content is not empty
        content = adapter.get('content', '')
        if len(content) < 100:  # Arbitrary minimum content length
            spider.logger.warning(f"Suspiciously short content for {adapter.get('url')}: {len(content)} bytes")

        # Check if it's actually HTML
        if content and not ('<html' in content.lower() or '<!doctype' in content.lower()):
            spider.logger.warning(f"Content doesn't appear to be HTML for {adapter.get('url')}")

        return item


# Import DropItem exception
from scrapy.exceptions import DropItem