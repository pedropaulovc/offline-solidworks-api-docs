#!/usr/bin/env python
"""
Validation script for SolidWorks API documentation crawl.

This script validates the completeness and integrity of a crawl by:
- Checking metadata files exist and are valid
- Verifying HTML files match metadata records
- Calculating statistics and success rates
- Detecting duplicates and inconsistencies
- Generating a detailed validation report
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import jsonlines


class CrawlValidator:
    """Validates crawl completeness and integrity"""

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.html_dir = self.output_dir / "html"
        self.metadata_dir = self.output_dir.parent / "metadata"
        self.errors = []
        self.warnings = []
        self.stats = defaultdict(int)

    def validate(self, verbose=False):
        """Run all validation checks"""
        print("=" * 60)
        print("SOLIDWORKS API DOCUMENTATION CRAWL VALIDATOR")
        print("=" * 60)
        print(f"Validation started: {datetime.now().isoformat()}")
        print(f"Output directory: {self.output_dir}\n")

        # Check directory structure
        if not self._check_directory_structure():
            return False

        # Validate metadata files
        self._validate_metadata_files(verbose)

        # Validate URLs crawled
        urls_valid = self._validate_urls_crawled(verbose)

        # Validate HTML files
        html_valid = self._validate_html_files(verbose)

        # Check for duplicates
        self._check_duplicates(verbose)

        # Validate crawl statistics
        stats_valid = self._validate_statistics()

        # Generate report
        self._generate_report()

        # Determine overall result
        success = len(self.errors) == 0 and urls_valid and html_valid and stats_valid

        print("\n" + "=" * 60)
        if success:
            print("[PASSED] VALIDATION PASSED")
        else:
            print("[FAILED] VALIDATION FAILED")
            print(f"   Errors: {len(self.errors)}")
            print(f"   Warnings: {len(self.warnings)}")
        print("=" * 60)

        return success

    def _check_directory_structure(self):
        """Check that expected directories exist"""
        print("Checking directory structure...")

        if not self.output_dir.exists():
            self.errors.append(f"Output directory does not exist: {self.output_dir}")
            return False

        if not self.metadata_dir.exists():
            self.errors.append(f"Metadata directory does not exist: {self.metadata_dir}")
            return False

        if not self.html_dir.exists():
            self.warnings.append(f"HTML directory does not exist: {self.html_dir}")

        print("  [OK] Directory structure verified\n")
        return True

    def _validate_metadata_files(self, verbose):
        """Validate metadata files exist and are valid"""
        print("Validating metadata files...")

        expected_files = ["manifest.json", "urls_crawled.jsonl", "crawl_stats.json"]

        for filename in expected_files:
            filepath = self.metadata_dir / filename
            if not filepath.exists():
                self.warnings.append(f"Missing metadata file: {filename}")
                continue

            if filename.endswith(".json"):
                try:
                    with open(filepath) as f:
                        data = json.load(f)
                    self.stats[f"metadata_{filename}_valid"] = 1

                    if verbose and filename == "manifest.json":
                        print(f"  Manifest version: {data.get('crawler_version', 'Unknown')}")
                        print(f"  Boundary: {data.get('boundary', 'Unknown')}")

                except json.JSONDecodeError as e:
                    self.errors.append(f"Invalid JSON in {filename}: {e}")

            elif filename.endswith(".jsonl"):
                try:
                    line_count = 0
                    with jsonlines.open(filepath) as reader:
                        for obj in reader:
                            line_count += 1
                    self.stats[f"{filename}_lines"] = line_count

                    if verbose:
                        print(f"  {filename}: {line_count} lines")

                except Exception as e:
                    self.errors.append(f"Error reading {filename}: {e}")

        print("  [OK] Metadata files validated\n")

    def _validate_urls_crawled(self, verbose):
        """Validate URLs crawled metadata"""
        print("Validating crawled URLs...")

        urls_file = self.metadata_dir / "urls_crawled.jsonl"
        if not urls_file.exists():
            self.errors.append("urls_crawled.jsonl not found")
            return False

        urls_seen = set()
        file_paths = set()
        total_size = 0
        url_count = 0

        try:
            with jsonlines.open(urls_file) as reader:
                for obj in reader:
                    url_count += 1

                    # Check required fields
                    required_fields = ["print_url", "file_path", "content_hash", "timestamp"]
                    for field in required_fields:
                        if field not in obj:
                            self.warnings.append(
                                f"Missing field '{field}' in URL record: {obj.get('print_url', 'Unknown')}"
                            )

                    # Check for duplicate URLs
                    url = obj.get("print_url")
                    if url in urls_seen:
                        self.warnings.append(f"Duplicate URL in metadata: {url}")
                    urls_seen.add(url)

                    # Track file paths
                    if "file_path" in obj:
                        file_paths.add(obj["file_path"])

                    # Track size
                    if "content_length" in obj:
                        total_size += obj["content_length"]

                    # Check URL is within boundary
                    if url and "/2026/english/api/" not in url:
                        self.warnings.append(f"URL outside boundary: {url}")

            self.stats["urls_crawled"] = url_count
            self.stats["unique_urls"] = len(urls_seen)
            self.stats["total_size_bytes"] = total_size

            print(f"  Total URLs: {url_count}")
            print(f"  Unique URLs: {len(urls_seen)}")
            print(f"  Total size: {total_size / (1024*1024):.2f} MB")

            if verbose and url_count > 0:
                print(f"  Average size: {total_size / url_count / 1024:.2f} KB")

            # Check for minimum page count (allow 5% regression from expected 458)
            min_pages = 435  # 95% of 458
            if url_count < min_pages:
                self.errors.append(f"Insufficient pages crawled: {url_count} < {min_pages}")
                return False

            print("  [OK] URLs validated\n")
            return True

        except Exception as e:
            self.errors.append(f"Error validating URLs: {e}")
            return False

    def _validate_html_files(self, verbose):
        """Validate HTML files match metadata"""
        print("Validating HTML files...")

        html_files = list(self.html_dir.rglob("*.html")) + list(self.html_dir.rglob("*.htm"))
        self.stats["html_files"] = len(html_files)

        print(f"  HTML files found: {len(html_files)}")

        # Load metadata to compare
        metadata_files = set()
        urls_file = self.metadata_dir / "urls_crawled.jsonl"

        if urls_file.exists():
            with jsonlines.open(urls_file) as reader:
                for obj in reader:
                    if "file_path" in obj:
                        # Convert relative path in metadata to absolute
                        file_path = self.output_dir.parent / obj["file_path"]
                        metadata_files.add(file_path)

            # Check for orphaned files
            html_paths = set(html_files)
            orphaned = html_paths - metadata_files
            missing = metadata_files - html_paths

            if orphaned:
                self.warnings.append(f"Found {len(orphaned)} HTML files without metadata")
                if verbose:
                    for f in list(orphaned)[:5]:  # Show first 5
                        print(f"    - Orphaned: {f.relative_to(self.output_dir)}")

            if missing:
                self.warnings.append(f"Found {len(missing)} metadata records without HTML files")
                if verbose:
                    for f in list(missing)[:5]:  # Show first 5
                        print(f"    - Missing: {f}")

        # Sample validation of HTML content
        if html_files and verbose:
            print("  Sampling HTML files for validation...")
            import random

            sample = random.sample(html_files, min(5, len(html_files)))

            for file in sample:
                try:
                    with open(file, encoding="utf-8") as f:
                        content = f.read()

                    if len(content) < 100:
                        self.warnings.append(f"Suspiciously small HTML file: {file.name}")

                    if not ("<html" in content.lower() or "<!doctype" in content.lower()):
                        self.warnings.append(f"File doesn't appear to be HTML: {file.name}")

                except Exception as e:
                    self.errors.append(f"Error reading HTML file {file.name}: {e}")

        print("  [OK] HTML files validated\n")
        return True

    def _check_duplicates(self, verbose):
        """Check for duplicate content based on hashes"""
        print("Checking for duplicates...")

        urls_file = self.metadata_dir / "urls_crawled.jsonl"
        if not urls_file.exists():
            return

        hash_to_urls = defaultdict(list)

        with jsonlines.open(urls_file) as reader:
            for obj in reader:
                if "content_hash" in obj and "print_url" in obj:
                    hash_to_urls[obj["content_hash"]].append(obj["print_url"])

        duplicates = {h: urls for h, urls in hash_to_urls.items() if len(urls) > 1}

        if duplicates:
            self.warnings.append(f"Found {len(duplicates)} duplicate content hashes")
            if verbose:
                for hash_val, urls in list(duplicates.items())[:3]:  # Show first 3
                    print(f"  Duplicate content (hash: {hash_val[:8]}...):")
                    for url in urls[:2]:  # Show first 2 URLs
                        print(f"    - {url}")

        self.stats["duplicate_content"] = len(duplicates)
        print(f"  Duplicate content groups: {len(duplicates)}")
        print("  [OK] Duplicate check completed\n")

    def _validate_statistics(self):
        """Validate crawl statistics"""
        print("Validating crawl statistics...")

        stats_file = self.metadata_dir / "crawl_stats.json"
        if not stats_file.exists():
            self.warnings.append("crawl_stats.json not found")
            return True  # Not critical

        try:
            with open(stats_file) as f:
                stats = json.load(f)

            # Calculate success rate
            total = stats.get("total_pages", 0)
            successful = stats.get("successful_pages", 0)

            if total > 0:
                success_rate = (successful / total) * 100
                self.stats["success_rate"] = success_rate

                print(f"  Total pages: {total}")
                print(f"  Successful: {successful}")
                print(f"  Failed: {stats.get('failed_pages', 0)}")
                print(f"  Skipped: {stats.get('skipped_pages', 0)}")
                print(f"  Success rate: {success_rate:.2f}%")

                if success_rate < 95:
                    self.errors.append(f"Success rate below 95%: {success_rate:.2f}%")
                    return False

            print("  [OK] Statistics validated\n")
            return True

        except Exception as e:
            self.errors.append(f"Error reading statistics: {e}")
            return False

    def _generate_report(self):
        """Generate validation report"""
        print("Validation Report Summary")
        print("-" * 40)

        # Summary stats
        print(f"URLs crawled: {self.stats.get('urls_crawled', 0)}")
        print(f"HTML files: {self.stats.get('html_files', 0)}")
        print(f"Success rate: {self.stats.get('success_rate', 0):.2f}%")
        print(f"Duplicate content: {self.stats.get('duplicate_content', 0)}")
        print(f"Total size: {self.stats.get('total_size_bytes', 0) / (1024*1024):.2f} MB")

        # Issues
        print("\nIssues found:")
        print(f"  Errors: {len(self.errors)}")
        print(f"  Warnings: {len(self.warnings)}")

        if self.errors:
            print("\nErrors:")
            for i, error in enumerate(self.errors[:5], 1):  # Show first 5
                print(f"  {i}. {error}")
            if len(self.errors) > 5:
                print(f"  ... and {len(self.errors) - 5} more")

        if self.warnings:
            print("\nWarnings:")
            for i, warning in enumerate(self.warnings[:5], 1):  # Show first 5
                print(f"  {i}. {warning}")
            if len(self.warnings) > 5:
                print(f"  ... and {len(self.warnings) - 5} more")

        # Save detailed report
        report_file = self.metadata_dir / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "stats": dict(self.stats),
            "errors": self.errors,
            "warnings": self.warnings,
            "success": len(self.errors) == 0,
        }

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\nDetailed report saved to: {report_file.name}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Validate SolidWorks API documentation crawl")
    parser.add_argument(
        "--output-dir",
        default="01-crawl-raw/output",
        help="Output directory to validate (default: 01-crawl-raw/output)",
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed validation information")

    args = parser.parse_args()

    # Resolve output directory
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        # If relative, assume relative to script location
        output_dir = Path(__file__).parent / args.output_dir

    # Create validator and run
    validator = CrawlValidator(output_dir)
    success = validator.validate(verbose=args.verbose)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
