"""
SolidWorks API Documentation Spider

This spider crawls the SolidWorks API documentation by:
1. Fetching the table of contents from the JSON API endpoint
2. Recursively extracting all URLs from the children array
3. Downloading each page
"""

import hashlib
import json
import re
import sys
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import scrapy
from scrapy.http import Response
from twisted.python.failure import Failure

# Add project root to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from shared.constants import SOLIDWORKS_API_BOUNDARY, SOLIDWORKS_BASE_URL, expand_toc_url


class ApiDocsSpider(scrapy.Spider):
    name = "api_docs"
    allowed_domains = ["help.solidworks.com"]

    # Root TOC node ids to seed the crawl (top-level nodes, parentId=-1, of the
    # SOLIDWORKS API reference at help.solidworks.com/<year>/english/api/SWHelp_List.html).
    # These ids are version-specific and must be re-mapped on every yearly bump.
    #
    # 2027 flattened the TOC: the per-product wrapper nodes of 2026 (id=2 core
    # API with children 2.0..2.11, id=13 Toolbox) are gone and their former
    # children are now top-level nodes:
    #   core SOLIDWORKS API:
    #     2  = Functional Categories (leaf)
    #     3  = Release Notes (leaf)
    #     4  = SolidWorks.Interop.sldworks Namespace (4.0 Overview, 4.1 Interfaces,
    #          4.2 Delegates, 4.3..4.11 swmotionstudy, swdimxpert, swpublished,
    #          sw3dprinter, dsgnchk, swhtmlcontrol, swscanto3d, swconst, swcommands)
    #   Toolbox API:
    #     44 = Welcome (leaf), 45 = Release Notes (leaf), 46 = Getting Started,
    #     47 = sldtoolboxconfigureaddin Namespace, 48 = swbrowser Namespace
    # The Programming Guide (id=1) is crawled separately by Phase 100.
    # A root's expandToc response is the node itself (with its own url), so leaf
    # roots still yield their page request via extract_urls_from_json. All roots
    # share the SOLIDWORKS_API_BOUNDARY, so the recursive expandToc logic and URL
    # boundary check below handle every subtree unchanged.
    TOC_ROOT_IDS = ["2", "3", "4", "44", "45", "46", "47", "48"]

    # 2027 also expands every type into "Methods"/"Properties" TOC nodes that list
    # each member page, and dropped the type's "Members" node. Member pages are
    # Phase 30's job, and Phase 20 parses the combined `<Type>_members.html` page,
    # which still exists on the server but is no longer linked from the TOC. So a
    # member-list node is replaced by its type's `_members.html` page (keyed by
    # the parent type node id, so Methods and Properties dedupe to one request)
    # and its member subtree is not expanded.
    MEMBER_LIST_PATH = re.compile(r"_(?:methods|properties)\.html$")

    # Starting URLs - JSON TOC endpoints, one per root node
    start_urls = [expand_toc_url(toc_id) for toc_id in TOC_ROOT_IDS]

    # Custom settings for this spider
    custom_settings = {
        "DEPTH_LIMIT": 0,  # No depth limit, we use URL boundaries instead
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.crawled_urls: set[str] = set()
        # TOC ids that requested each page path. 2027 type nodes have an "Overview"
        # child pointing at the same page with a different ?id=, which would
        # otherwise save every type page twice.
        self.page_path_requesters: dict[str, set[str | None]] = {}
        self.base_path: str = SOLIDWORKS_API_BOUNDARY
        self.base_url: str = SOLIDWORKS_BASE_URL

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

                query_params = parse_qs(parsed.query)
                id_value = query_params["id"][0] if "id" in query_params else None

                if self.MEMBER_LIST_PATH.search(parsed.path):
                    members_request = self.members_page_request(parsed.path, id_value)
                    if members_request is not None:
                        yield members_request
                    continue

                if self.is_overview_duplicate(parsed.path, id_value):
                    self.logger.debug(f"Skipping Overview duplicate of its parent page: {full_url}")
                    continue
                self.page_path_requesters.setdefault(parsed.path, set()).add(id_value)

                # Yield request for the page itself
                yield scrapy.Request(
                    full_url, callback=self.parse_page, errback=self.handle_error, meta={"original_url": full_url}
                )

                if id_value is None:
                    continue

                toc_url = expand_toc_url(id_value)
                self.logger.debug(f"Adding expandToc URL for id={id_value}: {toc_url}")
                yield scrapy.Request(toc_url, callback=self.parse, errback=self.handle_error, dont_filter=False)

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
            url = data.get("url")
            if url:
                urls.append(url)

            # Member-list nodes stand in for their type's _members page; their
            # per-member children are Phase 30's job.
            if url and self.MEMBER_LIST_PATH.search(urlparse(url).path):
                return urls

            # Recursively process children
            if data.get("children"):
                urls.extend(self.extract_urls_from_json(data["children"]))

        return urls

    def is_overview_duplicate(self, path: str, id_value: str | None) -> bool:
        """True for a node that repeats its parent node's page (the 2027 type "Overview" child).

        Only direct children of a node that requested the same path are skipped,
        page and subtree alike. Every requesting id is kept, so a page listed under
        two TOC branches has the Overview child of each branch skipped regardless of
        which response arrived first; the branches themselves keep their own fetch
        and expansion. help_list.htm is the shared page of every folder node and is
        never a duplicate.
        """
        if path.endswith("/help_list.htm") or id_value is None:
            return False
        return id_value.rsplit(".", 1)[0] in self.page_path_requesters.get(path, set())

    def members_page_request(self, member_list_path: str, member_list_id: str | None) -> scrapy.Request | None:
        """Request the `<Type>_members.html` page standing in for a Methods/Properties TOC node.

        Returns None when the type's members page was already requested (Methods and
        Properties siblings, or a nested member-list node under the same type)."""
        members_path = self.MEMBER_LIST_PATH.sub("_members.html", member_list_path)
        if members_path in self.page_path_requesters:
            return None
        type_id = member_list_id.rsplit(".", 1)[0] if member_list_id else None
        self.page_path_requesters[members_path] = {type_id}

        members_url = f"{self.base_url}{members_path}"
        if type_id:
            members_url = f"{members_url}?id={type_id}"
        return scrapy.Request(
            members_url, callback=self.parse_page, errback=self.handle_error, meta={"original_url": members_url}
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
