"""Seed and boundary computation for the referenced-pages closure crawl.

Phase 115 crawls every page under ``/2026/english/api/`` that the rest of the
corpus links to but that no earlier phase crawled. The URL primitives it needs --
:func:`canonical_key`, :func:`iter_page_links`, :class:`ReferenceSource` and
friends -- live in :mod:`shared.api_urls`, shared with phase 35, which runs the
mirror-image crawl over the generated reference tree. What stays here is specific
to *this* phase's seed:

- :func:`build_bundle_doc_keys` loads the pages already exported as bundle docs.
  That, not "already crawled", is the seed exclusion: a page crawled elsewhere but
  never exported still needs seeding to reach the bundle.
- :func:`build_saved_page_keys` does the same for pages that reach the bundle
  through extraction rather than a manifest, requiring the HTML to still exist.
- :func:`build_seed` scans the corpus for links -- absolute URLs in the extracted
  XML/Markdown, and ``href``/``src`` attributes (usually *relative*) in the crawled
  help-text HTML -- and returns the ones the bundle does not already ship, dropping
  generated reference pages, which belong to the type/enum pipeline.
"""

import sys
from pathlib import Path
from typing import Iterable

import jsonlines

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.api_urls import (  # noqa: E402,F401  (re-exported for this phase's callers)
    API_PREFIX,
    HOST,
    PAGE_SUFFIXES,
    ReferenceSource,
    build_exclusion_keys,
    build_saved_page_keys,
    canonical_key,
    crawled_html_sources,
    is_reference_page,
    iter_page_links,
    normalize_request_url,
    page_assembly,
)


def build_bundle_doc_keys(files_created_files: Iterable[Path]) -> set[str]:
    """Union of :func:`canonical_key` for every page already exported as a bundle
    doc, read from ``files_created.jsonl`` manifests (Phase 110/115). This is the
    *seed exclusion*: a page is only skipped as a seed if it is already available
    as a doc -- pages crawled elsewhere but never exported (e.g. FunctionalCategories)
    are still seeded so they get into the bundle."""
    keys: set[str] = set()
    for meta in files_created_files:
        if not Path(meta).exists():
            continue
        with jsonlines.open(meta) as reader:
            for entry in reader:
                key = canonical_key(entry.get("original_url", ""))
                if key:
                    keys.add(key)
    return keys


def build_seed(reference_sources: Iterable[ReferenceSource], exclusion_keys: set[str]) -> list[str]:
    """Page URLs referenced in the corpus but not already crawled.

    Generated reference pages are dropped here for the same reason the closure
    never follows them (see :func:`is_reference_page`): scanning raw help-text HTML
    surfaces thousands of ``~`` links, and they belong to the type/enum pipeline
    (phases 20/30/35), not to this doc-page closure.

    Deduplicated by :func:`canonical_key` and returned sorted for reproducibility.
    """
    seed: dict[str, str] = {}
    for source in reference_sources:
        if not source.path.exists():
            continue
        text = source.path.read_text(encoding="utf-8", errors="ignore")
        for url in iter_page_links(text, base=source.base_url):
            key = canonical_key(url)
            if not key or key in exclusion_keys or key in seed:
                continue
            if is_reference_page(url):
                continue
            request_url = normalize_request_url(url)
            if request_url:
                seed[key] = request_url
    return [seed[k] for k in sorted(seed)]
