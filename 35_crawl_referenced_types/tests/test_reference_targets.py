"""Unit tests for the referenced-types seed logic (network-free)."""

import sys
from pathlib import Path

import jsonlines
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "35_crawl_referenced_types"))
sys.path.insert(0, str(REPO_ROOT))

from reference_targets import build_seed, build_shipped_assemblies, member_list_url  # noqa: E402
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
