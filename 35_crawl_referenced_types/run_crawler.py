#!/usr/bin/env python
"""Entry point for the referenced-types crawl (Phase 35).

Crawls the generated reference pages the source TOC never exposes, so the types
and enums behind those nodes reach the extraction phases.

Usage:
    python 35_crawl_referenced_types/run_crawler.py [--resume]
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from reference_targets import crawl_failure
from solidworks_scraper.spiders.referenced_types_spider import ReferencedTypesSpider


def clear_previous(metadata_dir: Path, output_dir: Path) -> None:
    """Remove prior metadata/HTML so a fresh run doesn't append to old logs."""
    if metadata_dir.exists():
        for file in metadata_dir.glob("*"):
            if file.is_file():
                file.unlink()
    html_dir = output_dir / "html"
    if html_dir.exists():
        shutil.rmtree(html_dir)
    print("Cleared previous crawl data")


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl reference pages the TOC never exposes")
    parser.add_argument("--resume", action="store_true", help="Continue from a previous crawl (keep existing data)")
    args = parser.parse_args()

    project_dir = Path(__file__).parent.resolve()
    os.chdir(project_dir)
    output_dir = project_dir / "output"
    metadata_dir = project_dir / "metadata"
    (output_dir / "html").mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    if not args.resume:
        clear_previous(metadata_dir, output_dir)

    process = CrawlerProcess(get_project_settings())
    process.crawl(ReferencedTypesSpider)
    process.start()

    urls_file = metadata_dir / "urls_crawled.jsonl"
    crawled = sum(1 for _ in open(urls_file)) if urls_file.exists() else 0
    print(f"\nReferenced-types crawl complete: {crawled} pages saved to {output_dir / 'html'}")

    stats_file = metadata_dir / "crawl_stats.json"
    stats = json.loads(stats_file.read_text()) if stats_file.exists() else {}
    problem = crawl_failure(stats, crawled)
    if problem:
        print(f"ERROR: {problem}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
