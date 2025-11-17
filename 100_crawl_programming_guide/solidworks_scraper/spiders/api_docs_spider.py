"""
SolidWorks API Programming Guide Spider

This spider crawls the SolidWorks API Programming Guide documentation by:
1. Fetching the table of contents from the JSON API endpoint (id=1)
2. Recursively extracting all URLs from the children array
3. Downloading each page
"""

import hashlib
import json
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import scrapy
from scrapy.http import Response
from twisted.python.failure import Failure


class ApiDocsSpider(scrapy.Spider):
    name = "api_docs"
    allowed_domains = ["help.solidworks.com"]

    # Starting URL - JSON TOC endpoint for Programming Guide (id=1)
    start_urls = ["https://help.solidworks.com/expandToc?version=2026&language=english&product=api&queryParam=?id=1"]

    # Custom settings for this spider
    custom_settings = {
        "DEPTH_LIMIT": 0,  # No depth limit, we use URL boundaries instead
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.crawled_urls: set[str] = set()
        self.base_path: str = "/2026/english/api/"
        self.base_url: str = "https://help.solidworks.com"

        # Statistics tracking
        self.stats: dict[str, Any] = {
            "total_pages": 0,
            "successful_pages": 0,
            "failed_pages": 0,
            "skipped_pages": 0,
        }

    def parse(self, response: Response) -> Generator[Any, None, None]:
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
                "url": response.url,
                "status_code": response.status,
                "content": response.text,
                "headers": dict(response.headers),
                "content_hash": hashlib.sha256(response.body).hexdigest(),
                "content_length": len(response.body),
                "title": "expandToc JSON",
            }
            yield item

            # Recursively extract all URLs from the JSON structure
            urls = self.extract_urls_from_json(data)

            self.logger.info(f"Found {len(urls)} URLs in JSON TOC")

            # Create requests for each URL
            for url in urls:
                # Convert relative URL to absolute
                full_url = url
                if url.startswith("/"):
                    full_url = self.base_url + url

                # Check if URL is within our allowed boundary
                parsed = urlparse(full_url)
                if not parsed.path.startswith(self.base_path):
                    self.logger.debug(f"Skipping URL outside boundary: {full_url}")
                    continue

                # Yield request for the page itself
                yield scrapy.Request(
                    full_url, callback=self.parse_page, errback=self.handle_error, meta={"original_url": full_url}
                )

                # Extract id parameter and create expandToc request
                query_params = parse_qs(parsed.query)
                if "id" in query_params:
                    id_value = query_params["id"][0]
                    expand_toc_url = (
                        f"{self.base_url}/expandToc?version=2026&language=english&product=api&queryParam=?id={id_value}"
                    )

                    self.logger.debug(f"Adding expandToc URL for id={id_value}: {expand_toc_url}")

                    yield scrapy.Request(
                        expand_toc_url, callback=self.parse, errback=self.handle_error, dont_filter=False
                    )

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
        except Exception as e:
            self.logger.error(f"Error processing JSON TOC: {e}")

    def extract_urls_from_json(self, data: Any) -> list[str]:
        """
        Recursively extract all URLs from the JSON structure.

        Args:
            data: JSON object or array to process

        Returns:
            List of URLs found in the structure
        """
        urls: list[str] = []

        # Handle array (list of children)
        if isinstance(data, list):
            for item in data:
                urls.extend(self.extract_urls_from_json(item))

        # Handle object (dict)
        elif isinstance(data, dict):
            # Extract URL if present
            if "url" in data and data["url"]:
                urls.append(data["url"])

            # Recursively process children
            if "children" in data and data["children"]:
                urls.extend(self.extract_urls_from_json(data["children"]))

        return urls

    def parse_page(self, response: Response) -> Generator[dict[str, Any], None, None]:
        """Parse and save a documentation page"""
        # Check if this is actually HTML content
        content_type_bytes = response.headers.get("Content-Type", b"")
        content_type = content_type_bytes.decode("utf-8").lower() if content_type_bytes else ""
        if "text/html" not in content_type:
            self.logger.warning(f"Skipping non-HTML content: {response.url}")
            self.stats["skipped_pages"] += 1
            return

        # Check URL boundary again (belt and suspenders)
        parsed = urlparse(response.url)
        if not parsed.path.startswith(self.base_path):
            self.logger.warning(f"URL outside boundary, skipping: {response.url}")
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
            "content": content,  # Save only the helpContentData JSON
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
