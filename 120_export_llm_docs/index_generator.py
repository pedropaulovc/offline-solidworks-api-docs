"""
Index Generator for Phase 120: Export LLM-Friendly Documentation

This module generates index files that organize types by category, assembly, etc.
"""

from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from models import TypeInfo
from markdown_generator import sanitize_filename, _block, clean_text, strip_cross_references


def _format_signature(member) -> str:
    """Return a member's signature prefixed with its return type when known."""
    if getattr(member, 'return_type', '') and member.signature:
        return f"{member.return_type} {member.signature}"
    return member.signature or member.name


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
            md.append(_block([self._type_entry(t) for t in types_list]))

        # Uncategorized types
        if uncategorized:
            md.append("## Uncategorized\n")
            md.append(f"**{len(uncategorized)} types**\n")
            uncategorized.sort(key=lambda t: t.name)
            md.append(_block([self._type_entry(t, with_description=False) for t in uncategorized]))

        return "\n".join(md)

    def _type_entry(self, type_info: TypeInfo, with_description: bool = True) -> str:
        """Render a single ``- [Name](link) - description`` index entry on one line."""
        if type_info.is_enum:
            link = f"../enums/{type_info.name}.md"
        else:
            link = f"../types/{type_info.name}/_overview.md"

        entry = f"- [{type_info.name}]({link})"
        if not with_description:
            return entry

        # Reduce cross-references to plain label text and flatten to a single line
        # before truncating, so the 100-char cap never cuts through a tag or a
        # rendered link (index previews don't need to be navigable).
        description = strip_cross_references(clean_text(type_info.description))
        description = " ".join(description.split())
        if len(description) > 100:
            description = description[:100] + "..."
        if description:
            entry += f" - {description}"
        return entry

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
            md.append(_block([
                f"- **Regular Types**: {regular}",
                f"- **Enumerations**: {enums}",
            ]))

            entries = []
            for type_info in types_list:
                if type_info.is_enum:
                    link = f"../enums/{type_info.name}.md"
                    type_kind = "(enum)"
                else:
                    link = f"../types/{type_info.name}/_overview.md"
                    type_kind = f"({len(type_info.properties)} props, {len(type_info.methods)} methods)"
                entries.append(f"- [{type_info.name}]({link}) {type_kind}")
            md.append(_block(entries))

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
        md.append(_block([
            f"- **Total Types**: {total_types}",
            f"  - Regular Types (Interfaces/Classes): {total_regular}",
            f"  - Enumerations: {total_enums}",
            f"- **Total Properties**: {total_properties}",
            f"- **Total Methods**: {total_methods}",
            f"- **Total Enumeration Members**: {total_enum_members}",
        ]))

        # Largest types by member count
        md.append("## Largest Types by Member Count\n")
        types_by_size = sorted(
            [t for t in types.values() if not t.is_enum],
            key=lambda t: len(t.properties) + len(t.methods),
            reverse=True
        )[:20]

        rows = ["| Type | Properties | Methods | Total |", "|------|-----------|---------|-------|"]
        for type_info in types_by_size:
            total_members = len(type_info.properties) + len(type_info.methods)
            link = f"../types/{type_info.name}/_overview.md"
            rows.append(f"| [{type_info.name}]({link}) | {len(type_info.properties)} | {len(type_info.methods)} | {total_members} |")
        md.append(_block(rows))

        # Categories with most types
        md.append("## Functional Categories by Type Count\n")
        by_category = defaultdict(int)
        for type_info in types.values():
            if type_info.functional_category:
                by_category[type_info.functional_category] += 1

        category_counts = sorted(by_category.items(), key=lambda x: x[1], reverse=True)

        rows = ["| Category | Type Count |", "|----------|------------|"]
        for category, count in category_counts:
            rows.append(f"| {category} | {count} |")
        md.append(_block(rows))

        return "\n".join(md)

    def generate_members_by_type_index(self, types: Dict[str, TypeInfo]) -> str:
        """
        Generate an index listing every member of every interface/class.

        This lets a consumer answer "what methods/properties exist on type X?"
        from a single grep instead of having to list a directory.
        """
        md = []
        md.append("# API Members by Type\n")
        md.append("Every property and method of each interface/class, with signatures. "
                  "Grep for a type name to see its complete member list.\n")

        regular_types = sorted(
            (t for t in types.values() if not t.is_enum),
            key=lambda t: t.fully_qualified_name,
        )

        for type_info in regular_types:
            if not type_info.properties and not type_info.methods:
                continue

            md.append(f"## {type_info.fully_qualified_name}\n")

            entries = []
            for prop in sorted(type_info.properties, key=lambda m: m.name):
                link = f"../types/{type_info.name}/{sanitize_filename(prop.name)}.md"
                entries.append(f"- [property] [{prop.name}]({link}) — `{_format_signature(prop)}`")
            for method in sorted(type_info.methods, key=lambda m: m.name):
                link = f"../types/{type_info.name}/{sanitize_filename(method.name)}.md"
                entries.append(f"- [method] [{method.name}]({link}) — `{_format_signature(method)}`")
            md.append(_block(entries))

        return "\n".join(md)

    def generate_by_member_name_index(self, types: Dict[str, TypeInfo]) -> str:
        """
        Generate an index of all members sorted by member name.

        Sorting by name clusters near-identical sibling members across different
        interfaces together (e.g. ``GetCorresponding`` and
        ``GetCorrespondingEntity``), so a reader who found one easily discovers
        the others and can compare their contracts.
        """
        md = []
        md.append("# API Members by Name\n")
        md.append("All properties and methods across every type, sorted by member name. "
                  "Near-identically named siblings (e.g. `GetCorresponding` vs "
                  "`GetCorrespondingEntity`) appear adjacent so you can compare contracts.\n")

        # Collect (name, kind, type_info, member) for all non-enum members
        entries = []
        for type_info in types.values():
            if type_info.is_enum:
                continue
            for prop in type_info.properties:
                entries.append((prop.name, "property", type_info, prop))
            for method in type_info.methods:
                entries.append((method.name, "method", type_info, method))

        # Sort by member name (case-insensitive), then by type for stability
        entries.sort(key=lambda e: (e[0].lower(), e[2].fully_qualified_name))

        items = []
        for name, kind, type_info, member in entries:
            link = f"../types/{type_info.name}/{sanitize_filename(member.name)}.md"
            items.append(f"- `{name}` [{kind}] on **{type_info.name}** — "
                         f"[doc]({link}) `{_format_signature(member)}`")
        md.append(_block(items))

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

        # Generate members-by-type index (complete member list per interface)
        members_by_type_md = self.generate_members_by_type_index(types)
        with open(self.output_base_path / "members_by_type.md", 'w', encoding='utf-8') as f:
            f.write(members_by_type_md)

        # Generate by-member-name index (clusters sibling members across types)
        by_member_name_md = self.generate_by_member_name_index(types)
        with open(self.output_base_path / "by_member_name.md", 'w', encoding='utf-8') as f:
            f.write(by_member_name_md)

        print(f"  Generated index files in {self.output_base_path}")
