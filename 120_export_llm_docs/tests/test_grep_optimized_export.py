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


def test_enum_member_documentation_generation():
    """Test that enum member files are generated with YAML frontmatter."""
    # Create a sample enum type
    type_info = TypeInfo(
        name="swTestEnum_e",
        assembly="SolidWorks.Interop.swconst",
        namespace="SolidWorks.Interop.swconst"
    )

    enum_member = EnumMember(
        name="swTestValue",
        description="Test enum value description"
    )

    # Generate enum member documentation
    generator = MarkdownGenerator(output_base_path="test", grep_optimized=True)
    member_md = generator.generate_enum_member_documentation(type_info, enum_member)

    # Check YAML frontmatter
    assert member_md.startswith('---\n'), "Should start with YAML frontmatter"
    assert 'type: swTestEnum_e' in member_md
    assert 'member: swTestValue' in member_md
    assert 'kind: enum_member' in member_md
    assert 'assembly: SolidWorks.Interop.swconst' in member_md

    # Check content
    assert '# swTestEnum_e.swTestValue' in member_md
    assert 'Test enum value description' in member_md

    print("[PASS] Enum member documentation generation with YAML frontmatter")


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
    """Test that enum types generate correct file structure."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "test_enum"

        # Create a sample enum type
        type_info = TypeInfo(
            name="swTestEnum_e",
            assembly="SolidWorks.Interop.swconst",
            namespace="SolidWorks.Interop.swconst"
        )

        type_info.enum_members.append(EnumMember(name="swValue1", description="Value 1"))
        type_info.enum_members.append(EnumMember(name="swValue2", description="Value 2"))
        type_info.enum_members.append(EnumMember(name="swValue3", description="Value 3"))

        # Generate grep-optimized documentation
        generator = MarkdownGenerator(output_base_path=str(output_dir.parent), grep_optimized=True)
        files_count = generator.save_grep_optimized_documentation(type_info, output_dir)

        # Check file count: 1 overview + 3 enum members = 4
        assert files_count == 4, f"Expected 4 files, got {files_count}"

        # Check that files exist
        assert (output_dir / "_overview.md").exists(), "Overview file should exist"
        assert (output_dir / "swValue1.md").exists(), "swValue1 file should exist"
        assert (output_dir / "swValue2.md").exists(), "swValue2 file should exist"
        assert (output_dir / "swValue3.md").exists(), "swValue3 file should exist"

        # Check that overview identifies as enum
        overview_content = (output_dir / "_overview.md").read_text(encoding='utf-8')
        assert 'is_enum: True' in overview_content
        assert 'enum_member_count: 3' in overview_content

    print("[PASS] Enum file structure generation")


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
        assert "api/types/{TypeName}/_overview.md" in readme_content

        # Check that statistics are populated
        assert "Stats" in readme_content
        assert "types" in readme_content
        assert "enums" in readme_content
        assert "examples" in readme_content

        print("[PASS] README.md generation for LLMs")


if __name__ == '__main__':
    test_type_overview_generation()
    test_member_documentation_generation()
    test_enum_member_documentation_generation()
    test_cross_reference_simplification()
    test_grep_optimized_file_structure()
    test_enum_file_structure()
    test_yaml_frontmatter_format()
    test_readme_generation()
    print("\n[PASS] All grep-optimized export tests passed!")
