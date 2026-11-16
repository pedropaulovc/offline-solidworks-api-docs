"""Tests for resolving CHM alias links to their web help folder."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.chm_aliases import chm_alias_page, relative_chm_alias, resolve_chm_alias
from shared.constants import SOLIDWORKS_API_BASE_PATH, SOLIDWORKS_API_FULL_BASE_URL

API = SOLIDWORKS_API_FULL_BASE_URL


@pytest.mark.parametrize(
    ("link", "page"),
    [
        # Absolute, as Phases 40/50/60 used to record a bare alias under sldworksapi/.
        (
            f"{API}/sldworksapi/sldworksAPIProgGuide.chm::/OVERVIEW/Type_Libraries.htm",
            "sldworksapiprogguide/OVERVIEW/Type_Libraries.htm",
        ),
        (f"{API}/sldworksapi/ms-its:swconst.chm::/DP_Dimensions.htm", "swconst/DP_Dimensions.htm"),
        # Doubled separator.
        (
            f"{API}/sldworksapi/ms-its:sldworksapiprogguide.chm:://Overview/SOLIDWORKS_Connected.htm",
            "sldworksapiprogguide/Overview/SOLIDWORKS_Connected.htm",
        ),
        # Written directly under /api, in any casing of the path.
        (
            f"{API}/ms-its:swdimxpertapi.chm::/SOLIDWORKS.Interop.swdimxpert~SOLIDWORKS.Interop.swdimxpert_namespace.html",
            "swdimxpertapi/SOLIDWORKS.Interop.swdimxpert~SOLIDWORKS.Interop.swdimxpert_namespace.html",
        ),
        ("https://help.solidworks.com/2027/English/api/ms-its:swconst.chm::/X.htm", "swconst/X.htm"),
        # API-root relative, as Phases 40/50 record example URLs.
        (
            "/swconst/ms-its:sldworksapi.chm::/Add_Component_and_Mate_Example_VB.htm",
            "sldworksapi/Add_Component_and_Mate_Example_VB.htm",
        ),
        # Relative to the linking page, with or without dot segments.
        ("ms-its:swconst.chm::/DP_Dimensions.htm", "swconst/DP_Dimensions.htm"),
        ("swconst.chm::/DP_DimensionTolerance.htm", "swconst/DP_DimensionTolerance.htm"),
        ("../sldworksapi/ms-its:swconst.chm::/SO_Colors.htm", "swconst/SO_Colors.htm"),
        ("../ms-its:swconst.chm::/SO_Colors.htm", "swconst/SO_Colors.htm"),
        ("./ms-its:swconst.chm::/SO_Colors.htm", "swconst/SO_Colors.htm"),
        # Other CHM protocols.
        ("its:swconst.chm::/X.htm", "swconst/X.htm"),
        ("mk:@MSITStore:swconst.chm::/X.htm", "swconst/X.htm"),
        # The CHM name's case varies (swConst.chm); the folder is lowercase.
        ("ms-its:swConst.chm::/SO_Display.htm", "swconst/SO_Display.htm"),
    ],
)
def test_alias_names_a_page_under_the_api_root(link: str, page: str) -> None:
    assert chm_alias_page(link) == page
    assert resolve_chm_alias(link) == f"{API}/{page}"


@pytest.mark.parametrize(
    "link",
    [
        f"{API}/swconst/DP_Dimensions.htm",
        "../sldworksapiprogguide/Overview/Type_Libraries.htm",
        "/sldworksapi/Foo_Example_VB.htm",
        "Foo_Example_VB.htm",
        "https://example.com/page.htm",
        # No CHM name: only dots, or a name with an empty part.
        "ms-its:..chm::/X.htm",
        "ms-its:a..chm::/X.htm",
    ],
)
def test_other_links_unchanged(link: str) -> None:
    assert chm_alias_page(link) is None
    assert resolve_chm_alias(link) == link
    assert relative_chm_alias(link, f"{API}/swconst/SO_Export.htm") == link


@pytest.mark.parametrize(
    ("page_url", "relative"),
    [
        # Same folder as the page the alias names.
        (f"{API}/swconst/SO_Export.htm", "DP_Units.htm#top"),
        (f"{API}/sldworksapi/X.htm", "../swconst/DP_Units.htm#top"),
        # A help path works as well as a URL; deeper pages climb further.
        (f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/Overview/X.htm", "../../swconst/DP_Units.htm#top"),
    ],
)
def test_relative_alias_is_relative_to_the_linking_page(page_url: str, relative: str) -> None:
    assert relative_chm_alias("ms-its:swconst.chm::/DP_Units.htm#top", page_url) == relative
