#!/usr/bin/env python
"""
Main entry point for the SolidWorks Programming Guide crawler.

Usage:
    python 10_crawl_programming_guide/run_crawler.py [options]

Options:
    --test       Run a test crawl (first 100 pages only)
    --resume     Resume from previous crawl (uses existing metadata)
    --validate   Validate crawl after completion
    --help       Show this help message
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
from scrapy.utils.project import get_project_settings

# Add the scrapy project and parent directory to path (for shared_crawler)
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from solidworks_scraper.spiders.api_docs_spider import ApiDocsSpider


def setup_environment() -> tuple[Path, Path, Path]:
    """Set up the environment for running the crawler"""
    # Change to the scrapy project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    # Ensure output directories exist
    output_dir = project_dir / "output"
    html_dir = output_dir / "html"
    metadata_dir = project_dir / "metadata"

    html_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    return project_dir, output_dir, metadata_dir


def clear_previous_crawl(metadata_dir: Path, output_dir: Path) -> None:
    """Clear metadata and HTML files from previous crawl"""
    import shutil

    # Clear metadata files
    metadata_path = Path(metadata_dir)
    if metadata_path.exists():
        for file in metadata_path.glob("*"):
            if file.is_file():
                file.unlink()
        print(f"Cleared metadata files from {metadata_dir}")

    # Clear HTML output
    html_dir = Path(output_dir) / "html"
    if html_dir.exists():
        shutil.rmtree(html_dir)
        html_dir.mkdir(parents=True, exist_ok=True)
        print(f"Cleared HTML files from {html_dir}")


def get_crawl_settings(
    test_mode: bool = False, resume_mode: bool = False, metadata_dir: Path | None = None, output_dir: Path | None = None
) -> Settings:
    """Get Scrapy settings for the crawl"""
    settings = get_project_settings()

    if test_mode:
        # Limit crawl for testing
        settings.set("CLOSESPIDER_PAGECOUNT", 100)
        settings.set("LOG_LEVEL", "INFO")  # Don't use DEBUG to avoid logging full HTML content
        print("Running in TEST mode - limiting to 100 pages")

    if resume_mode:
        # Don't clear existing data
        print("Running in RESUME mode - continuing from previous crawl")
    else:
        # Clear previous crawl data
        print("Starting fresh crawl - clearing previous data")
        if metadata_dir and output_dir:
            clear_previous_crawl(metadata_dir, output_dir)

    return settings


def validate_crawl(metadata_dir: Path) -> bool:
    """Validate the crawl results"""
    print("\n" + "=" * 50)
    print("VALIDATING CRAWL RESULTS")
    print("=" * 50)

    urls_file = metadata_dir / "urls_crawled.jsonl"
    errors_file = metadata_dir / "errors.jsonl"
    stats_file = metadata_dir / "crawl_stats.json"

    # Count crawled URLs
    crawled_count = 0
    if urls_file.exists():
        with open(urls_file) as f:
            crawled_count = sum(1 for _ in f)

    print(f"Pages crawled: {crawled_count}")

    # Count errors
    error_count = 0
    if errors_file.exists():
        with open(errors_file) as f:
            error_count = sum(1 for _ in f)

    print(f"Errors encountered: {error_count}")

    # Load and display statistics
    if stats_file.exists():
        with open(stats_file) as f:
            stats = json.load(f)

        print("\nCrawl Statistics:")
        print(f"  Total pages: {stats.get('total_pages', 0)}")
        print(f"  Successful: {stats.get('successful_pages', 0)}")
        print(f"  Failed: {stats.get('failed_pages', 0)}")
        print(f"  Skipped: {stats.get('skipped_pages', 0)}")

        # Calculate success rate
        total = stats.get("total_pages", 0)
        successful = stats.get("successful_pages", 0)
        if total > 0:
            success_rate = (successful / total) * 100
            print(f"  Success rate: {success_rate:.2f}%")

            # Check regression threshold (95% success)
            if success_rate < 95:
                print("\n[WARNING]  WARNING: Success rate below 95% threshold!")
                return False
    else:
        print("\n[WARNING]  No statistics file found!")
        return False

    # Check for minimum page count (expecting at least 145 for Programming Guide, allow 5% regression)
    min_pages = 138  # 95% of 145
    if not test_mode and crawled_count < min_pages:
        print(f"\n[WARNING]  WARNING: Only {crawled_count} pages crawled (expected >= {min_pages})")
        return False

    print("\n[OK] Validation PASSED")
    return True


def print_summary(metadata_dir: Path) -> None:
    """Print a summary of the crawl"""
    print("\n" + "=" * 50)
    print("CRAWL SUMMARY")
    print("=" * 50)

    # Count saved files (HTML and JSON)
    html_dir = metadata_dir.parent / "html"
    if html_dir.exists():
        html_count = sum(1 for _ in html_dir.rglob("*.html"))
        json_count = sum(1 for _ in html_dir.rglob("*.json"))
        total_count = html_count + json_count
        print(f"Files saved: {total_count} ({html_count} HTML, {json_count} JSON)")
    else:
        print("Files saved: 0")

    # Show sample of crawled URLs
    urls_file = metadata_dir / "urls_crawled.jsonl"
    if urls_file.exists():
        print("\nSample of crawled URLs:")
        import jsonlines

        with jsonlines.open(urls_file) as reader:
            for i, obj in enumerate(reader):
                if i >= 5:  # Show first 5
                    break
                title = obj.get("title", "Untitled")
                url = obj.get("url", "")
                print(f"  - {title}: {url}")

    # Show metadata files
    print("\nMetadata files created:")
    for file in metadata_dir.glob("*.json*"):
        size = file.stat().st_size
        print(f"  - {file.name}: {size:,} bytes")


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run the SolidWorks Programming Guide crawler")
    parser.add_argument("--test", action="store_true", help="Run test crawl (10 pages only)")
    parser.add_argument("--resume", action="store_true", help="Resume from previous crawl")
    parser.add_argument("--validate", action="store_true", help="Validate crawl results")
    parser.add_argument("--no-crawl", action="store_true", help="Skip crawl, only validate")

    args = parser.parse_args()

    # Set up environment
    project_dir, output_dir, metadata_dir = setup_environment()

    # If only validating, skip crawl
    if args.no_crawl:
        if args.validate:
            success = validate_crawl(metadata_dir)
            sys.exit(0 if success else 1)
        else:
            print("No action specified. Use --help for options.")
            sys.exit(1)

    try:
        print("\n" + "=" * 50)
        print("SOLIDWORKS PROGRAMMING GUIDE CRAWLER")
        print("=" * 50)
        print(f"Start time: {datetime.now().isoformat()}")
        print(f"Output directory: {output_dir}")
        print(f"Mode: {'TEST' if args.test else 'FULL'} crawl")
        print("=" * 50 + "\n")

        # Get settings
        settings = get_crawl_settings(
            test_mode=args.test, resume_mode=args.resume, metadata_dir=metadata_dir, output_dir=output_dir
        )

        # Create and configure the crawler process
        process = CrawlerProcess(settings)

        # Add the spider to crawl
        process.crawl(ApiDocsSpider)

        # Start the crawling process
        print("Starting crawl... (Press Ctrl+C to stop)\n")
        process.start()

        print("\n" + "=" * 50)
        print("Crawl completed successfully!")
        print(f"End time: {datetime.now().isoformat()}")
        print("=" * 50)

        # Print summary
        print_summary(metadata_dir)

        # Validate if requested
        if args.validate:
            validate_crawl(metadata_dir)

    except KeyboardInterrupt:
        print("\n\nCrawl interrupted by user.")
        print("You can resume later with: python run_crawler.py --resume")
        sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] Error during crawl: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Store test_mode globally for validation function
    test_mode = "--test" in sys.argv
    main()
