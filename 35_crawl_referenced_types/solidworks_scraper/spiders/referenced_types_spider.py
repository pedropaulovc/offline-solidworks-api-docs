"""Referenced-types spider.

Crawls the generated reference pages (``Assembly~Namespace.Type[~Member]``) that
the corpus links to but that phases 10/30 never fetched, because the source TOC
does not expose them -- see :mod:`reference_targets` for the defect.

For each newly discovered *type* it also fetches the ``_members`` companion page
and the member pages linked from it, so the type arrives complete: phase 20 builds
its type list from ``*_members*`` pages and phase 50 reads member pages, and
neither re-runs the phase-30 crawl.

Page content is the ``helpText`` HTML embedded in each page's ``__NEXT_DATA__``
JSON, saved in the same per-assembly layout phases 10/30 use so the extraction
phases can read this output as just another input directory.
"""

import hashlib
import json
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import scrapy
from scrapy.http import Response
from twisted.python.failure import Failure

# spiders/ -> solidworks_scraper/ -> 35_crawl_referenced_types/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

sys.path.insert(0, str(REPO_ROOT / "35_crawl_referenced_types"))
sys.path.insert(0, str(REPO_ROOT))

from reference_targets import (  # noqa: E402
    build_seed,
    build_shipped_assemblies,
    member_list_url,
)
from shared.api_urls import (  # noqa: E402
    build_exclusion_keys,
    build_saved_page_keys,
    canonical_key,
    crawled_html_sources,
    is_reference_page,
    iter_page_links,
    normalize_request_url,
    page_assembly,
)

# Phases whose crawled help-text HTML is scanned for reference links, and which
# together define the already-crawled boundary.
#
# Split because run_pipeline.sh runs this phase twice. On the first pass only the
# TOC-driven crawls have re-run; phases 70/100/115 still hold the *previous*
# refresh's HTML, and scanning that would seed reference types the current corpus
# no longer links to. The post-115 pass adds them once they are current.
_SELF_PHASE = "35_crawl_referenced_types"
_EARLY_PHASES = [
    "10_crawl_toc_pages",
    "30_crawl_type_members",
    # This phase's own log, so --resume doesn't re-crawl.
    _SELF_PHASE,
]
_LATE_PHASES = [
    "70_crawl_examples",
    "100_crawl_programming_guide",
    "115_crawl_referenced_pages",
]


def corpus_phases(include_late: bool) -> list[str]:
    return _EARLY_PHASES + (_LATE_PHASES if include_late else [])

# Assemblies the pipeline ships, derived from what the TOC-driven phases crawled.
_SHIPPED_SOURCES = ["10_crawl_toc_pages", "30_crawl_type_members"]


def _metadata(phase: str) -> Path:
    return REPO_ROOT / phase / "metadata/urls_crawled.jsonl"


class ReferencedTypesSpider(scrapy.Spider):
    name = "referenced_types"
    allowed_domains = ["help.solidworks.com"]

    custom_settings = {
        "DEPTH_LIMIT": 0,  # bounded by the crawled set + reference-page check instead
    }

    # Safety net against an unexpected runaway expansion; logged if reached.
    MAX_PAGES = 20000

    def __init__(self, all_sources: Any = False, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Scrapy passes spider arguments as strings.
        self.all_sources = str(all_sources).lower() in {"1", "true", "yes"}
        phases = corpus_phases(self.all_sources)

        others = [ph for ph in phases if ph != _SELF_PHASE]
        self.crawled_keys = build_exclusion_keys([_metadata(ph) for ph in others])
        # This phase's own pages are excluded only while their HTML is still on
        # disk. output/ is gitignored but metadata/ is committed, so keying off the
        # manifest alone would make --resume on a fresh checkout skip all 748
        # recorded pages and leave nothing for extraction to read.
        self.crawled_keys |= build_saved_page_keys(
            REPO_ROOT / _SELF_PHASE, _metadata(_SELF_PHASE)
        )
        self.shipped = build_shipped_assemblies([_metadata(ph) for ph in _SHIPPED_SOURCES])

        # Deliberately not this phase's own HTML: parse_page expands member-list
        # pages only, and scanning pass 1's type/member pages here would bypass that
        # boundary and let each resume walk another step into the reference tree.
        sources = []
        for phase in others:
            sources += crawled_html_sources(REPO_ROOT / phase, _metadata(phase))
        seed, self.out_of_scope = build_seed(sources, self.crawled_keys, self.shipped)

        # A newly discovered type only enters phase 20 with its member list, so
        # queue that alongside the type page itself.
        self.seed: list[str] = []
        self.scheduled = 0
        self.limit_hit = False
        self.seen: set[str] = set(self.crawled_keys)
        for url in seed + [m for m in map(member_list_url, seed) if m]:
            key = canonical_key(url)
            if key and key not in self.seen:
                self.seen.add(key)
                self.seed.append(url)

        self.stats: dict[str, Any] = {
            "source_phases": phases,
            "seed_pages": len(self.seed),
            "unscheduled_pages": 0,
            "excluded_pages": len(self.crawled_keys),
            "out_of_scope_pages": sum(self.out_of_scope.values()),
            "out_of_scope_by_assembly": self.out_of_scope,
            "total_pages": 0,
            "successful_pages": 0,
            "failed_pages": 0,
            "skipped_pages": 0,
            "members_discovered": 0,
        }

    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        self.logger.info(
            f"Seed: {len(self.seed)} reference pages missing from the TOC-driven crawl; "
            f"{len(self.crawled_keys)} already crawled"
        )
        if self.out_of_scope:
            self.logger.info(
                "Skipped reference pages in trees this project does not crawl: "
                + ", ".join(f"{a}={n}" for a, n in sorted(self.out_of_scope.items()))
            )
        for url in self.seed:
            request = self.schedule(url)
            if request is None:
                break
            yield request

    def schedule(self, url: str) -> scrapy.Request | None:
        """Queue a page, or None once the safety limit is reached.

        The cap has to be applied here, where requests are created, rather than
        only before expanding a response: seeds are all scheduled up front, and a
        member list received just under the limit would otherwise enqueue its whole
        member set. In-flight requests can still land after the cap trips, so the
        real ceiling is MAX_PAGES plus at most one concurrency window.
        """
        if self.scheduled >= self.MAX_PAGES:
            if not self.limit_hit:
                self.limit_hit = True
                self.logger.warning(
                    f"MAX_PAGES ({self.MAX_PAGES}) reached; scheduling no further pages"
                )
            self.stats["unscheduled_pages"] += 1
            return None
        self.scheduled += 1
        return scrapy.Request(url, callback=self.parse_page, errback=self.handle_error)

    def parse_page(self, response: Response) -> Generator[Any, None, None]:
        key = canonical_key(response.url)
        if key is None:
            self.stats["skipped_pages"] += 1
            return

        # A page whose payload we cannot read is a *failure*, not a skip: skips do
        # not reach crawl_failure(), so a mangled response would drop the type from
        # the exports with the phase still reporting success. Only the recognised
        # soft-404 below (served-but-empty helpText) is legitimately skippable.
        json_text = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
        if not json_text:
            self.logger.error(f"No __NEXT_DATA__ in {response.url}")
            self.stats["failed_pages"] += 1
            return
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Bad __NEXT_DATA__ JSON in {response.url}: {e}")
            self.stats["failed_pages"] += 1
            return
        content = data.get("props", {}).get("pageProps", {}).get("helpContentData")
        if not isinstance(content, dict):
            self.logger.error(f"Unexpected __NEXT_DATA__ shape in {response.url}")
            self.stats["failed_pages"] += 1
            return
        help_text = content.get("helpText")
        if not help_text:
            # A page the docs link to but the source serves empty -- the same
            # soft-404 shape phase 115 sees. Not an error, just nothing to save.
            self.logger.warning(f"No helpText in {response.url}")
            self.stats["skipped_pages"] += 1
            return

        self.stats["total_pages"] += 1
        self.stats["successful_pages"] += 1
        title = response.xpath("//title/text()").get()
        yield {
            "url": response.url,
            "status_code": response.status,
            "content": help_text,
            "content_hash": hashlib.sha256(help_text.encode("utf-8")).hexdigest(),
            "content_length": len(help_text.encode("utf-8")),
            "title": title.strip() if title else "Untitled",
        }
        self.logger.info(f"Crawled referenced type page: {response.url}")

        # Only member-list pages expand: they enumerate the type's members, which
        # phase 50 needs. Every other reference page is a leaf here -- following
        # their links would walk the whole reference tree, which is phase 10/30's job.
        if "_members" not in key:
            return

        for raw in iter_page_links(help_text, base=response.url):
            target = normalize_request_url(raw)
            if not target or not is_reference_page(target):
                continue
            tkey = canonical_key(target)
            if not tkey or tkey in self.seen:
                continue
            if page_assembly(target) not in self.shipped:
                continue
            self.seen.add(tkey)
            request = self.schedule(target)
            if request is None:
                return
            self.stats["members_discovered"] += 1
            yield request

    def handle_error(self, failure: Failure) -> Generator[dict[str, Any], None, None]:
        self.stats["failed_pages"] += 1
        request_url = failure.request.url  # type: ignore[attr-defined]
        self.logger.error(f"Failed to crawl {request_url}: {failure.value}")
        yield {"type": "error", "url": request_url, "error": str(failure.value)}

    def closed(self, reason: str) -> None:
        self.stats["reason"] = reason
        stats_file = REPO_ROOT / "35_crawl_referenced_types" / "metadata" / "crawl_stats.json"
        stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2)
        self.logger.info(
            f"Closed ({reason}). Crawled {self.stats['successful_pages']} pages "
            f"({self.stats['members_discovered']} members discovered), {self.stats['failed_pages']} failed."
        )
