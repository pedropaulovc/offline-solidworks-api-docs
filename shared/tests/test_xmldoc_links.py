#!/usr/bin/env python3
"""
Unit tests for XMLDoc link conversion utilities.
"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.xmldoc_links import (
    convert_links_to_see_refs,
    parse_href_to_cref,
    convert_to_full_url
)


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
        self.assertEqual(result, "https://help.solidworks.com/2026/english/api/sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm")

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
        self.assertIn('<see cref="SolidWorks.Interop.sldworks.IFeatureManager.AdvancedHole">IFeatureManager::AdvancedHole</see>', result)
        self.assertNotIn('<a href=', result)

    def test_guide_page_to_see_href(self):
        """Test converting guide page link to see href."""
        html = 'See <a href="../sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm">SOLIDWORKS Design</a> documentation.'
        result = convert_links_to_see_refs(html)
        self.assertIn('<see href="https://help.solidworks.com/2026/english/api/sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm">SOLIDWORKS Design</see>', result)
        self.assertNotIn('<a href=', result)

    def test_preserves_spacing_around_links(self):
        """Test that spacing around links is preserved."""
        html = 'Text before <a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html">IFeature</a> text after.'
        result = convert_links_to_see_refs(html)
        self.assertIn(' <see cref=', result)
        self.assertIn('</see> ', result)

    def test_preserves_double_colon_in_link_text(self):
        """Test that :: in link text is preserved."""
        html = '<a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~OpenDoc7.html">ISldWorks::OpenDoc7</a>'
        result = convert_links_to_see_refs(html)
        self.assertIn('ISldWorks::OpenDoc7</see>', result)
        self.assertNotIn('ISldWorks.OpenDoc7</see>', result)

    def test_cleans_html_entities(self):
        """Test that HTML entities are cleaned up."""
        html = 'Text with&nbsp;<a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html">IFeature</a>&nbsp;more text.'
        result = convert_links_to_see_refs(html)
        self.assertNotIn('&nbsp;', result)
        self.assertIn(' ', result)

    def test_removes_other_html_tags(self):
        """Test that other HTML tags are removed."""
        html = '<p>Text with <a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html">IFeature</a> link.</p>'
        result = convert_links_to_see_refs(html)
        self.assertNotIn('<p>', result)
        self.assertNotIn('</p>', result)
        self.assertIn('<see cref=', result)


if __name__ == "__main__":
    unittest.main()
