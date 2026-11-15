"""Seed sanity against the real corpus (network-free, but needs crawled output).

Skipped when the gitignored crawl output is absent -- these assert on what the
actual corpus links to, which unit tests with synthetic fixtures cannot cover.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE_DIR = REPO_ROOT / "115_crawl_referenced_pages"
sys.path.insert(0, str(PHASE_DIR))
sys.path.insert(0, str(REPO_ROOT))

from link_targets import build_saved_page_keys, canonical_key  # noqa: E402

from shared.constants import SOLIDWORKS_API_FULL_BASE_URL, SOLIDWORKS_API_VERSION  # noqa: E402

EXAMPLES_META = REPO_ROOT / "70_crawl_examples/metadata/urls_crawled.jsonl"
EXAMPLES_HTML = REPO_ROOT / "70_crawl_examples/output/html"
# Written by the Phase 70 HtmlSavePipeline next to the gitignored corpus.
EXAMPLES_CRAWL_VERSION = REPO_ROOT / "70_crawl_examples/output/crawl_version.txt"


def _corpus_is_current_version() -> bool:
    """True when the local Phase 70 corpus was crawled for SOLIDWORKS_API_VERSION.

    After a doc-year bump the local corpus still holds the previous year's pages
    until phases 70-120 are re-run, while the committed metadata already names the
    new year; the assertions below then have nothing honest to check. Saved pages
    carry no year, so read the marker the crawl writes beside them."""
    if not EXAMPLES_CRAWL_VERSION.exists():
        return False
    return EXAMPLES_CRAWL_VERSION.read_text(encoding="utf-8").strip() == SOLIDWORKS_API_VERSION


# Gate on the local crawl output, not the metadata: the metadata is committed, so
# gating on it never skips, and these assertions then run against a corpus whose
# pages do not exist -- reporting a failure where the honest answer is "not
# available here". Same for a corpus crawled for a different doc version.
pytestmark = [
    pytest.mark.skipif(
        not EXAMPLES_HTML.is_dir() or not any(EXAMPLES_HTML.rglob("*.htm*")),
        reason="crawled HTML not present (output/ is gitignored); run phases 10-110 first",
    ),
    pytest.mark.skipif(
        not _corpus_is_current_version(),
        reason=f"Phase 70 corpus not crawled for {SOLIDWORKS_API_VERSION} (no matching output/crawl_version.txt); re-run phases 70-120",
    ),
]


@pytest.fixture(scope="module")
def spider():
    # The root conftest keeps ``solidworks_scraper`` (a package name five crawl
    # phases share) pointing at this phase's copy while this phase's tests run.
    from solidworks_scraper.spiders.referenced_spider import ReferencedSpider

    return ReferencedSpider()


def test_seed_excludes_pages_the_bundle_already_ships(spider):
    """Scanning raw help-text HTML surfaces every example page the docs link to.
    Those already ship as ``examples/*.md`` (Phase 70 -> 80 -> 120), so seeding them
    would re-crawl ~2800 pages and duplicate them under ``docs/``."""
    example_keys = build_saved_page_keys(REPO_ROOT / "70_crawl_examples", EXAMPLES_META)
    assert example_keys, "expected saved Phase 70 HTML"

    duplicated = [u for u in spider.seed if canonical_key(u) in example_keys]
    assert not duplicated, f"{len(duplicated)} already-bundled example pages seeded, e.g. {duplicated[:3]}"


def test_closure_boundary_covers_example_pages(spider):
    """The closure follows in-page links, and a module page links back to the example
    that referenced it. Without Phase 70 in the boundary, that pulls the example tree
    into this phase and duplicates it under ``docs/``.

    Keyed on examples whose HTML survives -- the same condition the boundary uses.
    A recorded-but-missing page is deliberately *outside* the boundary so it stays
    crawlable, since Phase 80 cannot export it."""
    shipping = build_saved_page_keys(REPO_ROOT / "70_crawl_examples", EXAMPLES_META)
    assert shipping, "expected saved Phase 70 HTML"

    leaked = [k for k in shipping if k not in spider.seen]
    assert not leaked, f"{len(leaked)} example pages outside the closure boundary, e.g. {leaked[:3]}"


def test_seed_excludes_generated_reference_pages(spider):
    """The ``~`` reference tree is phase 20/30's territory; the corpus links
    thousands of them and the closure must not expand into it."""
    leaked = [u for u in spider.seed if "~" in u]
    assert not leaked, f"{len(leaked)} reference pages seeded, e.g. {leaked[:3]}"


EXAMPLE_PAGE = (
    REPO_ROOT / "70_crawl_examples/output/html/swdimxpertapi"
    / "Get_DimXpert_Features_and_Annotations_in_a_Model_Example_CSharp.htm"
)
EXAMPLE_URL = (
    f"{SOLIDWORKS_API_FULL_BASE_URL}/swdimxpertapi/"
    "Get_DimXpert_Features_and_Annotations_in_a_Model_Example_CSharp.htm"
)


@pytest.mark.skipif(not EXAMPLE_PAGE.exists(), reason="Phase 70 crawl output not present")
def test_relative_links_are_discovered_from_the_real_corpus():
    """Regression: multi-module examples link their code pages with a bare relative
    href, which an absolute-URL-only scan never saw.

    Asserts on :func:`build_seed` over the real page with an *empty* exclusion set,
    so it fails if the raw-HTML relative-link scan breaks. Going through
    ``spider.seed`` instead would not: once this phase has run, the three pages are
    in the checked-in bundle manifest and drop out of the seed legitimately, which
    makes a bundle-aware assertion pass no matter what the scan does.
    """
    from link_targets import ReferenceSource, build_seed

    seed = build_seed([ReferenceSource(EXAMPLE_PAGE, base_url=EXAMPLE_URL)], set())

    base = f"{SOLIDWORKS_API_FULL_BASE_URL}/swdimxpertapi/"
    for module in ("Main", "FeatureData", "AnnotationData"):
        assert f"{base}DimXpert_{module}_Module_CSharp.htm" in seed


@pytest.mark.skipif(not EXAMPLE_PAGE.exists(), reason="Phase 70 crawl output not present")
def test_relatively_linked_pages_reach_the_bundle(spider):
    """The same three pages, from the pipeline's side: seeded on a fresh run, and
    already shipping once this phase has run. Complements the discovery test above,
    which is what actually guards the scan."""
    seed_keys = {canonical_key(u) for u in spider.seed}
    base = f"{SOLIDWORKS_API_FULL_BASE_URL}/swdimxpertapi/"
    for module in ("Main", "FeatureData", "AnnotationData"):
        key = canonical_key(f"{base}DimXpert_{module}_Module_CSharp.htm")
        assert key in seed_keys or key in spider.bundle_keys, f"{module} neither seeded nor bundled"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
