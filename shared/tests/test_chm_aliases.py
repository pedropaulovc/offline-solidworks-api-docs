"""Tests for resolving CHM alias links to their web help folder."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.chm_aliases import resolve_chm_alias
from shared.constants import SOLIDWORKS_API_FULL_BASE_URL

API = SOLIDWORKS_API_FULL_BASE_URL


@pytest.mark.parametrize(
    ("link", "page"),
    [
        # Absolute, as Phases 40/50/60 used to record a bare alias under sldworksapi/.
        (
            f"{API}/sldworksapi/sldworksAPIProgGuide.chm::/OVERVIEW/Type_Libraries.htm",
            f"{API}/sldworksapiprogguide/OVERVIEW/Type_Libraries.htm",
        ),
        (f"{API}/sldworksapi/ms-its:swconst.chm::/DP_Dimensions.htm", f"{API}/swconst/DP_Dimensions.htm"),
        # Doubled separator.
        (
            f"{API}/sldworksapi/ms-its:sldworksapiprogguide.chm:://Overview/SOLIDWORKS_Connected.htm",
            f"{API}/sldworksapiprogguide/Overview/SOLIDWORKS_Connected.htm",
        ),
        # Written directly under /api: no folder to swap.
        (
            f"{API}/ms-its:swdimxpertapi.chm::/SOLIDWORKS.Interop.swdimxpert~SOLIDWORKS.Interop.swdimxpert_namespace.html",
            f"{API}/swdimxpertapi/SOLIDWORKS.Interop.swdimxpert~SOLIDWORKS.Interop.swdimxpert_namespace.html",
        ),
        # API-root relative, as Phases 40/50 record example URLs.
        (
            "/swconst/ms-its:sldworksapi.chm::/Add_Component_and_Mate_Example_VB.htm",
            "/sldworksapi/Add_Component_and_Mate_Example_VB.htm",
        ),
        # Relative to the linking page.
        ("ms-its:swconst.chm::/DP_Dimensions.htm", "../swconst/DP_Dimensions.htm"),
        ("swconst.chm::/DP_DimensionTolerance.htm", "../swconst/DP_DimensionTolerance.htm"),
        ("../sldworksapi/ms-its:swconst.chm::/SO_Colors.htm", "../swconst/SO_Colors.htm"),
        # The CHM name's case varies (swConst.chm); the folder is lowercase.
        ("ms-its:swConst.chm::/SO_Display.htm", "../swconst/SO_Display.htm"),
    ],
)
def test_alias_resolves_to_chm_folder(link: str, page: str) -> None:
    assert resolve_chm_alias(link) == page


@pytest.mark.parametrize(
    "link",
    [
        f"{API}/swconst/DP_Dimensions.htm",
        "../sldworksapiprogguide/Overview/Type_Libraries.htm",
        "Foo_Example_VB.htm",
        "https://example.com/page.htm",
    ],
)
def test_other_links_unchanged(link: str) -> None:
    assert resolve_chm_alias(link) == link
