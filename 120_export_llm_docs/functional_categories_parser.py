"""
Functional Categories HTML Parser

This module parses the FunctionalCategories HTML file to extract the mapping
of types to their functional categories.
"""

import re
from pathlib import Path
from typing import Dict, List
from bs4 import BeautifulSoup
import json

from models import FunctionalCategory


class FunctionalCategoriesParser:
    """Parser for the FunctionalCategories HTML file."""

    def __init__(self, html_file_path: str):
        """
        Initialize the parser with the path to the FunctionalCategories HTML file.

        Args:
            html_file_path: Path to the FunctionalCategories HTML file
        """
        self.html_file_path = Path(html_file_path)
        self.categories: List[FunctionalCategory] = []

    def parse(self) -> List[FunctionalCategory]:
        """
        Parse the HTML file and extract functional categories with their types.

        Returns:
            List of FunctionalCategory objects
        """
        with open(self.html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all h4 headers that define categories
        headers = soup.find_all('h4')

        for header in headers:
            # Get the category name from the anchor
            anchor = header.find('a')
            if not anchor or not anchor.get('name'):
                continue

            category_name = header.get_text(strip=True)

            # Find the following ul element that contains the types
            ul_element = header.find_next_sibling('ul')
            if not ul_element:
                continue

            # Extract all type names from the links
            types = self._extract_types_from_ul(ul_element)

            if types:
                category = FunctionalCategory(name=category_name, types=types)
                self.categories.append(category)

        return self.categories

    def _extract_types_from_ul(self, ul_element) -> List[str]:
        """
        Recursively extract type names from a ul element and nested uls.

        Args:
            ul_element: BeautifulSoup ul element

        Returns:
            List of type names
        """
        types = []

        # Find all 'a' tags in this ul and nested uls
        for link in ul_element.find_all('a', href=True):
            href = link['href']

            # Extract type name from href
            # Pattern: SOLIDWORKS.Interop.assembly~SOLIDWORKS.Interop.namespace.TypeName.html
            # or: relative path like ../swmotionstudyapi/...
            type_name = self._extract_type_name_from_href(href)

            if type_name:
                types.append(type_name)

        return types

    def _extract_type_name_from_href(self, href: str) -> str:
        """
        Extract the type name from an href attribute.

        Args:
            href: The href attribute value

        Returns:
            The extracted type name or empty string if not found
        """
        # Pattern 1: SOLIDWORKS.Interop.assembly~SOLIDWORKS.Interop.namespace.TypeName.html
        # Pattern 2: ../assembly/SOLIDWORKS.Interop.assembly~SOLIDWORKS.Interop.namespace.TypeName.html
        # We want to extract: SOLIDWORKS.Interop.namespace.TypeName (fully qualified name)

        # Remove any path components
        filename = href.split('/')[-1]

        # Remove .html extension
        filename = filename.replace('.html', '')

        # Split by ~ to get the fully qualified name
        parts = filename.split('~')
        if len(parts) >= 2:
            fqn = parts[1]
            # Sometimes there are extra suffixes after .html, remove them
            fqn = fqn.split('.html')[0]
            return fqn

        return ""

    def get_category_mapping(self) -> Dict[str, str]:
        """
        Get a mapping of type names to their category names.

        Returns:
            Dictionary mapping fully qualified type names to category names
        """
        mapping = {}
        for category in self.categories:
            for type_name in category.types:
                mapping[type_name] = category.name

        return mapping

    def save_to_json(self, output_path: str):
        """
        Save the parsed categories to a JSON file.

        Args:
            output_path: Path to save the JSON file
        """
        data = {
            'categories': [
                {
                    'name': cat.name,
                    'type_count': len(cat.types),
                    'types': cat.types
                }
                for cat in self.categories
            ],
            'total_categories': len(self.categories),
            'total_types': sum(len(cat.types) for cat in self.categories)
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)


def main():
    """Main function for testing the parser."""
    import argparse

    parser = argparse.ArgumentParser(description='Parse FunctionalCategories HTML')
    parser.add_argument(
        '--html',
        default='10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html',
        help='Path to FunctionalCategories HTML file'
    )
    parser.add_argument(
        '--output',
        default='120_export_llm_docs/metadata/functional_categories.json',
        help='Output JSON file path'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print verbose output'
    )

    args = parser.parse_args()

    # Parse the HTML
    fc_parser = FunctionalCategoriesParser(args.html)
    categories = fc_parser.parse()

    # Print statistics
    print(f"Parsed {len(categories)} functional categories")
    for cat in categories:
        print(f"  - {cat.name}: {len(cat.types)} types")

    # Save to JSON
    fc_parser.save_to_json(args.output)
    print(f"\nSaved categories to {args.output}")

    if args.verbose:
        print("\nCategory-to-Type Mapping:")
        mapping = fc_parser.get_category_mapping()
        for type_name, category in sorted(mapping.items()):
            print(f"  {type_name} -> {category}")


if __name__ == '__main__':
    main()
