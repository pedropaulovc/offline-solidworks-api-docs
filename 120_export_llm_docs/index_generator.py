"""
Index Generator for Phase 120: Export LLM-Friendly Documentation

This module generates index files that organize types by category, assembly, etc.
"""

from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from models import TypeInfo


class IndexGenerator:
    """Generates index files for navigating the API documentation."""

    def __init__(self, output_base_path: str):
        """
        Initialize the index generator.

        Args:
            output_base_path: Base path for output index files (e.g., output/api/index/)
        """
        self.output_base_path = Path(output_base_path)
        self.output_base_path.mkdir(parents=True, exist_ok=True)

    def generate_by_category_index(self, types: Dict[str, TypeInfo]) -> str:
        """
        Generate index organized by functional categories.

        Args:
            types: Dictionary of all types

        Returns:
            Markdown content for the category index
        """
        md = []
        md.append("# API Types by Functional Category\n")
        md.append("This index organizes all SolidWorks API types by their functional categories.\n")

        # Group types by category
        by_category = defaultdict(list)
        uncategorized = []

        for type_info in types.values():
            if type_info.functional_category:
                by_category[type_info.functional_category].append(type_info)
            else:
                uncategorized.append(type_info)

        # Sort categories alphabetically
        for category in sorted(by_category.keys()):
            types_list = by_category[category]
            # Sort types within category
            types_list.sort(key=lambda t: t.name)

            md.append(f"## {category}\n")
            md.append(f"**{len(types_list)} types**\n")

            for type_info in types_list:
                # Create relative link to type overview
                if type_info.is_enum:
                    link = f"../enums/{type_info.name}/_overview.md"
                else:
                    link = f"../types/{type_info.name}/_overview.md"

                description = type_info.description[:100] + "..." if len(type_info.description) > 100 else type_info.description
                md.append(f"- [{type_info.name}]({link})")
                if description:
                    md.append(f" - {description}")
                md.append("\n")

            md.append("")

        # Uncategorized types
        if uncategorized:
            md.append("## Uncategorized\n")
            md.append(f"**{len(uncategorized)} types**\n")
            uncategorized.sort(key=lambda t: t.name)

            for type_info in uncategorized:
                if type_info.is_enum:
                    link = f"../enums/{type_info.name}/_overview.md"
                else:
                    link = f"../types/{type_info.name}/_overview.md"

                md.append(f"- [{type_info.name}]({link})\n")

            md.append("")

        return "\n".join(md)

    def generate_by_assembly_index(self, types: Dict[str, TypeInfo]) -> str:
        """
        Generate index organized by .NET assembly.

        Args:
            types: Dictionary of all types

        Returns:
            Markdown content for the assembly index
        """
        md = []
        md.append("# API Types by Assembly\n")
        md.append("This index organizes all SolidWorks API types by their .NET assembly.\n")

        # Group types by assembly
        by_assembly = defaultdict(list)

        for type_info in types.values():
            by_assembly[type_info.assembly].append(type_info)

        # Sort assemblies alphabetically
        for assembly in sorted(by_assembly.keys()):
            types_list = by_assembly[assembly]
            # Sort types within assembly
            types_list.sort(key=lambda t: t.name)

            md.append(f"## {assembly}\n")
            md.append(f"**{len(types_list)} types**\n")

            # Count types vs enums
            regular = sum(1 for t in types_list if not t.is_enum)
            enums = sum(1 for t in types_list if t.is_enum)
            md.append(f"- **Regular Types**: {regular}\n")
            md.append(f"- **Enumerations**: {enums}\n\n")

            for type_info in types_list:
                # Create relative link to type overview
                if type_info.is_enum:
                    link = f"../enums/{type_info.name}/_overview.md"
                    type_kind = "(enum)"
                else:
                    link = f"../types/{type_info.name}/_overview.md"
                    type_kind = f"({len(type_info.properties)} props, {len(type_info.methods)} methods)"

                md.append(f"- [{type_info.name}]({link}) {type_kind}\n")

            md.append("")

        return "\n".join(md)

    def generate_type_statistics_index(self, types: Dict[str, TypeInfo]) -> str:
        """
        Generate index with type statistics and quick facts.

        Args:
            types: Dictionary of all types

        Returns:
            Markdown content for the statistics index
        """
        md = []
        md.append("# API Documentation Statistics\n")

        # Overall counts
        total_types = len(types)
        total_enums = sum(1 for t in types.values() if t.is_enum)
        total_regular = total_types - total_enums
        total_properties = sum(len(t.properties) for t in types.values())
        total_methods = sum(len(t.methods) for t in types.values())
        total_enum_members = sum(len(t.enum_members) for t in types.values())

        md.append("## Overview\n")
        md.append(f"- **Total Types**: {total_types}\n")
        md.append(f"  - Regular Types (Interfaces/Classes): {total_regular}\n")
        md.append(f"  - Enumerations: {total_enums}\n")
        md.append(f"- **Total Properties**: {total_properties}\n")
        md.append(f"- **Total Methods**: {total_methods}\n")
        md.append(f"- **Total Enumeration Members**: {total_enum_members}\n\n")

        # Largest types by member count
        md.append("## Largest Types by Member Count\n")
        types_by_size = sorted(
            [t for t in types.values() if not t.is_enum],
            key=lambda t: len(t.properties) + len(t.methods),
            reverse=True
        )[:20]

        md.append("| Type | Properties | Methods | Total |\n")
        md.append("|------|-----------|---------|-------|\n")
        for type_info in types_by_size:
            total_members = len(type_info.properties) + len(type_info.methods)
            link = f"../types/{type_info.name}/_overview.md"
            md.append(f"| [{type_info.name}]({link}) | {len(type_info.properties)} | {len(type_info.methods)} | {total_members} |\n")

        md.append("\n")

        # Categories with most types
        md.append("## Functional Categories by Type Count\n")
        by_category = defaultdict(int)
        for type_info in types.values():
            if type_info.functional_category:
                by_category[type_info.functional_category] += 1

        category_counts = sorted(by_category.items(), key=lambda x: x[1], reverse=True)

        md.append("| Category | Type Count |\n")
        md.append("|----------|------------|\n")
        for category, count in category_counts:
            md.append(f"| {category} | {count} |\n")

        md.append("\n")

        return "\n".join(md)

    def save_all_indexes(self, types: Dict[str, TypeInfo]):
        """
        Generate and save all index files.

        Args:
            types: Dictionary of all types
        """
        # Generate by category
        by_category_md = self.generate_by_category_index(types)
        with open(self.output_base_path / "by_category.md", 'w', encoding='utf-8') as f:
            f.write(by_category_md)

        # Generate by assembly
        by_assembly_md = self.generate_by_assembly_index(types)
        with open(self.output_base_path / "by_assembly.md", 'w', encoding='utf-8') as f:
            f.write(by_assembly_md)

        # Generate statistics
        statistics_md = self.generate_type_statistics_index(types)
        with open(self.output_base_path / "statistics.md", 'w', encoding='utf-8') as f:
            f.write(statistics_md)

        print(f"  Generated index files in {self.output_base_path}")
