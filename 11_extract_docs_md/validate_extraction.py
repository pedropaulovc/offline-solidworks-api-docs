"""Validation script for Phase 11 markdown extraction."""

import json
import jsonlines
import sys
from datetime import datetime, timezone
from pathlib import Path


class ExtractionValidator:
    """Validate Phase 11 markdown extraction results."""

    def __init__(
        self,
        output_dir: Path = Path("11_extract_docs_md/output/markdown"),
        metadata_dir: Path = Path("11_extract_docs_md/metadata"),
        verbose: bool = False,
    ) -> None:
        """Initialize the validator.

        Args:
            output_dir: Output directory containing Markdown files
            metadata_dir: Directory containing metadata files
            verbose: Whether to print verbose output
        """
        self.output_dir = output_dir
        self.metadata_dir = metadata_dir
        self.verbose = verbose

        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate(self) -> bool:
        """Run all validation checks.

        Returns:
            True if validation passed, False otherwise
        """
        print("Validating Phase 11: Extract Documentation to Markdown")
        print("=" * 60)

        # Check directories exist
        if not self._check_directories():
            return False

        # Load and validate metadata
        if not self._validate_metadata():
            return False

        # Validate markdown files
        if not self._validate_markdown_files():
            return False

        # Validate file structure
        if not self._validate_file_structure():
            return False

        # Print summary
        self._print_summary()

        return len(self.errors) == 0

    def _check_directories(self) -> bool:
        """Check that required directories exist."""
        print("\n1. Checking directories...")

        if not self.output_dir.exists():
            self.errors.append(f"Output directory not found: {self.output_dir}")
            return False

        if not self.metadata_dir.exists():
            self.errors.append(f"Metadata directory not found: {self.metadata_dir}")
            return False

        print("   [OK] All directories exist")
        return True

    def _validate_metadata(self) -> bool:
        """Validate metadata files."""
        print("\n2. Validating metadata...")

        # Check required files
        required_files = [
            "files_created.jsonl",
            "extraction_stats.json",
            "manifest.json",
        ]

        for filename in required_files:
            filepath = self.metadata_dir / filename
            if not filepath.exists():
                self.errors.append(f"Required metadata file not found: {filename}")
                return False

        # Load and check extraction stats
        stats_path = self.metadata_dir / "extraction_stats.json"
        with stats_path.open(encoding="utf-8") as f:
            stats = json.load(f)

        total_nodes = stats.get("total_nodes", 0)
        converted = stats.get("converted_files", 0)
        failed = stats.get("failed_files", 0)

        print(f"   Total nodes: {total_nodes}")
        print(f"   Converted files: {converted}")
        print(f"   Failed files: {failed}")

        # Expect 125 content pages (145 nodes - 20 TOC pages)
        expected_min = 120  # 95% of expected

        if converted < expected_min:
            self.errors.append(
                f"Too few files converted: {converted} < {expected_min} (expected ~125)"
            )

        if failed > 5:  # Allow up to 5 failures
            self.errors.append(f"Too many failed files: {failed} > 5")

        # Check success rate
        if converted > 0:
            success_rate = converted / (converted + failed) * 100
            print(f"   Success rate: {success_rate:.1f}%")

            if success_rate < 95:
                self.errors.append(f"Success rate too low: {success_rate:.1f}% < 95%")

        if self.errors:
            return False

        print("   [OK] Metadata validation passed")
        return True

    def _validate_markdown_files(self) -> bool:
        """Validate markdown files."""
        print("\n3. Validating markdown files...")

        # Load files_created metadata
        files_created_path = self.metadata_dir / "files_created.jsonl"
        with jsonlines.open(files_created_path) as reader:
            files_created = list(reader)

        print(f"   Checking {len(files_created)} files...")

        missing_files = []
        empty_files = []

        for entry in files_created:
            markdown_path = entry.get("markdown_path", "")
            if not markdown_path:
                continue

            # Convert relative path to absolute
            full_path = Path(markdown_path)
            if not full_path.is_absolute():
                full_path = Path.cwd() / markdown_path

            # Check file exists
            if not full_path.exists():
                missing_files.append(markdown_path)
                continue

            # Check file is not empty
            if full_path.stat().st_size == 0:
                empty_files.append(markdown_path)

        if missing_files:
            self.errors.append(f"Missing {len(missing_files)} markdown files")
            if self.verbose:
                for f in missing_files[:10]:  # Show first 10
                    print(f"      Missing: {f}")

        if empty_files:
            self.warnings.append(f"Found {len(empty_files)} empty markdown files")
            if self.verbose:
                for f in empty_files[:10]:  # Show first 10
                    print(f"      Empty: {f}")

        if self.errors:
            return False

        print(f"   [OK] All markdown files validated")
        return True

    def _validate_file_structure(self) -> bool:
        """Validate hierarchical file structure."""
        print("\n4. Validating file structure...")

        # Count markdown files
        md_files = list(self.output_dir.rglob("*.md"))
        print(f"   Found {len(md_files)} markdown files")

        # Check for expected top-level directories
        expected_dirs = [
            "Overview",
            "SOLIDWORKS Partner Program",
            "Types of SOLIDWORKS API Applications",
            "SOLIDWORKS API Object Model and Class Hierarchy",
            "Programming with the SOLIDWORKS API",
        ]

        found_dirs = [d.name for d in self.output_dir.iterdir() if d.is_dir()]

        for expected_dir in expected_dirs:
            if expected_dir not in found_dirs:
                self.warnings.append(f"Expected directory not found: {expected_dir}")

        if self.verbose:
            print("\n   Top-level structure:")
            for item in sorted(self.output_dir.iterdir()):
                if item.is_dir():
                    count = len(list(item.rglob("*.md")))
                    print(f"      {item.name}/ ({count} files)")
                else:
                    print(f"      {item.name}")

        print(f"   [OK] File structure validated")
        return True

    def _print_summary(self) -> None:
        """Print validation summary."""
        print("\n" + "=" * 60)

        if self.errors:
            print(f"VALIDATION FAILED with {len(self.errors)} error(s)")
            for error in self.errors:
                print(f"  [ERROR] {error}")
        else:
            print("VALIDATION PASSED")

        if self.warnings:
            print(f"\nWarnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"  [WARN] {warning}")

    def save_report(self) -> None:
        """Save validation report to file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = self.metadata_dir / f"validation_report_{timestamp}.json"

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "passed": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
        }

        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print(f"\nValidation report saved to: {report_path}")


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate Phase 11 markdown extraction")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print verbose output",
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save validation report to file",
    )

    args = parser.parse_args()

    validator = ExtractionValidator(verbose=args.verbose)
    passed = validator.validate()

    if args.save_report:
        validator.save_report()

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
