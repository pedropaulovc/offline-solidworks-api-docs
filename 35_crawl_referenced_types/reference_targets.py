"""Seed computation for the referenced-types crawl.

Phase 10 discovers the API surface through ``expandToc``. That misses whole
categories of page, because the source TOC is defective: for several namespaces
the "Enumerations" node returns the *Interfaces* list verbatim (verified against
``expandToc`` for ids 2.3/2.4/2.6/2.7 -- only swconst (2.10) and swcommands (2.11)
serve real enum children). Pages behind those nodes exist and are linked from the
docs, but nothing in the TOC-driven pipeline ever reaches them.

This module computes what to crawl instead: the generated reference pages
(``Assembly~Namespace.Type[~Member]``) that the crawled corpus links to but that
phases 10/30 never fetched. It is the mirror image of phase 115's seed -- same
scan, opposite side of :func:`~shared.api_urls.is_reference_page`.

The seed is bounded to assemblies the pipeline already ships. The docs also link
into reference trees this project does not crawl at all (Routing, FeatureWorks,
PDM, …, each its own ``expandToc`` root); pulling those in piecemeal would ship a
fragment of an API rather than fix a gap, so they are excluded and reported.
"""

import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.api_urls import (  # noqa: E402
    ReferenceSource,
    canonical_key,
    is_reference_page,
    iter_page_links,
    normalize_request_url,
    page_assembly,
)


def build_shipped_assemblies(metadata_files: Iterable[Path]) -> set[str]:
    """Assembly folders (``sldworksapi``, ``swconst``, …) the pipeline already
    crawls, derived from the given ``urls_crawled.jsonl`` manifests.

    Derived rather than hardcoded: the pipeline is assembly-generic, so adding a
    reference tree to phase 10's ``TOC_ROOT_IDS`` must extend this crawl's reach
    automatically, with no list to keep in sync.
    """
    import jsonlines

    assemblies: set[str] = set()
    for meta in metadata_files:
        if not Path(meta).exists():
            continue
        with jsonlines.open(meta) as reader:
            for entry in reader:
                assembly = page_assembly(entry.get("url", ""))
                if assembly:
                    assemblies.add(assembly)
    return assemblies


def build_seed(
    reference_sources: Iterable[ReferenceSource],
    crawled_keys: set[str],
    shipped_assemblies: set[str],
) -> tuple[list[str], dict[str, int]]:
    """Reference pages linked by the corpus but not yet crawled.

    Returns ``(seed, out_of_scope)`` where ``out_of_scope`` counts, per assembly,
    the reference pages skipped because their tree is not crawled at all -- the
    caller logs it, so a growing external surface is visible rather than silent.

    Deduplicated by :func:`canonical_key` and sorted for reproducibility.
    """
    seed: dict[str, str] = {}
    out_of_scope: dict[str, int] = {}

    for source in reference_sources:
        if not source.path.exists():
            continue
        text = source.path.read_text(encoding="utf-8", errors="ignore")
        for url in iter_page_links(text, base=source.base_url):
            if not is_reference_page(url):
                continue
            key = canonical_key(url)
            if not key or key in crawled_keys or key in seed:
                continue

            assembly = page_assembly(url)
            if assembly not in shipped_assemblies:
                out_of_scope[assembly or "?"] = out_of_scope.get(assembly or "?", 0) + 1
                continue

            request_url = normalize_request_url(url)
            if request_url:
                seed[key] = request_url

    return [seed[k] for k in sorted(seed)], out_of_scope


def member_list_url(type_page_url: str) -> str | None:
    """The ``_members`` companion of a reference *type* page.

    Phase 20 builds its type list from ``*_members*`` pages, so a newly discovered
    type only enters the pipeline if its member list is crawled alongside it.
    Returns ``None`` for pages that have no such companion: member pages
    (already the leaf) and enums (no member list).
    """
    key = canonical_key(type_page_url)
    if not key:
        return None

    basename = key.rsplit("/", 1)[-1]
    stem = basename.rsplit(".", 1)[0]
    if stem.count("~") != 1:  # a member page (two ~) has no member list of its own
        return None
    if stem.endswith("_e") or stem.endswith("_members"):
        return None

    head, _, extension = type_page_url.rpartition(".")
    return f"{head}_members.{extension}" if head else None


def crawl_failure(stats: dict, crawled: int) -> str | None:
    """Describe why the crawl should be treated as failed, or None if it is fine.

    The spider only *records* failures -- ``process.start()`` returns normally
    however many requests died. Without this the phase exits 0 after a total
    network outage and the extraction phases publish a partial reference set as
    though it were complete.
    """
    # scrapy writes valid stats however the spider closed, so a graceful
    # interruption ("shutdown") otherwise looks like a clean partial crawl.
    reason = stats.get("reason")
    if reason != "finished":
        return f"the crawl closed as {reason!r}, not 'finished'"
    failed = stats.get("failed_pages", 0)
    if failed:
        return f"{failed} page(s) failed to crawl; see metadata/errors.jsonl"
    unscheduled = stats.get("unscheduled_pages", 0)
    if unscheduled:
        # MAX_PAGES tripped. Plenty of pages were still saved, so `crawled` alone
        # looks healthy -- but the reference set is knowingly truncated and the
        # exports must not treat it as complete.
        return f"page cap reached; {unscheduled} page(s) were never scheduled"
    if stats.get("seed_pages") and not crawled and not stats.get("skipped_pages"):
        # Reached nothing at all. A run whose seeds were *all* soft-404s is not a
        # failure -- that is the shape the second pass legitimately produces.
        return f"{stats['seed_pages']} seed page(s) produced no crawled page"
    return None
