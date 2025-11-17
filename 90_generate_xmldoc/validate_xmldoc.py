#!/usr/bin/env python3
"""
Validation script for generated XMLDoc files.

This script validates that the XMLDoc files are:
- Well-formed XML
- Follow XMLDoc format conventions
- Have proper ID strings
- Contain expected content

Usage:
    uv run python 90_generate_xmldoc/validate_xmldoc.py
    uv run python 90_generate_xmldoc/validate_xmldoc.py --verbose
"""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationIssue:
    """Represents a validation issue."""
    severity: str  # 'error', 'warning', 'info'
    category: str
    message: str
    file: str = ''


@dataclass
class ValidationResult:
    """Results from validation."""
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


class XMLDocValidator:
    """
    Validates generated XMLDoc files.
    """

    # Valid ID prefixes
    VALID_PREFIXES = {'T:', 'P:', 'M:', 'F:', 'E:', 'N:', '!:'}

    def __init__(self, output_dir: Path, verbose: bool = False):
        """
        Initialize the validator.

        Args:
            output_dir: Directory containing XMLDoc files
            verbose: If True, print all issues including info
        """
        self.output_dir = output_dir
        self.verbose = verbose
        self.result = ValidationResult(passed=True)

    def add_issue(self, severity: str, category: str, message: str, file: str = '') -> None:
        """Add a validation issue."""
        self.result.issues.append(ValidationIssue(
            severity=severity,
            category=category,
            message=message,
            file=file
        ))

        if severity == 'error':
            self.result.passed = False

    def validate_all(self) -> ValidationResult:
        """
        Validate all XMLDoc files in the output directory.

        Returns:
            ValidationResult with findings
        """
        print("=== XMLDoc Validator ===\n")

        # Find all XML files
        xml_files = list(self.output_dir.glob('*.xml'))

        if not xml_files:
            self.add_issue('error', 'files', f"No XML files found in {self.output_dir}")
            return self.result

        print(f"Found {len(xml_files)} XML files\n")
        self.result.stats['total_files'] = len(xml_files)

        # Validate each file
        for xml_file in xml_files:
            print(f"Validating {xml_file.name}...")
            self.validate_file(xml_file)

        return self.result

    def validate_file(self, xml_file: Path) -> None:
        """
        Validate a single XMLDoc file.

        Args:
            xml_file: Path to the XML file
        """
        file_stats = {
            'total_members': 0,
            'types': 0,
            'properties': 0,
            'methods': 0,
            'fields': 0,
            'events': 0,
            'members_with_summary': 0,
            'members_with_remarks': 0,
        }

        try:
            # Parse XML
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Validate root element
            if root.tag != 'doc':
                self.add_issue('error', 'structure',
                             f"Root element should be 'doc', found '{root.tag}'",
                             xml_file.name)
                return

            # Validate assembly element
            assembly_elem = root.find('assembly')
            if assembly_elem is None:
                self.add_issue('error', 'structure',
                             "Missing <assembly> element",
                             xml_file.name)
                return

            assembly_name = assembly_elem.findtext('name', '').strip()
            if not assembly_name:
                self.add_issue('error', 'structure',
                             "Missing assembly name",
                             xml_file.name)
                return

            # Validate members element
            members_elem = root.find('members')
            if members_elem is None:
                self.add_issue('error', 'structure',
                             "Missing <members> element",
                             xml_file.name)
                return

            # Validate each member
            for member_elem in members_elem.findall('member'):
                self.validate_member(member_elem, xml_file.name, file_stats)

            # Check file statistics
            file_stats['total_members'] = (
                file_stats['types'] +
                file_stats['properties'] +
                file_stats['methods'] +
                file_stats['fields'] +
                file_stats['events']
            )

            if file_stats['total_members'] == 0:
                self.add_issue('warning', 'content',
                             "File contains no members",
                             xml_file.name)

            # Store file stats
            self.result.stats[xml_file.name] = file_stats

        except ET.ParseError as e:
            self.add_issue('error', 'xml',
                         f"XML parse error: {e}",
                         xml_file.name)
        except Exception as e:
            self.add_issue('error', 'validation',
                         f"Validation error: {e}",
                         xml_file.name)

    def validate_member(self, member_elem: ET.Element, filename: str,
                       stats: dict) -> None:
        """
        Validate a single member element.

        Args:
            member_elem: The <member> element
            filename: Name of the file being validated
            stats: Statistics dictionary to update
        """
        # Check for name attribute
        member_id = member_elem.get('name', '').strip()
        if not member_id:
            self.add_issue('error', 'id',
                         "Member missing 'name' attribute",
                         filename)
            return

        # Validate ID prefix
        prefix_valid = False
        for prefix in self.VALID_PREFIXES:
            if member_id.startswith(prefix):
                prefix_valid = True
                # Update statistics based on prefix
                if prefix == 'T:':
                    stats['types'] += 1
                elif prefix == 'P:':
                    stats['properties'] += 1
                elif prefix == 'M:':
                    stats['methods'] += 1
                elif prefix == 'F:':
                    stats['fields'] += 1
                elif prefix == 'E:':
                    stats['events'] += 1
                break

        if not prefix_valid:
            self.add_issue('error', 'id',
                         f"Invalid ID prefix in '{member_id}'",
                         filename)

        # Validate ID format
        if ':' in member_id:
            fqn = member_id.split(':', 1)[1]

            # Check for invalid characters (spaces, etc.)
            if ' ' in fqn:
                self.add_issue('error', 'id',
                             f"ID contains whitespace: '{member_id}'",
                             filename)

            # Check for empty namespace/type/member names
            if '..' in fqn or fqn.startswith('.') or fqn.endswith('.'):
                self.add_issue('error', 'id',
                             f"Invalid ID format (empty component): '{member_id}'",
                             filename)

        # Check for summary element
        summary = member_elem.find('summary')
        if summary is not None:
            stats['members_with_summary'] += 1

            # Check if summary is not empty
            if not (summary.text or '').strip():
                self.add_issue('warning', 'content',
                             f"Empty summary for {member_id}",
                             filename)
        else:
            self.add_issue('info', 'content',
                         f"No summary for {member_id}",
                         filename)

        # Check for remarks element
        remarks = member_elem.find('remarks')
        if remarks is not None:
            stats['members_with_remarks'] += 1

    def print_report(self) -> None:
        """Print validation report."""
        print("\n=== Validation Report ===\n")

        # Print overall statistics
        print("Overall Statistics:")
        if 'total_files' in self.result.stats:
            print(f"  Total files: {self.result.stats['total_files']}")

        # Aggregate member statistics
        total_members = 0
        total_types = 0
        total_properties = 0
        total_methods = 0
        total_fields = 0
        total_events = 0
        total_with_summary = 0
        total_with_remarks = 0

        for filename, stats in self.result.stats.items():
            if isinstance(stats, dict) and 'total_members' in stats:
                total_members += stats['total_members']
                total_types += stats['types']
                total_properties += stats['properties']
                total_methods += stats['methods']
                total_fields += stats['fields']
                total_events += stats['events']
                total_with_summary += stats['members_with_summary']
                total_with_remarks += stats['members_with_remarks']

        print(f"  Total members: {total_members}")
        print(f"    Types: {total_types}")
        print(f"    Properties: {total_properties}")
        print(f"    Methods: {total_methods}")
        print(f"    Fields: {total_fields}")
        print(f"    Events: {total_events}")

        if total_members > 0:
            summary_pct = (total_with_summary / total_members) * 100
            remarks_pct = (total_with_remarks / total_members) * 100
            print(f"  Members with summary: {total_with_summary} ({summary_pct:.1f}%)")
            print(f"  Members with remarks: {total_with_remarks} ({remarks_pct:.1f}%)")

        # Print issues by severity
        errors = [i for i in self.result.issues if i.severity == 'error']
        warnings = [i for i in self.result.issues if i.severity == 'warning']
        infos = [i for i in self.result.issues if i.severity == 'info']

        print(f"\nIssues Found:")
        print(f"  Errors: {len(errors)}")
        print(f"  Warnings: {len(warnings)}")
        print(f"  Info: {len(infos)}")

        # Print error details
        if errors:
            print("\nErrors:")
            for issue in errors:
                file_str = f" ({issue.file})" if issue.file else ""
                print(f"  [{issue.category}]{file_str} {issue.message}")

        # Print warning details
        if warnings:
            print("\nWarnings:")
            for issue in warnings[:10]:  # Limit to first 10
                file_str = f" ({issue.file})" if issue.file else ""
                print(f"  [{issue.category}]{file_str} {issue.message}")

            if len(warnings) > 10:
                print(f"  ... and {len(warnings) - 10} more warnings")

        # Print info details if verbose
        if self.verbose and infos:
            print("\nInfo:")
            for issue in infos[:20]:  # Limit to first 20
                file_str = f" ({issue.file})" if issue.file else ""
                print(f"  [{issue.category}]{file_str} {issue.message}")

            if len(infos) > 20:
                print(f"  ... and {len(infos) - 20} more info messages")

        # Print overall result
        print("\n" + "=" * 50)
        if self.result.passed:
            print("✓ VALIDATION PASSED")
            if warnings:
                print(f"  (with {len(warnings)} warnings)")
        else:
            print("✗ VALIDATION FAILED")
            print(f"  Found {len(errors)} errors")


def main() -> None:
    """Main entry point for validation."""
    parser = argparse.ArgumentParser(
        description='Validate generated XMLDoc files',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('90_generate_xmldoc/output'),
        help='Directory containing XMLDoc files'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print all issues including info messages'
    )

    parser.add_argument(
        '--save-report',
        type=Path,
        help='Save validation report to JSON file'
    )

    args = parser.parse_args()

    # Validate
    validator = XMLDocValidator(args.output_dir, verbose=args.verbose)
    result = validator.validate_all()
    validator.print_report()

    # Save report if requested
    if args.save_report:
        report = {
            'passed': result.passed,
            'stats': result.stats,
            'issues': [
                {
                    'severity': i.severity,
                    'category': i.category,
                    'message': i.message,
                    'file': i.file
                }
                for i in result.issues
            ]
        }

        args.save_report.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f"\nReport saved to {args.save_report}")

    # Exit with appropriate code
    exit(0 if result.passed else 1)


if __name__ == '__main__':
    main()
