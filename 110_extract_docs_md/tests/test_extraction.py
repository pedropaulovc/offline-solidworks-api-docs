"""Tests for Phase 11 markdown extraction."""

import json
import tempfile
from pathlib import Path

import pytest

from toc_builder import TocNode, TocTreeBuilder
from html_to_markdown import HtmlToMarkdownConverter, has_text
from url_rewriter import UrlRewriter

from shared.constants import SOLIDWORKS_API_BASE_PATH

# A page two folders below /api, as Phase 110's guide pages are.
PAGE_URL = f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/Overview/Page.htm"


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
        markdown = converter.convert_html_to_markdown(html_file, PAGE_URL)

        # Check conversion
        assert "# Test Title" in markdown
        assert "This is a test paragraph." in markdown
        assert "Item 1" in markdown
        assert "Item 2" in markdown

    def test_conversion_does_not_depend_on_previous_page(self, tmp_path):
        """A page converts the same whether or not another page was converted first.

        html2text keeps parser state across ``handle()`` calls: after a page that
        leaves a ``<table>`` open, a shared instance renders the next page's paragraph
        as a table cell (``a| y``), so markdown depended on conversion order.
        """
        unclosed_table = tmp_path / "a.html"
        unclosed_table.write_text("<table><tr><td>x", encoding="utf-8")
        page = tmp_path / "b.html"
        page.write_text("<p>a</p><table><tr><td>y</td></tr></table>", encoding="utf-8")

        def converter() -> HtmlToMarkdownConverter:
            return HtmlToMarkdownConverter(html_dir=tmp_path, metadata_file=Path("."), output_dir=tmp_path)

        alone = converter().convert_html_to_markdown(page, PAGE_URL)
        after_other = converter()
        after_other.convert_html_to_markdown(unclosed_table, PAGE_URL)

        assert after_other.convert_html_to_markdown(page, PAGE_URL) == alone
        assert alone.startswith("a\n\n")

    def test_chm_alias_links_become_page_relative(self, tmp_path):
        """A CHM alias href is a dead link as written; it becomes the page-relative path
        of the page it names, the same form as the page's ordinary relative links."""
        page = tmp_path / "page.html"
        page.write_text(
            '<p><a href="sldworksapi.chm::/SOLIDWORKS.Interop.sldworks~X.html">X</a> '
            '<a href="ms-its:swconst.chm::/DP_Units.htm#top">units</a> '
            "<a href='swconst.chm::/DP_Quoted.htm'>quoted</a> "
            "<a href=swconst.chm::/DP_Bare.htm>bare</a> "
            '<a href="../swconst/DP_Dimensions.htm">dims</a></p>',
            encoding="utf-8",
        )
        converter = HtmlToMarkdownConverter(html_dir=tmp_path, metadata_file=Path("."), output_dir=tmp_path)

        markdown = converter.convert_html_to_markdown(page, PAGE_URL)

        assert "chm::" not in markdown
        assert "[X](../../sldworksapi/SOLIDWORKS.Interop.sldworks~X.html)" in markdown
        assert "[units](../../swconst/DP_Units.htm#top)" in markdown
        assert "[quoted](../../swconst/DP_Quoted.htm)" in markdown
        assert "[bare](../../swconst/DP_Bare.htm)" in markdown
        assert "[dims](../swconst/DP_Dimensions.htm)" in markdown

    @pytest.mark.parametrize(
        ("html", "expected"),
        [
            ('<p><img src="../IMAGE/SYM_LIBRARY.GIF"></p>\n\n', False),
            # Shapes that leave text-like residue in the Markdown: a linked thumbnail,
            # a layout table, a parenthesised file name, a non-breaking space.
            ('<a href="big.htm"><img src="a.gif"></a>', False),
            ('<table><tr><td><img src="a.gif"></td></tr></table>', False),
            ('<img src="a(1).gif">&nbsp;', False),
            ('<script>var shown = 1;</script><style>p {}</style><img src="a.gif">', False),
            # html2text drops <head>, <title> included.
            ('<html><head><title>Free Form Curves</title></head><body><img src="a.gif"></body></html>', False),
            ("", False),
            ('<img src="a.gif"><p>The symbol libraries.</p>', True),
            ("<h1>Title</h1>", True),
            ("<html><head><title>T</title></head><body><p>Body text.</p></body></html>", True),
        ],
    )
    def test_has_text(self, html, expected):
        """Image-only pages would ship as a dangling image (the bundle has no images)."""
        assert has_text(html) is expected

    def test_image_only_page_converts_to_none(self, tmp_path):
        page = tmp_path / "page.html"
        page.write_text('<a href="big.htm"><img src="a.gif"></a>', encoding="utf-8")
        converter = HtmlToMarkdownConverter(html_dir=tmp_path, metadata_file=Path("."), output_dir=tmp_path)

        assert converter.convert_html_to_markdown(page, PAGE_URL) is None

    def test_rewriter_matches_guide_pages_case_insensitively(self):
        """An alias keeps the CHM's path case (``OVERVIEW/``), the TOC uses ``Overview/``;
        the server treats them as one page, so the link still becomes the ``.md`` file.
        A destination with a space is angle-wrapped: bare, CommonMark would end it there."""
        target = f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/Overview/Type_Libraries.htm?id=1.2"
        rewriter = UrlRewriter({target: Path("out/Overview/Type Libraries.md")})
        page = f"https://help.solidworks.com{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/Overview/Page.htm"

        content, count = rewriter.rewrite_urls(
            "[types](../OVERVIEW/Type_Libraries.htm)", page, Path("out/Overview/Page.md")
        )

        assert count == 1
        assert content == "[types](<Type Libraries.md>)"

    def test_rewriter_leaves_plain_destinations_bare(self):
        target = f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/Overview/Type_Libraries.htm?id=1.2"
        rewriter = UrlRewriter({target: Path("out/Overview/Type_Libraries.md")})
        page = f"https://help.solidworks.com{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/Overview/Page.htm"

        content, _ = rewriter.rewrite_urls("[types](Type_Libraries.htm)", page, Path("out/Overview/Page.md"))

        assert content == "[types](Type_Libraries.md)"

    def test_rewriter_encodes_hash_in_file_names(self):
        """``Visual C#.md``: a bare '#' would start the fragment, leaving ``Visual C``."""
        target = f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/GettingStarted/VisualCSharp.htm?id=1.3"
        rewriter = UrlRewriter({target: Path("out/Apps/Visual C#.md")})
        page = f"https://help.solidworks.com{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/GettingStarted/Page.htm"

        content, _ = rewriter.rewrite_urls("[C#](VisualCSharp.htm)", page, Path("out/Apps/Overview.md"))

        assert content == "[C#](<Visual C%23.md>)"

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
        "url": f"{SOLIDWORKS_API_BASE_PATH}/help_list.htm?id=1",
        "isLeaf": False,
        "children": [
            {
                "id": "1.0",
                "parentId": "1",
                "name": "Overview",
                "url": f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/GettingStarted/Overview.htm?id=1.0",
                "isLeaf": True,
                "Expanded": False,
                "Selected": False,
            },
            {
                "id": "1.1",
                "parentId": "1",
                "name": "Installation",
                "url": f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/GettingStarted/Installation.htm?id=1.1",
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
        "url": f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/GettingStarted/Overview.htm?id=1.0",
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
        "url": f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/GettingStarted/Installation.htm?id=1.1",
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


class TestMarkdownExtractor:
    """End-to-end runs of the Phase 110 extractor."""

    @staticmethod
    def _write_inputs(phase100: Path) -> Path:
        """A two-page programming guide: one text page, one image-only page."""
        html_dir = phase100 / "output" / "html"
        html_dir.mkdir(parents=True)
        pages = {
            "1.0": ("Overview", '<p>See <a href="sldworksapi.chm::/SOLIDWORKS.Interop.sldworks~X.html">X</a>.</p>'),
            "1.1": ("Diagram", '<img src="../IMAGE/DIAGRAM.GIF">'),
        }
        children = []
        crawled = []
        for node_id, (name, html) in pages.items():
            url = f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/Guide/{name}.htm?id={node_id}"
            children.append({"id": node_id, "parentId": "1", "name": name, "url": url, "isLeaf": True})
            (html_dir / f"{name}.html").write_text(html, encoding="utf-8")
            crawled.append({"url": f"https://help.solidworks.com{url}", "file_path": f"output/html/{name}.html"})
        root = {"id": "1", "parentId": "-1", "name": "Guide", "url": "", "isLeaf": False, "children": children}
        (html_dir / "expandToc_id_1.json").write_text(json.dumps(root), encoding="utf-8")
        metadata_file = phase100 / "metadata" / "urls_crawled.jsonl"
        metadata_file.parent.mkdir()
        metadata_file.write_text("".join(json.dumps(entry) + "\n" for entry in crawled), encoding="utf-8")
        return metadata_file

    def test_run_writes_only_this_runs_pages(self, tmp_path):
        """A stale page from an earlier run is gone, an image-only page is not written,
        and CHM aliases are resolved in what is."""
        from extract_markdown import MarkdownExtractor

        metadata_file = self._write_inputs(tmp_path / "100")
        output_dir = tmp_path / "110" / "output" / "markdown"
        output_dir.mkdir(parents=True)
        (output_dir / "Stale.md").write_text("# From an earlier run\n", encoding="utf-8")
        metadata_dir = tmp_path / "110" / "metadata"

        MarkdownExtractor(
            input_dir=tmp_path / "100" / "output" / "html",
            metadata_file=metadata_file,
            output_dir=output_dir,
            metadata_dir=metadata_dir,
        ).run()

        assert sorted(p.relative_to(output_dir).as_posix() for p in output_dir.rglob("*.md")) == ["Overview.md"]
        overview = (output_dir / "Overview.md").read_text(encoding="utf-8")
        assert "(../../sldworksapi/SOLIDWORKS.Interop.sldworks~X.html)" in overview
        with (metadata_dir / "files_created.jsonl").open(encoding="utf-8") as f:
            assert [json.loads(line)["node_name"] for line in f] == ["Overview"]
        stats = json.loads((metadata_dir / "extraction_stats.json").read_text(encoding="utf-8"))
        assert stats["image_only_pages"] == [f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/Guide/Diagram.htm?id=1.1"]
        assert stats["skipped_files"] == 0
