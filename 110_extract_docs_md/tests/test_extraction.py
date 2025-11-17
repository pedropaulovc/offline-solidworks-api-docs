"""Tests for Phase 11 markdown extraction."""

import json
import tempfile
from pathlib import Path

import pytest

from toc_builder import TocNode, TocTreeBuilder
from html_to_markdown import HtmlToMarkdownConverter


class TestTocTreeBuilder:
    """Test TOC tree building functionality."""

    def test_build_tree_creates_root_node(self, sample_expandtoc_dir):
        """Test that tree builder creates a root node."""
        builder = TocTreeBuilder(sample_expandtoc_dir)
        root = builder.build_tree()

        assert root is not None
        assert root.id == "1"
        assert root.parent_id == "-1"
        assert root.name == "Getting Started"

    def test_build_tree_creates_children(self, sample_expandtoc_dir):
        """Test that tree builder creates child nodes."""
        builder = TocTreeBuilder(sample_expandtoc_dir)
        root = builder.build_tree()

        assert len(root.children) > 0

    def test_node_hierarchy(self, sample_expandtoc_dir):
        """Test that nodes maintain correct parent-child relationships."""
        builder = TocTreeBuilder(sample_expandtoc_dir)
        root = builder.build_tree()

        # Check that all children have correct parent_id
        for child in root.children:
            assert child.parent_id == root.id

    def test_leaf_nodes(self, sample_expandtoc_dir):
        """Test that leaf nodes are properly identified."""
        builder = TocTreeBuilder(sample_expandtoc_dir)
        root = builder.build_tree()

        # Find a leaf node
        def find_leaf(node):
            if node.is_leaf:
                return node
            for child in node.children:
                result = find_leaf(child)
                if result:
                    return result
            return None

        leaf = find_leaf(root)
        assert leaf is not None
        assert leaf.is_leaf is True
        assert len(leaf.children) == 0


class TestHtmlToMarkdownConverter:
    """Test HTML to Markdown conversion."""

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        converter = HtmlToMarkdownConverter(
            html_dir=Path("."),
            metadata_file=Path("."),
            output_dir=Path("."),
        )

        # Test invalid characters
        assert converter.sanitize_filename("test:file") == "test_file"
        assert converter.sanitize_filename('test"file') == "test_file"
        assert converter.sanitize_filename("test<file>") == "test_file_"
        assert converter.sanitize_filename("test/file") == "test_file"

        # Test leading/trailing spaces and dots
        assert converter.sanitize_filename(" test ") == "test"
        assert converter.sanitize_filename(".test.") == "test"

        # Test length limiting
        long_name = "a" * 250
        sanitized = converter.sanitize_filename(long_name)
        assert len(sanitized) <= 200

    def test_convert_simple_html(self, tmp_path):
        """Test converting simple HTML to Markdown."""
        # Create sample HTML file
        html_file = tmp_path / "test.html"
        html_content = """
        <h1>Test Title</h1>
        <p>This is a test paragraph.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        """
        html_file.write_text(html_content, encoding="utf-8")

        # Convert to markdown
        converter = HtmlToMarkdownConverter(
            html_dir=tmp_path,
            metadata_file=Path("."),
            output_dir=tmp_path,
        )
        markdown = converter.convert_html_to_markdown(html_file)

        # Check conversion
        assert "# Test Title" in markdown
        assert "This is a test paragraph." in markdown
        assert "Item 1" in markdown
        assert "Item 2" in markdown

    def test_save_markdown(self, tmp_path):
        """Test saving Markdown file."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        converter = HtmlToMarkdownConverter(
            html_dir=Path("."),
            metadata_file=Path("."),
            output_dir=output_dir,
        )

        markdown_content = "# Test\n\nThis is a test."
        output_path = output_dir / "test.md"

        metadata = converter.save_markdown(markdown_content, output_path)

        # Check file was created
        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == markdown_content

        # Check metadata
        assert "file_path" in metadata
        assert "content_hash" in metadata
        assert "content_length" in metadata
        assert metadata["content_length"] == len(markdown_content)


class TestTocNode:
    """Test TocNode data structure."""

    def test_create_node(self):
        """Test creating a TocNode."""
        node = TocNode(
            id="1.2.3",
            parent_id="1.2",
            name="Test Node",
            url="/test/url",
            is_leaf=True,
            children=[],
        )

        assert node.id == "1.2.3"
        assert node.parent_id == "1.2"
        assert node.name == "Test Node"
        assert node.url == "/test/url"
        assert node.is_leaf is True
        assert len(node.children) == 0

    def test_node_with_children(self):
        """Test node with children."""
        child1 = TocNode(
            id="1.2.0", parent_id="1.2", name="Child 1", url="/child1", is_leaf=True, children=[]
        )
        child2 = TocNode(
            id="1.2.1", parent_id="1.2", name="Child 2", url="/child2", is_leaf=True, children=[]
        )

        parent = TocNode(
            id="1.2",
            parent_id="1",
            name="Parent",
            url="/parent",
            is_leaf=False,
            children=[child1, child2],
        )

        assert len(parent.children) == 2
        assert parent.children[0].parent_id == parent.id
        assert parent.children[1].parent_id == parent.id


# Fixtures


@pytest.fixture
def sample_expandtoc_dir(tmp_path):
    """Create a sample expandToc directory structure for testing."""
    expandtoc_dir = tmp_path / "expandtoc"
    expandtoc_dir.mkdir()

    # Create root node
    root_data = {
        "id": "1",
        "parentId": "-1",
        "name": "Getting Started",
        "url": "/2026/english/api/help_list.htm?id=1",
        "isLeaf": False,
        "children": [
            {
                "id": "1.0",
                "parentId": "1",
                "name": "Overview",
                "url": "/2026/english/api/sldworksapiprogguide/GettingStarted/Overview.htm?id=1.0",
                "isLeaf": True,
                "Expanded": False,
                "Selected": False,
            },
            {
                "id": "1.1",
                "parentId": "1",
                "name": "Installation",
                "url": "/2026/english/api/sldworksapiprogguide/GettingStarted/Installation.htm?id=1.1",
                "isLeaf": True,
                "Expanded": False,
                "Selected": False,
            },
        ],
        "Expanded": True,
        "Selected": False,
    }

    root_file = expandtoc_dir / "expandToc_id_1.json"
    with root_file.open("w", encoding="utf-8") as f:
        json.dump(root_data, f)

    # Create child nodes
    child1_data = {
        "id": "1.0",
        "parentId": "1",
        "name": "Overview",
        "url": "/2026/english/api/sldworksapiprogguide/GettingStarted/Overview.htm?id=1.0",
        "isLeaf": True,
        "Expanded": False,
        "Selected": False,
    }

    child1_file = expandtoc_dir / "expandToc_id_1.0.json"
    with child1_file.open("w", encoding="utf-8") as f:
        json.dump(child1_data, f)

    child2_data = {
        "id": "1.1",
        "parentId": "1",
        "name": "Installation",
        "url": "/2026/english/api/sldworksapiprogguide/GettingStarted/Installation.htm?id=1.1",
        "isLeaf": True,
        "Expanded": False,
        "Selected": False,
    }

    child2_file = expandtoc_dir / "expandToc_id_1.1.json"
    with child2_file.open("w", encoding="utf-8") as f:
        json.dump(child2_data, f)

    return expandtoc_dir


@pytest.fixture
def sample_html_file(tmp_path):
    """Create a sample HTML file for testing."""
    html_file = tmp_path / "test.html"
    html_content = """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>SOLIDWORKS API Help</h1>
        <h1>Getting Started Overview</h1>
        <p>This is an overview of the SOLIDWORKS API.</p>
        <h2>Key Features</h2>
        <ul>
            <li>Feature 1</li>
            <li>Feature 2</li>
            <li>Feature 3</li>
        </ul>
    </body>
    </html>
    """
    html_file.write_text(html_content, encoding="utf-8")
    return html_file
