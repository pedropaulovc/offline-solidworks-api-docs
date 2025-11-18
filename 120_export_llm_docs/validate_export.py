"""
Validation Script for Phase 120: Export LLM-Friendly Documentation

This script validates the completeness and quality of the exported documentation.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List
from collections import defaultdict


class ExportValidator:
    """Validates the exported documentation."""

    def __init__(self, output_path: str):
        """
        Initialize the validator.

        Args:
            output_path: Path to the output directory
        """
        self.output_path = Path(output_path)
        self.errors = []
        self.warnings = []

    def validate(self) -> bool:
        """
        Run all validation checks.

        Returns:
            True if validation passes, False otherwise
        """
        print("="*80)
        print("Validating Phase 120 Export")
        print("="*80)

        # Check directory structure
        print("\n[1/5] Validating directory structure...")
        self._validate_directory_structure()

        # Check API documentation
        print("\n[2/5] Validating API documentation...")
        self._validate_api_docs()

        # Check example documentation
        print("\n[3/5] Validating example documentation...")
        self._validate_example_docs()

        # Check programming guide
        print("\n[4/5] Validating programming guide...")
        self._validate_programming_guide()

        # Check summary report
        print("\n[5/5] Validating summary report...")
        self._validate_summary_report()

        # Print results
        print("\n" + "="*80)
        print("Validation Results")
        print("="*80)

        if self.errors:
            print(f"\nERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print(f"\nWARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if not self.errors and not self.warnings:
            print("\n[PASS] All validation checks passed!")
            return True
        elif not self.errors:
            print(f"\n[PASS] Validation passed with {len(self.warnings)} warnings")
            return True
        else:
            print(f"\n[FAIL] Validation failed with {len(self.errors)} errors and {len(self.warnings)} warnings")
            return False

    def _validate_directory_structure(self):
        """Validate that the expected directory structure exists."""
        expected_dirs = [
            self.output_path / "api",
            self.output_path / "docs",
            self.output_path / "docs" / "examples",
        ]

        for dir_path in expected_dirs:
            if not dir_path.exists():
                self.errors.append(f"Missing directory: {dir_path}")
            elif not dir_path.is_dir():
                self.errors.append(f"Not a directory: {dir_path}")

        print(f"  Found {len([d for d in expected_dirs if d.exists()])} / {len(expected_dirs)} expected directories")

    def _validate_api_docs(self):
        """Validate API documentation files."""
        api_path = self.output_path / "api"

        if not api_path.exists():
            self.errors.append("API directory does not exist")
            return

        # Count markdown files
        md_files = list(api_path.rglob('*.md'))

        if not md_files:
            self.errors.append("No API documentation files found")
            return

        print(f"  Found {len(md_files)} API documentation files")

        # Check a sample for basic content
        sample_size = min(10, len(md_files))
        for md_file in md_files[:sample_size]:
            self._validate_markdown_file(md_file, "API")

        # Count assemblies and categories
        assemblies = set()
        categories = set()
        for md_file in md_files:
            parts = md_file.relative_to(api_path).parts
            if parts:
                assemblies.add(parts[0])
            if len(parts) > 1:
                categories.add(parts[1])

        print(f"  Found {len(assemblies)} assemblies")
        print(f"  Found {len(categories)} categories")

    def _validate_example_docs(self):
        """Validate example documentation files."""
        examples_path = self.output_path / "docs" / "examples"

        if not examples_path.exists():
            self.errors.append("Examples directory does not exist")
            return

        # Count markdown files
        md_files = list(examples_path.rglob('*.md'))

        if not md_files:
            self.warnings.append("No example documentation files found")
            return

        print(f"  Found {len(md_files)} example documentation files")

        # Check a sample for basic content
        sample_size = min(10, len(md_files))
        for md_file in md_files[:sample_size]:
            self._validate_markdown_file(md_file, "Example")

        # Count categories
        categories = set()
        for md_file in md_files:
            parts = md_file.relative_to(examples_path).parts
            if len(parts) > 1:
                categories.add(parts[0])

        print(f"  Found {len(categories)} example categories")

    def _validate_programming_guide(self):
        """Validate programming guide files."""
        docs_path = self.output_path / "docs"

        if not docs_path.exists():
            self.errors.append("Docs directory does not exist")
            return

        # Count markdown files (excluding examples folder)
        md_files = []
        for md_file in docs_path.rglob('*.md'):
            # Skip files in examples folder
            if 'examples' not in md_file.relative_to(docs_path).parts:
                md_files.append(md_file)

        if not md_files:
            self.warnings.append("No programming guide files found")
            return

        print(f"  Found {len(md_files)} programming guide files")

    def _validate_summary_report(self):
        """Validate the summary report."""
        report_path = self.output_path.parent / "metadata" / "export_summary.json"

        if not report_path.exists():
            self.warnings.append("Summary report not found")
            return

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)

            # Check required fields
            required_fields = ['export_timestamp', 'statistics', 'output_location']
            for field in required_fields:
                if field not in report:
                    self.warnings.append(f"Missing field in summary report: {field}")

            # Print statistics
            if 'statistics' in report:
                stats = report['statistics']
                print(f"  Total types: {stats.get('total_types', 0)}")
                print(f"  Total examples: {stats.get('total_examples', 0)}")
                print(f"  Total files generated: {stats.get('markdown_files_generated', 0)}")

        except json.JSONDecodeError:
            self.errors.append("Summary report is not valid JSON")
        except Exception as e:
            self.errors.append(f"Error reading summary report: {e}")

    def _validate_markdown_file(self, file_path: Path, doc_type: str):
        """
        Validate a markdown file for basic content.

        Args:
            file_path: Path to the markdown file
            doc_type: Type of documentation (API or Example)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for empty files
            if not content.strip():
                self.errors.append(f"Empty {doc_type} file: {file_path}")
                return

            # Check for basic markdown structure
            if not content.startswith('#'):
                self.warnings.append(f"{doc_type} file missing title: {file_path}")

        except Exception as e:
            self.errors.append(f"Error reading {doc_type} file {file_path}: {e}")


def main():
    """Main entry point for the validation script."""
    parser = argparse.ArgumentParser(description='Validate Phase 120 export')
    parser.add_argument(
        '--output',
        default='120_export_llm_docs/output',
        help='Output directory to validate'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print verbose output'
    )

    args = parser.parse_args()

    # Create and run validator
    validator = ExportValidator(output_path=args.output)
    success = validator.validate()

    # Exit with appropriate code
    exit(0 if success else 1)


if __name__ == '__main__':
    main()
