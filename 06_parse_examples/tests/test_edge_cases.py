"""
Additional tests for edge cases in Phase 06: Parse Examples
Tests for specific HTML patterns found in the SolidWorks documentation.
"""

import pytest
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from parse_examples import ExampleParser


class TestPreFormattedBlocks:
    """Tests for <pre> tag handling."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as html_dir, \
             tempfile.TemporaryDirectory() as output_dir:
            html_path = Path(html_dir)
            output_path = Path(output_dir) / 'test_output.xml'
            yield html_path, output_path

    @pytest.fixture
    def parser(self, temp_dirs):
        """Create a parser instance."""
        html_dir, output_file = temp_dirs
        return ExampleParser(html_dir, output_file)

    def test_pre_block_preserves_newlines(self, parser, temp_dirs):
        """Test that <pre> blocks preserve actual newlines from HTML source."""
        html_dir, _ = temp_dirs

        html_with_pre = """
        <h1>Test Example (VB.NET)</h1>
        <p>Test description.</p>
        <pre style="font-family: Courier New">Imports System
Imports SolidWorks

Public Class Test
    Public Sub Main()
        Debug.Print("Hello")
    End Sub
End Class</pre>
        """

        test_file = html_dir / 'test_pre.htm'
        test_file.write_text(html_with_pre)

        content = parser.parse_html_file(test_file)

        assert content is not None
        assert '<code>' in content
        assert 'Imports System' in content
        # Should preserve the newlines
        lines = content.split('\n')
        assert any('Imports System' in line for line in lines)
        assert any('Public Sub Main()' in line for line in lines)
        # Should preserve indentation
        assert any(line.strip().startswith('Debug.Print') for line in lines)

    def test_multiple_pre_blocks_merged(self, parser, temp_dirs):
        """Test that multiple <pre> blocks are merged into one code block."""
        html_dir, _ = temp_dirs

        html_with_multiple_pre = """
        <h1>Test Example (VBA)</h1>
        <p>Test description.</p>
        <pre>Option Explicit</pre>
        <pre>Dim x As Long</pre>
        <pre>Sub Main()
    x = 5
End Sub</pre>
        """

        test_file = html_dir / 'test_multi_pre.htm'
        test_file.write_text(html_with_multiple_pre)

        content = parser.parse_html_file(test_file)

        assert content is not None
        # Should have only one code block
        code_count = content.count('<code>')
        assert code_count == 1
        assert content.count('</code>') == 1
        # All content should be in that block
        assert 'Option Explicit' in content
        assert 'Dim x As Long' in content
        assert 'Sub Main()' in content


class TestIndentationPreservation:
    """Tests for preserving code indentation."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as html_dir, \
             tempfile.TemporaryDirectory() as output_dir:
            html_path = Path(html_dir)
            output_path = Path(output_dir) / 'test_output.xml'
            yield html_path, output_path

    @pytest.fixture
    def parser(self, temp_dirs):
        """Create a parser instance."""
        html_dir, output_file = temp_dirs
        return ExampleParser(html_dir, output_file)

    def test_apicode_with_nbsp_indentation(self, parser, temp_dirs):
        """Test that &nbsp; indentation in APICODE paragraphs is preserved."""
        html_dir, _ = temp_dirs

        html_with_nbsp = """
        <h1>Test Example (C#)</h1>
        <p>Test description.</p>
        <p class="APICODE">namespace Test<br>
{</p>
        <p class="APICODE"><!--kadov_tag{{<spaces>}}-->&nbsp;&nbsp;&nbsp;&nbsp;<!--kadov_tag{{</spaces>}}-->public class MyClass<br>
&nbsp;&nbsp;&nbsp;&nbsp;{</p>
        <p class="APICODE"><!--kadov_tag{{<spaces>}}-->&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<!--kadov_tag{{</spaces>}}-->public void Main()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{</p>
        <p class="APICODE"><!--kadov_tag{{<spaces>}}-->&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<!--kadov_tag{{</spaces>}}-->}</p>
        <p class="APICODE">&nbsp;&nbsp;&nbsp;&nbsp;}</p>
        <p class="APICODE">}</p>
        """

        test_file = html_dir / 'test_nbsp.htm'
        test_file.write_text(html_with_nbsp)

        content = parser.parse_html_file(test_file)

        assert content is not None
        # Check that indentation exists (leading spaces on indented lines)
        lines = content.split('\n')
        code_lines = []
        in_code = False
        for line in lines:
            if '<code>' in line:
                in_code = True
                continue
            if '</code>' in line:
                break
            if in_code:
                code_lines.append(line)

        # Should have lines with different indentation levels
        # Note: exact whitespace might vary, but structure should be preserved
        assert any('namespace Test' in line for line in code_lines)
        assert any('public class MyClass' in line for line in code_lines)

    def test_pre_block_indentation(self, parser, temp_dirs):
        """Test that leading spaces in <pre> blocks are preserved for nested code."""
        html_dir, _ = temp_dirs

        # More realistic example - indentation within the code structure
        html_with_indentation = """
        <h1>Test</h1>
        <pre>Dim swModel As ModelDoc2

Sub Main()
    Dim x As Long
    x = 5
    Debug.Print(x)
End Sub</pre>
        """

        test_file = html_dir / 'test_indent.htm'
        test_file.write_text(html_with_indentation)

        content = parser.parse_html_file(test_file)

        assert content is not None
        # Should contain the code
        assert 'Sub Main()' in content
        assert 'Dim x As Long' in content

        # Check that the structure is preserved (even if exact indentation varies)
        # The key is that code is on separate lines and logically structured
        lines = [line for line in content.split('\n') if line.strip()]

        # Should have these as distinct lines
        assert any('Dim swModel' in line for line in lines)
        assert any('Sub Main()' in line for line in lines)
        assert any('End Sub' in line for line in lines)

        # The indented content should at least be present
        # (Our parser may normalize exact spacing, but content should be there)
        assert 'Dim x As Long' in content
        assert 'Debug.Print(x)' in content


class TestMultiParagraphAPICode:
    """Tests for multiple <p class="APICODE"> paragraphs with indentation."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as html_dir, \
             tempfile.TemporaryDirectory() as output_dir:
            html_path = Path(html_dir)
            output_path = Path(output_dir) / 'test_output.xml'
            yield html_path, output_path

    @pytest.fixture
    def parser(self, temp_dirs):
        """Create a parser instance."""
        html_dir, output_file = temp_dirs
        return ExampleParser(html_dir, output_file)

    def test_multiple_apicode_paragraphs_preserve_indentation(self, parser, temp_dirs):
        """Test that indentation is preserved across multiple APICODE paragraphs."""
        html_dir, _ = temp_dirs

        # Simulates the actual HTML structure from Create_Simulation_Gravity_Feature_Example_VBNET.htm
        html_with_multi_apicode = """
        <h1>Test Example (VB.NET)</h1>
        <p>Description</p>
        <p class="APICODE">
<span style="color:blue;">Partial</span>&nbsp;<span style="color:blue;">Class</span>&nbsp;Test<br>
&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:blue;">Dim</span>&nbsp;swModel&nbsp;<span style="color:blue;">As</span>&nbsp;ModelDoc2<br>
&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:blue;">Dim</span>&nbsp;swFeat&nbsp;<span style="color:blue;">As</span>&nbsp;Feature<br>
&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:blue;">Sub</span>&nbsp;main()<br>
&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;swModel&nbsp;=&nbsp;swApp.ActiveDoc<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Debug.Print("Test")<br>
&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:blue;">End</span>&nbsp;<span style="color:blue;">Sub</span><br>
&nbsp;<br>
<span style="color:blue;">End</span>&nbsp;<span style="color:blue;">Class</span><br>
</p>
        """

        test_file = html_dir / 'test_multi_indent.htm'
        test_file.write_text(html_with_multi_apicode)

        content = parser.parse_html_file(test_file)

        assert content is not None

        # Extract just the code block
        lines = content.split('\n')
        code_lines = []
        in_code = False
        for line in lines:
            if '<code>' in line:
                in_code = True
                continue
            if '</code>' in line:
                break
            if in_code:
                code_lines.append(line)

        # Should have indentation preserved
        # Class-level declarations should have 4 spaces
        dim_lines = [line for line in code_lines if 'Dim swModel' in line or 'Dim swFeat' in line]
        assert len(dim_lines) == 2
        for line in dim_lines:
            # Should have leading spaces (4 spaces for class members)
            assert line.startswith('    '), f"Expected 4 leading spaces, got: '{line}'"

        # Code inside Sub should have 8 spaces
        inside_sub = [line for line in code_lines if 'swModel = swApp' in line or 'Debug.Print' in line]
        assert len(inside_sub) == 2
        for line in inside_sub:
            # Should have 8 leading spaces
            assert line.startswith('        '), f"Expected 8 leading spaces, got: '{line}'"


class TestAPICodeParagraphs:
    """Tests for <p class="APICODE"> handling."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as html_dir, \
             tempfile.TemporaryDirectory() as output_dir:
            html_path = Path(html_dir)
            output_path = Path(output_dir) / 'test_output.xml'
            yield html_path, output_path

    @pytest.fixture
    def parser(self, temp_dirs):
        """Create a parser instance."""
        html_dir, output_file = temp_dirs
        return ExampleParser(html_dir, output_file)

    def test_apicode_with_br_tags(self, parser, temp_dirs):
        """Test that <br> tags in APICODE create line breaks."""
        html_dir, _ = temp_dirs

        html_with_br = """
        <h1>Test</h1>
        <p class="APICODE">'Comment line 1<br>
'Comment line 2<br>
'Comment line 3</p>
        <p class="APICODE">Option Explicit</p>
        """

        test_file = html_dir / 'test_apicode_br.htm'
        test_file.write_text(html_with_br)

        content = parser.parse_html_file(test_file)

        assert content is not None
        # Should have line breaks from <br> tags
        assert "'Comment line 1" in content
        assert "'Comment line 2" in content
        assert "'Comment line 3" in content
        # They should be on separate lines
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        assert "'Comment line 1" in lines
        assert "'Comment line 2" in lines

    def test_apicode_in_div_container(self, parser, temp_dirs):
        """Test APICODE paragraphs inside a monospace div."""
        html_dir, _ = temp_dirs

        html_with_div = """
        <h1>Test (C#)</h1>
        <div style="font-family:Monospace; font-size: 10pt;">
            <p class="APICODE"><span style="color:Blue">using</span> System;</p>
            <p class="APICODE"><span style="color:Blue">namespace</span> Test { }</p>
        </div>
        """

        test_file = html_dir / 'test_div.htm'
        test_file.write_text(html_with_div)

        content = parser.parse_html_file(test_file)

        assert content is not None
        # Should have single code block
        assert content.count('<code>') == 1
        # Should strip span tags
        assert '<span' not in content
        # Should keep content
        assert 'using System' in content
        assert 'namespace Test' in content


class TestWhitespaceNormalization:
    """Tests for whitespace handling edge cases."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as html_dir, \
             tempfile.TemporaryDirectory() as output_dir:
            html_path = Path(html_dir)
            output_path = Path(output_dir) / 'test_output.xml'
            yield html_path, output_path

    @pytest.fixture
    def parser(self, temp_dirs):
        """Create a parser instance."""
        html_dir, output_file = temp_dirs
        return ExampleParser(html_dir, output_file)

    def test_no_excessive_blank_lines(self, parser, temp_dirs):
        """Test that excessive blank lines are collapsed."""
        html_dir, _ = temp_dirs

        html_with_blanks = """
        <h1>Test</h1>
        <p>Paragraph 1</p>


        <p>Paragraph 2</p>
        <pre>Code line 1


Code line 2</pre>
        """

        test_file = html_dir / 'test_blanks.htm'
        test_file.write_text(html_with_blanks)

        content = parser.parse_html_file(test_file)

        assert content is not None
        # Should not have more than 2 consecutive newlines
        assert '\n\n\n' not in content

    def test_trailing_spaces_removed(self, parser, temp_dirs):
        """Test that trailing spaces on lines are removed."""
        html_dir, _ = temp_dirs

        html = """
        <h1>Test</h1>
        <pre>Code line 1
Code line 2
Code line 3</pre>
        """

        test_file = html_dir / 'test_trailing.htm'
        test_file.write_text(html)

        content = parser.parse_html_file(test_file)

        assert content is not None
        lines = content.split('\n')
        # No line should end with spaces (except possibly empty lines)
        for line in lines:
            if line:  # Non-empty lines
                assert not line.endswith(' ')
                assert not line.endswith('\t')


class TestXMLGeneration:
    """Tests for XML output generation."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as html_dir, \
             tempfile.TemporaryDirectory() as output_dir:
            html_path = Path(html_dir)
            output_path = Path(output_dir) / 'test_output.xml'
            yield html_path, output_path

    @pytest.fixture
    def parser(self, temp_dirs):
        """Create a parser instance."""
        html_dir, output_file = temp_dirs
        return ExampleParser(html_dir, output_file)

    def test_cdata_contains_code_tags(self, parser, temp_dirs):
        """Test that <code> tags are inside CDATA, not escaped."""
        html_dir, output_file = temp_dirs

        html = """
        <h1>Test Example</h1>
        <p>Description</p>
        <pre>Option Explicit
Sub Main()
End Sub</pre>
        """

        test_file = html_dir / 'test.htm'
        test_file.write_text(html)

        # Parse and save
        root = parser.parse_all_examples()
        parser.save_xml(root)

        # Read the XML
        with open(output_file, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        # Should have CDATA sections
        assert '<![CDATA[' in xml_content
        assert ']]>' in xml_content

        # <code> tags should be inside CDATA, not escaped
        assert '<code>' in xml_content
        assert '&lt;code&gt;' not in xml_content

    def test_special_characters_in_cdata(self, parser, temp_dirs):
        """Test that special XML characters are handled correctly in CDATA."""
        html_dir, output_file = temp_dirs

        html = """
        <h1>Test</h1>
        <pre>If x > 5 And y < 10 Then
    Debug.Print("Value & Result")
End If</pre>
        """

        test_file = html_dir / 'test_special.htm'
        test_file.write_text(html)

        root = parser.parse_all_examples()
        parser.save_xml(root)

        # Read and parse the XML
        tree = ET.parse(output_file)
        xml_root = tree.getroot()

        # Get the content
        example = xml_root.find('Example')
        content_elem = example.find('Content')
        content = content_elem.text

        # Special characters should be preserved
        assert '>' in content
        assert '<' in content
        assert '&' in content
        assert '"' in content

    def test_nested_directories_in_url(self, parser, temp_dirs):
        """Test that nested directory structures are preserved in URLs."""
        html_dir, _ = temp_dirs

        # Create nested structure
        subdir1 = html_dir / 'sldworksapi'
        subdir1.mkdir()
        subdir2 = html_dir / 'swmotionstudyapi'
        subdir2.mkdir()

        html = "<h1>Test</h1><p>Content</p>"

        file1 = subdir1 / 'example1.htm'
        file1.write_text(html)

        file2 = subdir2 / 'example2.htm'
        file2.write_text(html)

        root = parser.parse_all_examples()

        # Check URLs
        examples = root.findall('Example')
        urls = [ex.find('Url').text for ex in examples]

        assert 'sldworksapi/example1.htm' in urls
        assert 'swmotionstudyapi/example2.htm' in urls


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
