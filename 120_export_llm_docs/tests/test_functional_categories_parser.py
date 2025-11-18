"""
Tests for the Functional Categories Parser
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from functional_categories_parser import FunctionalCategoriesParser


def test_parser_loads_categories():
    """Test that the parser can load and parse categories."""
    html_path = "10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html"

    parser = FunctionalCategoriesParser(html_path)
    categories = parser.parse()

    # Should have at least 10 categories
    assert len(categories) >= 10, f"Expected at least 10 categories, got {len(categories)}"

    # Each category should have a name and types
    for cat in categories:
        assert cat.name, "Category should have a name"
        assert len(cat.types) > 0, f"Category {cat.name} should have types"

    print(f"[PASS] Parser loaded {len(categories)} categories")


def test_category_mapping():
    """Test that the category mapping is created correctly."""
    html_path = "10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html"

    parser = FunctionalCategoriesParser(html_path)
    parser.parse()
    mapping = parser.get_category_mapping()

    # Should have types mapped
    assert len(mapping) > 0, "Should have types in mapping"

    # Check for a known type
    assert "SOLIDWORKS.Interop.sldworks.IModelDoc2" in mapping, "Should contain IModelDoc2"
    assert mapping["SOLIDWORKS.Interop.sldworks.IModelDoc2"] == "Application Interfaces"

    print(f"[PASS] Category mapping has {len(mapping)} types")


if __name__ == '__main__':
    test_parser_loads_categories()
    test_category_mapping()
    print("\n[PASS] All tests passed!")
