"""
Tests for resolving programming-guide API-reference links (Phase 120).

Phase 110 leaves ``sldworksapi``/``swconst``/… reference links pointing at the
original ``.html`` pages; Phase 120 must rewrite them to the ``types/``/``enums/``
files it ships (case-insensitively, so source-doc typos still resolve) and fall
back to the online help page when the target is not in the bundle.
"""

import sys
from pathlib import Path
import tempfile

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import TypeInfo, Property, Method, EnumMember
from markdown_generator import parse_api_ref_url
from export_pipeline import ExportPipeline


SLD = "SolidWorks.interop.sldworks~SolidWorks.interop.sldworks"


def test_parse_member_url():
    """Type~Member reference resolves to (assembly, type, member)."""
    url = f"../../sldworksapi/{SLD}.IFeature~ModifyDefinition.html"
    assert parse_api_ref_url(url) == ("sldworksapi", "IFeature", "ModifyDefinition")


def test_parse_type_only_url():
    """A bare type page has no member component."""
    url = f"../../sldworksapi/{SLD}.IMacroFeatureData.html"
    assert parse_api_ref_url(url) == ("sldworksapi", "IMacroFeatureData", None)


def test_parse_enum_url_other_assembly():
    """Enum pages in other assemblies parse the same way."""
    url = ("../../swconst/SolidWorks.Interop.swconst~"
           "SolidWorks.Interop.swconst.swFeatureNameID_e.html")
    assert parse_api_ref_url(url) == ("swconst", "swFeatureNameID_e", None)


def test_parse_non_reference_url_returns_none():
    """Example/guide pages (no ``~`` in the basename) are not reference pages."""
    assert parse_api_ref_url("../../sldworksapi/Create_Advanced_Hole_Example_CSharp.htm") is None
    assert parse_api_ref_url("Welcome.htm") is None


def _make_types():
    """A regular type with a member, plus an enum."""
    hole = TypeInfo(name="IWizardHoleFeatureData2",
                    assembly="SolidWorks.Interop.sldworks",
                    namespace="SolidWorks.Interop.sldworks")
    hole.methods.append(Method(name="InitializeHole"))

    feat = TypeInfo(name="IFeature",
                    assembly="SolidWorks.Interop.sldworks",
                    namespace="SolidWorks.Interop.sldworks")
    feat.methods.append(Method(name="GetDefinition"))

    enum = TypeInfo(name="swFeatureNameID_e",
                    assembly="SolidWorks.Interop.swconst",
                    namespace="SolidWorks.Interop.swconst")
    enum.enum_members.append(EnumMember(name="swFeatureBoss", description=""))

    return {t.fully_qualified_name: t for t in (hole, feat, enum)}


def _write_guide(tmp: Path, body: str) -> Path:
    guide = tmp / "docs" / "Programming with the SOLIDWORKS API" / "Hole Wizard Features and Objects.md"
    guide.parent.mkdir(parents=True, exist_ok=True)
    guide.write_text(body, encoding="utf-8")
    return guide


def test_rewrite_resolves_member_typo_to_md():
    """The reported case: a typo'd member link resolves to the shipping .md file."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Note the source typo: IWizardHoleFeatureDAta2 (capital A).
        guide = _write_guide(
            tmp,
            f"Init using [IWizardHoleFeatureData2::InitializeHole.]"
            f"(../../sldworksapi/{SLD}.IWizardHoleFeatureDAta2~InitializeHole.html)\n",
        )

        ExportPipeline(str(tmp))._rewrite_guide_api_links(
            _make_types(), "https://help.solidworks.com/2026/english/api/", {}, {})

        text = guide.read_text(encoding="utf-8")
        assert "(../../types/IWizardHoleFeatureData2/InitializeHole.md)" in text
        assert ".html)" not in text


def test_rewrite_type_only_and_enum_and_external():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        guide = _write_guide(
            tmp,
            "\n".join([
                f"[type](../../sldworksapi/{SLD}.IFeature.html)",
                f"[method](../../sldworksapi/{SLD}.IFeature~GetDefinition.html)",
                ("[enum](../../swconst/SolidWorks.Interop.swconst~"
                 "SolidWorks.Interop.swconst.swFeatureNameID_e.html)"),
                f"[missing](../../sldworksapi/{SLD}.INotShipped~DoThing.html)",
                "",
            ]),
        )

        ExportPipeline(str(tmp))._rewrite_guide_api_links(
            _make_types(), "https://help.solidworks.com/2026/english/api/", {}, {})

        text = guide.read_text(encoding="utf-8")
        assert "[type](../../types/IFeature/_overview.md)" in text
        assert "[method](../../types/IFeature/GetDefinition.md)" in text
        assert "[enum](../../enums/swFeatureNameID_e.md)" in text
        # Unresolved target -> canonical online page, not a dead relative path.
        assert ("[missing](https://help.solidworks.com/2026/english/api/sldworksapi/"
                f"{SLD}.INotShipped~DoThing.html)") in text


def test_missing_member_falls_back_to_online_page():
    """A member the type does not export lands on the online page, not the overview."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        guide = _write_guide(
            tmp,
            f"[gone](../../sldworksapi/{SLD}.IFeature~ObsoleteMethod.html)\n",
        )
        ExportPipeline(str(tmp))._rewrite_guide_api_links(
            _make_types(), "https://help.solidworks.com/2026/english/api/", {}, {})

        text = guide.read_text(encoding="utf-8")
        assert "_overview.md" not in text
        assert ("[gone](https://help.solidworks.com/2026/english/api/sldworksapi/"
                f"{SLD}.IFeature~ObsoleteMethod.html)") in text


def test_reference_link_with_fragment_resolves():
    """A #fragment (or ?query) after .html still resolves to the member file."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        guide = _write_guide(
            tmp,
            f"[m](../../sldworksapi/{SLD}.IFeature~GetDefinition.html#remarks)\n",
        )
        ExportPipeline(str(tmp))._rewrite_guide_api_links(
            _make_types(), "https://help.solidworks.com/2026/english/api/", {}, {})

        assert "[m](../../types/IFeature/GetDefinition.md)" in guide.read_text(encoding="utf-8")


def test_basename_only_unresolved_recovers_assembly_from_folder():
    """A same-directory ref with no assembly segment must not emit a `//` URL."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Referenced pages live under docs/{assembly}/; the link has no path prefix.
        ref = tmp / "docs" / "sldworksapi" / "SomePage.md"
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text(
            f"[x]({SLD.replace('interop', 'Interop')}.INotShipped.html)\n",
            encoding="utf-8",
        )
        ExportPipeline(str(tmp))._rewrite_guide_api_links(
            _make_types(), "https://help.solidworks.com/2026/english/api/", {}, {})

        text = ref.read_text(encoding="utf-8")
        assert "api//" not in text
        assert "https://help.solidworks.com/2026/english/api/sldworksapi/" in text


def test_rewrite_leaves_unshipped_non_reference_links_untouched():
    """With nothing in the page/example maps there is no bundle file to point at."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        original = "[sibling guide](Other%20Page.md) and [ex](../../sldworksapi/Some_Example.htm)\n"
        guide = _write_guide(tmp, original)

        ExportPipeline(str(tmp))._rewrite_guide_api_links(
            _make_types(), "https://help.solidworks.com/2026/english/api/", {}, {})

        assert guide.read_text(encoding="utf-8") == original


def test_rewrite_resolves_guide_and_example_page_links():
    """The regression: multi-module examples link sibling code pages by bare
    basename, and those pages ship under docs/ (Phase 115) and examples/."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        page = tmp / "docs" / "swdimxpertapi" / "DimXpert_Main_Module_CSharp.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            "component of [example](Get_DimXpert_Example_CSharp.htm) "
            "see [settings](../swconst/DP_Units.htm) "
            "and [gone](../swconst/NotShipped.htm)\n",
            encoding="utf-8",
        )

        guide_links = {"dp_units.htm": "docs/swconst/DP_Units.md"}
        examples = {"https://help.solidworks.com/2026/english/api/swdimxpertapi/"
                    "Get_DimXpert_Example_CSharp.htm": object()}

        ExportPipeline(str(tmp))._rewrite_guide_api_links(
            _make_types(), "https://help.solidworks.com/2026/english/api/", guide_links, examples)

        text = page.read_text(encoding="utf-8")
        assert "[example](../../examples/Get_DimXpert_Example_CSharp.md)" in text
        assert "[settings](../swconst/DP_Units.md)" in text
        # Not in the bundle: left alone rather than pointed at a wrong file.
        assert "[gone](../swconst/NotShipped.htm)" in text


def test_rewrite_carries_fragment_onto_resolved_page_link():
    """A #section names a place within a page, so it must not change which page the
    link resolves to, and must survive onto the local target."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        page = tmp / "docs" / "swconst" / "Some_Page.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("see [section](DP_Units.htm#remarks)\n", encoding="utf-8")

        ExportPipeline(str(tmp))._rewrite_guide_api_links(
            _make_types(), "https://help.solidworks.com/2026/english/api/",
            {"dp_units.htm": "docs/swconst/DP_Units.md"}, {})

        assert "[section](DP_Units.md#remarks)" in page.read_text(encoding="utf-8")


def test_guide_link_key_ignores_fragment():
    """``Page.htm#remarks`` and ``Page.htm`` name the same page."""
    from markdown_generator import guide_link_key

    assert guide_link_key("Other_Page.htm#remarks") == guide_link_key("Other_Page.htm")


def test_guide_link_key_decodes_percent_escapes():
    """A link may percent-encode a comma the manifest stores literally; both name
    the same page, so they must share a key or the link ships dead."""
    from markdown_generator import guide_link_key

    encoded = guide_link_key("SolidWorks_API_Add-Ins%2c_Project_Templates%2c_and_Wizards.htm")
    literal = guide_link_key("/2026/english/api/sldworksapiprogguide/Overview/"
                             "SolidWorks_API_Add-Ins,_Project_Templates,_and_Wizards.htm?id=1.2.3.0")
    assert encoded == literal


def test_see_href_reattaches_fragment_to_resolved_target():
    """guide_link_key ignores fragments when identifying a page, so a <see href>
    pointing at a section must not land at the top of the bundled page."""
    from markdown_generator import simplify_cross_references

    out = simplify_cross_references(
        '<see href="https://help.solidworks.com/2026/english/api/swconst/DP_Units.htm#remarks">Units</see>',
        {"dp_units.htm": "docs/swconst/DP_Units.md"},
        rel_prefix="../../",
    )
    assert out == "[Units](<../../docs/swconst/DP_Units.md#remarks>)"


def test_see_href_without_fragment_is_unchanged():
    from markdown_generator import simplify_cross_references

    out = simplify_cross_references(
        '<see href="https://help.solidworks.com/2026/english/api/swconst/DP_Units.htm">Units</see>',
        {"dp_units.htm": "docs/swconst/DP_Units.md"},
        rel_prefix="../../",
    )
    assert out == "[Units](<../../docs/swconst/DP_Units.md>)"
