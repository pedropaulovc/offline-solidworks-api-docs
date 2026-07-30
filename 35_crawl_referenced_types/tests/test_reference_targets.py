"""Unit tests for the referenced-types seed logic (network-free)."""

import sys
from pathlib import Path

import jsonlines
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "35_crawl_referenced_types"))
sys.path.insert(0, str(REPO_ROOT))

from reference_targets import (  # noqa: E402
    build_seed,
    build_shipped_assemblies,
    crawl_failure,
    member_list_url,
)
from shared.api_urls import ReferenceSource, canonical_key  # noqa: E402

BASE = "https://help.solidworks.com/2026/english/api"
SLD = "SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks"
DIM = "SolidWorks.Interop.swdimxpert~SolidWorks.Interop.swdimxpert"


def _source(tmp_path: Path, body: str, page: str) -> ReferenceSource:
    path = tmp_path / "page.html"
    path.write_text(body, encoding="utf-8")
    return ReferenceSource(path, base_url=page)


def test_seed_keeps_reference_pages_and_drops_doc_pages(tmp_path):
    """The mirror image of phase 115: this crawl wants exactly what that one skips."""
    page = f"{BASE}/swdimxpertapi/IDimXpertPart.html"
    body = (
        f'<a href="{DIM}.swDimXpertGtolType_e.html">enum</a>'      # reference page -> seed
        f'<a href="Get_DimXpert_Example_CSharp.htm">example</a>'   # doc page -> not ours
    )
    seed, out_of_scope = build_seed([_source(tmp_path, body, page)], set(), {"swdimxpertapi"})

    assert seed == [f"{BASE}/swdimxpertapi/{DIM}.swDimXpertGtolType_e.html"]
    assert out_of_scope == {}


def test_seed_excludes_already_crawled(tmp_path):
    page = f"{BASE}/swdimxpertapi/IDimXpertPart.html"
    body = f'<a href="{DIM}.swDimXpertGtolType_e.html">enum</a>'
    # The manifest spells it however the crawl saw it; identity is the canonical key.
    crawled = {canonical_key(f"{BASE}/swdimxpertapi/{DIM}.swDimXpertGtolType_e.html")}

    seed, _ = build_seed([_source(tmp_path, body, page)], crawled, {"swdimxpertapi"})
    assert seed == []


def test_seed_reports_pages_in_trees_the_project_does_not_crawl(tmp_path):
    """Routing/PDM/FeatureWorks are separate expandToc roots. Pulling a page out of
    one would ship a fragment of an API, so they are skipped -- but counted, so the
    external surface stays visible."""
    page = f"{BASE}/sldworksapi/ISomething.html"
    body = (
        f'<a href="../routingapi/SolidWorks.Interop.swrouting~SolidWorks.Interop.swrouting.IRoute.html">r</a>'
        f'<a href="{SLD}.IFace.html">in-scope</a>'
    )
    seed, out_of_scope = build_seed([_source(tmp_path, body, page)], set(), {"sldworksapi"})

    assert seed == [f"{BASE}/sldworksapi/{SLD}.IFace.html"]
    assert out_of_scope == {"routingapi": 1}


def test_shipped_assemblies_derived_from_crawl_manifests(tmp_path):
    """Derived, not hardcoded: adding a TOC root to phase 10 must widen this crawl
    with no list to keep in sync."""
    meta = tmp_path / "urls_crawled.jsonl"
    with jsonlines.open(meta, mode="w") as w:
        w.write({"url": f"{BASE}/sldworksapi/{SLD}.IFace.html"})
        w.write({"url": f"{BASE}/toolboxapi/Whatever.html"})
        w.write({"url": f"{BASE}/help_list.htm"})  # no assembly folder

    assert build_shipped_assemblies([meta]) == {"sldworksapi", "toolboxapi"}


@pytest.mark.parametrize(
    "url, expected",
    [
        # A type page gets its member list -- phase 20 builds the type list from those.
        (f"{BASE}/sldworksapi/{SLD}.IFace.html", f"{BASE}/sldworksapi/{SLD}.IFace_members.html"),
        # Enums have no member list.
        (f"{BASE}/swdimxpertapi/{DIM}.swDimXpertGtolType_e.html", None),
        # A member page is already a leaf (two tildes).
        (f"{BASE}/sldworksapi/{SLD}.IFace~DoThing.html", None),
        # Don't ask for the member list of a member list.
        (f"{BASE}/sldworksapi/{SLD}.IFace_members.html", None),
    ],
)
def test_member_list_url(url, expected):
    assert member_list_url(url) == expected


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


class TestCrawlFailure:
    """The phase must not report success when the crawl did not actually happen."""

    def test_recorded_failures_fail_the_phase(self):
        assert crawl_failure({"reason": "finished", "failed_pages": 3, "seed_pages": 10}, crawled=7) is not None

    def test_a_clean_crawl_passes(self):
        assert crawl_failure({"reason": "finished", "failed_pages": 0, "seed_pages": 10}, crawled=10) is None

    def test_a_total_outage_fails_even_with_no_recorded_errors(self):
        """errback may never fire (e.g. DNS dead before any request); zero pages
        against a non-empty seed is still a failed phase."""
        assert crawl_failure({"reason": "finished", "failed_pages": 0, "seed_pages": 887}, crawled=0) is not None

    def test_nothing_to_do_is_not_a_failure(self):
        """A --resume run with everything already crawled seeds nothing."""
        assert crawl_failure({"reason": "finished", "failed_pages": 0, "seed_pages": 0}, crawled=0) is None

    def test_empty_stats_are_not_trusted(self):
        """A spider that died before closed() leaves nothing behind; that is a
        failed crawl, not an unremarkable one."""
        assert crawl_failure({}, crawled=0) is not None


class TestTruncationIsFailure:
    def test_hitting_the_page_cap_fails_even_with_many_pages_saved(self):
        stats = {"reason": "finished", "failed_pages": 0, "seed_pages": 30000, "unscheduled_pages": 12}
        assert crawl_failure(stats, crawled=20000) is not None

    def test_no_truncation_passes(self):
        stats = {"reason": "finished", "failed_pages": 0, "seed_pages": 748, "unscheduled_pages": 0}
        assert crawl_failure(stats, crawled=748) is None

    def test_a_seed_set_that_is_entirely_soft_404s_is_not_a_failure(self):
        """The pass-2 seed on the 2026 corpus is exactly this: 4 pages the docs
        link to that the site serves 200-with-empty-helpText."""
        stats = {"reason": "finished", "failed_pages": 0, "seed_pages": 4, "skipped_pages": 4, "unscheduled_pages": 0}
        assert crawl_failure(stats, crawled=0) is None

    def test_reaching_nothing_at_all_is_still_a_failure(self):
        stats = {"reason": "finished", "failed_pages": 0, "seed_pages": 4, "skipped_pages": 0, "unscheduled_pages": 0}
        assert crawl_failure(stats, crawled=0) is not None


class TestClosureReason:
    """scrapy writes a valid stats file however the spider closed, so the reason
    is the only thing separating a completed crawl from an interrupted one."""

    def test_a_graceful_interruption_is_a_failure(self):
        stats = {"reason": "shutdown", "failed_pages": 0, "seed_pages": 887}
        assert crawl_failure(stats, crawled=400) is not None

    def test_a_cancelled_crawl_is_a_failure(self):
        stats = {"reason": "cancelled", "failed_pages": 0, "seed_pages": 887}
        assert crawl_failure(stats, crawled=880) is not None

    def test_stats_with_no_reason_at_all_are_not_trusted(self):
        assert crawl_failure({"failed_pages": 0, "seed_pages": 10}, crawled=10) is not None

    def test_only_finished_passes(self):
        stats = {"reason": "finished", "failed_pages": 0, "seed_pages": 887, "unscheduled_pages": 0}
        assert crawl_failure(stats, crawled=748) is None
