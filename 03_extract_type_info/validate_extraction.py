#!/usr/bin/env python3
"""
Validate type information extraction results.

Performs sanity checks on the extracted type information XML.
"""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def validate_xml_structure(xml_file: Path) -> dict[str, Any]:
    """
    Validate that the XML file is well-formed and has expected structure.

    Returns:
        Dictionary with validation results
    """
    results: dict[str, Any] = {
        "valid_xml": False,
        "has_root": False,
        "type_count": 0,
        "types_with_description": 0,
        "types_with_examples": 0,
        "types_with_remarks": 0,
        "total_examples": 0,
        "issues": [],
    }

    try:
        tree = ET.parse(xml_file)
        results["valid_xml"] = True

        root = tree.getroot()
        if root.tag == "Types":
            results["has_root"] = True

        # Count and validate types
        for type_elem in root.findall("Type"):
            results["type_count"] += 1

            # Check required fields
            name = type_elem.find("Name")
            if name is None or not name.text:
                results["issues"].append(f"Type at position {results['type_count']} missing name")

            assembly = type_elem.find("Assembly")
            if assembly is None or not assembly.text:
                results["issues"].append(f"Type {name.text if name is not None else 'Unknown'} missing assembly")

            namespace = type_elem.find("Namespace")
            if namespace is None or not namespace.text:
                results["issues"].append(f"Type {name.text if name is not None else 'Unknown'} missing namespace")

            # Check optional fields
            description = type_elem.find("Description")
            if description is not None and description.text:
                results["types_with_description"] += 1

            examples = type_elem.find("Examples")
            if examples is not None:
                example_count = len(examples.findall("Example"))
                if example_count > 0:
                    results["types_with_examples"] += 1
                    results["total_examples"] += example_count

            remarks = type_elem.find("Remarks")
            if remarks is not None and remarks.text:
                results["types_with_remarks"] += 1

    except ET.ParseError as e:
        results["issues"].append(f"XML parsing error: {e}")
    except Exception as e:
        results["issues"].append(f"Validation error: {e}")

    return results


def validate_summary(summary_file: Path) -> dict[str, Any]:
    """
    Validate the extraction summary metadata.

    Returns:
        Dictionary with validation results
    """
    results: dict[str, Any] = {
        "valid_json": False,
        "has_required_fields": False,
        "total_files": 0,
        "types_extracted": 0,
        "error_count": 0,
        "issues": [],
    }

    try:
        with open(summary_file, encoding="utf-8") as f:
            summary = json.load(f)

        results["valid_json"] = True

        # Check required fields
        required_fields = ["total_files_processed", "types_extracted", "errors", "output_file"]
        if all(field in summary for field in required_fields):
            results["has_required_fields"] = True
            results["total_files"] = summary["total_files_processed"]
            results["types_extracted"] = summary["types_extracted"]
            results["error_count"] = summary["errors"]
        else:
            missing = [f for f in required_fields if f not in summary]
            results["issues"].append(f"Missing required fields: {missing}")

    except json.JSONDecodeError as e:
        results["issues"].append(f"JSON parsing error: {e}")
    except Exception as e:
        results["issues"].append(f"Summary validation error: {e}")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate type information extraction results")
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=Path("03_extract_type_info/metadata"),
        help="Directory containing extraction metadata",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    xml_file = args.metadata_dir / "api_types.xml"
    summary_file = args.metadata_dir / "extraction_summary.json"

    print("Validating type extraction results...")
    print(f"  XML file: {xml_file}")
    print(f"  Summary file: {summary_file}")
    print()

    # Validate XML
    if not xml_file.exists():
        print(f"ERROR: XML file not found: {xml_file}")
        return 1

    print("Validating XML structure...")
    xml_results = validate_xml_structure(xml_file)

    if not xml_results["valid_xml"]:
        print("  [FAIL] XML is not well-formed")
        for issue in xml_results["issues"]:
            print(f"    - {issue}")
        return 1

    print("  [PASS] XML is well-formed")
    print(f"  [PASS] Root element: {'Types' if xml_results['has_root'] else 'INVALID'}")
    print(f"  [INFO] Type count: {xml_results['type_count']}")
    print(
        f"  [INFO] Types with description: {xml_results['types_with_description']} ({100 * xml_results['types_with_description'] // xml_results['type_count'] if xml_results['type_count'] > 0 else 0}%)"
    )
    print(
        f"  [INFO] Types with examples: {xml_results['types_with_examples']} ({100 * xml_results['types_with_examples'] // xml_results['type_count'] if xml_results['type_count'] > 0 else 0}%)"
    )
    print(f"  [INFO] Total examples: {xml_results['total_examples']}")
    print(
        f"  [INFO] Types with remarks: {xml_results['types_with_remarks']} ({100 * xml_results['types_with_remarks'] // xml_results['type_count'] if xml_results['type_count'] > 0 else 0}%)"
    )

    if xml_results["issues"]:
        print(f"  [WARN] Issues found: {len(xml_results['issues'])}")
        if args.verbose:
            for issue in xml_results["issues"]:
                print(f"    - {issue}")

    print()

    # Validate summary
    if not summary_file.exists():
        print(f"ERROR: Summary file not found: {summary_file}")
        return 1

    print("Validating extraction summary...")
    summary_results = validate_summary(summary_file)

    if not summary_results["valid_json"]:
        print("  [FAIL] Summary is not valid JSON")
        for issue in summary_results["issues"]:
            print(f"    - {issue}")
        return 1

    print("  [PASS] Summary is valid JSON")
    print(f"  [PASS] Has required fields: {summary_results['has_required_fields']}")
    print(f"  [INFO] Total files processed: {summary_results['total_files']}")
    print(f"  [INFO] Types extracted: {summary_results['types_extracted']}")
    print(f"  [INFO] Errors: {summary_results['error_count']}")

    if summary_results["issues"]:
        print(f"  [WARN] Issues found: {len(summary_results['issues'])}")
        for issue in summary_results["issues"]:
            print(f"    - {issue}")

    print()

    # Cross-validate
    print("Cross-validation...")
    if xml_results["type_count"] == summary_results["types_extracted"]:
        print(f"  [PASS] Type count matches summary ({xml_results['type_count']})")
    else:
        print(
            f"  [FAIL] Type count mismatch: XML={xml_results['type_count']}, Summary={summary_results['types_extracted']}"
        )
        return 1

    # Overall assessment
    print()
    print("=" * 60)
    if xml_results["valid_xml"] and summary_results["valid_json"] and not xml_results["issues"]:
        print("[PASS] Validation PASSED")
        print()
        print(f"Successfully extracted {xml_results['type_count']} types")
        print(f"  - {xml_results['types_with_description']} with descriptions")
        print(f"  - {xml_results['types_with_examples']} with examples ({xml_results['total_examples']} total)")
        print(f"  - {xml_results['types_with_remarks']} with remarks")
        return 0
    else:
        print("[WARN] Validation completed with issues")
        return 1


if __name__ == "__main__":
    exit(main())
