"""Unit tests for the referenced-pages seed/boundary logic (network-free)."""

import sys
from pathlib import Path

import jsonlines

sys.path.insert(0, str(Path(__file__).parent.parent))

from link_targets import (
    ReferenceSource,
    build_bundle_doc_keys,
    build_exclusion_keys,
    build_seed,
    canonical_key,
    crawled_html_sources,
    is_reference_page,
    iter_page_links,
    normalize_request_url,
)

BASE = "https://help.solidworks.com/2026/english/api"


def test_canonical_key_case_and_slash_insensitive():
    # Case and double slashes collapse to one identity.
    a = canonical_key(f"{BASE}/sldworksapiprogguide/OVERVIEW/In-process_Methods.htm")
    b = canonical_key(f"{BASE}/sldworksapiprogguide//Overview/In-process_Methods.htm")
    assert a == b == "2026/english/api/sldworksapiprogguide/overview/in-process_methods.htm"


def test_canonical_key_decodes_percent_escapes():
    """A link may encode a space the manifest stores literally; both are one page.
    Without decoding, the encoded form slips past the crawled-set boundary."""
    encoded = canonical_key(f"{BASE}/sldworksapi/Multiselect_Same%20and_Different_Objects_Example_VB.htm")
    literal = canonical_key(f"{BASE}/sldworksapi/Multiselect_Same and_Different_Objects_Example_VB.htm")
    assert encoded == literal is not None


def test_canonical_key_rejects_non_pages():
    assert canonical_key(f"{BASE}/swconst/DP.gif") is None          # not .htm/.html
    assert canonical_key("https://example.com/2026/english/api/x.htm") is None  # wrong host tree
    assert canonical_key("") is None


def test_normalize_request_url_preserves_case_resolves_relative():
    # Relative link resolves against the page and keeps original casing.
    page = f"{BASE}/swconst/DP_Dimensions.htm"
    assert normalize_request_url("../swconst/SO_Colors.htm", base=page) == \
        f"{BASE}/swconst/SO_Colors.htm"
    # Double slash in an absolute URL is cleaned.
    assert normalize_request_url(f"{BASE}//swconst/SO_Colors.htm") == \
        f"{BASE}/swconst/SO_Colors.htm"
    # Non-page returns None.
    assert normalize_request_url("../swconst/icon.png", base=page) is None


def test_iter_page_links_absolute_only_without_base():
    text = f'see <see href="{BASE}/swconst/SO_Colors.htm">Colors</see> and http://other/x.htm'
    assert list(iter_page_links(text)) == [
        f"{BASE}/swconst/SO_Colors.htm",  # absolute literal
        f"{BASE}/swconst/SO_Colors.htm",  # same page, via the href attribute
    ]
    # A relative href is unresolvable with no base, so it is skipped rather than guessed.
    assert list(iter_page_links('<a href="Sibling_Page.htm">x</a>')) == []


def test_iter_page_links_resolves_relative_hrefs_against_base():
    """The regression: help-text HTML links siblings relatively, and those pages
    were invisible to a scan that only matched absolute URLs."""
    page = f"{BASE}/swdimxpertapi/Get_DimXpert_Features_Example_CSharp.htm"
    html = (
        '<p>Copy and paste the <a href="DimXpert_Main_Module_CSharp.htm">Main module</a> '
        'and the <a href="../swconst/DP_Dimensions.htm">settings</a>, '
        'not the <img src="diagram.png"> image.</p>'
    )
    assert sorted(iter_page_links(html, base=page)) == [
        f"{BASE}/swconst/DP_Dimensions.htm",
        f"{BASE}/swdimxpertapi/DimXpert_Main_Module_CSharp.htm",
    ]


def test_exclusion_and_seed(tmp_path):
    # A crawled-URLs manifest marks one page as already covered.
    meta = tmp_path / "urls_crawled.jsonl"
    with jsonlines.open(meta, mode="w") as w:
        w.write({"url": f"{BASE}/swconst/SO_Colors.htm"})
    excl = build_exclusion_keys([meta])
    assert canonical_key(f"{BASE}/swconst/SO_Colors.htm") in excl

    # A source references two pages; only the not-yet-crawled one is seeded.
    source = tmp_path / "refs.xml"
    source.write_text(
        f'<see href="{BASE}/swconst/SO_Colors.htm"/> '        # excluded
        f'<see href="{BASE}/swconst/DP_Dimensions.htm"/>',     # new
        encoding="utf-8",
    )
    seed = build_seed([ReferenceSource(source)], excl)
    assert seed == [f"{BASE}/swconst/DP_Dimensions.htm"]


def test_seed_excludes_bundle_docs_not_merely_crawled(tmp_path):
    """A page crawled elsewhere but not exported as a doc is still seeded."""
    # files_created manifest keyed by original_url (path form, as Phase 110 stores it).
    manifest = tmp_path / "files_created.jsonl"
    with jsonlines.open(manifest, mode="w") as w:
        w.write({"original_url": "/2026/english/api/sldworksapiprogguide/Bitmasks.htm"})
    bundle = build_bundle_doc_keys([manifest])
    assert canonical_key(f"{BASE}/sldworksapiprogguide/Bitmasks.htm") in bundle

    source = tmp_path / "refs.xml"
    source.write_text(
        f'<see href="{BASE}/sldworksapiprogguide/Bitmasks.htm"/> '        # in bundle -> skip
        f'<see href="{BASE}/sldworksapi/FunctionalCategories-sldworksapi.html"/>',  # crawled, not a doc -> seed
        encoding="utf-8",
    )
    seed = build_seed([ReferenceSource(source)], bundle)
    assert seed == [f"{BASE}/sldworksapi/FunctionalCategories-sldworksapi.html"]


def test_crawled_html_sources_pairs_each_page_with_its_url(tmp_path):
    """Crawl manifests store Windows-separator paths; each surviving file becomes a
    source based at its own URL. Missing files (output/ is gitignored) are dropped."""
    phase = tmp_path / "70_crawl_examples"
    (phase / "output/html/swdimxpertapi").mkdir(parents=True)
    (phase / "output/html/swdimxpertapi/Example.htm").write_text("<p>x</p>", encoding="utf-8")

    meta = phase / "metadata/urls_crawled.jsonl"
    meta.parent.mkdir(parents=True)
    with jsonlines.open(meta, mode="w") as w:
        w.write({"url": f"{BASE}/swdimxpertapi/Example.htm",
                 "file_path": "output\\html\\swdimxpertapi\\Example.htm"})
        w.write({"url": f"{BASE}/swdimxpertapi/Gone.htm",
                 "file_path": "output\\html\\swdimxpertapi\\Gone.htm"})

    sources = crawled_html_sources(phase, meta)
    assert [(s.path.name, s.base_url) for s in sources] == [
        ("Example.htm", f"{BASE}/swdimxpertapi/Example.htm")
    ]
    assert crawled_html_sources(phase, phase / "metadata/absent.jsonl") == []


def test_seed_from_crawled_html_finds_relative_siblings(tmp_path):
    """End-to-end for the bug class: a crawled example page linking a sibling code
    page relatively seeds that page."""
    page_url = f"{BASE}/swdimxpertapi/Get_DimXpert_Features_Example_CSharp.htm"
    source = tmp_path / "Example.htm"
    source.write_text('<a href="DimXpert_Main_Module_CSharp.htm">Main module</a>', encoding="utf-8")

    seed = build_seed([ReferenceSource(source, base_url=page_url)], set())
    assert seed == [f"{BASE}/swdimxpertapi/DimXpert_Main_Module_CSharp.htm"]


def test_seed_drops_generated_reference_pages(tmp_path):
    """Raw help-text HTML links thousands of ``~`` reference pages -- phase 20/30's
    territory. They must never become seeds."""
    page_url = f"{BASE}/sldworksapi/Some_Page.htm"
    source = tmp_path / "page.htm"
    source.write_text(
        '<a href="SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IView.html">IView</a>'
        '<a href="Real_Guide_Page.htm">guide</a>',
        encoding="utf-8",
    )

    seed = build_seed([ReferenceSource(source, base_url=page_url)], set())
    assert seed == [f"{BASE}/sldworksapi/Real_Guide_Page.htm"]


def test_is_reference_page_guard():
    # Reference type/member pages (~ in the filename) are guarded out of the closure...
    assert is_reference_page(
        f"{BASE}/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IView.html"
    )
    # ...including URL-encoded-space variants that dodge exact key matching.
    assert is_reference_page(
        f"{BASE}/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IDistance%20MateFeatureData.html"
    )
    # Plain guide/settings pages are not reference pages.
    assert not is_reference_page(f"{BASE}/swconst/DP_Dimensions.htm")
    assert not is_reference_page(f"{BASE}/sldworksapi/FunctionalCategories-sldworksapi.html")


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))
