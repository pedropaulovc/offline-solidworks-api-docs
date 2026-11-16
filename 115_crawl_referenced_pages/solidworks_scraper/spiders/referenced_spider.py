"""Referenced-pages closure spider.

Crawls every page under ``SOLIDWORKS_API_BOUNDARY`` that the extracted corpus links to
but that phases 10/30/100 never fetched, following in-page ``/api`` links until the
set is closed. Pages already crawled by other phases are pre-seeded as "seen" so
the closure stops at the corpus boundary instead of re-crawling the reference tree.

Page content is the ``helpText`` HTML embedded in each page's ``__NEXT_DATA__``
JSON -- identical to the Phase 100 programming-guide spider.
"""

import glob
import hashlib
import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import scrapy
from scrapy.http import Response

# spiders/ -> solidworks_scraper/ -> 115_crawl_referenced_pages/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

import sys

sys.path.insert(0, str(REPO_ROOT / "115_crawl_referenced_pages"))
sys.path.insert(0, str(REPO_ROOT))
from shared.constants import SOLIDWORKS_API_FULL_BASE_URL  # noqa: E402
from shared.help_page_spider import DeadLinkPolicy, HelpPageSpider  # noqa: E402
from link_targets import (  # noqa: E402
    ReferenceSource,
    build_bundle_doc_keys,
    build_exclusion_keys,
    build_saved_page_keys,
    build_seed,
    canonical_key,
    crawled_html_sources,
    is_reference_page,
    iter_page_links,
)

# Pages to crawl beyond what the corpus literally references. The docs link
# DP_ImageQuality under sldworksapi/, which is an empty stub; the real content is
# under swconst/. Guide-link resolution is by basename, so crawling the swconst
# page satisfies the (basename-identical) sldworksapi reference.
_EXTRA_SEED_URLS = [
    f"{SOLIDWORKS_API_FULL_BASE_URL}/swconst/DP_ImageQuality.htm",
]

# Pages already crawled by earlier phases -- the closure boundary (link-following
# stops here so it never re-expands into the reference tree).
_EXCLUSION_METADATA = [
    REPO_ROOT / "10_crawl_toc_pages/metadata/urls_crawled.jsonl",
    REPO_ROOT / "30_crawl_type_members/metadata/urls_crawled.jsonl",
    REPO_ROOT / "100_crawl_programming_guide/metadata/urls_crawled.jsonl",
    # This phase's own log, so --resume doesn't re-crawl.
    REPO_ROOT / "115_crawl_referenced_pages/metadata/urls_crawled.jsonl",
]

# Pages already exported as bundle docs -- the seed exclusion. A referenced page is
# only skipped as a seed if it already ships; pages crawled elsewhere but never
# exported (e.g. FunctionalCategories) are still seeded so they reach the bundle.
# Keyed by ``original_url``.
_BUNDLE_MANIFESTS = [
    REPO_ROOT / "110_extract_docs_md/metadata/files_created.jsonl",
    REPO_ROOT / "115_crawl_referenced_pages/metadata/files_created.jsonl",
]

# Also already in the bundle, but with no files_created manifest of their own:
# Phase 70's example pages, which Phase 80 parses and Phase 120 emits as
# ``examples/*.md``. These both bound the closure -- module pages link back to the
# example that referenced them, which would otherwise pull Phase 70's tree in --
# and exclude seeds, so ~2800 already-shipping pages are not re-crawled into docs/.
# Only pages whose HTML is still on disk count, in both roles: Phase 80 exports what
# it can read, so a recorded-but-missing page ships nowhere and must stay crawlable.
_BUNDLE_CRAWL_PHASES = [
    REPO_ROOT / "70_crawl_examples",
]

# Crawled help-text HTML, scanned for *relative* links. The extracted corpus below
# preserves only absolute ``<see href>`` URLs, so a page linked the way multi-module
# examples link their sibling code pages -- ``href="DimXpert_Main_Module_CSharp.htm"``
# -- was invisible to the seed and shipped as a dead link. The raw HTML is the ground
# truth for what the docs actually link to.
_CRAWLED_HTML_PHASES = [
    "10_crawl_toc_pages",
    "30_crawl_type_members",
    "70_crawl_examples",
    "100_crawl_programming_guide",
    "115_crawl_referenced_pages",
]


# Corpus scanned for the initial ``<see href>`` / link references.
def _reference_sources() -> list[ReferenceSource]:
    # Derived files: no single origin page, so absolute URLs only.
    sources = [
        ReferenceSource(REPO_ROOT / "40_extract_type_details/metadata/api_types.xml"),
        ReferenceSource(REPO_ROOT / "50_extract_type_member_details/metadata/api_member_details.xml"),
        ReferenceSource(REPO_ROOT / "60_extract_enum_members/metadata/enum_members.xml"),
    ]
    sources += [
        ReferenceSource(Path(p))
        for p in glob.glob(str(REPO_ROOT / "110_extract_docs_md/output/markdown/**/*.md"), recursive=True)
    ]
    # Crawled HTML: each page's own URL resolves its relative links.
    for phase in _CRAWLED_HTML_PHASES:
        sources += crawled_html_sources(REPO_ROOT / phase, REPO_ROOT / phase / "metadata/urls_crawled.jsonl")
    return sources


class ReferencedSpider(HelpPageSpider):
    name = "referenced_pages"
    allowed_domains = ["help.solidworks.com"]

    # Seeds and followed links include dead links the server cannot find
    # (help_list.htm, stubs like DP_ImageQuality.htm, pages dropped from the help).
    dead_link_policy = DeadLinkPolicy.SKIP_CONFIRMED

    custom_settings = {
        "DEPTH_LIMIT": 0,  # bounded by the exclusion set + /api boundary instead
    }

    # Safety net against an unexpected runaway closure; logged if reached.
    MAX_PAGES = 2000

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.crawled_keys = build_exclusion_keys(_EXCLUSION_METADATA)
        self.bundle_keys = build_bundle_doc_keys(_BUNDLE_MANIFESTS)
        # Phase 70 bounds the closure *and* excludes seeds, on the same condition:
        # the page ships only if Phase 80 can read its HTML. Adding it to the
        # boundary off the raw manifest would let a recorded-but-missing page be
        # skipped when link-following reaches it, stranding it exactly as an
        # unfiltered seed exclusion would.
        for phase in _BUNDLE_CRAWL_PHASES:
            saved = build_saved_page_keys(phase, phase / "metadata/urls_crawled.jsonl")
            self.bundle_keys |= saved
            self.crawled_keys |= saved
        # Seed = referenced pages not yet available as bundle docs, plus explicit
        # extra seeds. Deduplicate by key and drop any already in the bundle.
        seed_keys: set[str] = set()
        self.seed: list[str] = []
        for url in build_seed(_reference_sources(), self.bundle_keys) + _EXTRA_SEED_URLS:
            key = canonical_key(url)
            if key and key not in self.bundle_keys and key not in seed_keys:
                seed_keys.add(key)
                self.seed.append(url)

        # Closure boundary: pages crawled elsewhere OR already queued here.
        self.seen: set[str] = set(self.crawled_keys) | seed_keys

        self.stats.update(
            {
                "seed_pages": len(self.seed),
                "excluded_pages": len(self.crawled_keys),
                "discovered_via_links": 0,
            }
        )

    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        self.logger.info(
            f"Seed: {len(self.seed)} referenced pages not yet in the bundle; "
            f"closure boundary excludes {len(self.crawled_keys)} already-crawled pages"
        )
        for url in self.seed:
            yield scrapy.Request(url, callback=self.parse_page, errback=self.handle_error, meta={"origin": "seed"})

    def parse_page(self, response: Response) -> Generator[Any, None, None]:
        content_type = response.headers.get("Content-Type", b"").decode("utf-8", "ignore").lower()
        if "text/html" not in content_type:
            self.stats["skipped_pages"] += 1
            return

        key = canonical_key(response.url)
        if key is None:
            self.stats["skipped_pages"] += 1
            return

        # Extract helpText from __NEXT_DATA__ (same shape as the guide pages); a page
        # without it is retried, then failed or skipped as a confirmed dead link.
        help_text = yield from self.help_text_or_retry(response)
        if help_text is None:
            return

        self.stats["successful_pages"] += 1
        title = response.xpath("//title/text()").get()
        item = {
            "url": response.url,
            "original_url": response.meta.get("origin", response.url),
            "status_code": response.status,
            "content": help_text,
            "content_hash": hashlib.sha256(help_text.encode("utf-8")).hexdigest(),
            "content_length": len(help_text.encode("utf-8")),
            "title": title.strip() if title else "Untitled",
        }
        yield item
        self.logger.info(f"Crawled referenced page: {response.url} - {item['title']}")

        # Follow in-page /api links, expanding the closure to newly-referenced pages.
        if self.stats["successful_pages"] >= self.MAX_PAGES:
            self.logger.warning(f"MAX_PAGES ({self.MAX_PAGES}) reached; stopping closure expansion")
            return

        for target in iter_page_links(help_text, base=response.url):
            tkey = canonical_key(target)
            if not tkey or tkey in self.seen:
                continue
            # Never follow into the generated reference tree (belt-and-suspenders
            # against URL-encoding mismatches slipping past the crawled-set boundary).
            if is_reference_page(target):
                continue
            self.seen.add(tkey)
            self.stats["discovered_via_links"] += 1
            yield scrapy.Request(target, callback=self.parse_page, errback=self.handle_error, meta={"origin": "link"})

    def closed(self, reason: str) -> None:
        self.stats["reason"] = reason
        stats_file = Path(__file__).parent.parent.parent / "metadata" / "crawl_stats.json"
        stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2)
        self.logger.info(
            f"Closed ({reason}). Crawled {self.stats['successful_pages']} pages "
            f"({self.stats['discovered_via_links']} discovered via links), {self.stats['failed_pages']} failed."
        )
