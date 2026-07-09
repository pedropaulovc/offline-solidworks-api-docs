#!/usr/bin/env python3
"""
Unit tests for XMLDoc link conversion utilities.
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import xml.etree.ElementTree as ET

from shared.extraction_utils import add_see_also_element
from shared.xmldoc_links import convert_links_to_see_refs, convert_to_full_url, href_to_see_ref, parse_href_to_cref


class TestParseHrefToCref(unittest.TestCase):
    """Test parsing hrefs to cref values."""

    def test_simple_type_reference(self):
        """Test parsing simple type reference."""
        href = "SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~AdvancedHole.html"
        result = parse_href_to_cref(href)
        self.assertEqual(result, "SolidWorks.Interop.sldworks.IFeatureManager.AdvancedHole")

    def test_type_reference_with_path_prefix(self):
        """Test parsing type reference with path prefix."""
        href = "../sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISectionViewData~SectionedZones.html"
        result = parse_href_to_cref(href)
        self.assertEqual(result, "SolidWorks.Interop.sldworks.ISectionViewData.SectionedZones")

    def test_type_reference_with_url(self):
        """Test parsing type reference from full URL."""
        href = "https://example.com/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html"
        result = parse_href_to_cref(href)
        self.assertEqual(result, "SolidWorks.Interop.sldworks.IFeature")

    def test_non_type_guide_page_returns_none(self):
        """Test that guide pages return None."""
        href = "../sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm"
        result = parse_href_to_cref(href)
        self.assertIsNone(result)

    def test_file_path_without_type_pattern_returns_none(self):
        """Test that paths without type pattern return None."""
        href = "../some/path/to/file.html"
        result = parse_href_to_cref(href)
        self.assertIsNone(result)


class TestConvertToFullUrl(unittest.TestCase):
    """Test converting relative URLs to full URLs."""

    def test_relative_path_with_parent_dir(self):
        """Test converting relative path with ../."""
        href = "../sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm"
        result = convert_to_full_url(href)
        self.assertEqual(
            result,
            "https://help.solidworks.com/2026/english/api/sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm",
        )

    def test_relative_path_current_dir(self):
        """Test converting relative path in current directory."""
        href = "SomeFile.html"
        result = convert_to_full_url(href)
        self.assertEqual(result, "https://help.solidworks.com/2026/english/api/sldworksapi/SomeFile.html")

    def test_full_url_unchanged(self):
        """Test that full URLs are returned unchanged."""
        href = "https://example.com/page.htm"
        result = convert_to_full_url(href)
        self.assertEqual(result, "https://example.com/page.htm")


class TestConvertLinksToSeeRefs(unittest.TestCase):
    """Test converting HTML links to XMLDoc see refs."""

    def test_type_reference_to_see_cref(self):
        """Test converting type reference to see cref."""
        html = 'Use <a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~AdvancedHole.html">IFeatureManager::AdvancedHole</a> method.'
        result = convert_links_to_see_refs(html)
        self.assertIn(
            '<see cref="SolidWorks.Interop.sldworks.IFeatureManager.AdvancedHole">IFeatureManager::AdvancedHole</see>',
            result,
        )
        self.assertNotIn("<a href=", result)

    def test_guide_page_to_see_href(self):
        """Test converting guide page link to see href."""
        html = 'See <a href="../sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm">SOLIDWORKS Design</a> documentation.'
        result = convert_links_to_see_refs(html)
        self.assertIn(
            '<see href="https://help.solidworks.com/2026/english/api/sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm">SOLIDWORKS Design</see>',
            result,
        )
        self.assertNotIn("<a href=", result)

    def test_preserves_spacing_around_links(self):
        """Test that spacing around links is preserved."""
        html = 'Text before <a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html">IFeature</a> text after.'
        result = convert_links_to_see_refs(html)
        self.assertIn(" <see cref=", result)
        self.assertIn("</see> ", result)

    def test_preserves_double_colon_in_link_text(self):
        """Test that :: in link text is preserved."""
        html = '<a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~OpenDoc7.html">ISldWorks::OpenDoc7</a>'
        result = convert_links_to_see_refs(html)
        self.assertIn("ISldWorks::OpenDoc7</see>", result)
        self.assertNotIn("ISldWorks.OpenDoc7</see>", result)

    def test_cleans_html_entities(self):
        """Test that HTML entities are cleaned up."""
        html = 'Text with&nbsp;<a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html">IFeature</a>&nbsp;more text.'
        result = convert_links_to_see_refs(html)
        self.assertNotIn("&nbsp;", result)
        self.assertIn(" ", result)

    def test_removes_other_html_tags(self):
        """Test that other HTML tags are removed."""
        html = '<p>Text with <a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html">IFeature</a> link.</p>'
        result = convert_links_to_see_refs(html)
        self.assertNotIn("<p>", result)
        self.assertNotIn("</p>", result)
        self.assertIn("<see cref=", result)


class TestHtmlStructureToMarkdown(unittest.TestCase):
    """Structural HTML in help text is converted to markdown, not flattened."""

    def test_unordered_list_becomes_bullets(self):
        result = convert_links_to_see_refs("<ul><li>First</li><li>Second</li></ul>")
        self.assertIn("- First", result)
        self.assertIn("- Second", result)

    def test_ordered_list_is_numbered(self):
        result = convert_links_to_see_refs("<ol><li>Alpha</li><li>Beta</li><li>Gamma</li></ol>")
        self.assertIn("1. Alpha", result)
        self.assertIn("2. Beta", result)
        self.assertIn("3. Gamma", result)

    def test_paragraphs_separated_by_blank_line(self):
        result = convert_links_to_see_refs("<p>One.</p><p>Two.</p>")
        self.assertEqual(result, "One.\n\nTwo.")

    def test_heading_becomes_markdown_heading(self):
        result = convert_links_to_see_refs("<h4>Counterbore Holes</h4><p>Body.</p>")
        self.assertIn("#### Counterbore Holes", result)

    def test_bold_becomes_double_asterisks(self):
        self.assertIn("**Screw Fit**", convert_links_to_see_refs("<strong>Screw Fit</strong>"))
        self.assertIn("**Screw Fit**", convert_links_to_see_refs("<b>Screw Fit</b>"))
        self.assertIn(
            "**Head Clearance**",
            convert_links_to_see_refs('<span style="FONT-WEIGHT: bold">Head Clearance</span>'),
        )

    def test_trailing_space_moved_outside_bold(self):
        """Source often wraps a trailing space inside <strong>; the markers must
        hug the text so CommonMark still recognises the emphasis."""
        result = convert_links_to_see_refs("see <strong>Remarks </strong>for details")
        self.assertIn("**Remarks**", result)
        self.assertNotIn("**Remarks **", result)

    def test_list_item_wrapping_paragraph_hugs_marker(self):
        result = convert_links_to_see_refs("<ul><li><p>Wrapped item.</p></li></ul>")
        self.assertIn("- Wrapped item.", result)
        self.assertNotIn("- \n", result)

    def test_see_ref_preserved_through_conversion(self):
        html = ('<ul><li>Use '
                '<a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html">IFeature</a>'
                '</li></ul>')
        result = convert_links_to_see_refs(html)
        self.assertIn('- Use <see cref="SolidWorks.Interop.sldworks.IFeature">IFeature</see>', result)

    def test_nested_list_is_indented(self):
        result = convert_links_to_see_refs("<ul><li>Outer<ul><li>Inner</li></ul></li></ul>")
        self.assertIn("- Outer", result)
        self.assertIn("  - Inner", result)

    def test_second_paragraph_in_list_item_is_indented(self):
        """A list item with two paragraphs keeps the second one indented under
        the marker so it stays part of the item instead of escaping the list."""
        result = convert_links_to_see_refs("<ul><li><p>First</p><p>Second</p></li></ul>")
        self.assertIn("- First", result)
        self.assertIn("\n  Second", result)
        self.assertNotIn("\nSecond", result.replace("\n  Second", ""))

    def test_nested_list_under_two_digit_ordered_item_aligns_to_content_column(self):
        """A nested list under item 10 must indent 4 spaces (past ``10. ``), not
        the 2 that would suffice for a single-digit parent, or it escapes."""
        items = "".join(f"<li>Item {i}</li>" for i in range(1, 10))
        html = f"<ol>{items}<li>Tenth<ul><li>Nested</li></ul></li></ol>"
        result = convert_links_to_see_refs(html)
        self.assertIn("10. Tenth", result)
        self.assertIn("\n    - Nested", result)

    def test_nested_list_under_single_digit_ordered_item(self):
        result = convert_links_to_see_refs("<ol><li>Outer<ul><li>Inner</li></ul></li></ol>")
        self.assertIn("1. Outer", result)
        self.assertIn("\n   - Inner", result)


class TestHrefToSeeRef(unittest.TestCase):
    """Test resolving See Also hrefs to (attr, value) tuples."""

    def test_api_member_becomes_cref(self):
        attr, value = href_to_see_ref(
            "SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2~GetCorresponding.html"
        )
        self.assertEqual(attr, "cref")
        self.assertEqual(value, "SolidWorks.Interop.sldworks.IComponent2.GetCorresponding")

    def test_guide_page_becomes_href(self):
        attr, value = href_to_see_ref("../sldworksapiprogguide//Overview/Welcome.htm")
        self.assertEqual(attr, "href")
        self.assertTrue(value.startswith("https://help.solidworks.com/"))


class TestAddSeeAlsoElement(unittest.TestCase):
    """Test building the <SeeAlso> XML element."""

    def test_builds_see_elements(self):
        parent = ET.Element("Member")
        add_see_also_element(parent, [
            {"attr": "cref", "value": "A.B.C", "label": "C Method"},
            {"attr": "href", "value": "https://example.com", "label": "Guide"},
        ])
        sees = parent.findall("./SeeAlso/See")
        self.assertEqual(len(sees), 2)
        self.assertEqual(sees[0].get("cref"), "A.B.C")
        self.assertEqual(sees[0].text, "C Method")
        self.assertEqual(sees[1].get("href"), "https://example.com")

    def test_empty_list_is_noop(self):
        parent = ET.Element("Member")
        add_see_also_element(parent, [])
        self.assertIsNone(parent.find("SeeAlso"))


if __name__ == "__main__":
    unittest.main()
