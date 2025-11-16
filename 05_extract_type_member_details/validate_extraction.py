#!/usr/bin/env python3
"""
Validation script for Phase 5: Extract Member Details.

This script validates the extracted member details XML file to ensure:
- XML is well-formed and parseable
- All required fields are present
- Member count matches summary metadata
- Reasonable percentage of members have parameters/returns/remarks
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def validate_xml_structure(xml_file: Path) -> tuple[bool, list[str]]:
    """
    Validate that the XML file is well-formed and has the expected structure.

    Returns:
        (is_valid, error_messages)
    """
    errors = []

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except ET.ParseError as e:
        errors.append(f"XML parsing error: {e}")
        return False, errors

    if root.tag != "Members":
        errors.append(f"Root element should be 'Members', got '{root.tag}'")

    return len(errors) == 0, errors


def validate_member_elements(xml_file: Path) -> tuple[bool, list[str], dict[str, Any]]:
    """
    Validate that member elements have required fields.

    Returns:
        (is_valid, error_messages, statistics)
    """
    errors = []
    stats: dict[str, Any] = {
        "total_members": 0,
        "members_with_assembly": 0,
        "members_with_type": 0,
        "members_with_name": 0,
        "members_with_signature": 0,
        "members_with_description": 0,
        "members_with_parameters": 0,
        "members_with_returns": 0,
        "members_with_remarks": 0,
        "duplicate_members": [],
    }

    tree = ET.parse(xml_file)
    root = tree.getroot()

    seen_members = set()

    for member in root.findall("Member"):
        stats["total_members"] += 1

        # Check required fields
        assembly = member.find("Assembly")
        type_elem = member.find("Type")
        name = member.find("Name")

        if assembly is not None and assembly.text:
            stats["members_with_assembly"] += 1
        else:
            errors.append(f"Member {stats['total_members']} missing Assembly")

        if type_elem is not None and type_elem.text:
            stats["members_with_type"] += 1
        else:
            errors.append(f"Member {stats['total_members']} missing Type")

        if name is not None and name.text:
            stats["members_with_name"] += 1
        else:
            errors.append(f"Member {stats['total_members']} missing Name")

        # Check for duplicates (same Type + Name)
        if type_elem is not None and name is not None and type_elem.text and name.text:
            member_key = (type_elem.text, name.text)
            if member_key in seen_members:
                stats["duplicate_members"].append(f"{type_elem.text}.{name.text}")
            else:
                seen_members.add(member_key)

        # Check optional but expected fields
        if member.find("Signature") is not None and member.find("Signature").text:
            stats["members_with_signature"] += 1

        if member.find("Description") is not None and member.find("Description").text:
            stats["members_with_description"] += 1

        if member.find("Parameters") is not None:
            stats["members_with_parameters"] += 1

        if member.find("Returns") is not None and member.find("Returns").text:
            stats["members_with_returns"] += 1

        if member.find("Remarks") is not None and member.find("Remarks").text:
            stats["members_with_remarks"] += 1

    return len(errors) == 0, errors, stats


def validate_against_summary(xml_file: Path, summary_file: Path) -> tuple[bool, list[str]]:
    """
    Validate that XML member count matches the summary metadata.

    Returns:
        (is_valid, error_messages)
    """
    errors = []

    if not summary_file.exists():
        errors.append(f"Summary file not found: {summary_file}")
        return False, errors

    with open(summary_file) as f:
        summary = json.load(f)

    tree = ET.parse(xml_file)
    root = tree.getroot()
    member_count = len(root.findall("Member"))

    expected_count = summary.get("members_extracted", 0)
    if member_count != expected_count:
        errors.append(f"Member count mismatch: XML has {member_count}, summary says {expected_count}")

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate extracted member details")
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=Path("05_extract_type_member_details/metadata"),
        help="Directory containing extraction output",
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed validation results")

    args = parser.parse_args()

    xml_file = args.metadata_dir / "api_member_details.xml"
    summary_file = args.metadata_dir / "extraction_summary.json"

    if not xml_file.exists():
        print(f"❌ Error: XML file not found: {xml_file}")
        print("   Run extract_member_details.py first")
        return 1

    print("Validating Phase 5: Extract Member Details")
    print("=" * 60)

    all_valid = True

    # 1. Validate XML structure
    print("\n1. Checking XML structure...")
    is_valid, errors = validate_xml_structure(xml_file)
    if is_valid:
        print("   ✅ XML is well-formed")
    else:
        print("   ❌ XML structure validation failed:")
        for error in errors:
            print(f"      - {error}")
        all_valid = False

    # 2. Validate member elements
    print("\n2. Checking member elements...")
    is_valid, errors, stats = validate_member_elements(xml_file)
    if is_valid:
        print("   ✅ All members have required fields")
    else:
        print("   ❌ Member validation failed:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"      - {error}")
        if len(errors) > 10:
            print(f"      ... and {len(errors) - 10} more errors")
        all_valid = False

    # Show statistics
    print("\n3. Member statistics:")
    print(f"   Total members: {stats['total_members']}")
    print(f"   Members with assembly: {stats['members_with_assembly']} ({stats['members_with_assembly'] / max(stats['total_members'], 1) * 100:.1f}%)")
    print(f"   Members with type: {stats['members_with_type']} ({stats['members_with_type'] / max(stats['total_members'], 1) * 100:.1f}%)")
    print(f"   Members with name: {stats['members_with_name']} ({stats['members_with_name'] / max(stats['total_members'], 1) * 100:.1f}%)")
    print(f"   Members with signature: {stats['members_with_signature']} ({stats['members_with_signature'] / max(stats['total_members'], 1) * 100:.1f}%)")
    print(f"   Members with description: {stats['members_with_description']} ({stats['members_with_description'] / max(stats['total_members'], 1) * 100:.1f}%)")
    print(f"   Members with parameters: {stats['members_with_parameters']} ({stats['members_with_parameters'] / max(stats['total_members'], 1) * 100:.1f}%)")
    print(f"   Members with return values: {stats['members_with_returns']} ({stats['members_with_returns'] / max(stats['total_members'], 1) * 100:.1f}%)")
    print(f"   Members with remarks: {stats['members_with_remarks']} ({stats['members_with_remarks'] / max(stats['total_members'], 1) * 100:.1f}%)")

    if stats["duplicate_members"]:
        print(f"\n   ⚠️  Warning: Found {len(stats['duplicate_members'])} duplicate members")
        if args.verbose:
            for dup in stats["duplicate_members"][:10]:
                print(f"      - {dup}")
            if len(stats["duplicate_members"]) > 10:
                print(f"      ... and {len(stats['duplicate_members']) - 10} more")

    # 4. Validate against summary
    print("\n4. Checking against summary metadata...")
    is_valid, errors = validate_against_summary(xml_file, summary_file)
    if is_valid:
        print("   ✅ Member count matches summary")
    else:
        print("   ❌ Summary validation failed:")
        for error in errors:
            print(f"      - {error}")
        all_valid = False

    # 5. Validate reasonable coverage
    print("\n5. Checking coverage...")
    warnings = []

    # At least 80% should have descriptions
    desc_percentage = stats["members_with_description"] / max(stats["total_members"], 1) * 100
    if desc_percentage < 80:
        warnings.append(f"Only {desc_percentage:.1f}% of members have descriptions (expected >80%)")

    # At least 60% should have signatures
    sig_percentage = stats["members_with_signature"] / max(stats["total_members"], 1) * 100
    if sig_percentage < 60:
        warnings.append(f"Only {sig_percentage:.1f}% of members have signatures (expected >60%)")

    if warnings:
        print("   ⚠️  Coverage warnings:")
        for warning in warnings:
            print(f"      - {warning}")
    else:
        print("   ✅ Coverage looks good")

    # Final summary
    print("\n" + "=" * 60)
    if all_valid:
        print("✅ All validation checks passed!")
        return 0
    else:
        print("❌ Validation failed - see errors above")
        return 1


if __name__ == "__main__":
    exit(main())
