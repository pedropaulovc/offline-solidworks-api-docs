"""
Export Pipeline for Phase 120: Export LLM-Friendly Documentation

This script orchestrates the entire export process, generating markdown documentation
from the outputs of phases 20, 40, 50, 60, 80, and 110.
"""

import argparse
import json
import re
import shutil
from pathlib import Path
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
            functional_categories_html: str,
            phase115_path: str = ""):
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
            phase115_path: Path to Phase 115 referenced-page markdown directory (optional)
        """
        # Markdown roots whose pages are copied into ``docs/`` and cross-linked.
        self.guide_roots = [phase110_path] + ([phase115_path] if phase115_path else [])
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

        # Step 3: Map examples to categories (needed for both API docs and example docs)
        print("\n[3/9] Mapping examples to categories...")
        example_categories = self._map_examples_to_categories(data_loader.examples, types)
        print(f"  Mapped {len(example_categories)} examples to categories")

        # Build the guide-link map so inline <see href> references to guide/referenced
        # pages that ship in the bundle become relative file links (docs/ folder).
        guide_links = self._build_guide_links(self.guide_roots)
        print(f"  Resolved {len(guide_links)} guide/referenced pages for cross-linking")

        # Step 4: Generate API documentation
        print("\n[4/9] Generating API documentation...")
        self._generate_api_docs(types, data_loader, example_categories, guide_links)

        # Step 5: Generate index files
        print("\n[5/9] Generating index files...")
        self._generate_indexes(types)

        # Step 6: Generate example documentation
        print("\n[6/9] Generating example documentation...")
        self._generate_example_docs(data_loader.examples, example_categories)

        # Step 7: Copy programming guide + referenced pages into docs/
        print("\n[7/9] Copying programming guide...")
        for root in self.guide_roots:
            self._copy_programming_guide(root)
        # Resolve the API-reference links Phase 110 left pointing at the original
        # ``.html`` pages so they target the ``types/``/``enums/`` files we ship.
        self._rewrite_guide_api_links(types, self._api_base_url(), guide_links, data_loader.examples)

        # Step 8: Generate output README for LLMs
        print("\n[8/9] Generating output README...")
        self._generate_output_readme(types, data_loader.examples)

        # Step 9: Generate summary report
        print("\n[9/9] Generating summary report...")
        self._generate_summary_report()

        print("\n" + "="*80)
        print("Export Complete!")
        print("="*80)
        print(f"\nOutput location: {self.output_base}")
        print(f"Total markdown files generated: {self.stats.markdown_files_generated}")

    def _build_guide_links(self, markdown_roots: List[str]) -> Dict[str, str]:
        """Map guide/referenced-page URLs to their bundle-relative ``docs/`` paths.

        Reads the ``files_created.jsonl`` beside each markdown root (Phase 110's
        programming guide and Phase 115's referenced-page closure) and keys it by
        :func:`guide_link_key` so ``<see href>`` references resolve to the copies
        ``_copy_programming_guide`` places under ``docs/``. Missing manifests are
        skipped (those references fall back to external links).
        """
        from markdown_generator import guide_link_key

        guide_links: Dict[str, str] = {}
        for root in markdown_roots:
            manifest = Path(root).parent.parent / "metadata" / "files_created.jsonl"
            if not manifest.exists():
                print(f"  Warning: guide manifest not found at {manifest}; those <see href> links stay external")
                continue
            with open(manifest, encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    # markdown_path is repo-relative and always under ".../output/markdown/".
                    rel = entry["markdown_path"].replace("\\", "/").split("output/markdown/", 1)[-1]
                    guide_links[guide_link_key(entry["original_url"])] = f"docs/{rel}"
        return guide_links

    def _generate_api_docs(self, types: Dict[str, TypeInfo], data_loader: DataLoader,
                           example_categories: Dict[str, str], guide_links: Dict[str, str]):
        """Generate grep-optimized markdown documentation for all API types."""
        # Create markdown generator in grep-optimized mode
        generator = MarkdownGenerator(
            output_base_path=str(self.output_base),
            examples_loader_func=data_loader.get_example_content,
            grep_optimized=True,
            example_categories=example_categories,
            guide_links=guide_links
        )

        # Separate types from enums
        regular_types = {fqn: t for fqn, t in types.items() if not t.is_enum}
        enum_types = {fqn: t for fqn, t in types.items() if t.is_enum}

        # Generate regular types
        print(f"  Generating {len(regular_types)} regular types...")
        types_path = self.output_base / "types"
        for fqn, type_info in regular_types.items():
            # Create directory: types/TypeName/
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

        # Generate enums (one flat file per enum: enums/EnumName.md with all members inline)
        print(f"  Generating {len(enum_types)} enumerations...")
        enums_path = self.output_base / "enums"
        for fqn, enum_info in enum_types.items():
            enum_file = enums_path / f"{sanitize_filename(enum_info.name)}.md"
            files_count = generator.save_enum_documentation(enum_info, enum_file)
            self.stats.markdown_files_generated += files_count

            # Update stats
            self.stats.total_types += 1
            if enum_info.description:
                self.stats.types_with_descriptions += 1
            if enum_info.remarks:
                self.stats.types_with_remarks += 1
            self.stats.total_enum_members += len(enum_info.enum_members)

        print(f"    Generated {len(enum_types)} enum files")

    def _generate_indexes(self, types: Dict[str, TypeInfo]):
        """Generate index files for navigating the documentation."""
        index_path = self.output_base / "index"

        # Create index generator
        generator = IndexGenerator(output_base_path=str(index_path))

        # Generate all index files
        generator.save_all_indexes(types)
        # by_category, by_assembly, statistics, members_by_type, by_member_name
        self.stats.markdown_files_generated += 5

    def _generate_example_docs(self,
                                examples: Dict[str, ExampleContent],
                                example_categories: Dict[str, str]):
        """Generate markdown documentation for all examples in a flat folder structure."""
        examples_path = self.output_base / "examples"

        # Create example generator
        generator = ExampleGenerator(output_base_path=str(examples_path))

        # Generate example docs (all in flat folder, category passed for API compatibility only)
        for url, example in examples.items():
            # Category is still computed but not used for folder organization
            category = example_categories.get(url, "Other")

            # Generate and save (category parameter is ignored, kept for API compatibility)
            generator.save_example_documentation(example, category)
            self.stats.markdown_files_generated += 1
            self.stats.total_examples += 1

        print(f"  Generated {len(examples)} example files in flat folder structure")

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

    def _api_base_url(self) -> str:
        """Online help base URL (``https://help.solidworks.com/2026/english/api/``).

        Derived from a guide manifest's ``original_url`` so the version year is not
        hard-coded; falls back to the 2026 base if no manifest is available.
        """
        default = "https://help.solidworks.com/2026/english/api/"
        for root in self.guide_roots:
            manifest = Path(root).parent.parent / "metadata" / "files_created.jsonl"
            if not manifest.exists():
                continue
            with open(manifest, encoding="utf-8") as f:
                for line in f:
                    url = json.loads(line).get("original_url", "")
                    idx = url.find("/api/")
                    if idx != -1:
                        return f"https://help.solidworks.com{url[:idx + 5]}"
            break
        return default

    @staticmethod
    def _md_destination(path: str) -> str:
        """A Markdown link destination, angle-wrapped when it needs to be.

        Phase 110 mirrors the guide's own hierarchy, so many targets are paths like
        ``Programming with the SOLIDWORKS API/Add-ins/Toolbars.md``. A bare space
        ends the destination in CommonMark, which would break the link -- ``<...>``
        is how ``_render_see_also`` already handles it.
        """
        return f"<{path}>" if re.search(r"[ ()]", path) else path

    def _rewrite_guide_api_links(self, types: Dict[str, TypeInfo], base_url: str,
                                 guide_links: Dict[str, str],
                                 examples: Dict[str, "ExampleContent"]) -> None:
        """Resolve links in the copied programming guide and referenced pages.

        Phase 110/115 leave links pointing at the original ``.html`` pages (they
        have no knowledge of the tree Phase 120 generates). Three kinds resolve:

        - *Reference pages* (``Assembly~Type~Member.html``) become the shipping
          ``types/{Type}/{Member}.md``, ``types/{Type}/_overview.md`` or
          ``enums/{Enum}.md`` file, matching names case-insensitively so source-doc
          typos (e.g. ``IWizardHoleFeatureDAta2``) still resolve.
        - *Guide/referenced pages* become their ``docs/`` copy.
        - *Example pages* become their flat ``examples/{name}.md`` file.

        The last two are usually written as bare relative hrefs
        (``DimXpert_Main_Module_CSharp.htm``, ``../swconst/DP_Units.htm``), which is
        why they are matched on basename, the same key ``<see href>`` resolution
        uses. Reference links whose target does not ship are pointed at the online
        help page instead of a dead relative path.
        """
        import posixpath
        from markdown_generator import guide_link_key, parse_api_ref_url

        # Basename -> shipping file, for the non-reference page kinds.
        page_idx: Dict[str, str] = dict(guide_links)
        for url in examples:
            md_name = re.sub(r"\.html?$", ".md", url.split("/")[-1], flags=re.IGNORECASE)
            page_idx.setdefault(guide_link_key(url), f"examples/{md_name}")

        # Case-insensitive indexes over the shipping API-reference tree.
        type_idx: Dict[str, tuple] = {}       # type_lower -> (sanitized name, is_enum)
        member_idx: Dict[tuple, str] = {}     # (type_lower, member_lower) -> filename
        for t in types.values():
            type_idx[t.name.lower()] = (sanitize_filename(t.name), t.is_enum)
            if t.is_enum:
                continue
            for m in list(t.properties) + list(t.methods):
                member_idx[(t.name.lower(), m.name.lower())] = sanitize_filename(m.name)

        docs_root = self.output_base / "docs"
        if not docs_root.exists():
            return

        # Allow a #fragment or ?query after the extension (parse_api_ref_url strips them).
        link_re = re.compile(r'(\[[^\]]+\]\()<?([^)>]+?\.html?(?:[?#][^)>]*)?)>?(\))')
        resolved = external = pages = 0

        for md_file in docs_root.rglob("*.md"):
            guide_dir = posixpath.dirname(md_file.relative_to(self.output_base).as_posix())
            state = {"changed": False}

            def repl(match: "re.Match[str]") -> str:
                nonlocal resolved, external, pages
                head, url, tail = match.group(1), match.group(2), match.group(3)
                parsed = parse_api_ref_url(url)
                if parsed is None:
                    # Not a reference page: a guide, referenced or example page,
                    # linked by bare basename. Point at the copy the bundle ships,
                    # carrying any #section across to the local file.
                    target = page_idx.get(guide_link_key(url))
                    if not target:
                        return match.group(0)
                    _, _, fragment = url.partition("#")
                    anchor = f"#{fragment}" if fragment else ""
                    destination = f"{posixpath.relpath(target, guide_dir)}{anchor}"
                    pages += 1
                    state["changed"] = True
                    return f"{head}{self._md_destination(destination)}{tail}"

                assembly, type_name, member_name = parsed
                entry = type_idx.get(type_name.lower())
                if entry:
                    sanitized_type, is_enum = entry
                    target = None
                    if is_enum:
                        target = f"enums/{sanitized_type}.md"
                    elif member_name is None:
                        target = f"types/{sanitized_type}/_overview.md"
                    elif (type_name.lower(), member_name.lower()) in member_idx:
                        member_file = member_idx[(type_name.lower(), member_name.lower())]
                        target = f"types/{sanitized_type}/{member_file}.md"
                    # A named member the type does not export (obsolete/typoed) has no
                    # file to point at — fall through to the canonical online page
                    # rather than silently redirecting to the type overview.
                    if target:
                        resolved += 1
                        state["changed"] = True
                        return f"{head}{posixpath.relpath(target, guide_dir)}{tail}"

                # Not in the bundle: link the canonical online page, not a dead path.
                # Same-directory references carry no assembly segment in the URL; recover
                # it from the referenced page's own folder so the URL is not malformed.
                asm = assembly or posixpath.basename(guide_dir)
                if not asm or asm == "docs":
                    return match.group(0)
                basename = url.split('?')[0].split('#')[0].split('/')[-1]
                external += 1
                state["changed"] = True
                return f"{head}{base_url}{asm}/{basename}{tail}"

            new_content = link_re.sub(repl, md_file.read_text(encoding="utf-8"))
            if state["changed"]:
                md_file.write_text(new_content, encoding="utf-8")

        print(f"  Rewrote programming-guide API links: {resolved} in-bundle, {external} external")
        print(f"  Resolved {pages} guide/example page links to bundle files")

    def _generate_output_readme(self, types: Dict[str, TypeInfo], examples: Dict[str, ExampleContent]):
        """Generate a README.md in the output folder explaining how to consume the docs."""
        readme_path = self.output_base / "README.md"

        # Count stats for the README
        regular_types = [t for t in types.values() if not t.is_enum]
        enum_types = [t for t in types.values() if t.is_enum]
        total_members = sum(len(t.properties) + len(t.methods) for t in regular_types)
        total_enum_members = sum(len(t.enum_members) for t in enum_types)

        readme_content = f"""# SolidWorks API Documentation - LLM-Optimized

**Stats**: {len(regular_types):,} types, {len(enum_types):,} enums, {total_members:,} members, {len(examples):,} examples ({self.stats.markdown_files_generated:,} files)

## Structure

```
types/{{TypeName}}/               # Regular types (interfaces, classes)
  _overview.md                    # Type info: description, remarks, member counts
  {{MethodName}}.md               # Individual method files
  {{PropertyName}}.md             # Individual property files

enums/{{EnumName}}.md             # One file per enumeration (all members inline)

index/
  by_category.md                  # Types by functional category
  by_assembly.md                  # Types by .NET assembly
  statistics.md                   # Stats and largest types
  members_by_type.md              # Every member of every type (grep a type for its full surface)
  by_member_name.md               # All members sorted by name (siblings cluster adjacently)

examples/                         # Code examples (flat folder, all in one directory)

docs/                             # Programming guide content
```

## Query Patterns

**Find type overview**: Read `types/{{TypeName}}/_overview.md`
**Find method/property**: Read `types/{{TypeName}}/{{MemberName}}.md`
**List all members**: List files in `types/{{TypeName}}/`, or grep `index/members_by_type.md`
**Find related/sibling members**: A member's `## See Also` section links related members; or grep `index/by_member_name.md` where near-identical names (e.g. `GetCorresponding` vs `GetCorrespondingEntity`) appear adjacent. Absence of a name there means it is not in the API — not merely undocumented.
**Find an enum (with all members)**: Read `enums/{{EnumName}}.md`
**Find by category**: Read `index/by_category.md`
**Search by keyword**: Search file contents in `types/` or `enums/`
**Filter by metadata**: Search YAML frontmatter (e.g., `kind: method`, `category: Assembly Interfaces`)

## YAML Frontmatter

**Type overviews** have: `name`, `assembly`, `namespace`, `category`, `is_enum`, `property_count`, `method_count`, `enum_member_count`

**Enum files** have: `name`, `kind: enum`, `assembly`, `namespace`, `category`, `is_enum`, `enum_member_count`

**Member files** have: `type`, `member`, `kind` (method|property), `assembly`, `namespace`, `category`

## Cross-References

Use `[[TypeName]]` or `[[TypeName::MemberName]]` format for type references.

---
*SolidWorks API Help 2026 | For personal/educational use only*
"""

        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)

        print(f"  Generated README.md at: {readme_path}")
        self.stats.markdown_files_generated += 1

    def _generate_summary_report(self):
        """Generate a summary report of the export process."""
        report_path = self.output_base.parent / "metadata" / "export_summary.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        report = {
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
        # Normalize URLs by removing leading slash for consistency
        url_to_types = defaultdict(list)
        for type_info in types.values():
            for example_ref in type_info.examples:
                normalized_url = example_ref.url.lstrip('/')
                url_to_types[normalized_url].append(type_info)

        # Assign category based on the most common category among referencing types
        for url in examples.keys():
            # Normalize URL for lookup
            normalized_url = url.lstrip('/')
            if normalized_url in url_to_types:
                # Count categories
                category_counts = defaultdict(int)
                for type_info in url_to_types[normalized_url]:
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
    # Determine project root (script is in 120_export_llm_docs/)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    parser = argparse.ArgumentParser(
        description='Export LLM-friendly markdown documentation from SolidWorks API data'
    )

    parser.add_argument(
        '--phase20',
        default=str(project_root / '20_extract_types/metadata/api_members.xml'),
        help='Path to Phase 20 XML (type listings)'
    )
    parser.add_argument(
        '--phase40',
        default=str(project_root / '40_extract_type_details/metadata/api_types.xml'),
        help='Path to Phase 40 XML (type details)'
    )
    parser.add_argument(
        '--phase50',
        default=str(project_root / '50_extract_type_member_details/metadata/api_member_details.xml'),
        help='Path to Phase 50 XML (member details)'
    )
    parser.add_argument(
        '--phase60',
        default=str(project_root / '60_extract_enum_members/metadata/enum_members.xml'),
        help='Path to Phase 60 XML (enum members)'
    )
    parser.add_argument(
        '--phase80',
        default=str(project_root / '80_parse_examples/output/examples.xml'),
        help='Path to Phase 80 XML (examples)'
    )
    parser.add_argument(
        '--phase110',
        default=str(project_root / '110_extract_docs_md/output/markdown'),
        help='Path to Phase 110 markdown directory'
    )
    parser.add_argument(
        '--phase115',
        default=str(project_root / '115_crawl_referenced_pages/output/markdown'),
        help='Path to Phase 115 referenced-page markdown directory'
    )
    parser.add_argument(
        '--functional-categories',
        default=str(project_root / '10_crawl_toc_pages/output/html/sldworksapi/FunctionalCategories-sldworksapi_2cd1902c_2cd1902c.htmll.html'),
        help='Path to FunctionalCategories HTML file'
    )
    parser.add_argument(
        '--output',
        default=str(project_root / '120_export_llm_docs/output'),
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
        functional_categories_html=args.functional_categories,
        phase115_path=args.phase115
    )


if __name__ == '__main__':
    main()
