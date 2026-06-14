"""
Tests for See Also rendering, return-type output, and discovery indexes.

These guard the bundle against the failure mode where a correct sibling method
(e.g. IComponent2.GetCorresponding) is present but undiscoverable.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import TypeInfo, Method, CrossRef
from markdown_generator import MarkdownGenerator
from index_generator import IndexGenerator


def _two_types():
    """Build IComponent2 with the GetCorresponding* sibling family across two types."""
    comp = TypeInfo(name="IComponent2", assembly="A", namespace="N")
    comp.methods.append(Method(
        name="GetCorrespondingEntity",
        description="Gets the entity (vertex, face, or edge).",
        signature="GetCorrespondingEntity( System.object Entity )",
        return_type="System.object",
        see_also=[CrossRef(attr="cref",
                           value="N.IComponent2.GetCorresponding",
                           label="IComponent2::GetCorresponding Method")],
    ))
    comp.methods.append(Method(
        name="GetCorresponding",
        description="Gets the corresponding object; works for any persistent-ID object.",
        signature="GetCorresponding( System.object InputObject )",
        return_type="System.object",
    ))
    ext = TypeInfo(name="IModelDocExtension", assembly="A", namespace="N")
    ext.methods.append(Method(
        name="GetCorresponding",
        signature="GetCorresponding( System.object InputObject )",
        return_type="System.object",
    ))
    return {"N.IComponent2": comp, "N.IModelDocExtension": ext}


def test_member_doc_includes_see_also_and_return_type(tmp_path):
    """A member doc surfaces its See Also siblings and the return type (P0 + P3)."""
    gen = MarkdownGenerator(output_base_path=str(tmp_path))
    comp = _two_types()["N.IComponent2"]
    entity_method = comp.methods[0]

    md = gen.generate_member_documentation(comp, entity_method, "method")

    # P0: the stripped cross-link is restored
    assert "## See Also" in md
    assert "[[IComponent2::GetCorresponding Method]]" in md
    # P3: return type is shown, not discarded
    assert "**Return type**: `System.object`" in md
    assert "System.object GetCorrespondingEntity(" in md


def test_by_member_name_index_clusters_siblings(tmp_path):
    """Sorting by member name places sibling families adjacently (P1)."""
    idx = IndexGenerator(output_base_path=str(tmp_path))
    md = idx.generate_by_member_name_index(_two_types())

    lines = [ln for ln in md.splitlines() if ln.startswith("- `GetCorresponding")]
    # All GetCorresponding / GetCorrespondingEntity entries cluster together,
    # with the exact-name matches sorting before the longer sibling name.
    assert lines[0].startswith("- `GetCorresponding` ")
    assert any("GetCorrespondingEntity" in ln for ln in lines)
    joined = "\n".join(lines)
    assert "IComponent2" in joined and "IModelDocExtension" in joined


def test_members_by_type_index_lists_full_member_set(tmp_path):
    """Every member of a type is listed under that type (P1)."""
    idx = IndexGenerator(output_base_path=str(tmp_path))
    md = idx.generate_members_by_type_index(_two_types())

    assert "## N.IComponent2" in md
    assert "GetCorresponding" in md
    assert "GetCorrespondingEntity" in md
    assert "`System.object GetCorresponding( System.object InputObject )`" in md
