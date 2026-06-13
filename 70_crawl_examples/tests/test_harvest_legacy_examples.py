"""
Tests for harvest_legacy_examples.py (orphan-example recovery).

These tests exercise the pure parsing/normalization logic against a synthetic
__NEXT_DATA__ fixture modeled on the 2017 IChainPatternFeatureData type page,
which links Modify_Chain_Pattern_Feature_Example_* (de-linked in 2026). No
network access is required.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import harvest_legacy_examples as h


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
    url = "https://help.solidworks.com/2026/english/api/sldworksapi/Foo.html"
    assert h.to_version(url, "2017") == "https://help.solidworks.com/2017/english/api/sldworksapi/Foo.html"


def test_subdir_of():
    url = "https://help.solidworks.com/2026/english/api/sldworksapi/Foo.html"
    assert h.subdir_of(url) == "sldworksapi"


def test_normalize_example_url():
    assert (
        h.normalize_example_url("Modify_Chain_Pattern_Feature_Example_CSharp.htm", "sldworksapi", "2026")
        == "https://help.solidworks.com/2026/english/api/sldworksapi/Modify_Chain_Pattern_Feature_Example_CSharp.htm"
    )


def test_iter_type_page_urls_filters(tmp_path):
    jsonl = tmp_path / "toc.jsonl"
    lines = [
        # Type page (kept)
        {"url": "https://help.solidworks.com/2026/english/api/sldworksapi/A.Interop~A.Interop.IFoo.html?id=1"},
        # Members page (dropped)
        {"url": "https://help.solidworks.com/2026/english/api/sldworksapi/A.Interop~A.Interop.IFoo_members.html?id=1.0"},
        # Example page (dropped: no '~')
        {"url": "https://help.solidworks.com/2026/english/api/sldworksapi/Foo_Example_CSharp.htm"},
        # FunctionalCategories (dropped)
        {"url": "https://help.solidworks.com/2026/english/api/sldworksapi/FunctionalCategories~x.html"},
    ]
    jsonl.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")

    urls = h.iter_type_page_urls(jsonl)
    assert urls == ["https://help.solidworks.com/2026/english/api/sldworksapi/A.Interop~A.Interop.IFoo.html"]


def test_end_to_end_parse_pipeline():
    """helpText -> example hrefs -> normalized 2026 URLs (the recovery core)."""
    type_url = "https://help.solidworks.com/2026/english/api/sldworksapi/X~X.IChainPatternFeatureData.html"
    page = _make_page(HELP_TEXT)

    help_text = h.extract_help_text(page)
    subdir = h.subdir_of(type_url)
    recovered = {h.normalize_example_url(fn, subdir, "2026") for fn in h.extract_example_hrefs(help_text)}

    assert (
        "https://help.solidworks.com/2026/english/api/sldworksapi/Modify_Chain_Pattern_Feature_Example_CSharp.htm"
        in recovered
    )
