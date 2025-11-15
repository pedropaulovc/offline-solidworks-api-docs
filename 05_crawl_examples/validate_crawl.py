#!/usr/bin/env python
"""
Validation script for the SolidWorks API examples crawler.

This script validates the completeness and correctness of the crawled
example pages from phase 05.

Usage:
    python 05_crawl_examples/validate_crawl.py [options]

Options:
    --verbose    Print detailed validation information
    --report     Generate detailed JSON report
    --help       Show this help message
"""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonlines


class CrawlValidator:
    """Validator for example pages crawl results"""

    def __init__(self, metadata_dir: Path, output_dir: Path, verbose: bool = False):
        self.metadata_dir = metadata_dir
        self.output_dir = output_dir
        self.verbose = verbose

        # Files to check
        self.urls_file = metadata_dir / "urls_crawled.jsonl"
        self.errors_file = metadata_dir / "errors.jsonl"
        self.stats_file = metadata_dir / "crawl_stats.json"
        self.source_xml_file = Path("03_extract_type_info/metadata/api_types.xml")
        self.html_dir = output_dir / "html"

        # Validation results
        self.results: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "validation_passed": True,
            "checks": {},
            "warnings": [],
            "errors": [],
        }

    def validate(self) -> bool:
        """Run all validation checks"""
        print("=" * 60)
        print("VALIDATING PHASE 05 CRAWL RESULTS")
        print("=" * 60)

        # Run all checks
        self.check_files_exist()
        self.check_url_coverage()
        self.check_html_files()
        self.check_metadata_consistency()
        self.check_success_rate()
        self.check_content_integrity()

        # Print summary
        self.print_summary()

        return self.results["validation_passed"]

    def check_files_exist(self) -> None:
        """Check that all required files exist"""
        print("\n1. Checking required files...")

        required_files = {
            "URLs file": self.urls_file,
            "Statistics file": self.stats_file,
            "Source XML": self.source_xml_file,
            "HTML directory": self.html_dir,
        }

        missing_files = []
        for name, path in required_files.items():
            if path.exists():
                if self.verbose:
                    print(f"  ✓ {name}: {path}")
            else:
                print(f"  ✗ {name} missing: {path}")
                missing_files.append(name)
                self.results["errors"].append(f"Missing {name}: {path}")

        self.results["checks"]["files_exist"] = len(missing_files) == 0

        if missing_files:
            self.results["validation_passed"] = False
            print(f"  [FAIL] Missing files: {', '.join(missing_files)}")
        else:
            print("  [PASS] All required files exist")

    def check_url_coverage(self) -> None:
        """Check URL coverage against source XML file"""
        print("\n2. Checking URL coverage...")

        if not self.source_xml_file.exists():
            print("  [SKIP] Source XML file not found")
            return

        # Load source URLs from XML
        import xml.etree.ElementTree as ET
        source_urls = set()

        try:
            tree = ET.parse(self.source_xml_file)
            root = tree.getroot()

            for example in root.findall(".//Example/Url"):
                url = example.text
                if url and url.strip():
                    source_urls.add(url.strip())

        except Exception as e:
            print(f"  [ERROR] Failed to parse XML: {e}")
            return

        # Load crawled URLs
        crawled_urls = set()
        if self.urls_file.exists():
            with jsonlines.open(self.urls_file) as reader:
                for obj in reader:
                    url = obj.get("url", "")
                    # Extract the path portion to match against source URLs
                    if "/2026/english/api" in url:
                        path = url.split("/2026/english/api")[1]
                        crawled_urls.add(path)

        # Calculate coverage
        coverage = len(crawled_urls) / len(source_urls) * 100 if source_urls else 0
        missing = source_urls - crawled_urls

        print(f"  Source URLs: {len(source_urls)}")
        print(f"  Crawled URLs: {len(crawled_urls)}")
        print(f"  Coverage: {coverage:.2f}%")

        self.results["checks"]["url_coverage"] = {
            "source_count": len(source_urls),
            "crawled_count": len(crawled_urls),
            "coverage_percent": coverage,
            "missing_count": len(missing),
        }

        if coverage < 95:
            self.results["warnings"].append(f"URL coverage below 95%: {coverage:.2f}%")
            print(f"  [WARN] Coverage below 95%")

            if self.verbose and len(missing) <= 20:
                print(f"\n  Missing URLs:")
                for url in sorted(missing)[:20]:
                    print(f"    - {url}")
        else:
            print("  [PASS] URL coverage >= 95%")

    def check_html_files(self) -> None:
        """Check HTML files exist and are valid"""
        print("\n3. Checking HTML files...")

        if not self.html_dir.exists():
            print("  [FAIL] HTML directory not found")
            self.results["validation_passed"] = False
            return

        html_files = list(self.html_dir.rglob("*.html"))
        total_size = sum(f.stat().st_size for f in html_files)

        print(f"  HTML files: {len(html_files)}")
        print(f"  Total size: {total_size / (1024 * 1024):.2f} MB")

        self.results["checks"]["html_files"] = {
            "count": len(html_files),
            "total_size_bytes": total_size,
        }

        # Check for empty files
        empty_files = [f for f in html_files if f.stat().st_size == 0]
        if empty_files:
            self.results["warnings"].append(f"Found {len(empty_files)} empty HTML files")
            print(f"  [WARN] {len(empty_files)} empty files")
        else:
            print("  [PASS] No empty HTML files")

    def check_metadata_consistency(self) -> None:
        """Check metadata consistency"""
        print("\n4. Checking metadata consistency...")

        if not self.urls_file.exists():
            print("  [SKIP] URLs file not found")
            return

        # Load metadata
        metadata_entries = []
        with jsonlines.open(self.urls_file) as reader:
            metadata_entries = list(reader)

        # Check for duplicates
        urls = [entry.get("url") for entry in metadata_entries]
        duplicates = len(urls) - len(set(urls))

        print(f"  Metadata entries: {len(metadata_entries)}")
        print(f"  Unique URLs: {len(set(urls))}")

        if duplicates > 0:
            self.results["errors"].append(f"Found {duplicates} duplicate URLs in metadata")
            print(f"  [FAIL] {duplicates} duplicate URLs")
            self.results["validation_passed"] = False
        else:
            print("  [PASS] No duplicate URLs")

        # Check for missing required fields
        required_fields = ["url", "timestamp", "content_hash", "file_path"]
        incomplete_entries = []

        for entry in metadata_entries:
            missing = [field for field in required_fields if not entry.get(field)]
            if missing:
                incomplete_entries.append((entry.get("url", "unknown"), missing))

        if incomplete_entries:
            self.results["warnings"].append(f"{len(incomplete_entries)} entries missing fields")
            print(f"  [WARN] {len(incomplete_entries)} incomplete entries")

            if self.verbose and len(incomplete_entries) <= 10:
                for url, missing in incomplete_entries[:10]:
                    print(f"    - {url}: missing {', '.join(missing)}")
        else:
            print("  [PASS] All entries complete")

    def check_success_rate(self) -> None:
        """Check crawl success rate"""
        print("\n5. Checking crawl success rate...")

        if not self.stats_file.exists():
            print("  [SKIP] Statistics file not found")
            return

        with open(self.stats_file) as f:
            stats = json.load(f)

        total = stats.get("total_pages", 0)
        successful = stats.get("successful_pages", 0)
        failed = stats.get("failed_pages", 0)
        skipped = stats.get("skipped_pages", 0)

        if total > 0:
            success_rate = (successful / total) * 100
        else:
            success_rate = 0

        print(f"  Total pages: {total}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Skipped: {skipped}")
        print(f"  Success rate: {success_rate:.2f}%")

        self.results["checks"]["success_rate"] = {
            "total": total,
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "success_rate_percent": success_rate,
        }

        if success_rate < 90:
            self.results["warnings"].append(f"Success rate below 90%: {success_rate:.2f}%")
            print("  [WARN] Success rate below 90%")
        else:
            print("  [PASS] Success rate >= 90%")

    def check_content_integrity(self) -> None:
        """Check content integrity using hashes"""
        print("\n6. Checking content integrity...")

        if not self.urls_file.exists():
            print("  [SKIP] URLs file not found")
            return

        # Sample check (not all files for performance)
        with jsonlines.open(self.urls_file) as reader:
            entries = list(reader)

        # Check up to 100 random files
        import random

        sample_size = min(100, len(entries))
        sample = random.sample(entries, sample_size) if len(entries) > sample_size else entries

        mismatches = 0
        for entry in sample:
            file_path = entry.get("file_path")
            stored_hash = entry.get("content_hash")

            if not file_path or not stored_hash:
                continue

            full_path = Path(file_path)
            if not full_path.exists():
                full_path = Path(__file__).parent.parent / file_path

            if full_path.exists():
                with open(full_path, "rb") as f:
                    actual_hash = hashlib.sha256(f.read()).hexdigest()

                if actual_hash != stored_hash:
                    mismatches += 1
                    if self.verbose:
                        print(f"  Hash mismatch: {file_path}")

        print(f"  Sampled files: {sample_size}")
        print(f"  Hash mismatches: {mismatches}")

        self.results["checks"]["content_integrity"] = {
            "sampled": sample_size,
            "mismatches": mismatches,
        }

        if mismatches > 0:
            self.results["warnings"].append(f"{mismatches} files with hash mismatches")
            print("  [WARN] Hash mismatches detected")
        else:
            print("  [PASS] All sampled files have correct hashes")

    def print_summary(self) -> None:
        """Print validation summary"""
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)

        if self.results["validation_passed"]:
            print("\n[PASS] VALIDATION PASSED")
        else:
            print("\n[FAIL] VALIDATION FAILED")

        if self.results["errors"]:
            print(f"\nErrors ({len(self.results['errors'])}):")
            for error in self.results["errors"]:
                print(f"  - {error}")

        if self.results["warnings"]:
            print(f"\nWarnings ({len(self.results['warnings'])}):")
            for warning in self.results["warnings"]:
                print(f"  - {warning}")

        print()

    def save_report(self, report_file: Path) -> None:
        """Save detailed validation report"""
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)

        print(f"\nDetailed report saved to: {report_file}")


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Validate the SolidWorks API examples crawl")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print detailed validation information")
    parser.add_argument("--report", type=Path, help="Save detailed JSON report to file")

    args = parser.parse_args()

    # Set up paths
    script_dir = Path(__file__).parent
    metadata_dir = script_dir / "metadata"
    output_dir = script_dir / "output"

    # Create validator
    validator = CrawlValidator(metadata_dir, output_dir, verbose=args.verbose)

    # Run validation
    success = validator.validate()

    # Save report if requested
    if args.report:
        validator.save_report(args.report)

    # Exit with appropriate code
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
