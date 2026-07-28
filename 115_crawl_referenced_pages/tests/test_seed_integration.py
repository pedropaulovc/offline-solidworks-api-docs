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

from link_targets import build_exclusion_keys, canonical_key  # noqa: E402

EXAMPLES_META = REPO_ROOT / "70_crawl_examples/metadata/urls_crawled.jsonl"

pytestmark = pytest.mark.skipif(
    not EXAMPLES_META.exists(),
    reason="crawl output not present (gitignored); run phases 10-110 first",
)


@pytest.fixture(scope="module")
def spider():
    # Load by path: ``solidworks_scraper`` is a package name five crawl phases
    # share, so a plain import resolves to whichever phase pytest imported first.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "phase115_referenced_spider",
        PHASE_DIR / "solidworks_scraper/spiders/referenced_spider.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ReferencedSpider()


def test_seed_excludes_pages_the_bundle_already_ships(spider):
    """Scanning raw help-text HTML surfaces every example page the docs link to.
    Those already ship as ``examples/*.md`` (Phase 70 -> 80 -> 120), so seeding them
    would re-crawl ~2800 pages and duplicate them under ``docs/``."""
    example_keys = build_exclusion_keys([EXAMPLES_META])
    assert example_keys, "expected a populated Phase 70 crawl manifest"

    duplicated = [u for u in spider.seed if canonical_key(u) in example_keys]
    assert not duplicated, f"{len(duplicated)} already-bundled example pages seeded, e.g. {duplicated[:3]}"


def test_closure_boundary_covers_example_pages(spider):
    """The closure follows in-page links, and a module page links back to the example
    that referenced it. Without Phase 70 in the boundary, that pulls the example tree
    into this phase and duplicates it under ``docs/``."""
    example_keys = build_exclusion_keys([EXAMPLES_META])
    leaked = [k for k in example_keys if k not in spider.seen]
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
    "https://help.solidworks.com/2026/english/api/swdimxpertapi/"
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

    base = "https://help.solidworks.com/2026/english/api/swdimxpertapi/"
    for module in ("Main", "FeatureData", "AnnotationData"):
        assert f"{base}DimXpert_{module}_Module_CSharp.htm" in seed


@pytest.mark.skipif(not EXAMPLE_PAGE.exists(), reason="Phase 70 crawl output not present")
def test_relatively_linked_pages_reach_the_bundle(spider):
    """The same three pages, from the pipeline's side: seeded on a fresh run, and
    already shipping once this phase has run. Complements the discovery test above,
    which is what actually guards the scan."""
    seed_keys = {canonical_key(u) for u in spider.seed}
    base = "https://help.solidworks.com/2026/english/api/swdimxpertapi/"
    for module in ("Main", "FeatureData", "AnnotationData"):
        key = canonical_key(f"{base}DimXpert_{module}_Module_CSharp.htm")
        assert key in seed_keys or key in spider.bundle_keys, f"{module} neither seeded nor bundled"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
