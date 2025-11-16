"""
SolidWorks API Type Members Spider

This spider crawls the SolidWorks API type member documentation by:
1. Reading URLs directly from Phase 2's api_members.xml
2. Downloading each property and method detail page
3. Extracting the helpText HTML content from __NEXT_DATA__ JSON
"""

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections.abc import Generator
from pathlib import Path
from typing import Any

import scrapy
from scrapy.http import Response
from twisted.python.failure import Failure

# Add project root to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from shared.constants import SOLIDWORKS_API_FULL_BASE_URL, make_absolute_url


class TypeMembersSpider(scrapy.Spider):
    name = "type_members"
    allowed_domains = ["help.solidworks.com"]

    # Custom settings for this spider
    custom_settings = {
        "DEPTH_LIMIT": 0,  # No depth limit, we crawl a predefined list
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.crawled_urls: set[str] = set()

        # Statistics tracking
        self.stats: dict[str, Any] = {
            "total_pages": 0,
            "successful_pages": 0,
            "failed_pages": 0,
            "skipped_pages": 0,
        }

        # Load URLs from file
        self.urls_to_crawl = self.load_urls()

    def load_urls(self) -> list[str]:
        """Load URLs directly from Phase 2's api_members.xml"""
        # Path to Phase 2 output
        xml_file = (
            Path(__file__).parent.parent.parent.parent / "02_extract_types" / "metadata" / "api_members.xml"
        )

        if not xml_file.exists():
            self.logger.error(f"XML file not found: {xml_file}")
            self.logger.error("Please run Phase 2 (02_extract_types) first!")
            return []

        urls: set[str] = set()

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Iterate through all Type elements
            for type_elem in root.findall("Type"):
                # Extract property URLs
                properties = type_elem.find("PublicProperties")
                if properties is not None:
                    for prop in properties.findall("Property"):
                        url_elem = prop.find("Url")
                        if url_elem is not None and url_elem.text:
                            urls.add(url_elem.text)

                # Extract method URLs
                methods = type_elem.find("PublicMethods")
                if methods is not None:
                    for method in methods.findall("Method"):
                        url_elem = method.find("Url")
                        if url_elem is not None and url_elem.text:
                            urls.add(url_elem.text)

        except ET.ParseError as e:
            self.logger.error(f"Failed to parse XML file: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error loading URLs from XML: {e}")
            return []

        urls_list = sorted(urls)
        self.logger.info(f"Loaded {len(urls_list)} unique URLs from {xml_file}")
        return urls_list

    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        """Generate initial requests from the URL list"""
        if not self.urls_to_crawl:
            self.logger.error("No URLs to crawl! Exiting.")
            return

        for url in self.urls_to_crawl:
            # Convert relative URL to absolute using shared function
            full_url = make_absolute_url(url)

            yield scrapy.Request(
                full_url,
                callback=self.parse_page,
                errback=self.handle_error,
                meta={"original_url": url},
            )

    def parse_page(self, response: Response) -> Generator[dict[str, Any], None, None]:
        """Parse and save a documentation page"""
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

        # Create item with extracted HTML
        item = {
            "url": response.url,
            "original_url": response.meta.get("original_url", response.url),
            "status_code": response.status,
            "content": content,
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
