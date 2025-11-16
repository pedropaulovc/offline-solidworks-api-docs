"""
SolidWorks API Examples Spider

This spider crawls example pages from the SolidWorks API documentation by:
1. Reading example URLs directly from api_types.xml
2. Converting relative URLs to absolute URLs
3. Downloading each example page
4. Extracting clean HTML content from the __NEXT_DATA__ JSON
"""

import hashlib
import json
import xml.etree.ElementTree as ET
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import scrapy
from scrapy.http import Response
from twisted.python.failure import Failure


class ExamplesSpider(scrapy.Spider):
    name = "examples"
    allowed_domains = ["help.solidworks.com"]

    # Custom settings for this spider
    custom_settings = {
        "DEPTH_LIMIT": 0,  # No depth limit, we're just crawling a list
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.crawled_urls: set[str] = set()
        self.base_url: str = "https://help.solidworks.com/2026/english/api"

        # Statistics tracking
        self.stats: dict[str, Any] = {
            "total_pages": 0,
            "successful_pages": 0,
            "failed_pages": 0,
            "skipped_pages": 0,
        }

        # XML source file from Phase 3
        self.xml_file = Path(__file__).parent.parent.parent.parent / "04_extract_type_details" / "metadata" / "api_types.xml"
        self.example_urls = self._load_urls()

    def _load_urls(self) -> list[str]:
        """Load example URLs directly from the XML file"""
        urls = set()

        if not self.xml_file.exists():
            self.logger.error(f"XML file not found: {self.xml_file}")
            return []

        try:
            tree = ET.parse(self.xml_file)
            root = tree.getroot()

            # Find all <Url> elements within <Example> elements
            for example in root.findall(".//Example/Url"):
                url = example.text
                if url:
                    url = url.strip()
                    # Convert relative URL to absolute
                    if url.startswith("/"):
                        full_url = self.base_url + url
                    else:
                        full_url = url
                    urls.add(full_url)

            self.logger.info(f"Loaded {len(urls)} unique example URLs from {self.xml_file}")
            return sorted(urls)

        except Exception as e:
            self.logger.error(f"Failed to parse XML file {self.xml_file}: {e}")
            return []

    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        """Generate initial requests for all example URLs"""
        for url in self.example_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_page,
                errback=self.handle_error,
                meta={"original_url": url},
            )

    def parse_page(self, response: Response) -> Generator[dict[str, Any], None, None]:
        """Parse and save an example page"""
        # Check if this is actually HTML content
        content_type_bytes = response.headers.get("Content-Type", b"")
        content_type = content_type_bytes.decode("utf-8").lower() if content_type_bytes else ""
        if "text/html" not in content_type:
            self.logger.warning(f"Skipping non-HTML content: {response.url}")
            self.stats["skipped_pages"] += 1
            return

        # Avoid duplicate processing
        if response.url in self.crawled_urls:
            self.logger.debug(f"Already crawled: {response.url}")
            return

        self.crawled_urls.add(response.url)
        self.stats["total_pages"] += 1

        # Extract __NEXT_DATA__ JSON from the page
        json_text = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()

        if not json_text:
            self.logger.warning(f"No __NEXT_DATA__ JSON found in {response.url}")
            self.stats["skipped_pages"] += 1
            return

        # Parse JSON and extract only helpText from helpContentData
        try:
            data = json.loads(json_text)
            help_content_data = data.get("props", {}).get("pageProps", {}).get("helpContentData", {})
            help_text = help_content_data.get("helpText")

            if not help_text:
                self.logger.warning(f"No helpText found in {response.url}")
                self.stats["skipped_pages"] += 1
                return

            # Use the HTML content directly
            content = help_text

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse __NEXT_DATA__ JSON from {response.url}: {e}")
            self.stats["skipped_pages"] += 1
            return

        # Create item with JSON data
        item = {
            "url": response.url,
            "original_url": response.meta.get("original_url", response.url),
            "status_code": response.status,
            "content": content,  # Save only the helpText HTML
            "headers": dict(response.headers),
        }

        # Calculate content hash for integrity
        item["content_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        item["content_length"] = len(content.encode("utf-8"))

        # Extract title for better organization
        title = response.xpath("//title/text()").get()
        item["title"] = title.strip() if title else "Untitled"

        self.stats["successful_pages"] += 1
        self.logger.info(f"Successfully crawled: {response.url} - {item['title']}")

        # Yield the item to be processed by pipelines
        yield item

    def handle_error(self, failure: Failure) -> Generator[dict[str, Any], None, None]:
        """Handle failed requests"""
        self.stats["failed_pages"] += 1
        request_url = failure.request.url  # type: ignore[attr-defined]
        self.logger.error(f"Failed to crawl {request_url}: {failure.value}")

        # Create error item for logging
        error_item: dict[str, Any] = {
            "type": "error",
            "url": request_url,
            "error": str(failure.value),
        }

        yield error_item

    def closed(self, reason: str) -> None:
        """Called when the spider is closed"""
        self.stats["reason"] = reason

        # Save final statistics
        stats_file = Path(__file__).parent.parent.parent / "metadata" / "crawl_stats.json"
        stats_file.parent.mkdir(parents=True, exist_ok=True)

        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2)

        self.logger.info(f"Spider closed. Statistics saved to {stats_file}")
        self.logger.info(f"Total pages crawled: {self.stats['successful_pages']}")
        self.logger.info(f"Failed pages: {self.stats['failed_pages']}")
        self.logger.info(f"Skipped pages: {self.stats['skipped_pages']}")
