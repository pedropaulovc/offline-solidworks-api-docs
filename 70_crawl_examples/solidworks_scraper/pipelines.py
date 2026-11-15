"""
Pipelines for processing and storing crawled SolidWorks API example pages.
"""

import hashlib
import json
import re
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import jsonlines
from itemadapter import ItemAdapter
from scrapy import Spider, signals
from scrapy.exceptions import DropItem

# Add project root to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.constants import SOLIDWORKS_API_FULL_BASE_URL, SOLIDWORKS_API_PATH_PREFIX, SOLIDWORKS_API_VERSION

# Doc year the local (gitignored) output/html corpus was crawled for. Saved pages
# carry no year, so consumers that need a current-version corpus check this file.
# It reads exactly "<year>" only after a crawl finished with no failed pages on a
# corpus holding nothing but that year's pages. While a crawl runs (or after one
# is interrupted) it reads "<year> partial", so a --resume run knows the existing
# pages are this year's and can complete the corpus.
CRAWL_VERSION_FILE = Path(__file__).parent.parent / "output" / "crawl_version.txt"
PARTIAL_SUFFIX = " partial"


class CorpusVersion(Enum):
    """Whether output/html holds only current-year pages when a crawl starts."""

    CURRENT = "current"  # empty, or marked (complete or partial) with SOLIDWORKS_API_VERSION
    MIXED = "mixed"  # older or unknown pages a --resume run would mix with new ones


def read_marker_year() -> str | None:
    """Year recorded in the marker, whether the crawl it describes completed or not."""
    if not CRAWL_VERSION_FILE.exists():
        return None
    return CRAWL_VERSION_FILE.read_text(encoding="utf-8").strip().removesuffix(PARTIAL_SUFFIX) or None


class HtmlSavePipeline:
    """Pipeline to save HTML content to organized file structure"""

    def __init__(self) -> None:
        self.output_dir: Path = Path(__file__).parent.parent / "output" / "html"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.corpus_version: CorpusVersion = CorpusVersion.MIXED

    @classmethod
    def from_crawler(cls, crawler: Any) -> "HtmlSavePipeline":
        pipeline = cls()
        crawler.signals.connect(pipeline.spider_closed, signal=signals.spider_closed)
        return pipeline

    def open_spider(self, spider: Spider) -> None:
        corpus_empty = not any(self.output_dir.rglob("*.htm*"))
        if not corpus_empty and read_marker_year() != SOLIDWORKS_API_VERSION:
            # Older or unmarked pages: leave the marker as it is (never this
            # year's complete marker), so the corpus stays non-current until a
            # fresh crawl clears it.
            self.corpus_version = CorpusVersion.MIXED
            return

        self.corpus_version = CorpusVersion.CURRENT
        CRAWL_VERSION_FILE.write_text(f"{SOLIDWORKS_API_VERSION}{PARTIAL_SUFFIX}\n", encoding="utf-8")

    def spider_closed(self, spider: Spider, reason: str) -> None:
        if reason != "finished" or self.corpus_version is not CorpusVersion.CURRENT:
            return
        # "finished" only means the scheduler drained; failed downloads leave holes.
        if getattr(spider, "stats", {}).get("failed_pages", 0):
            return
        CRAWL_VERSION_FILE.write_text(f"{SOLIDWORKS_API_VERSION}\n", encoding="utf-8")

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
            spider.logger.error(f"Failed to save HTML for {url}: {e}")
            item["save_error"] = str(e)

        return item

    def url_to_file_path(self, url: str) -> Path:
        """Convert URL to organized file path (deterministic)"""
        parsed = urlparse(url)
        path = parsed.path.strip("/")

        # Remove the base path prefix
        if path.startswith(SOLIDWORKS_API_PATH_PREFIX):
            path = path[len(SOLIDWORKS_API_PATH_PREFIX) :]

        # Remove query parameters from filename but keep them for uniqueness
        # by appending a deterministic hash if query params exist
        if parsed.query:
            # Create a deterministic hash from query params for uniqueness
            # Using MD5 for deterministic hashing (not for security)
            query_hash = hashlib.md5(parsed.query.encode("utf-8")).hexdigest()[:8]

            # Replace .htm or .html extension with _{hash}.html
            if path.endswith(".htm"):
                path = path[:-4] + f"_{query_hash}.html"
            elif path.endswith(".html"):
                path = path[:-5] + f"_{query_hash}.html"
            else:
                path += f"_{query_hash}.html"
        else:
            # Ensure it has an HTML extension (preserve .htm or .html from original)
            if not (path.endswith(".html") or path.endswith(".htm")):
                # Only add extension if missing entirely
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

        # Initialize manifest
        self.init_manifest()

    def init_manifest(self) -> None:
        """Initialize or update the manifest file"""
        manifest = {
            "crawler_version": "1.0.0",
            "source_file": "40_extract_type_details/metadata/api_types.xml",
            "urls_file": "70_crawl_examples/metadata/example_urls.txt",
            "base_url": SOLIDWORKS_API_FULL_BASE_URL,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "respect_robots_txt": False,
            "crawl_delay_seconds": 0.1,
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
            spider.logger.error(f"Failed to log metadata: {e}")

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
