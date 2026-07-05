"""Unit tests for the referenced-pages seed/boundary logic (network-free)."""

import sys
from pathlib import Path

import jsonlines

sys.path.insert(0, str(Path(__file__).parent.parent))

from link_targets import (
    build_bundle_doc_keys,
    build_exclusion_keys,
    build_seed,
    canonical_key,
    is_reference_page,
    iter_api_page_urls,
    normalize_request_url,
)

BASE = "https://help.solidworks.com/2026/english/api"


def test_canonical_key_case_and_slash_insensitive():
    # Case and double slashes collapse to one identity.
    a = canonical_key(f"{BASE}/sldworksapiprogguide/OVERVIEW/In-process_Methods.htm")
    b = canonical_key(f"{BASE}/sldworksapiprogguide//Overview/In-process_Methods.htm")
    assert a == b == "2026/english/api/sldworksapiprogguide/overview/in-process_methods.htm"


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


def test_iter_api_page_urls():
    text = f'see <see href="{BASE}/swconst/SO_Colors.htm">Colors</see> and http://other/x.htm'
    urls = list(iter_api_page_urls(text))
    assert urls == [f"{BASE}/swconst/SO_Colors.htm"]


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
    seed = build_seed([source], excl)
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
    seed = build_seed([source], bundle)
    assert seed == [f"{BASE}/sldworksapi/FunctionalCategories-sldworksapi.html"]


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
