"""Seed and boundary computation for the referenced-pages closure crawl.

Phase 115 crawls every page under ``/2026/english/api/`` that the rest of the
corpus links to but that no earlier phase crawled. This module is the pure,
network-free core:

- :func:`canonical_key` reduces any page URL to a case-insensitive identity so a
  reference (``.../OVERVIEW/In-process_Methods.htm``) matches its crawled copy
  (``.../Overview/In-process_Methods.htm``) and double slashes don't matter.
- :func:`build_exclusion_keys` loads the keys of pages already crawled by phases
  10/30/100 (and 115 itself on resume). These bound the closure: the spider
  treats them as already-seen, so it never re-expands into the reference tree.
- :func:`build_seed` scans the extracted corpus for absolute ``/api`` page links
  and returns those whose key is not already crawled -- the crawl's entry points.
"""

import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import jsonlines

HOST = "https://help.solidworks.com"
API_PREFIX = "2026/english/api/"
PAGE_SUFFIXES = (".htm", ".html")

# Absolute page URLs under the /api boundary, e.g.
# https://help.solidworks.com/2026/english/api/swconst/DP_Dimensions.htm
_ABS_API_URL = re.compile(
    r"https?://help\.solidworks\.com/2026/english/api/[^\s\"'<>)\]]+?\.html?",
    re.IGNORECASE,
)


def canonical_key(url: str) -> str | None:
    """Case-insensitive identity of an ``/api`` documentation page.

    Returns ``<lower path under api>`` with collapsed slashes and no query, or
    ``None`` when the URL is not a page (wrong host/tree, or not ``.htm``/``.html``).
    """
    if not url:
        return None

    parsed = urlparse(url)
    # Accept absolute help.solidworks.com URLs and host-relative paths (e.g. the
    # ``/2026/...`` form stored in Phase 110's manifest); reject other hosts.
    if parsed.netloc and parsed.netloc != "help.solidworks.com":
        return None

    path = re.sub(r"/{2,}", "/", parsed.path).strip("/").lower()
    if not path.startswith(API_PREFIX):
        return None
    if not path.endswith(PAGE_SUFFIXES):
        return None
    return path


def is_reference_page(url: str) -> bool:
    """True for a generated API reference type/member page.

    These use a ``Assembly~Namespace.Type~Member`` filename (the ``~`` is the
    tell) and are all crawled by phases 20/30. The closure must never follow
    into them -- an index page like FunctionalCategories links to hundreds, and a
    URL-encoding mismatch (e.g. a space rendered ``%20``) could otherwise slip one
    past the crawled-set boundary.
    """
    key = canonical_key(url)
    return bool(key and "~" in key)


def normalize_request_url(url: str, base: str | None = None) -> str | None:
    """Resolve ``url`` (possibly relative to ``base``) to an absolute page URL
    under the boundary, collapsing accidental double slashes. Returns ``None``
    when it is not a crawlable ``/api`` page.

    Original casing is preserved (the live site is case-sensitive); only the
    matching *key* is lowercased.
    """
    absolute = urljoin(base, url) if base else url
    if absolute.startswith("/"):
        absolute = HOST + absolute
    if canonical_key(absolute) is None:
        return None

    parsed = urlparse(absolute)
    clean_path = re.sub(r"/{2,}", "/", parsed.path)
    return f"{HOST}{clean_path}"


def iter_api_page_urls(text: str) -> Iterable[str]:
    """Yield every absolute ``/api`` page URL that literally appears in ``text``."""
    for match in _ABS_API_URL.finditer(text):
        yield match.group(0)


def build_exclusion_keys(metadata_files: Iterable[Path]) -> set[str]:
    """Union of :func:`canonical_key` for every page in the given
    ``urls_crawled.jsonl`` files (missing files are skipped). This is the *closure
    boundary*: the crawl treats these as already-seen so link-following never
    re-expands into the reference tree."""
    keys: set[str] = set()
    for meta in metadata_files:
        if not Path(meta).exists():
            continue
        with jsonlines.open(meta) as reader:
            for entry in reader:
                key = canonical_key(entry.get("url", ""))
                if key:
                    keys.add(key)
    return keys


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


def build_seed(reference_sources: Iterable[Path], exclusion_keys: set[str]) -> list[str]:
    """Absolute page URLs referenced in the corpus but not already crawled.

    Deduplicated by :func:`canonical_key` and returned sorted for reproducibility.
    """
    seed: dict[str, str] = {}
    for source in reference_sources:
        if not Path(source).exists():
            continue
        text = Path(source).read_text(encoding="utf-8", errors="ignore")
        for url in iter_api_page_urls(text):
            key = canonical_key(url)
            if not key or key in exclusion_keys or key in seed:
                continue
            request_url = normalize_request_url(url)
            if request_url:
                seed[key] = request_url
    return [seed[k] for k in sorted(seed)]
