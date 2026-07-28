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


def test_seed_includes_relatively_linked_sibling_pages(spider):
    """Regression: multi-module examples link their code pages with a bare relative
    href, which an absolute-URL-only scan never saw."""
    expected = [
        "https://help.solidworks.com/2026/english/api/swdimxpertapi/DimXpert_Main_Module_CSharp.htm",
        "https://help.solidworks.com/2026/english/api/swdimxpertapi/DimXpert_FeatureData_Module_CSharp.htm",
        "https://help.solidworks.com/2026/english/api/swdimxpertapi/DimXpert_AnnotationData_Module_CSharp.htm",
    ]
    seed_keys = {canonical_key(u) for u in spider.seed}
    bundled = spider.bundle_keys
    for url in expected:
        key = canonical_key(url)
        # Seeded on a fresh run; already in the bundle once this phase has run.
        assert key in seed_keys or key in bundled, f"{url} neither seeded nor bundled"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
