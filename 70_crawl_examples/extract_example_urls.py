#!/usr/bin/env python
"""
Extract unique example URLs from the api_types.xml file.

This script parses the XML output from phase 03 and extracts all unique
example URLs referenced in the <Example><Url> elements.

Usage:
    python 70_crawl_examples/extract_example_urls.py
    python 70_crawl_examples/extract_example_urls.py --output urls.txt
"""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def extract_urls_from_xml(xml_file: Path) -> set[str]:
    """
    Extract all unique example URLs from the api_types.xml file.

    Args:
        xml_file: Path to the api_types.xml file

    Returns:
        Set of unique example URLs
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    urls = set()

    # Find all <Url> elements within <Example> elements
    for example in root.findall(".//Example/Url"):
        url = example.text
        if url:
            urls.add(url.strip())

    return urls


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Extract unique example URLs from api_types.xml"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("40_extract_type_details/metadata/api_types.xml"),
        help="Path to api_types.xml file (default: 40_extract_type_details/metadata/api_types.xml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("70_crawl_examples/metadata/example_urls.txt"),
        help="Output file for extracted URLs (default: 70_crawl_examples/metadata/example_urls.txt)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print verbose output",
    )

    args = parser.parse_args()

    # Check if input file exists
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return

    # Extract URLs
    print(f"Extracting URLs from: {args.input}")
    urls = extract_urls_from_xml(args.input)

    print(f"Found {len(urls)} unique example URLs")

    # Create output directory if needed
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Write URLs to output file
    with open(args.output, "w", encoding="utf-8") as f:
        for url in sorted(urls):
            f.write(f"{url}\n")

    print(f"URLs written to: {args.output}")

    # Print sample URLs if verbose
    if args.verbose:
        print("\nSample URLs:")
        for i, url in enumerate(sorted(urls)[:10], 1):
            print(f"  {i}. {url}")
        if len(urls) > 10:
            print(f"  ... and {len(urls) - 10} more")


if __name__ == "__main__":
    main()
