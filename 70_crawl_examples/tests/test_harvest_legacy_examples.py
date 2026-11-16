"""
Tests for harvest_legacy_examples.py (orphan-example recovery).

These tests exercise the pure parsing/normalization logic against a synthetic
__NEXT_DATA__ fixture modeled on the 2017 IChainPatternFeatureData type page,
which links Modify_Chain_Pattern_Feature_Example_* (de-linked in newer versions). No
network access is required.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import harvest_legacy_examples as h

from shared.constants import SOLIDWORKS_API_FULL_BASE_URL, SOLIDWORKS_API_VERSION

API = SOLIDWORKS_API_FULL_BASE_URL


def _make_page(help_text: str) -> str:
    """Wrap helpText in a __NEXT_DATA__ document like the live SOLIDWORKS pages."""
    next_data = {"props": {"pageProps": {"helpContentData": {"helpText": help_text}}}}
    return (
        "<html><body>"
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(next_data)
        + "</script></body></html>"
    )


# helpText mirroring the 2017 IChainPatternFeatureData "Example" section: it links
# both the still-referenced "Create and Modify Distance..." example and the
# now-orphaned "Modify Chain Pattern Feature" example.
HELP_TEXT = (
    '<span id="pagetitle">IChainPatternFeatureData Interface</span>'
    "<div>Provides access to a chain pattern feature.</div>"
    "<h1>Example</h1>"
    '<a href="Modify_Chain_Pattern_Feature_Example_CSharp.htm">Modify Chain Pattern Feature Example (C#)</a>'
    '<a href="Modify_Chain_Pattern_Feature_Example_VB.htm">Modify Chain Pattern Feature Example (VBA)</a>'
    '<a href="Create_and_Modify_Distance_Chain_Pattern_Feature_Example_CSharp.htm">Create and Modify (C#)</a>'
    "<h1>See Also</h1>"
    '<a href="SomeOtherType_Example_CSharp.htm">A see-also link that must be ignored</a>'
)


def test_extract_help_text():
    page = _make_page("<span id='pagetitle'>X</span>")
    assert h.extract_help_text(page) == "<span id='pagetitle'>X</span>"


def test_extract_help_text_missing():
    assert h.extract_help_text("<html>no next data</html>") is None


def test_extract_example_hrefs_only_from_example_section():
    hrefs = h.extract_example_hrefs(HELP_TEXT)
    # Example-section links are captured...
    assert "Modify_Chain_Pattern_Feature_Example_CSharp.htm" in hrefs
    assert "Modify_Chain_Pattern_Feature_Example_VB.htm" in hrefs
    assert "Create_and_Modify_Distance_Chain_Pattern_Feature_Example_CSharp.htm" in hrefs
    # ...but the "See Also" link is NOT (section-aware extraction).
    assert "SomeOtherType_Example_CSharp.htm" not in hrefs


def test_to_version():
    url = f"{API}/sldworksapi/Foo.html"
    assert h.to_version(url, "2017") == "https://help.solidworks.com/2017/english/api/sldworksapi/Foo.html"


def test_subdir_of():
    url = f"{API}/sldworksapi/Foo.html"
    assert h.subdir_of(url) == "sldworksapi"


def test_normalize_example_url():
    assert (
        h.normalize_example_url("Modify_Chain_Pattern_Feature_Example_CSharp.htm", "sldworksapi", SOLIDWORKS_API_VERSION)
        == f"{API}/sldworksapi/Modify_Chain_Pattern_Feature_Example_CSharp.htm"
    )


@pytest.mark.parametrize(
    ("href", "url"),
    [
        # Scheme, year and language casing are canonicalized ...
        ("http://help.solidworks.com/2017/English/api/sldworksapi/X_Example_VB.htm", "sldworksapi/X_Example_VB.htm"),
        # ... and so is the folder's casing, as Phases 40/50 record it.
        ("/2017/English/api/SldWorksAPI/X_Example_VB.htm", "sldworksapi/X_Example_VB.htm"),
        # A relative link to another folder keeps that folder.
        ("../sldworksapi/X_Example_VB.htm", "sldworksapi/X_Example_VB.htm"),
        ("X_Example_VB.htm", "swconst/X_Example_VB.htm"),
        # A resolved CHM alias is an API-root path.
        ("/sldworksapi/X_Example_VB.htm", "sldworksapi/X_Example_VB.htm"),
    ],
)
def test_example_links_are_canonicalized(href, url):
    """The result has to match the URLs phases 40/50 found, or the same example is crawled twice."""
    assert h.normalize_example_url(href, "swconst", SOLIDWORKS_API_VERSION) == f"{API}/{url}"


@pytest.mark.parametrize(
    "href",
    [
        "https://www.3ds.com/x/Foo_Example.htm",
        "https://help.solidworks.com/2017/english/sldworks/Foo_Example.htm",
        "/2017/english/sldworks/Foo_Example.htm",
        "mailto:Foo_Example.htm",
    ],
)
def test_links_outside_the_api_tree_are_dropped(href):
    assert h.normalize_example_url(href, "swconst", SOLIDWORKS_API_VERSION) is None


def test_unknown_candidates_ignore_case():
    known = {f"{API}/sldworksapi/Known_Example_VB.htm"}
    candidates = {
        f"{API}/sldworksapi/known_example_vb.htm",
        f"{API}/sldworksapi/New_Example_VB.htm",
        f"{API}/sldworksapi/NEW_Example_VB.htm",
    }
    assert h.unknown_candidates(candidates, known) == [f"{API}/sldworksapi/NEW_Example_VB.htm"]


def test_chm_alias_example_resolves_to_its_own_folder():
    """An swconst page links an sldworksapi example through a CHM alias; it must not land in swconst/."""
    help_text = (
        '<span id="pagetitle">swMateType_e Enumeration</span>'
        "<h1>Example</h1>"
        '<a href="ms-its:sldworksapi.chm::/Add_Component_and_Mate_Example_VB.htm">Add Component and Mate (VBA)</a>'
    )
    recovered = {
        h.normalize_example_url(url, "swconst", SOLIDWORKS_API_VERSION) for url in h.extract_example_hrefs(help_text)
    }
    assert recovered == {f"{API}/sldworksapi/Add_Component_and_Mate_Example_VB.htm"}


def test_iter_type_page_urls_filters(tmp_path):
    jsonl = tmp_path / "toc.jsonl"
    lines = [
        # Type page (kept)
        {"url": f"{API}/sldworksapi/A.Interop~A.Interop.IFoo.html?id=1"},
        # Members page (dropped)
        {"url": f"{API}/sldworksapi/A.Interop~A.Interop.IFoo_members.html?id=1.0"},
        # Example page (dropped: no '~')
        {"url": f"{API}/sldworksapi/Foo_Example_CSharp.htm"},
        # FunctionalCategories (dropped)
        {"url": f"{API}/sldworksapi/FunctionalCategories~x.html"},
    ]
    jsonl.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")

    urls = h.iter_type_page_urls(jsonl)
    assert urls == [f"{API}/sldworksapi/A.Interop~A.Interop.IFoo.html"]


def test_end_to_end_parse_pipeline():
    """helpText -> example hrefs -> normalized current-version URLs (the recovery core)."""
    type_url = f"{API}/sldworksapi/X~X.IChainPatternFeatureData.html"
    page = _make_page(HELP_TEXT)

    help_text = h.extract_help_text(page)
    subdir = h.subdir_of(type_url)
    recovered = {
        h.normalize_example_url(url, subdir, SOLIDWORKS_API_VERSION) for url in h.extract_example_hrefs(help_text)
    }

    assert (
        f"{API}/sldworksapi/Modify_Chain_Pattern_Feature_Example_CSharp.htm"
        in recovered
    )
