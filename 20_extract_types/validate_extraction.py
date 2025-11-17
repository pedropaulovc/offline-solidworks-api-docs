#!/usr/bin/env python3
"""
Validate the extracted API members XML file.

This script performs various validation checks on the generated XML file
to ensure data quality and completeness.
"""

import argparse
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any


def load_xml(xml_file: Path) -> ET.Element | None:
    """Load and parse the XML file."""
    try:
        tree = ET.parse(xml_file)
        return tree.getroot()
    except Exception as e:
        print(f"Error loading XML: {e}")
        return None


def validate_structure(root: ET.Element) -> dict[str, Any]:
    """Validate the basic XML structure."""
    results: dict[str, Any] = {"valid": True, "errors": [], "warnings": []}

    if root.tag != "Types":
        results["valid"] = False
        results["errors"].append("Root element should be 'Types'")
        return results

    types = root.findall("Type")
    if not types:
        results["valid"] = False
        results["errors"].append("No Type elements found")
        return results

    # Check each type
    for i, type_elem in enumerate(types):
        name_elem = type_elem.find("Name")
        if name_elem is None:
            results["warnings"].append(f"Type at index {i} has no Name element")
        elif not name_elem.text or not name_elem.text.strip():
            results["warnings"].append(f"Type at index {i} has empty Name")

    return results


def analyze_types(root: ET.Element) -> dict[str, Any]:
    """Analyze the extracted types."""
    stats: dict[str, Any] = {
        "total_types": 0,
        "types_with_properties": 0,
        "types_with_methods": 0,
        "types_with_no_members": 0,
        "total_properties": 0,
        "total_methods": 0,
        "type_names": [],
    }

    for type_elem in root.findall("Type"):
        stats["total_types"] += 1

        name_elem = type_elem.find("Name")
        if name_elem is not None and name_elem.text:
            stats["type_names"].append(name_elem.text)

        props = type_elem.find("PublicProperties")
        methods = type_elem.find("PublicMethods")

        has_props = props is not None and len(props.findall("Property")) > 0
        has_methods = methods is not None and len(methods.findall("Method")) > 0

        if has_props and props is not None:
            stats["types_with_properties"] += 1
            stats["total_properties"] += len(props.findall("Property"))

        if has_methods and methods is not None:
            stats["types_with_methods"] += 1
            stats["total_methods"] += len(methods.findall("Method"))

        if not has_props and not has_methods:
            stats["types_with_no_members"] += 1

    return stats


def check_duplicates(root: ET.Element) -> dict[str, Any]:
    """Check for duplicate type names."""
    type_names: list[str] = []
    for type_elem in root.findall("Type"):
        name_elem = type_elem.find("Name")
        if name_elem is not None and name_elem.text:
            type_names.append(name_elem.text)

    counter = Counter(type_names)
    duplicates = {name: count for name, count in counter.items() if count > 1}

    return {"has_duplicates": len(duplicates) > 0, "duplicates": duplicates, "unique_types": len(counter)}


def check_url_format(root: ET.Element) -> dict[str, Any]:
    """Check that URLs follow expected format."""
    issues: list[str] = []
    total_urls: int = 0

    for type_elem in root.findall("Type"):
        type_name = type_elem.find("Name")
        type_name_text = type_name.text if type_name is not None else "Unknown"

        # Check property URLs
        props = type_elem.find("PublicProperties")
        if props is not None:
            for prop in props.findall("Property"):
                url_elem = prop.find("Url")
                if url_elem is not None and url_elem.text:
                    total_urls += 1
                    if not url_elem.text.endswith(".html"):
                        issues.append(f"{type_name_text}: Property URL doesn't end with .html: {url_elem.text}")

        # Check method URLs
        methods = type_elem.find("PublicMethods")
        if methods is not None:
            for method in methods.findall("Method"):
                url_elem = method.find("Url")
                if url_elem is not None and url_elem.text:
                    total_urls += 1
                    if not url_elem.text.endswith(".html"):
                        issues.append(f"{type_name_text}: Method URL doesn't end with .html: {url_elem.text}")

    return {"total_urls": total_urls, "issues": issues, "all_valid": len(issues) == 0}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate extracted API members XML")
    parser.add_argument(
        "--xml-file",
        type=Path,
        default=Path("20_extract_types/metadata/api_members.xml"),
        help="Path to the XML file to validate",
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed validation results")
    parser.add_argument("--output", type=Path, help="Save validation report to JSON file")

    args = parser.parse_args()

    if not args.xml_file.exists():
        print(f"Error: XML file not found: {args.xml_file}")
        return 1

    print(f"Validating {args.xml_file}...")
    print()

    # Load XML
    root = load_xml(args.xml_file)
    if root is None:
        return 1

    # Run validations
    validation_report = {}

    # 1. Structure validation
    print("1. Validating XML structure...")
    structure = validate_structure(root)
    validation_report["structure"] = structure

    if not structure["valid"]:
        print("   [FAILED]")
        for error in structure["errors"]:
            print(f"      - {error}")
    else:
        print("   [OK] Valid structure")
        if structure["warnings"] and args.verbose:
            for warning in structure["warnings"]:
                print(f"      Warning: {warning}")

    # 2. Type analysis
    print("\n2. Analyzing types...")
    stats = analyze_types(root)
    validation_report["statistics"] = stats

    print(f"   Total types: {stats['total_types']}")
    print(f"   Types with properties: {stats['types_with_properties']}")
    print(f"   Types with methods: {stats['types_with_methods']}")
    print(f"   Types with no members: {stats['types_with_no_members']}")
    print(f"   Total properties: {stats['total_properties']}")
    print(f"   Total methods: {stats['total_methods']}")

    # 3. Duplicate check
    print("\n3. Checking for duplicates...")
    duplicates = check_duplicates(root)
    validation_report["duplicates"] = duplicates

    print(f"   Unique type names: {duplicates['unique_types']}")
    if duplicates["has_duplicates"]:
        print(f"   Warning: Found {len(duplicates['duplicates'])} duplicate type names:")
        if args.verbose:
            for name, count in duplicates["duplicates"].items():
                print(f"      - {name}: {count} occurrences")
    else:
        print("   [OK] No duplicates found")

    # 4. URL format check
    print("\n4. Validating URL formats...")
    url_check = check_url_format(root)
    validation_report["urls"] = url_check

    print(f"   Total URLs checked: {url_check['total_urls']}")
    if url_check["all_valid"]:
        print("   [OK] All URLs are valid")
    else:
        print(f"   Warning: Found {len(url_check['issues'])} URL issues")
        if args.verbose:
            for issue in url_check["issues"][:10]:  # Show first 10
                print(f"      - {issue}")

    # Save report if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(validation_report, f, indent=2)
        print(f"\nValidation report saved to: {args.output}")

    print("\n" + "=" * 60)
    if structure["valid"] and url_check["all_valid"]:
        print("Validation PASSED")
        return 0
    else:
        print("Validation completed with warnings")
        return 0


if __name__ == "__main__":
    exit(main())
