"""Tests for the filename/title parsing shared by the extraction phases.

These cover the two filename dialects the pipeline sees: phase 10/30 save pages
under a hashed name (``Type_members_<hash>.html``), while phase 35 saves the bare
upstream name (``Type_members.html``). Parsers that only knew the first dialect
silently mangled the second.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from shared.extraction_utils import (  # noqa: E402
    canonical_assembly,
    extract_namespace_from_filename,
    is_type_file,
    strip_page_title_kind,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("SolidWorks.Interop.sldworks", "SolidWorks.Interop.sldworks"),
        # The reference tree shouts the vendor name; it is the same assembly.
        ("SOLIDWORKS.Interop.sldworks", "SolidWorks.Interop.sldworks"),
        ("SOLIDWORKS.Interop.swpublished", "SolidWorks.Interop.swpublished"),
        ("solidworks.interop.SWCONST", "SolidWorks.Interop.swconst"),
        # Unrecognised families pass through rather than being mangled.
        ("Some.Other.Assembly", "Some.Other.Assembly"),
        ("", ""),
    ],
)
def test_canonical_assembly(raw, expected):
    assert canonical_assembly(raw) == expected


@pytest.mark.parametrize(
    "title, expected",
    [
        ("IBody Interface", "IBody"),
        ("swBodyType_e Enumeration", "swBodyType_e"),
        ("SldWorks Class", "SldWorks"),
        # Reference-tree titles carry a disambiguating parenthetical.
        (
            "DAssemblyDocEvents_AutoSaveNotifyEventHandler Delegate (SolidWorks.Interop.sldworks)",
            "DAssemblyDocEvents_AutoSaveNotifyEventHandler",
        ),
        ("ConfigureDialog_e Enumeration (SolidWorks.Interop.sw3dprinter)", "ConfigureDialog_e"),
        # No recognised kind: left intact so an unfamiliar shape stays visible.
        ("Getting Started", "Getting Started"),
        ("  IBody Interface  ", "IBody"),
    ],
)
def test_strip_page_title_kind(title, expected):
    assert strip_page_title_kind(title) == expected


def test_strip_page_title_kind_keeps_names_ending_in_a_kind_word():
    """Only a *separate* trailing kind word is a suffix; a name is not truncated."""
    assert strip_page_title_kind("IPartDoc Interface") == "IPartDoc"
    assert strip_page_title_kind("Interface") == "Interface"


@pytest.mark.parametrize(
    "name, is_type",
    [
        ("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IBody.html", True),
        ("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IBody_a1b2.html", True),
        # phase 10 dialect
        ("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IBody_members_a1b2.html", False),
        # phase 35 dialect -- the case that used to slip through as a pseudo-type
        ("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IBody_members.html", False),
        ("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks_namespace.html", False),
        ("FunctionalCategories-sldworksapi.html", False),
    ],
)
def test_is_type_file(name, is_type):
    assert is_type_file(Path("html") / name) is is_type


def test_namespace_parsing_normalises_assembly_and_namespace_casing():
    """A SHOUTED reference page must land on the same type as its TOC twin."""
    shouted = Path(
        "html/SOLIDWORKS.Interop.swpublished~"
        "SOLIDWORKS.Interop.swpublished.IPropertyManagerPage2Handler4~OnUndo.html"
    )
    assembly, namespace, type_name = extract_namespace_from_filename(shouted)
    assert assembly == "SolidWorks.Interop.swpublished"
    assert namespace == "SolidWorks.Interop.swpublished"
    assert type_name == "IPropertyManagerPage2Handler4"


def test_namespace_parsing_handles_the_bare_members_suffix():
    """``Type_members.html`` must not leave ``_members`` glued to the type path."""
    bare = Path(
        "html/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IBody_members.html"
    )
    assembly, namespace, type_name = extract_namespace_from_filename(bare)
    assert (assembly, namespace, type_name) == (
        "SolidWorks.Interop.sldworks",
        "SolidWorks.Interop.sldworks",
        "IBody",
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
