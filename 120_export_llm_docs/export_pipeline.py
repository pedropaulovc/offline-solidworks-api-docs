"""
Export Pipeline for Phase 120: Export LLM-Friendly Documentation

This script orchestrates the entire export process, generating markdown documentation
from the outputs of phases 20, 40, 50, 60, 80, and 110.
"""

import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

from functional_categories_parser import FunctionalCategoriesParser
from data_loader import DataLoader
from markdown_generator import MarkdownGenerator, sanitize_filename
from example_generator import ExampleGenerator
from index_generator import IndexGenerator
from models import TypeInfo, ExampleContent, ExportStatistics


class ExportPipeline:
    """Main export pipeline coordinator."""

    def __init__(self, output_base: str):
        """
        Initialize the export pipeline.

        Args:
            output_base: Base output directory (120_export_llm_docs/output/)
        """
        self.output_base = Path(output_base)
        self.stats = ExportStatistics()

    def run(self,
            phase20_path: str,
            phase40_path: str,
            phase50_path: str,
            phase60_path: str,
            phase80_path: str,
            phase110_path: str,
            functional_categories_html: str):
        """
        Run the complete export pipeline.

        Args:
            phase20_path: Path to Phase 20 XML
            phase40_path: Path to Phase 40 XML
            phase50_path: Path to Phase 50 XML
            phase60_path: Path to Phase 60 XML
            phase80_path: Path to Phase 80 XML
            phase110_path: Path to Phase 110 markdown directory
            functional_categories_html: Path to FunctionalCategories HTML
        """
        print("="*80)
        print("Phase 120: Export LLM-Friendly Documentation")
        print("="*80)

        # Step 1: Parse functional categories
        print("\n[1/6] Parsing functional categories...")
        categories_parser = FunctionalCategoriesParser(functional_categories_html)
        categories = categories_parser.parse()
        category_mapping = categories_parser.get_category_mapping()
        self.stats.functional_categories = len(categories)
        print(f"  Parsed {len(categories)} categories with {len(category_mapping)} types")

        # Step 2: Load and merge API data
        print("\n[2/6] Loading and merging API data...")
        data_loader = DataLoader()
        types = data_loader.load_all(
            phase20_path,
            phase40_path,
            phase50_path,
            phase60_path,
            phase80_path
        )
        print(f"  Loaded {len(types)} types")
        print(f"  Loaded {len(data_loader.examples)} examples")

        # Assign functional categories to types (case-insensitive lookup)
        # Create a lowercase version of the category mapping for case-insensitive lookup
        category_mapping_lower = {k.lower(): v for k, v in category_mapping.items()}

        for fqn, type_info in types.items():
            # Try exact match first, then case-insensitive
            if fqn in category_mapping:
                type_info.functional_category = category_mapping[fqn]
            elif fqn.lower() in category_mapping_lower:
                type_info.functional_category = category_mapping_lower[fqn.lower()]

        # Step 3: Generate API documentation
        print("\n[3/7] Generating API documentation...")
        self._generate_api_docs(types, data_loader)

        # Step 4: Generate index files
        print("\n[4/7] Generating index files...")
        self._generate_indexes(types)

        # Step 5: Generate example documentation
        print("\n[5/7] Generating example documentation...")
        self._generate_example_docs(data_loader.examples, category_mapping, types)

        # Step 6: Copy programming guide
        print("\n[6/7] Copying programming guide...")
        self._copy_programming_guide(phase110_path)

        # Step 7: Generate summary report
        print("\n[7/7] Generating summary report...")
        self._generate_summary_report()

        print("\n" + "="*80)
        print("Export Complete!")
        print("="*80)
        print(f"\nOutput location: {self.output_base}")
        print(f"Total markdown files generated: {self.stats.markdown_files_generated}")

    def _generate_api_docs(self, types: Dict[str, TypeInfo], data_loader: DataLoader):
        """Generate grep-optimized markdown documentation for all API types."""
        api_path = self.output_base / "api"

        # Create markdown generator in grep-optimized mode
        generator = MarkdownGenerator(
            output_base_path=str(api_path),
            examples_loader_func=data_loader.get_example_content,
            grep_optimized=True
        )

        # Separate types from enums
        regular_types = {fqn: t for fqn, t in types.items() if not t.is_enum}
        enum_types = {fqn: t for fqn, t in types.items() if t.is_enum}

        # Generate regular types
        print(f"  Generating {len(regular_types)} regular types...")
        types_path = api_path / "types"
        for fqn, type_info in regular_types.items():
            # Create directory: api/types/TypeName/
            type_dir = types_path / sanitize_filename(type_info.name)
            files_count = generator.save_grep_optimized_documentation(type_info, type_dir)
            self.stats.markdown_files_generated += files_count

            # Update stats
            self.stats.total_types += 1
            if type_info.description:
                self.stats.types_with_descriptions += 1
            if type_info.remarks:
                self.stats.types_with_remarks += 1
            if type_info.examples:
                self.stats.types_with_examples += 1
            self.stats.total_properties += len(type_info.properties)
            self.stats.total_methods += len(type_info.methods)

        print(f"    Generated {len(regular_types)} type directories")

        # Generate enums
        print(f"  Generating {len(enum_types)} enumerations...")
        enums_path = api_path / "enums"
        for fqn, enum_info in enum_types.items():
            # Create directory: api/enums/EnumName/
            enum_dir = enums_path / sanitize_filename(enum_info.name)
            files_count = generator.save_grep_optimized_documentation(enum_info, enum_dir)
            self.stats.markdown_files_generated += files_count

            # Update stats
            self.stats.total_types += 1
            if enum_info.description:
                self.stats.types_with_descriptions += 1
            if enum_info.remarks:
                self.stats.types_with_remarks += 1
            self.stats.total_enum_members += len(enum_info.enum_members)

        print(f"    Generated {len(enum_types)} enum directories")

    def _generate_indexes(self, types: Dict[str, TypeInfo]):
        """Generate index files for navigating the documentation."""
        index_path = self.output_base / "api" / "index"

        # Create index generator
        generator = IndexGenerator(output_base_path=str(index_path))

        # Generate all index files
        generator.save_all_indexes(types)
        self.stats.markdown_files_generated += 3  # by_category, by_assembly, statistics

    def _generate_example_docs(self,
                                examples: Dict[str, ExampleContent],
                                category_mapping: Dict[str, str],
                                types: Dict[str, TypeInfo]):
        """Generate markdown documentation for all examples."""
        examples_path = self.output_base / "docs" / "examples"

        # Create example generator
        generator = ExampleGenerator(output_base_path=str(examples_path))

        # Map examples to categories based on which types reference them
        example_categories = self._map_examples_to_categories(examples, types)

        # Generate example docs
        for url, example in examples.items():
            # Determine category for this example
            category = example_categories.get(url, "Other")

            # Generate and save
            generator.save_example_documentation(example, category)
            self.stats.markdown_files_generated += 1
            self.stats.total_examples += 1

        # Print stats by category
        category_counts = defaultdict(int)
        for category in example_categories.values():
            category_counts[category] += 1

        print(f"  Generated {len(examples)} example files")
        for category, count in sorted(category_counts.items()):
            print(f"    {category}: {count} examples")

    def _copy_programming_guide(self, phase110_path: str):
        """Copy programming guide markdown from Phase 110."""
        source_path = Path(phase110_path)
        dest_path = self.output_base / "docs"

        if not source_path.exists():
            print(f"  Warning: Programming guide not found at {source_path}")
            return

        # Copy all markdown files and directories except examples folder
        for item in source_path.iterdir():
            if item.name == 'examples':
                continue  # Skip examples folder (we generate our own)

            dest = dest_path / item.name

            if item.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
                self.stats.programming_guide_files += 1
            elif item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
                # Count files in copied directory
                for md_file in dest.rglob('*.md'):
                    self.stats.programming_guide_files += 1

        print(f"  Copied {self.stats.programming_guide_files} programming guide files")

    def _generate_summary_report(self):
        """Generate a summary report of the export process."""
        report_path = self.output_base.parent / "metadata" / "export_summary.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            'export_timestamp': datetime.now().isoformat(),
            'statistics': self.stats.to_dict(),
            'output_location': str(self.output_base),
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        print(f"  Summary report saved to: {report_path}")

    def _group_types_by_assembly_category(self,
                                           types: Dict[str, TypeInfo]) -> Dict[str, Dict[str, List[TypeInfo]]]:
        """
        Group types by assembly and then by category.

        Returns:
            Nested dict: {assembly: {category: [types]}}
        """
        grouped = defaultdict(lambda: defaultdict(list))

        for type_info in types.values():
            assembly = type_info.assembly
            category = type_info.functional_category or ""  # Empty string for uncategorized

            grouped[assembly][category].append(type_info)

        return dict(grouped)

    def _map_examples_to_categories(self,
                                     examples: Dict[str, ExampleContent],
                                     types: Dict[str, TypeInfo]) -> Dict[str, str]:
        """
        Map each example URL to a functional category based on which types reference it.

        Returns:
            Dict mapping example URL to category name
        """
        example_to_category = {}

        # Build a mapping of URL to types that reference it
        url_to_types = defaultdict(list)
        for type_info in types.values():
            for example_ref in type_info.examples:
                url_to_types[example_ref.url].append(type_info)

        # Assign category based on the most common category among referencing types
        for url in examples.keys():
            if url in url_to_types:
                # Count categories
                category_counts = defaultdict(int)
                for type_info in url_to_types[url]:
                    if type_info.functional_category:
                        category_counts[type_info.functional_category] += 1

                # Pick the most common category
                if category_counts:
                    best_category = max(category_counts.items(), key=lambda x: x[1])[0]
                    example_to_category[url] = best_category
                else:
                    example_to_category[url] = "Other"
            else:
                example_to_category[url] = "Other"

        return example_to_category


def main():
    """Main entry point for the export pipeline."""
    parser = argparse.ArgumentParser(
        description='Export LLM-friendly markdown documentation from SolidWorks API data'
    )

    parser.add_argument(
        '--phase20',
        default='20_extract_types/metadata/api_members.xml',
        help='Path to Phase 20 XML (type listings)'
    )
    parser.add_argument(
        '--phase40',
        default='40_extract_type_details/metadata/api_types.xml',
        help='Path to Phase 40 XML (type details)'
    )
    parser.add_argument(
        '--phase50',
        default='50_extract_type_member_details/metadata/api_member_details.xml',
        help='Path to Phase 50 XML (member details)'
    )
    parser.add_argument(
        '--phase60',
        default='60_extract_enum_members/metadata/enum_members.xml',
        help='Path to Phase 60 XML (enum members)'
    )
    parser.add_argument(
        '--phase80',
        default='80_parse_examples/output/examples.xml',
        help='Path to Phase 80 XML (examples)'
    )
    parser.add_argument(
        '--phase110',
        default='110_extract_docs_md/output/markdown',
        help='Path to Phase 110 markdown directory'
    )
    parser.add_argument(
        '--functional-categories',
        default='10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html',
        help='Path to FunctionalCategories HTML file'
    )
    parser.add_argument(
        '--output',
        default='120_export_llm_docs/output',
        help='Output directory for generated markdown'
    )

    args = parser.parse_args()

    # Create and run pipeline
    pipeline = ExportPipeline(output_base=args.output)
    pipeline.run(
        phase20_path=args.phase20,
        phase40_path=args.phase40,
        phase50_path=args.phase50,
        phase60_path=args.phase60,
        phase80_path=args.phase80,
        phase110_path=args.phase110,
        functional_categories_html=args.functional_categories
    )


if __name__ == '__main__':
    main()
