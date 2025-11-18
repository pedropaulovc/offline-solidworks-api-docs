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

    # Should have at least 35 categories (we know there are 39)
    assert len(categories) >= 35, f"Expected at least 35 categories, got {len(categories)}"

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

    # Should have at least 450 types mapped (we know there are 482)
    assert len(mapping) >= 450, f"Expected at least 450 types, got {len(mapping)}"

    # Check for a known type
    assert "SOLIDWORKS.Interop.sldworks.IModelDoc2" in mapping, "Should contain IModelDoc2"
    assert mapping["SOLIDWORKS.Interop.sldworks.IModelDoc2"] == "Application Interfaces"

    print(f"[PASS] Category mapping has {len(mapping)} types")


def test_hierarchical_subcategories():
    """Test that hierarchical subcategories are parsed correctly."""
    html_path = "10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html"

    parser = FunctionalCategoriesParser(html_path)
    parser.parse()
    mapping = parser.get_category_mapping()

    # Test Table Annotations subcategory
    assert "SOLIDWORKS.Interop.sldworks.IBomTableAnnotation" in mapping, "Should contain IBomTableAnnotation"
    assert mapping["SOLIDWORKS.Interop.sldworks.IBomTableAnnotation"] == "Annotation Interfaces/Table Annotations", \
        f"IBomTableAnnotation should be in 'Annotation Interfaces/Table Annotations', got '{mapping.get('SOLIDWORKS.Interop.sldworks.IBomTableAnnotation')}'"

    # Test Folders subcategory
    assert "SOLIDWORKS.Interop.sldworks.IComment" in mapping, "Should contain IComment"
    assert mapping["SOLIDWORKS.Interop.sldworks.IComment"] == "Feature Interfaces/Folders", \
        f"IComment should be in 'Feature Interfaces/Folders', got '{mapping.get('SOLIDWORKS.Interop.sldworks.IComment')}'"

    # Test Mates subcategory
    assert "SolidWorks.Interop.sldworks.IAngleMateFeatureData" in mapping, "Should contain IAngleMateFeatureData"
    assert mapping["SolidWorks.Interop.sldworks.IAngleMateFeatureData"] == "Assembly Interfaces/Mates", \
        f"IAngleMateFeatureData should be in 'Assembly Interfaces/Mates', got '{mapping.get('SolidWorks.Interop.sldworks.IAngleMateFeatureData')}'"

    # Test Drawing Interfaces/Tables subcategory
    assert "SOLIDWORKS.Interop.sldworks.IBomTable" in mapping, "Should contain IBomTable"
    assert mapping["SOLIDWORKS.Interop.sldworks.IBomTable"] == "Drawing Interfaces/Tables", \
        f"IBomTable should be in 'Drawing Interfaces/Tables', got '{mapping.get('SOLIDWORKS.Interop.sldworks.IBomTable')}'"

    print("[PASS] Hierarchical subcategories parsed correctly")


def test_parent_types_with_nested_subcategories():
    """Test that parent types with nested subcategories are categorized."""
    html_path = "10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html"

    parser = FunctionalCategoriesParser(html_path)
    parser.parse()
    mapping = parser.get_category_mapping()

    # IDisplayDimension has child types (ICalloutAngleVariable, etc.) in a nested subcategory
    # The parent type should be categorized under "Annotation Interfaces"
    assert "SOLIDWORKS.Interop.sldworks.IDisplayDimension" in mapping, "Should contain IDisplayDimension"
    assert mapping["SOLIDWORKS.Interop.sldworks.IDisplayDimension"] == "Annotation Interfaces", \
        f"IDisplayDimension should be in 'Annotation Interfaces', got '{mapping.get('SOLIDWORKS.Interop.sldworks.IDisplayDimension')}'"

    # The child types should be in the subcategory
    assert "SolidWorks.Interop.sldworks.ICalloutAngleVariable" in mapping, "Should contain ICalloutAngleVariable"
    assert mapping["SolidWorks.Interop.sldworks.ICalloutAngleVariable"] == "Annotation Interfaces/IDisplayDimension", \
        f"ICalloutAngleVariable should be in 'Annotation Interfaces/IDisplayDimension', got '{mapping.get('SolidWorks.Interop.sldworks.ICalloutAngleVariable')}'"

    print("[PASS] Parent types with nested subcategories categorized correctly")


def test_enumeration_interfaces():
    """Test that enumeration interfaces are parsed correctly."""
    html_path = "10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html"

    parser = FunctionalCategoriesParser(html_path)
    parser.parse()
    mapping = parser.get_category_mapping()

    # Enumeration Interfaces had issues with multiple <ul> elements
    assert "SOLIDWORKS.Interop.sldworks.IEnumEdges" in mapping, "Should contain IEnumEdges"
    assert mapping["SOLIDWORKS.Interop.sldworks.IEnumEdges"] == "Enumeration Interfaces", \
        f"IEnumEdges should be in 'Enumeration Interfaces', got '{mapping.get('SOLIDWORKS.Interop.sldworks.IEnumEdges')}'"

    # Count enumeration interfaces - should have at least 10
    enum_types = [t for t, c in mapping.items() if c == "Enumeration Interfaces"]
    assert len(enum_types) >= 10, f"Expected at least 10 enumeration interfaces, got {len(enum_types)}"

    print(f"[PASS] Enumeration Interfaces parsed correctly ({len(enum_types)} types)")


def test_drawing_interfaces():
    """Test that Drawing Interfaces are parsed (header without anchor name)."""
    html_path = "10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html"

    parser = FunctionalCategoriesParser(html_path)
    parser.parse()
    mapping = parser.get_category_mapping()

    # Drawing Interfaces header has no anchor name attribute
    drawing_types = [t for t, c in mapping.items() if c == "Drawing Interfaces"]
    assert len(drawing_types) >= 10, f"Expected at least 10 drawing interfaces, got {len(drawing_types)}"

    # Check for a known type
    assert "SOLIDWORKS.Interop.sldworks.IBreakLine" in mapping, "Should contain IBreakLine"
    assert mapping["SOLIDWORKS.Interop.sldworks.IBreakLine"] == "Drawing Interfaces", \
        f"IBreakLine should be in 'Drawing Interfaces', got '{mapping.get('SOLIDWORKS.Interop.sldworks.IBreakLine')}'"

    print(f"[PASS] Drawing Interfaces parsed correctly ({len(drawing_types)} types)")


def test_model_interfaces():
    """Test that Model Interfaces are parsed correctly."""
    html_path = "10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html"

    parser = FunctionalCategoriesParser(html_path)
    parser.parse()
    mapping = parser.get_category_mapping()

    # IBody2 should be in Model Interfaces
    assert "SOLIDWORKS.Interop.sldworks.IBody2" in mapping, "Should contain IBody2"
    assert mapping["SOLIDWORKS.Interop.sldworks.IBody2"] == "Model Interfaces", \
        f"IBody2 should be in 'Model Interfaces', got '{mapping.get('SOLIDWORKS.Interop.sldworks.IBody2')}'"

    print("[PASS] Model Interfaces parsed correctly")


def test_type_name_extraction():
    """Test that type names are extracted correctly from hrefs."""
    html_path = "10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html"

    parser = FunctionalCategoriesParser(html_path)

    # Test various href formats
    test_cases = [
        (
            "SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2.html",
            "SOLIDWORKS.Interop.sldworks.IModelDoc2"
        ),
        (
            "../sldworks/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IBody2.html",
            "SOLIDWORKS.Interop.sldworks.IBody2"
        ),
    ]

    for href, expected in test_cases:
        result = parser._extract_type_name_from_href(href)
        assert result == expected, f"Expected '{expected}' from '{href}', got '{result}'"

    print("[PASS] Type name extraction works correctly")


def test_statistics():
    """Test overall statistics of parsed categories."""
    html_path = "10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html"

    parser = FunctionalCategoriesParser(html_path)
    categories = parser.parse()
    mapping = parser.get_category_mapping()

    # Count types by category
    total_types = len(mapping)
    total_categories = len(categories)

    # Count hierarchical categories
    hierarchical = [c for c in categories if '/' in c.name]

    print(f"\n=== Statistics ===")
    print(f"Total categories: {total_categories}")
    print(f"Hierarchical categories: {len(hierarchical)}")
    print(f"Total types: {total_types}")
    print(f"\nTop 5 categories by type count:")

    # Sort categories by type count
    sorted_cats = sorted(categories, key=lambda c: len(c.types), reverse=True)
    for cat in sorted_cats[:5]:
        print(f"  - {cat.name}: {len(cat.types)} types")

    print("[PASS] Statistics generated successfully")


if __name__ == '__main__':
    test_parser_loads_categories()
    test_category_mapping()
    test_hierarchical_subcategories()
    test_parent_types_with_nested_subcategories()
    test_enumeration_interfaces()
    test_drawing_interfaces()
    test_model_interfaces()
    test_type_name_extraction()
    test_statistics()
    print("\n[PASS] All tests passed!")
