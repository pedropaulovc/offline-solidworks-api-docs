"""
Tests for the Grep-Optimized Export Structure
"""

import sys
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import TypeInfo, Property, Method, EnumMember
from markdown_generator import MarkdownGenerator


def test_type_overview_generation():
    """Test that type overview files are generated with YAML frontmatter."""
    # Create a sample type
    type_info = TypeInfo(
        name="ITestType",
        assembly="SolidWorks.Interop.sldworks",
        namespace="SolidWorks.Interop.sldworks",
        description="Test type description",
        remarks="Test type remarks",
        functional_category="Application Interfaces"
    )

    # Add some members
    type_info.properties.append(Property(
        name="TestProperty",
        description="Test property description"
    ))

    type_info.methods.append(Method(
        name="TestMethod",
        description="Test method description"
    ))

    # Generate overview
    generator = MarkdownGenerator(output_base_path="test", grep_optimized=True)
    overview_md = generator.generate_type_overview(type_info)

    # Check YAML frontmatter
    assert overview_md.startswith('---\n'), "Should start with YAML frontmatter"
    assert 'name: ITestType' in overview_md
    assert 'assembly: SolidWorks.Interop.sldworks' in overview_md
    assert 'category: Application Interfaces' in overview_md
    assert 'is_enum: False' in overview_md
    assert 'property_count: 1' in overview_md
    assert 'method_count: 1' in overview_md

    # Check content
    assert '# ITestType' in overview_md
    assert 'Test type description' in overview_md
    assert 'Test type remarks' in overview_md
    assert '- **Properties**: 1' in overview_md
    assert '- **Methods**: 1' in overview_md

    print("[PASS] Type overview generation with YAML frontmatter")


def test_member_documentation_generation():
    """Test that member files are generated with YAML frontmatter."""
    # Create a sample type and method
    type_info = TypeInfo(
        name="ITestType",
        assembly="SolidWorks.Interop.sldworks",
        namespace="SolidWorks.Interop.sldworks",
        functional_category="Application Interfaces"
    )

    from models import Parameter
    method = Method(
        name="TestMethod",
        description="Test method description",
        signature="TestMethod(string param1, int param2)",
        returns="bool - True if successful",
        remarks="Test method remarks"
    )
    method.parameters.append(Parameter(name="param1", description="First parameter"))
    method.parameters.append(Parameter(name="param2", description="Second parameter"))

    # Generate member documentation
    generator = MarkdownGenerator(output_base_path="test", grep_optimized=True)
    member_md = generator.generate_member_documentation(type_info, method, "method")

    # Check YAML frontmatter
    assert member_md.startswith('---\n'), "Should start with YAML frontmatter"
    assert 'type: ITestType' in member_md
    assert 'member: TestMethod' in member_md
    assert 'kind: method' in member_md
    assert 'assembly: SolidWorks.Interop.sldworks' in member_md
    assert 'category: Application Interfaces' in member_md

    # Check content
    assert '# ITestType.TestMethod' in member_md
    assert 'Test method description' in member_md
    assert '**Signature**:' in member_md
    assert '## Parameters' in member_md
    assert '**param1**:' in member_md
    assert '**param2**:' in member_md
    assert '## Returns' in member_md
    assert 'True if successful' in member_md
    assert '## Remarks' in member_md
    assert 'Test method remarks' in member_md

    print("[PASS] Member documentation generation with YAML frontmatter")


def test_multiline_param_description_indented_under_bullet():
    """A parameter whose description carries block markdown (a sublist, extra
    paragraphs) must keep its continuation lines indented under the ``- `` bullet
    so it renders as one list item instead of escaping the list."""
    from models import Parameter

    type_info = TypeInfo(
        name="IFeatureManager",
        assembly="SolidWorks.Interop.sldworks",
        namespace="SolidWorks.Interop.sldworks",
    )
    method = Method(name="HoleWizard5", description="Creates holes.")
    method.parameters.append(Parameter(
        name="Length",
        description="Length of slot; valid only if GenericHoleType set to:\n\n- swWzdCounterBoreSlot\n- swWzdHoleSlot",
    ))
    method.parameters.append(Parameter(name="Depth", description="Depth of the hole"))

    generator = MarkdownGenerator(output_base_path="test", grep_optimized=True)
    member_md = generator.generate_member_documentation(type_info, method, "method")

    # The sublist items are indented two spaces so they nest under "- **Length**".
    assert "- **Length**: Length of slot" in member_md
    assert "\n  - swWzdCounterBoreSlot" in member_md
    assert "\n  - swWzdHoleSlot" in member_md
    # The next parameter is a sibling bullet, not indented.
    assert "\n- **Depth**: Depth of the hole" in member_md

    print("[PASS] Multi-line parameter description indented under its bullet")


def test_enum_documentation_generation():
    """Test that a single enum file is generated with all members inline."""
    # Create a sample enum type
    type_info = TypeInfo(
        name="swTestEnum_e",
        assembly="SolidWorks.Interop.swconst",
        namespace="SolidWorks.Interop.swconst",
        description="Test enum description",
    )
    type_info.enum_members.append(EnumMember(name="swValueA", description="Value A description"))
    type_info.enum_members.append(EnumMember(name="swValueB", description="Value B description"))

    # Generate single-file enum documentation
    generator = MarkdownGenerator(output_base_path="test", grep_optimized=True)
    enum_md = generator.generate_enum_documentation(type_info)

    # Check YAML frontmatter
    assert enum_md.startswith('---\n'), "Should start with YAML frontmatter"
    assert 'name: swTestEnum_e' in enum_md
    assert 'kind: enum' in enum_md
    assert 'is_enum: True' in enum_md
    assert 'enum_member_count: 2' in enum_md
    assert 'assembly: SolidWorks.Interop.swconst' in enum_md

    # Check that ALL members are inline in the single file
    assert '## Enumeration Members' in enum_md
    assert '### swValueA' in enum_md
    assert 'Value A description' in enum_md
    assert '### swValueB' in enum_md
    assert 'Value B description' in enum_md

    print("[PASS] Single-file enum documentation generation with members inline")


def test_cross_reference_simplification():
    """Test that XML-style cross-references are simplified to markdown links."""
    generator = MarkdownGenerator(output_base_path="test", grep_optimized=True)

    # Test standard see tag
    text1 = 'See <see cref="SOLIDWORKS.Interop.sldworks.IModelDoc2">IModelDoc2</see> for details.'
    result1 = generator._simplify_cross_references(text1)
    assert result1 == 'See [[IModelDoc2]] for details.', f"Got: {result1}"

    # Test self-closing see tag
    text2 = 'Refer to <see cref="SOLIDWORKS.Interop.sldworks.IFeature" /> for more info.'
    result2 = generator._simplify_cross_references(text2)
    assert result2 == 'Refer to [[IFeature]] for more info.', f"Got: {result2}"

    # Test multiple references
    text3 = 'Use <see cref="A.B.TypeA">TypeA</see> with <see cref="C.D.TypeB">TypeB</see>.'
    result3 = generator._simplify_cross_references(text3)
    assert result3 == 'Use [[TypeA]] with [[TypeB]].', f"Got: {result3}"

    print("[PASS] Cross-reference simplification")


def test_href_cross_reference_resolution():
    """<see href> becomes a relative file link when the page is in the bundle,
    otherwise a plain external link."""
    guide_links = {
        "in-process_methods.htm": "docs/Programming with the SOLIDWORKS API/In-process Methods.md",
    }
    generator = MarkdownGenerator(output_base_path="test", grep_optimized=True, guide_links=guide_links)

    # In-bundle href from a type/member file (two levels deep) -> relative file link
    text = ('See <see href="https://help.solidworks.com/2026/english/api/'
            'sldworksapiprogguide/OVERVIEW/In-process_Methods.htm">In-process Methods</see>.')
    result = generator._simplify_cross_references(text, "../../")
    assert result == ('See [In-process Methods]'
                      '(<../../docs/Programming with the SOLIDWORKS API/In-process Methods.md>).'), f"Got: {result}"

    # From an enum file (one level deep) -> shallower prefix
    result_flat = generator._simplify_cross_references(text, "../")
    assert result_flat == ('See [In-process Methods]'
                           '(<../docs/Programming with the SOLIDWORKS API/In-process Methods.md>).'), f"Got: {result_flat}"

    # href NOT in the bundle -> plain external link, no prefix
    ext = 'See <see href="https://help.solidworks.com/2026/english/api/x/Unknown.htm">Unknown Page</see>.'
    result_ext = generator._simplify_cross_references(ext, "../../")
    assert result_ext == 'See [Unknown Page](https://help.solidworks.com/2026/english/api/x/Unknown.htm).', f"Got: {result_ext}"

    print("[PASS] href cross-reference resolution")


def test_strip_cross_references():
    """Index previews reduce <see …> tags to plain label text (no links to truncate)."""
    from markdown_generator import strip_cross_references

    assert strip_cross_references(
        'Access <see cref="A.B.IView">IView</see> per '
        '<see href="https://x/Bitmasks.htm">Bitmasks</see>.'
    ) == 'Access IView per Bitmasks.'

    # Self-closing cref collapses to the last FQN segment.
    assert strip_cross_references(
        'See <see cref="SolidWorks.Interop.sldworks.IFeature" />.'
    ) == 'See IFeature.'

    print("[PASS] strip cross-references to plain text")


def test_grep_optimized_file_structure():
    """Test that grep-optimized structure creates the correct files."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "test_type"

        # Create a sample type with members
        type_info = TypeInfo(
            name="ITestType",
            assembly="SolidWorks.Interop.sldworks",
            namespace="SolidWorks.Interop.sldworks",
            functional_category="Application Interfaces"
        )

        type_info.properties.append(Property(name="Prop1", description="Property 1"))
        type_info.properties.append(Property(name="Prop2", description="Property 2"))
        type_info.methods.append(Method(name="Method1", description="Method 1"))
        type_info.methods.append(Method(name="Method2", description="Method 2"))
        type_info.methods.append(Method(name="Method3", description="Method 3"))

        # Generate grep-optimized documentation
        generator = MarkdownGenerator(output_base_path=str(output_dir.parent), grep_optimized=True)
        files_count = generator.save_grep_optimized_documentation(type_info, output_dir)

        # Check file count: 1 overview + 2 properties + 3 methods = 6
        assert files_count == 6, f"Expected 6 files, got {files_count}"

        # Check that files exist
        assert (output_dir / "_overview.md").exists(), "Overview file should exist"
        assert (output_dir / "Prop1.md").exists(), "Prop1 file should exist"
        assert (output_dir / "Prop2.md").exists(), "Prop2 file should exist"
        assert (output_dir / "Method1.md").exists(), "Method1 file should exist"
        assert (output_dir / "Method2.md").exists(), "Method2 file should exist"
        assert (output_dir / "Method3.md").exists(), "Method3 file should exist"

        # Check that overview file has correct content
        overview_content = (output_dir / "_overview.md").read_text(encoding='utf-8')
        assert overview_content.startswith('---\n'), "Overview should have YAML frontmatter"
        assert 'name: ITestType' in overview_content
        assert 'property_count: 2' in overview_content
        assert 'method_count: 3' in overview_content

        # Check that member file has correct content
        method1_content = (output_dir / "Method1.md").read_text(encoding='utf-8')
        assert method1_content.startswith('---\n'), "Method1 should have YAML frontmatter"
        assert 'member: Method1' in method1_content
        assert 'kind: method' in method1_content
        assert '# ITestType.Method1' in method1_content

    print("[PASS] Grep-optimized file structure generation")


def test_enum_file_structure():
    """Test that enums are written as a single flat file with all members inline."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        enums_dir = Path(temp_dir) / "enums"

        # Create a sample enum type
        type_info = TypeInfo(
            name="swTestEnum_e",
            assembly="SolidWorks.Interop.swconst",
            namespace="SolidWorks.Interop.swconst"
        )

        type_info.enum_members.append(EnumMember(name="swValue1", description="Value 1"))
        type_info.enum_members.append(EnumMember(name="swValue2", description="Value 2"))
        type_info.enum_members.append(EnumMember(name="swValue3", description="Value 3"))

        # Write the single flat enum file: enums/swTestEnum_e.md
        generator = MarkdownGenerator(output_base_path=str(temp_dir), grep_optimized=True)
        enum_file = enums_dir / "swTestEnum_e.md"
        files_count = generator.save_enum_documentation(type_info, enum_file)

        # Exactly one file is written, and there is NO per-enum subdirectory
        assert files_count == 1, f"Expected 1 file, got {files_count}"
        assert enum_file.exists(), "Flat enum file should exist"
        assert not (enums_dir / "swTestEnum_e").exists(), "No per-enum subdirectory should be created"
        assert not (enums_dir / "swValue1.md").exists(), "No per-member files should be created"

        # Check content: identifies as enum and contains all members inline
        content = enum_file.read_text(encoding='utf-8')
        assert 'kind: enum' in content
        assert 'is_enum: True' in content
        assert 'enum_member_count: 3' in content
        assert '## Enumeration Members' in content
        assert '### swValue1' in content
        assert '### swValue2' in content
        assert '### swValue3' in content

    print("[PASS] Flat single-file enum structure generation")


def test_yaml_frontmatter_format():
    """Test that YAML frontmatter is properly formatted."""
    type_info = TypeInfo(
        name="ITestType",
        assembly="SolidWorks.Interop.sldworks",
        namespace="SolidWorks.Interop.sldworks",
        functional_category="Application Interfaces"
    )

    generator = MarkdownGenerator(output_base_path="test", grep_optimized=True)
    overview_md = generator.generate_type_overview(type_info)

    # Extract YAML frontmatter
    lines = overview_md.split('\n')
    assert lines[0] == '---', "Should start with ---"

    # Find end of frontmatter
    end_idx = -1
    for i, line in enumerate(lines[1:], start=1):
        if line == '---':
            end_idx = i
            break

    assert end_idx > 0, "Should have closing ---"

    # Check YAML content format
    yaml_section = '\n'.join(lines[1:end_idx])
    assert 'name:' in yaml_section
    assert 'assembly:' in yaml_section
    assert 'namespace:' in yaml_section
    assert 'category:' in yaml_section

    # Check that content starts after frontmatter
    content_start = end_idx + 1
    assert lines[content_start] == '', "Should have blank line after frontmatter"
    assert lines[content_start + 1].startswith('# '), "Should have title after frontmatter"

    print("[PASS] YAML frontmatter format validation")


def test_readme_generation():
    """Test that README.md is generated with proper content for LLMs."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        output_base = Path(temp_dir)

        # Create sample data
        types = {
            "ITestType1": TypeInfo(
                name="ITestType1",
                assembly="SolidWorks.Interop.sldworks",
                namespace="SolidWorks.Interop.sldworks"
            ),
            "swTestEnum_e": TypeInfo(
                name="swTestEnum_e",
                assembly="SolidWorks.Interop.swconst",
                namespace="SolidWorks.Interop.swconst"
            )
        }

        types["ITestType1"].methods.append(Method(name="TestMethod", description="Test"))
        types["swTestEnum_e"].enum_members.append(EnumMember(name="swValue1", description="Val1"))

        examples = {
            "example1.html": None  # Just need count for test
        }

        # Import and use the pipeline's README generation
        from export_pipeline import ExportPipeline
        pipeline = ExportPipeline(output_base=str(output_base))
        pipeline._generate_output_readme(types, examples)

        # Verify README exists
        readme_path = output_base / "README.md"
        assert readme_path.exists(), "README.md should be generated"

        # Read and verify content
        readme_content = readme_path.read_text(encoding='utf-8')

        # Check for key sections
        assert "# SolidWorks API Documentation - LLM-Optimized" in readme_content
        assert "## Structure" in readme_content
        assert "## Query Patterns" in readme_content
        assert "## YAML Frontmatter" in readme_content
        assert "## Cross-References" in readme_content

        # Check for essential query patterns
        assert "Find type overview" in readme_content
        assert "Find method/property" in readme_content
        assert "List all members" in readme_content
        assert "Find by category" in readme_content
        assert "types/{TypeName}/_overview.md" in readme_content

        # Check that statistics are populated
        assert "Stats" in readme_content
        assert "types" in readme_content
        assert "enums" in readme_content
        assert "examples" in readme_content

        print("[PASS] README.md generation for LLMs")


if __name__ == '__main__':
    test_type_overview_generation()
    test_member_documentation_generation()
    test_enum_documentation_generation()
    test_cross_reference_simplification()
    test_grep_optimized_file_structure()
    test_enum_file_structure()
    test_yaml_frontmatter_format()
    test_readme_generation()
    print("\n[PASS] All grep-optimized export tests passed!")
