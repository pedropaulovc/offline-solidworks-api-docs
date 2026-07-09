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
            _make_types(), "https://help.solidworks.com/2026/english/api/")

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
            _make_types(), "https://help.solidworks.com/2026/english/api/")

        text = guide.read_text(encoding="utf-8")
        assert "[type](../../types/IFeature/_overview.md)" in text
        assert "[method](../../types/IFeature/GetDefinition.md)" in text
        assert "[enum](../../enums/swFeatureNameID_e.md)" in text
        # Unresolved target -> canonical online page, not a dead relative path.
        assert ("[missing](https://help.solidworks.com/2026/english/api/sldworksapi/"
                f"{SLD}.INotShipped~DoThing.html)") in text


def test_rewrite_leaves_non_reference_links_untouched():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        original = "[sibling guide](Other%20Page.md) and [ex](../../sldworksapi/Some_Example.htm)\n"
        guide = _write_guide(tmp, original)

        ExportPipeline(str(tmp))._rewrite_guide_api_links(
            _make_types(), "https://help.solidworks.com/2026/english/api/")

        assert guide.read_text(encoding="utf-8") == original
