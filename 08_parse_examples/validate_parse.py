"""
Validation script for Phase 06: Parse Examples
Validates the generated XML file contains properly formatted examples.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET


class ValidationReport:
    """Validation report generator."""

    def __init__(self):
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.stats: Dict[str, int] = {}

    def add_issue(self, message: str) -> None:
        """Add a validation issue."""
        self.issues.append(message)

    def add_warning(self, message: str) -> None:
        """Add a warning."""
        self.warnings.append(message)

    def add_stat(self, name: str, value: int) -> None:
        """Add a statistic."""
        self.stats[name] = value

    def is_valid(self) -> bool:
        """Check if validation passed."""
        return len(self.issues) == 0

    def print_report(self, verbose: bool = False) -> None:
        """Print the validation report."""
        print("\n" + "=" * 60)
        print("Validation Report")
        print("=" * 60)
        print()

        # Print statistics
        print("Statistics:")
        for name, value in self.stats.items():
            print(f"  {name}: {value:,}")
        print()

        # Print issues
        if self.issues:
            print(f"Issues Found: {len(self.issues)}")
            for issue in self.issues:
                print(f"  [FAIL] {issue}")
            print()
        else:
            print("[PASS] No issues found!")
            print()

        # Print warnings
        if self.warnings:
            print(f"Warnings: {len(self.warnings)}")
            if verbose:
                for warning in self.warnings:
                    print(f"  [WARN] {warning}")
            else:
                print(f"  (Use --verbose to see all warnings)")
            print()

        # Final verdict
        print("=" * 60)
        if self.is_valid():
            print("VALIDATION PASSED")
        else:
            print("VALIDATION FAILED")
        print("=" * 60)


def validate_xml_structure(xml_file: Path, report: ValidationReport) -> Tuple[ET.Element, bool]:
    """
    Validate that the XML file exists and is well-formed.

    Args:
        xml_file: Path to XML file
        report: Validation report

    Returns:
        Tuple of (root element, success flag)
    """
    # Check file exists
    if not xml_file.exists():
        report.add_issue(f"XML file not found: {xml_file}")
        return None, False

    # Check file size
    file_size = xml_file.stat().st_size
    report.add_stat("File size (bytes)", file_size)

    if file_size == 0:
        report.add_issue("XML file is empty")
        return None, False

    # Try to parse XML
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except ET.ParseError as e:
        report.add_issue(f"XML parse error: {e}")
        return None, False
    except Exception as e:
        report.add_issue(f"Error reading XML: {e}")
        return None, False

    # Check root element
    if root.tag != 'Examples':
        report.add_issue(f"Root element should be 'Examples', found '{root.tag}'")
        return None, False

    return root, True


def validate_examples(root: ET.Element, report: ValidationReport, verbose: bool = False) -> None:
    """
    Validate individual example elements.

    Args:
        root: Root XML element
        report: Validation report
        verbose: Whether to show all warnings
    """
    examples = root.findall('Example')
    report.add_stat("Total examples", len(examples))

    if len(examples) == 0:
        report.add_issue("No examples found in XML")
        return

    # Track statistics
    empty_content_count = 0
    missing_url_count = 0
    missing_content_count = 0
    duplicate_urls = set()
    seen_urls = set()
    short_content_count = 0

    for idx, example in enumerate(examples):
        # Check for Url element
        url_elem = example.find('Url')
        if url_elem is None:
            report.add_issue(f"Example {idx + 1} missing <Url> element")
            missing_url_count += 1
            continue

        url = url_elem.text
        if not url:
            report.add_issue(f"Example {idx + 1} has empty URL")
            missing_url_count += 1
            continue

        # Check for duplicate URLs
        if url in seen_urls:
            if url not in duplicate_urls:
                report.add_warning(f"Duplicate URL: {url}")
                duplicate_urls.add(url)
        seen_urls.add(url)

        # Check for Content element
        content_elem = example.find('Content')
        if content_elem is None:
            report.add_issue(f"Example {idx + 1} ({url}) missing <Content> element")
            missing_content_count += 1
            continue

        content = content_elem.text
        if not content:
            report.add_warning(f"Example {idx + 1} ({url}) has empty content")
            empty_content_count += 1
            continue

        # Check content length
        if len(content.strip()) < 50:
            report.add_warning(f"Example {idx + 1} ({url}) has suspiciously short content ({len(content)} chars)")
            short_content_count += 1

        # Check for <code> tags in content
        if '<code>' not in content and verbose:
            report.add_warning(f"Example {idx + 1} ({url}) has no code blocks")

    # Add statistics
    report.add_stat("Empty content", empty_content_count)
    report.add_stat("Missing URLs", missing_url_count)
    report.add_stat("Missing content", missing_content_count)
    report.add_stat("Duplicate URLs", len(duplicate_urls))
    report.add_stat("Short content", short_content_count)


def validate_against_source(xml_file: Path, source_dir: Path, report: ValidationReport) -> None:
    """
    Validate XML against source HTML files.

    Args:
        xml_file: Path to XML file
        source_dir: Path to source HTML directory
        report: Validation report
    """
    if not source_dir.exists():
        report.add_warning(f"Source directory not found: {source_dir}")
        return

    # Count HTML files in source
    html_files = list(source_dir.rglob('*.htm'))
    source_count = len(html_files)
    report.add_stat("Source HTML files", source_count)

    # Parse XML to get example count
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        example_count = len(root.findall('Example'))

        # Compare counts
        if example_count != source_count:
            report.add_warning(
                f"Example count ({example_count}) doesn't match source file count ({source_count})"
            )

        # Calculate coverage
        coverage = (example_count / source_count * 100) if source_count > 0 else 0
        report.add_stat("Coverage (%)", int(coverage))

    except Exception as e:
        report.add_warning(f"Could not validate against source: {e}")


def validate_metadata(metadata_dir: Path, report: ValidationReport) -> None:
    """
    Validate metadata files.

    Args:
        metadata_dir: Path to metadata directory
        report: Validation report
    """
    # Check parse_stats.json
    stats_file = metadata_dir / 'parse_stats.json'
    if not stats_file.exists():
        report.add_warning(f"Metadata file not found: {stats_file}")
    else:
        try:
            with open(stats_file, 'r') as f:
                stats = json.load(f)

            # Check for expected fields
            expected_fields = ['total_files', 'successful', 'failed', 'empty_content']
            for field in expected_fields:
                if field not in stats:
                    report.add_warning(f"Missing field in parse_stats.json: {field}")

            # Check for failures
            if stats.get('failed', 0) > 0:
                report.add_warning(f"Parse had {stats['failed']} failures")

        except Exception as e:
            report.add_warning(f"Could not read parse_stats.json: {e}")

    # Check manifest.json
    manifest_file = metadata_dir / 'manifest.json'
    if not manifest_file.exists():
        report.add_warning(f"Metadata file not found: {manifest_file}")


def main(verbose: bool = False) -> int:
    """
    Main validation function.

    Args:
        verbose: Show all warnings

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print("=" * 60)
    print("Phase 06: Parse Examples - Validation")
    print("=" * 60)
    print()

    # Get project root
    project_root = Path(__file__).parent.parent

    # Define paths
    xml_file = project_root / '08_parse_examples' / 'output' / 'examples.xml'
    metadata_dir = project_root / '08_parse_examples' / 'metadata'
    source_dir = project_root / '07_crawl_examples' / 'output' / 'html'

    # Create report
    report = ValidationReport()

    # Validate XML structure
    print("Validating XML structure...")
    root, success = validate_xml_structure(xml_file, report)
    if not success:
        report.print_report(verbose)
        return 1

    # Validate examples
    print("Validating example elements...")
    validate_examples(root, report, verbose)

    # Validate against source
    print("Validating against source files...")
    validate_against_source(xml_file, source_dir, report)

    # Validate metadata
    print("Validating metadata...")
    validate_metadata(metadata_dir, report)

    # Print report
    report.print_report(verbose)

    # Return exit code
    return 0 if report.is_valid() else 1


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Validate Phase 06 parsed examples')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show all warnings')

    args = parser.parse_args()

    sys.exit(main(verbose=args.verbose))
