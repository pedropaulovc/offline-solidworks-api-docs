#!/usr/bin/env python
"""
Validation script for Phase 3 crawl results.

This script validates the completeness and quality of the type members crawl.

Usage:
    uv run python 03_crawl_type_members/validate_crawl.py [--verbose]
"""

import argparse
import json
from pathlib import Path

import jsonlines


def load_crawl_stats(metadata_dir: Path) -> dict:
    """Load crawl statistics from metadata"""
    stats_file = metadata_dir / "crawl_stats.json"

    if not stats_file.exists():
        return {}

    with open(stats_file) as f:
        return json.load(f)


def count_crawled_urls(metadata_dir: Path) -> int:
    """Count the number of URLs that were crawled"""
    urls_file = metadata_dir / "urls_crawled.jsonl"

    if not urls_file.exists():
        return 0

    count = 0
    with jsonlines.open(urls_file) as reader:
        for _ in reader:
            count += 1

    return count


def count_errors(metadata_dir: Path) -> int:
    """Count the number of errors encountered"""
    errors_file = metadata_dir / "errors.jsonl"

    if not errors_file.exists():
        return 0

    count = 0
    with jsonlines.open(errors_file) as reader:
        for _ in reader:
            count += 1

    return count


def count_html_files(output_dir: Path) -> int:
    """Count the number of HTML files saved"""
    html_dir = output_dir / "html"

    if not html_dir.exists():
        return 0

    return sum(1 for _ in html_dir.rglob("*.html"))


def analyze_errors(metadata_dir: Path, verbose: bool = False) -> dict:
    """Analyze error patterns"""
    errors_file = metadata_dir / "errors.jsonl"

    if not errors_file.exists():
        return {}

    error_types: dict[str, int] = {}
    error_examples: dict[str, list[str]] = {}

    with jsonlines.open(errors_file) as reader:
        for error in reader:
            error_msg = error.get("error", "Unknown")
            error_types[error_msg] = error_types.get(error_msg, 0) + 1

            if error_msg not in error_examples:
                error_examples[error_msg] = []
            if len(error_examples[error_msg]) < 3:
                error_examples[error_msg].append(error.get("url", ""))

    return {"types": error_types, "examples": error_examples}


def validate_crawl(verbose: bool = False) -> bool:
    """Main validation function"""
    project_dir = Path(__file__).parent
    metadata_dir = project_dir / "metadata"
    output_dir = project_dir / "output"

    print("=" * 60)
    print("PHASE 3 CRAWL VALIDATION")
    print("=" * 60)
    print()

    # Check if metadata directory exists
    if not metadata_dir.exists():
        print("[ERROR] Metadata directory not found!")
        print("Please run the crawler first:")
        print("  uv run python 03_crawl_type_members/run_crawler.py")
        return False

    # Load statistics
    stats = load_crawl_stats(metadata_dir)
    crawled_count = count_crawled_urls(metadata_dir)
    error_count = count_errors(metadata_dir)
    html_count = count_html_files(output_dir)

    # Print basic statistics
    print(f"URLs crawled:     {crawled_count:,}")
    print(f"HTML files saved: {html_count:,}")
    print(f"Errors:           {error_count:,}")
    print()

    # Print detailed statistics if available
    if stats:
        print("Detailed Statistics:")
        print(f"  Total pages:      {stats.get('total_pages', 0):,}")
        print(f"  Successful:       {stats.get('successful_pages', 0):,}")
        print(f"  Failed:           {stats.get('failed_pages', 0):,}")
        print(f"  Skipped:          {stats.get('skipped_pages', 0):,}")
        print()

        # Calculate success rate
        total = stats.get("total_pages", 0)
        successful = stats.get("successful_pages", 0)
        if total > 0:
            success_rate = (successful / total) * 100
            print(f"Success rate: {success_rate:.2f}%")
            print()

    # Validate against expected counts
    validation_passed = True

    # Check for minimum page count (expect thousands of type members)
    # A conservative estimate is at least 1000 pages for a partial crawl
    if crawled_count < 100:
        print(f"[WARNING] Very few pages crawled ({crawled_count})")
        print("Expected at least 100 pages. This may be a test crawl.")
        print()

    # Check success rate
    if stats:
        total = stats.get("total_pages", 0)
        successful = stats.get("successful_pages", 0)
        if total > 0:
            success_rate = (successful / total) * 100
            if success_rate < 95:
                print(f"[ERROR] Success rate too low: {success_rate:.2f}%")
                print("Expected at least 95% success rate")
                validation_passed = False
                print()

    # Check HTML file count matches crawled URLs
    if html_count != crawled_count:
        print(f"[WARNING] HTML file count ({html_count}) doesn't match crawled URL count ({crawled_count})")
        print("Some files may not have been saved properly")
        print()

    # Analyze errors if verbose
    if verbose and error_count > 0:
        print("Error Analysis:")
        error_analysis = analyze_errors(metadata_dir, verbose)

        print("\nError types:")
        for error_type, count in sorted(
            error_analysis["types"].items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            print(f"  {error_type}: {count} occurrences")

            if verbose:
                examples = error_analysis["examples"].get(error_type, [])
                for example_url in examples[:3]:
                    print(f"    - {example_url}")
        print()

    # Final result
    print("=" * 60)
    if validation_passed:
        print("[OK] VALIDATION PASSED")
    else:
        print("[FAILED] VALIDATION FAILED")
    print("=" * 60)

    return validation_passed


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Validate Phase 3 crawl results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed error analysis")

    args = parser.parse_args()

    success = validate_crawl(verbose=args.verbose)

    # Exit with appropriate code
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
