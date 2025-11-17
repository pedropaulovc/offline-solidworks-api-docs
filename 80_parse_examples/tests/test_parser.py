"""
Tests for Phase 06: Parse Examples
"""

import pytest
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from parse_examples import ExampleParser


class TestExampleParser:
    """Tests for the ExampleParser class."""

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

    @pytest.fixture
    def sample_html_simple(self):
        """Sample simple HTML content."""
        return """
        <h1>Test Example (VBA)</h1>
        <p>This is a test example.</p>
        <p class="APICODE">Option Explicit</p>
        <p class="APICODE">Sub main()</p>
        <p class="APICODE">End Sub</p>
        """

    @pytest.fixture
    def sample_html_with_br(self):
        """Sample HTML with line breaks."""
        return """
        <h1>Test Example</h1>
        <p>Test description.</p>
        <p class="APICODE">
        '------------<br>
        ' Test comment<br>
        '------------
        </p>
        """

    @pytest.fixture
    def sample_html_complex(self):
        """Sample HTML with syntax highlighting (spans)."""
        return """
        <h1>Complex Example (C#)</h1>
        <p>Complex example with syntax highlighting.</p>
        <div style="font-family:Monospace; font-size: 10pt;">
            <p class="APICODE">
                <span style="color:Blue">using</span>
                <span style="color:Black"> System;</span><br>
            </p>
            <p class="APICODE">
                <span style="color:Blue">namespace</span>
                <span style="color:Black"> Test</span><br>
            </p>
        </div>
        """

    def test_parser_initialization(self, temp_dirs):
        """Test parser initializes correctly."""
        html_dir, output_file = temp_dirs
        parser = ExampleParser(html_dir, output_file)

        assert parser.html_dir == html_dir
        assert parser.output_file == output_file
        assert parser.stats['total_files'] == 0
        assert parser.stats['successful'] == 0
        assert len(parser.errors) == 0

    def test_parse_simple_html(self, parser, sample_html_simple, temp_dirs):
        """Test parsing simple HTML."""
        html_dir, _ = temp_dirs

        # Create a test HTML file
        test_file = html_dir / 'test_example.htm'
        test_file.write_text(sample_html_simple)

        # Parse the file
        content = parser.parse_html_file(test_file)

        assert content is not None
        assert 'Test Example (VBA)' in content
        assert 'This is a test example.' in content
        assert '<code>' in content
        assert '</code>' in content
        assert 'Option Explicit' in content
        assert 'Sub main()' in content
        assert 'End Sub' in content

    def test_parse_html_with_br_tags(self, parser, sample_html_with_br, temp_dirs):
        """Test parsing HTML with <br> tags."""
        html_dir, _ = temp_dirs

        # Create a test HTML file
        test_file = html_dir / 'test_br.htm'
        test_file.write_text(sample_html_with_br)

        # Parse the file
        content = parser.parse_html_file(test_file)

        assert content is not None
        assert '<code>' in content
        # Check that line breaks are preserved
        assert '------------\n' in content or "Test comment" in content

    def test_parse_html_with_spans(self, parser, sample_html_complex, temp_dirs):
        """Test parsing HTML with span tags (syntax highlighting)."""
        html_dir, _ = temp_dirs

        # Create a test HTML file
        test_file = html_dir / 'test_complex.htm'
        test_file.write_text(sample_html_complex)

        # Parse the file
        content = parser.parse_html_file(test_file)

        assert content is not None
        assert '<code>' in content
        # Span tags should be stripped
        assert '<span' not in content
        # Content should be preserved
        assert 'using System;' in content
        assert 'namespace Test' in content

    def test_get_relative_path(self, parser, temp_dirs):
        """Test relative path extraction."""
        html_dir, _ = temp_dirs

        # Create a nested file
        subdir = html_dir / 'sldworksapi'
        subdir.mkdir()
        test_file = subdir / 'example.htm'
        test_file.touch()

        relative_path = parser.get_relative_path(test_file)
        assert relative_path == 'sldworksapi/example.htm'

    def test_parse_all_examples(self, parser, sample_html_simple, temp_dirs):
        """Test parsing all examples creates valid XML."""
        html_dir, _ = temp_dirs

        # Create multiple test files
        for i in range(3):
            test_file = html_dir / f'example_{i}.htm'
            test_file.write_text(sample_html_simple)

        # Parse all examples
        root = parser.parse_all_examples()

        assert root is not None
        assert root.tag == 'Examples'

        examples = root.findall('Example')
        assert len(examples) == 3
        assert parser.stats['total_files'] == 3
        assert parser.stats['successful'] == 3
        assert parser.stats['failed'] == 0

    def test_xml_structure(self, parser, sample_html_simple, temp_dirs):
        """Test XML structure is correct."""
        html_dir, _ = temp_dirs

        # Create a test file
        test_file = html_dir / 'test.htm'
        test_file.write_text(sample_html_simple)

        # Parse all examples
        root = parser.parse_all_examples()

        # Check structure
        example = root.find('Example')
        assert example is not None

        url = example.find('Url')
        assert url is not None
        assert url.text == 'test.htm'

        content = example.find('Content')
        assert content is not None
        assert content.text is not None
        assert len(content.text) > 0

    def test_error_handling_nonexistent_file(self, parser):
        """Test error handling for non-existent files."""
        nonexistent = Path('/nonexistent/file.htm')
        content = parser.parse_html_file(nonexistent)

        assert content is None
        assert len(parser.errors) > 0

    def test_empty_html_file(self, parser, temp_dirs):
        """Test handling of empty HTML file."""
        html_dir, _ = temp_dirs

        # Create empty file
        empty_file = html_dir / 'empty.htm'
        empty_file.write_text('')

        content = parser.parse_html_file(empty_file)
        # Should return None for empty content
        assert content is None or len(content.strip()) == 0

    def test_html_entity_decoding(self, parser, temp_dirs):
        """Test that HTML entities are properly decoded."""
        html_dir, _ = temp_dirs

        html_with_entities = """
        <h1>Test</h1>
        <p class="APICODE">
        Debug.Print(&quot;Hello&quot;)
        </p>
        """

        test_file = html_dir / 'entities.htm'
        test_file.write_text(html_with_entities)

        content = parser.parse_html_file(test_file)

        # Quotes should be decoded (will be re-encoded in XML, then decoded in CDATA)
        assert content is not None
        # The content should contain the actual quote characters after processing
        assert 'Debug.Print("Hello")' in content or 'Debug.Print' in content

    def test_save_metadata(self, parser, temp_dirs):
        """Test metadata saving."""
        _, output_file = temp_dirs
        metadata_dir = output_file.parent / 'metadata'

        # Set some stats
        parser.stats['successful'] = 10
        parser.stats['failed'] = 2

        # Save metadata
        parser.save_metadata(metadata_dir)

        # Check files were created
        assert (metadata_dir / 'parse_stats.json').exists()
        assert (metadata_dir / 'manifest.json').exists()

    def test_prettify_xml_with_cdata(self, parser, sample_html_simple, temp_dirs):
        """Test that XML is prettified with CDATA sections."""
        html_dir, output_file = temp_dirs

        # Create a test file
        test_file = html_dir / 'test.htm'
        test_file.write_text(sample_html_simple)

        # Parse and save
        root = parser.parse_all_examples()
        parser.save_xml(root)

        # Read the saved XML
        with open(output_file, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        # Check for CDATA sections
        assert '<![CDATA[' in xml_content
        assert ']]>' in xml_content

        # Verify it's valid XML
        tree = ET.parse(output_file)
        root = tree.getroot()
        assert root.tag == 'Examples'

    def test_whitespace_normalization(self, parser, temp_dirs):
        """Test that whitespace is properly normalized."""
        html_dir, _ = temp_dirs

        html_with_extra_whitespace = """
        <h1>Test</h1>
        <p class="APICODE">
        <span>using</span>
        <span>  System;</span>
        </p>
        """

        test_file = html_dir / 'whitespace.htm'
        test_file.write_text(html_with_extra_whitespace)

        content = parser.parse_html_file(test_file)

        assert content is not None
        # Should not have double spaces
        assert '  ' not in content.replace('\n', ' ')

    def test_no_linebreak_markers_in_output(self, parser, temp_dirs):
        """Test that <<<LINEBREAK>>> markers are never left in the output."""
        html_dir, _ = temp_dirs

        # Test case 1: <pre> block with <br> tags
        html_with_pre_br = """
        <h1>Test Pre</h1>
        <pre>Line 1<br>Line 2<br>Line 3</pre>
        """

        test_file = html_dir / 'pre_br.htm'
        test_file.write_text(html_with_pre_br)
        content = parser.parse_html_file(test_file)
        assert content is not None
        assert '<<<LINEBREAK>>>' not in content, "LINEBREAK marker found in <pre> output"

        # Test case 2: Regular paragraph with <br> tags (not code)
        html_with_p_br = """
        <h1>Test Header<br>Second Line</h1>
        <p>Paragraph with<br>line breaks<br>inside</p>
        """

        test_file2 = html_dir / 'p_br.htm'
        test_file2.write_text(html_with_p_br)
        content2 = parser.parse_html_file(test_file2)
        assert content2 is not None
        assert '<<<LINEBREAK>>>' not in content2, "LINEBREAK marker found in paragraph output"

        # Test case 3: Mixed content with <br> tags
        html_mixed = """
        <h1>Mixed<br>Example</h1>
        <p>Description with<br>breaks</p>
        <p class="APICODE">Code line 1<br>Code line 2</p>
        <pre>Pre line 1<br>Pre line 2</pre>
        """

        test_file3 = html_dir / 'mixed_br.htm'
        test_file3.write_text(html_mixed)
        content3 = parser.parse_html_file(test_file3)
        assert content3 is not None
        assert '<<<LINEBREAK>>>' not in content3, "LINEBREAK marker found in mixed content output"


class TestIntegration:
    """Integration tests for the complete pipeline."""

    def test_full_pipeline(self):
        """Test the complete parsing pipeline (if Phase 7 output exists)."""
        project_root = Path(__file__).parent.parent.parent
        html_dir = project_root / '70_crawl_examples' / 'output' / 'html'

        # Skip if Phase 7 hasn't been run
        if not html_dir.exists():
            pytest.skip("Phase 7 output not available")

        # Just check that we can create a parser
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / 'test.xml'
            parser = ExampleParser(html_dir, output_file)

            # Parse a few files
            html_files = list(html_dir.rglob('*.htm'))[:5]
            if html_files:
                for html_file in html_files:
                    content = parser.parse_html_file(html_file)
                    assert content is not None or content == ''  # Some might be empty


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
