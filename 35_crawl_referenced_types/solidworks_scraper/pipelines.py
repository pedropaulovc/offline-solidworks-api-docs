"""
Pipelines for processing and storing crawled SolidWorks API documentation.
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import jsonlines
from itemadapter import ItemAdapter
from scrapy import Spider
from scrapy.exceptions import DropItem


class HtmlSavePipeline:
    """Pipeline to save HTML content to organized file structure"""

    def __init__(self) -> None:
        self.output_dir: Path = Path(__file__).parent.parent / "output" / "html"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_item(self, item: dict[str, Any], spider: Spider) -> dict[str, Any]:
        """Save HTML content to file"""
        # Skip error items
        if item.get("type") == "error":
            return item

        adapter = ItemAdapter(item)

        # Get the URL and content
        url = adapter.get("url")
        content = adapter.get("content")

        if not url or not content:
            spider.logger.warning("Missing URL or content for item")
            return item

        # Generate file path from URL
        file_path = self.url_to_file_path(url)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Save HTML content
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Add file path to item for metadata
            item["file_path"] = str(file_path.relative_to(self.output_dir.parent.parent))
            spider.logger.debug(f"Saved HTML to {file_path}")

        except Exception as e:
            # Drop rather than pass on: MetadataLogPipeline runs next (400 vs this
            # pipeline's 300) and would record the URL in urls_crawled.jsonl with no
            # file behind it. The page would then be missing from extraction *and*
            # skipped by the next --resume as already crawled. Counting it as a
            # failure is what makes run_crawler exit non-zero.
            spider.logger.error(f"Failed to save HTML for {url}: {e}")
            spider.stats["failed_pages"] += 1
            raise DropItem(f"could not save {url}: {e}") from e

        return item

    def url_to_file_path(self, url: str) -> Path:
        """Convert URL to organized file path (deterministic)"""
        from urllib.parse import parse_qs

        parsed = urlparse(url)
        path = parsed.path.strip("/")

        # Special handling for expandToc URLs
        if path == "expandToc":
            # Extract id from queryParam
            query_params = parse_qs(parsed.query)
            if "queryParam" in query_params:
                query_param_value = query_params["queryParam"][0]
                # Parse the id from ?id=5 or ?id=2.1 (handles decimal IDs)
                id_match = re.search(r"id=(-?[\d.]+)", query_param_value)
                if id_match:
                    id_value = id_match.group(1)
                    path = f"expandToc_id_{id_value}.json"
                else:
                    # Fallback if no id found
                    query_hash = hashlib.md5(parsed.query.encode("utf-8")).hexdigest()[:8]
                    path = f"expandToc_{query_hash}.json"
            else:
                # No queryParam, use hash
                query_hash = hashlib.md5(parsed.query.encode("utf-8")).hexdigest()[:8]
                path = f"expandToc_{query_hash}.json"
        else:
            # Regular page handling
            # Remove the base path prefix
            if path.startswith("2026/english/api/"):
                path = path[len("2026/english/api/") :]

            # Remove query parameters from filename but keep them for uniqueness
            # by appending a deterministic hash if query params exist
            if parsed.query:
                # Create a deterministic hash from query params for uniqueness
                # Using MD5 for deterministic hashing (not for security)
                query_hash = hashlib.md5(parsed.query.encode("utf-8")).hexdigest()[:8]
                path = path.replace(".htm", f"_{query_hash}.html")
                path = path.replace(".html", f"_{query_hash}.html")

            # Ensure it ends with .html (we're saving helpText HTML content)
            if not path.endswith(".html"):
                path += ".html"

        # Clean up the path - replace unsafe characters
        path = re.sub(r'[<>:"|?*]', "_", path)

        # Create full file path
        file_path = self.output_dir / path

        return file_path


class MetadataLogPipeline:
    """Pipeline to log metadata about crawled pages"""

    def __init__(self) -> None:
        self.metadata_dir: Path = Path(__file__).parent.parent / "metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        # File paths for different metadata
        self.urls_file: Path = self.metadata_dir / "urls_crawled.jsonl"
        self.errors_file: Path = self.metadata_dir / "errors.jsonl"
        self.manifest_file: Path = self.metadata_dir / "manifest.json"

    def open_spider(self, spider: Spider) -> None:
        # Written here rather than in __init__ so the crawl policy it records is
        # read from the settings actually in force, not restated by hand.
        self.init_manifest(spider)

    def init_manifest(self, spider: Spider) -> None:
        """Initialize or update the manifest file"""
        settings = spider.settings
        manifest = {
            "crawler_version": "1.0.0",
            "start_url": "seed: /api pages referenced but not crawled by phases 10/30/100",
            "boundary": "/2026/english/api/",
            "user_agent": settings.get("USER_AGENT"),
            "respect_robots_txt": settings.getbool("ROBOTSTXT_OBEY"),
            "crawl_delay_seconds": settings.getfloat("DOWNLOAD_DELAY"),
            "concurrent_requests_per_domain": settings.getint("CONCURRENT_REQUESTS_PER_DOMAIN"),
        }

        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def process_item(self, item: dict[str, Any], spider: Spider) -> dict[str, Any]:
        """Log metadata for the crawled item"""
        adapter = ItemAdapter(item)

        # Handle error items separately
        if adapter.get("type") == "error":
            self.log_error(item)
            return item

        # Prepare metadata entry
        metadata = {
            "url": adapter.get("url"),
            "file_path": adapter.get("file_path"),
            "content_hash": adapter.get("content_hash"),
            "content_length": adapter.get("content_length"),
            "status_code": adapter.get("status_code"),
            "title": adapter.get("title"),
        }

        # Log to URLs file
        try:
            with jsonlines.open(self.urls_file, mode="a") as writer:
                writer.write(metadata)
            spider.logger.debug(f"Logged metadata for {metadata['url']}")

        except Exception as e:
            # The HTML is on disk but nothing maps it back to its URL: source
            # discovery works off this manifest, so the page is orphaned, and the
            # next --resume re-fetches it. Same treatment as a failed HTML write.
            spider.logger.error(f"Failed to log metadata for {metadata['url']}: {e}")
            spider.stats["failed_pages"] += 1

        return item

    def log_error(self, error_item: dict[str, Any]) -> None:
        """Log error information"""
        error_data: dict[str, Any] = {
            "url": error_item.get("url"),
            "error": error_item.get("error"),
        }

        try:
            with jsonlines.open(self.errors_file, mode="a") as writer:
                writer.write(error_data)

        except Exception as e:
            # Can't log to spider here, just print
            print(f"Failed to log error: {e}")


class DuplicateCheckPipeline:
    """Pipeline to check for and skip duplicate URLs"""

    def __init__(self) -> None:
        self.seen_urls: set[str] = set()
        self.load_existing_urls()

    def load_existing_urls(self) -> None:
        """Load already crawled URLs from metadata"""
        urls_file = Path(__file__).parent.parent / "metadata" / "urls_crawled.jsonl"

        if urls_file.exists():
            try:
                with jsonlines.open(urls_file) as reader:
                    for obj in reader:
                        if obj.get("url"):
                            self.seen_urls.add(obj["url"])

            except Exception as e:
                print(f"Could not load existing URLs: {e}")

    def process_item(self, item: dict[str, Any], spider: Spider) -> dict[str, Any]:
        """Check if URL has already been processed"""
        # Skip error items
        if item.get("type") == "error":
            return item

        url = item.get("url")

        # Skip items without URL
        if not url:
            return item

        if url in self.seen_urls:
            spider.logger.debug(f"Duplicate URL, skipping: {url}")
            raise DropItem(f"Duplicate URL: {url}")

        self.seen_urls.add(url)
        return item


class ValidationPipeline:
    """Pipeline to validate crawled content"""

    def process_item(self, item: dict[str, Any], spider: Spider) -> dict[str, Any]:
        """Validate that the item has required fields and content"""
        # Skip error items
        if item.get("type") == "error":
            return item

        adapter = ItemAdapter(item)

        # Check required fields
        required_fields = ["url", "content", "content_hash"]
        for field in required_fields:
            if not adapter.get(field):
                spider.logger.warning(f"Missing required field '{field}' for {adapter.get('url')}")

        # Validate content is not empty
        content = adapter.get("content", "")
        if len(content) < 100:  # Arbitrary minimum content length
            spider.logger.warning(f"Suspiciously short content for {adapter.get('url')}: {len(content)} bytes")

        # Check if it's actually HTML
        if content and not ("<html" in content.lower() or "<!doctype" in content.lower()):
            spider.logger.warning(f"Content doesn't appear to be HTML for {adapter.get('url')}")

        return item
