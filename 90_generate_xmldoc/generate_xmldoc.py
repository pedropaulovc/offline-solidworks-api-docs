#!/usr/bin/env python3
"""
Generate XMLDoc files from merged API documentation data.

This script combines data from phases 20, 40, 50, 60, and 80 to generate
standard XMLDoc files (one per assembly) that can be used for IntelliSense
in Visual Studio and other IDEs.

Usage:
    uv run python 90_generate_xmldoc/generate_xmldoc.py
    uv run python 90_generate_xmldoc/generate_xmldoc.py --verbose
    uv run python 90_generate_xmldoc/generate_xmldoc.py --output-dir custom/path
"""

import argparse
import html
import json
import re
import time
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from data_merger import DataMerger, TypeInfo
from id_generator import XMLDocIDGenerator


def set_element_content(element: ET.Element, content: str) -> None:
    """
    Set element content, preserving XML tags like <see cref="...">.

    This function properly handles content that contains XML tags by parsing
    them as sub-elements rather than escaping them as text.

    Args:
        element: The parent element
        content: The content string (may contain XML tags)
    """
    if not content:
        return

    # Wrap content in a temporary root element for parsing
    try:
        # Try to parse as XML fragment
        wrapped = f"<root>{content}</root>"
        temp_root = ET.fromstring(wrapped)

        # Copy text and children from temp root to our element
        element.text = temp_root.text
        for child in temp_root:
            element.append(child)

    except ET.ParseError:
        # If parsing fails, treat as plain text (escape it)
        element.text = content


def set_code_content(element: ET.Element, code: str) -> None:
    """
    Set code element content using CDATA to prevent HTML escaping.

    This function wraps code content in CDATA sections so that characters
    like <, >, & are preserved as-is without HTML escaping.

    Args:
        element: The <code> element
        code: The code content
    """
    if not code:
        return

    # Mark the element for CDATA wrapping with a special marker
    # We'll replace this after XML generation
    element.text = f"__CDATA_START__{code}__CDATA_END__"
    element.set("__cdata__", "true")


class XMLDocGenerator:
    """
    Generates XMLDoc files from merged API documentation.
    """

    def __init__(self, output_dir: Path, metadata_dir: Path, verbose: bool = False):
        """
        Initialize the XMLDoc generator.

        Args:
            output_dir: Directory for generated XMLDoc files
            metadata_dir: Directory for metadata files
            verbose: If True, print detailed progress information
        """
        self.output_dir = output_dir
        self.metadata_dir = metadata_dir
        self.verbose = verbose
        self.id_gen = XMLDocIDGenerator()
        self.merger = None  # Will be set when generate_all is called

        # Statistics
        self.stats = {
            'total_assemblies': 0,
            'total_types': 0,
            'total_properties': 0,
            'total_methods': 0,
            'total_enum_members': 0,
            'types_with_descriptions': 0,
            'types_with_remarks': 0,
            'types_with_examples': 0,
            'examples_added': 0,
            'properties_with_params': 0,
            'methods_with_params': 0,
            'total_parameters_documented': 0,
        }

    def log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def generate_all(self, merger: DataMerger) -> dict[str, Path]:
        """
        Generate XMLDoc files for all assemblies.

        Args:
            merger: DataMerger instance with loaded data

        Returns:
            Dictionary mapping assembly name to output file path
        """
        # Store merger so we can access example content
        self.merger = merger

        self.log("Grouping types by assembly...")
        assemblies = merger.group_by_assembly()
        self.stats['total_assemblies'] = len(assemblies)

        self.log(f"Found {len(assemblies)} assemblies")

        output_files = {}
        for assembly_name, types in assemblies.items():
            self.log(f"\nGenerating XMLDoc for {assembly_name}...")
            output_file = self.generate_assembly_xmldoc(assembly_name, types)
            output_files[assembly_name] = output_file
            self.log(f"  -> {output_file}")

        return output_files

    def generate_assembly_xmldoc(self, assembly_name: str, types: list[TypeInfo]) -> Path:
        """
        Generate XMLDoc file for a single assembly.

        Args:
            assembly_name: Name of the assembly
            types: List of TypeInfo objects for this assembly

        Returns:
            Path to the generated XMLDoc file
        """
        # Create root element
        doc = ET.Element('doc')

        # Add assembly element
        assembly_elem = ET.SubElement(doc, 'assembly')
        name_elem = ET.SubElement(assembly_elem, 'name')
        name_elem.text = assembly_name

        # Add members element
        members_elem = ET.SubElement(doc, 'members')

        # Add each type and its members
        for type_info in types:
            self.add_type_to_members(members_elem, type_info)

        # Pretty-print and save
        xml_str = ET.tostring(doc, encoding='unicode')

        # Replace CDATA markers with actual CDATA sections before parsing
        xml_str = self._process_cdata_markers(xml_str)

        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ')

        # Remove extra blank lines
        lines = [line for line in pretty_xml.split('\n') if line.strip()]
        pretty_xml = '\n'.join(lines)

        # Write to file
        output_file = self.output_dir / f"{assembly_name}.xml"
        output_file.write_text(pretty_xml, encoding='utf-8')

        return output_file

    def _add_example_content(self, example_elem: ET.Element, content: str) -> None:
        """
        Add example content to the example element, parsing <code> tags manually.

        Phase 06 wraps code in <code> tags, but the content inside has special
        characters that make it invalid XML. This method manually parses the
        content to extract text and code blocks.

        Args:
            example_elem: The <example> element to add content to
            content: The content string from Phase 06 (with <code> tags)
        """
        # Split content by <code> and </code> tags
        # Simple regex to find code blocks
        import re

        # Pattern to match <code>...</code> blocks
        code_pattern = r'<code>(.*?)</code>'

        # Find all code blocks
        code_blocks = list(re.finditer(code_pattern, content, re.DOTALL))

        if not code_blocks:
            # No code blocks, just add as text
            example_elem.text = content
            return

        # Process text and code blocks
        last_end = 0
        current_elem = example_elem

        for match in code_blocks:
            # Add text before this code block
            text_before = content[last_end:match.start()]
            if text_before:
                if current_elem == example_elem and example_elem.text is None:
                    example_elem.text = text_before
                else:
                    # Add as tail of previous element
                    if len(current_elem) > 0:
                        if current_elem[-1].tail:
                            current_elem[-1].tail += text_before
                        else:
                            current_elem[-1].tail = text_before
                    else:
                        if current_elem.text:
                            current_elem.text += text_before
                        else:
                            current_elem.text = text_before

            # Add code block
            code_elem = ET.SubElement(example_elem, 'code')
            code_content = match.group(1)
            set_code_content(code_elem, code_content)
            current_elem = example_elem

            last_end = match.end()

        # Add any remaining text after the last code block
        text_after = content[last_end:]
        if text_after and len(example_elem) > 0:
            example_elem[-1].tail = text_after

    def _process_cdata_markers(self, xml_str: str) -> str:
        """
        Process CDATA markers in the XML string.

        Replaces __CDATA_START__content__CDATA_END__ markers with
        actual CDATA sections and removes the marker attributes.

        Args:
            xml_str: The XML string with CDATA markers

        Returns:
            XML string with proper CDATA sections
        """
        import html as html_module

        # Pattern to find code elements with CDATA markers
        # The content between markers will be HTML-escaped, so we need to unescape it
        pattern = r'<code __cdata__="true">(__CDATA_START__)(.*?)(__CDATA_END__)</code>'

        def replace_cdata(match):
            # Get the content between markers (will be HTML-escaped)
            content = match.group(2)
            # Unescape the HTML entities
            content = html_module.unescape(content)
            # Return with proper CDATA wrapper
            return f'<code><![CDATA[{content}]]></code>'

        # Replace all CDATA markers
        xml_str = re.sub(pattern, replace_cdata, xml_str, flags=re.DOTALL)

        return xml_str

    def add_type_to_members(self, members_elem: ET.Element, type_info: TypeInfo) -> None:
        """
        Add a type and all its members to the members element.

        Args:
            members_elem: The <members> XML element
            type_info: TypeInfo object to add
        """
        self.stats['total_types'] += 1

        # Generate type ID
        type_id = self.id_gen.generate_type_id(type_info.namespace, type_info.name)

        # Create member element for the type
        type_member = ET.SubElement(members_elem, 'member')
        type_member.set('name', type_id)

        # Add summary (description)
        if type_info.description:
            summary = ET.SubElement(type_member, 'summary')
            set_element_content(summary, type_info.description)
            self.stats['types_with_descriptions'] += 1

        # Add remarks
        if type_info.remarks:
            remarks = ET.SubElement(type_member, 'remarks')
            set_element_content(remarks, '\n' + type_info.remarks + '\n')
            self.stats['types_with_remarks'] += 1

        # Add examples (C# only)
        if type_info.examples:
            self.stats['types_with_examples'] += 1

            # Filter for C# examples
            csharp_examples = [ex for ex in type_info.examples if ex.language == 'C#']

            for example_ref in csharp_examples:
                # Get example content from merger
                if self.merger:
                    content = self.merger.get_example_content(example_ref.url)
                    if content:
                        # Create example element
                        example_elem = ET.SubElement(type_member, 'example')

                        # Parse content manually since Phase 06 content has <code> tags
                        # but the code inside contains special characters
                        self._add_example_content(example_elem, content)

                        self.stats['examples_added'] += 1
                        self.log(f"  Added C# example: {example_ref.name}")

        # Add properties
        for prop in type_info.properties:
            self.add_property_to_members(members_elem, type_info, prop)

        # Add methods
        for method in type_info.methods:
            self.add_method_to_members(members_elem, type_info, method)

        # Add enum members (as fields)
        for enum_member in type_info.enum_members:
            self.add_enum_member_to_members(members_elem, type_info, enum_member)

    def add_property_to_members(self, members_elem: ET.Element, type_info: TypeInfo,
                                prop: Any) -> None:
        """
        Add a property member to the members element.

        Args:
            members_elem: The <members> XML element
            type_info: Parent type info
            prop: Property object
        """
        self.stats['total_properties'] += 1

        # Generate property ID
        # Use parameter_types from Phase 05 if available (for indexed properties)
        prop_id = self.id_gen.generate_property_id(
            type_info.namespace,
            type_info.name,
            prop.name,
            parameters=getattr(prop, 'parameter_types', None)
        )

        # Create member element
        member = ET.SubElement(members_elem, 'member')
        member.set('name', prop_id)

        # Add summary if available
        if hasattr(prop, 'summary') and prop.summary:
            summary = ET.SubElement(member, 'summary')
            set_element_content(summary, prop.summary)
        else:
            # Placeholder summary
            summary = ET.SubElement(member, 'summary')
            summary.text = f"Gets or sets {prop.name}."

        # Add param tags for indexed properties
        if hasattr(prop, 'parameters') and prop.parameters:
            self.stats['properties_with_params'] += 1
            for param in prop.parameters:
                param_elem = ET.SubElement(member, 'param')
                param_elem.set('name', param.name)
                if param.description:
                    set_element_content(param_elem, param.description)
                self.stats['total_parameters_documented'] += 1

        # Add value description if available
        if hasattr(prop, 'value') and prop.value:
            value = ET.SubElement(member, 'value')
            set_element_content(value, prop.value)

        # Add remarks if available
        if hasattr(prop, 'remarks') and prop.remarks:
            remarks = ET.SubElement(member, 'remarks')
            set_element_content(remarks, '\n' + prop.remarks + '\n')

        # Add availability if available
        if hasattr(prop, 'availability') and prop.availability:
            # Availability can be added as a custom tag or in remarks
            avail = ET.SubElement(member, 'availability')
            avail.text = prop.availability

    def add_method_to_members(self, members_elem: ET.Element, type_info: TypeInfo,
                              method: Any) -> None:
        """
        Add a method member to the members element.

        Args:
            members_elem: The <members> XML element
            type_info: Parent type info
            method: Method object
        """
        self.stats['total_methods'] += 1

        # Generate method ID
        # Use parameter_types from Phase 05 if available
        method_id = self.id_gen.generate_method_id(
            type_info.namespace,
            type_info.name,
            method.name,
            parameters=getattr(method, 'parameter_types', None)
        )

        # Create member element
        member = ET.SubElement(members_elem, 'member')
        member.set('name', method_id)

        # Add summary if available
        if hasattr(method, 'summary') and method.summary:
            summary = ET.SubElement(member, 'summary')
            set_element_content(summary, method.summary)
        else:
            # Placeholder summary
            summary = ET.SubElement(member, 'summary')
            summary.text = f"{method.name} method."

        # Add param tags for each parameter
        if hasattr(method, 'parameters') and method.parameters:
            self.stats['methods_with_params'] += 1
            for param in method.parameters:
                param_elem = ET.SubElement(member, 'param')
                param_elem.set('name', param.name)
                if param.description:
                    set_element_content(param_elem, param.description)
                self.stats['total_parameters_documented'] += 1

        # Add returns if available
        if hasattr(method, 'returns') and method.returns:
            returns = ET.SubElement(member, 'returns')
            set_element_content(returns, method.returns)

        # Add remarks if available
        if hasattr(method, 'remarks') and method.remarks:
            remarks = ET.SubElement(member, 'remarks')
            set_element_content(remarks, '\n' + method.remarks + '\n')

        # Add availability if available
        if hasattr(method, 'availability') and method.availability:
            avail = ET.SubElement(member, 'availability')
            avail.text = method.availability

    def add_enum_member_to_members(self, members_elem: ET.Element, type_info: TypeInfo,
                                   enum_member: Any) -> None:
        """
        Add an enum member to the members element.

        Enum members are represented as fields (F:) in XMLDoc.

        Args:
            members_elem: The <members> XML element
            type_info: Parent enum type info
            enum_member: EnumMember object
        """
        self.stats['total_enum_members'] += 1

        # Generate field ID for enum member
        field_id = self.id_gen.generate_field_id(
            type_info.namespace,
            type_info.name,
            enum_member.name
        )

        # Create member element
        member = ET.SubElement(members_elem, 'member')
        member.set('name', field_id)

        # Add summary from description
        if enum_member.description:
            summary = ET.SubElement(member, 'summary')
            set_element_content(summary, enum_member.description)
        else:
            summary = ET.SubElement(member, 'summary')
            summary.text = enum_member.name

    def save_metadata(self, output_files: dict[str, Path]) -> None:
        """
        Save generation metadata and statistics.

        Args:
            output_files: Dictionary of assembly names to output file paths
        """
        # Generate summary
        summary = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'statistics': self.stats,
            'output_files': {name: str(path) for name, path in output_files.items()},
        }

        # Save summary
        summary_file = self.metadata_dir / 'generation_summary.json'
        summary_file.write_text(json.dumps(summary, indent=2), encoding='utf-8')
        self.log(f"\nSaved summary to {summary_file}")

        # Generate manifest
        manifest = {
            'generator_version': '1.0.0',
            'input_sources': [
                '20_extract_types/metadata/api_members.xml',
                '40_extract_type_details/metadata/api_types.xml',
                '50_extract_type_member_details/metadata/api_member_details.xml',
                '60_extract_enum_members/metadata/enum_members.xml',
                '80_parse_examples/output/examples.xml',
            ],
            'output_directory': str(self.output_dir),
            'total_assemblies': self.stats['total_assemblies'],
            'xmldoc_format': 'Microsoft XMLDoc (VS IntelliSense)',
        }

        manifest_file = self.metadata_dir / 'manifest.json'
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def main() -> None:
    """Main entry point for XMLDoc generation."""
    parser = argparse.ArgumentParser(
        description='Generate XMLDoc files from API documentation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate XMLDoc files with default paths
  uv run python 90_generate_xmldoc/generate_xmldoc.py

  # Generate with verbose output
  uv run python 90_generate_xmldoc/generate_xmldoc.py --verbose

  # Generate with custom output directory
  uv run python 90_generate_xmldoc/generate_xmldoc.py --output-dir custom/path
        """
    )

    parser.add_argument(
        '--members-file',
        type=Path,
        default=Path('20_extract_types/metadata/api_members.xml'),
        help='Path to api_members.xml from Phase 2'
    )

    parser.add_argument(
        '--types-file',
        type=Path,
        default=Path('40_extract_type_details/metadata/api_types.xml'),
        help='Path to api_types.xml from Phase 4'
    )

    parser.add_argument(
        '--member-details-file',
        type=Path,
        default=Path('50_extract_type_member_details/metadata/api_member_details.xml'),
        help='Path to api_member_details.xml from Phase 5'
    )

    parser.add_argument(
        '--enums-file',
        type=Path,
        default=Path('60_extract_enum_members/metadata/enum_members.xml'),
        help='Path to enum_members.xml from Phase 6'
    )

    parser.add_argument(
        '--examples-file',
        type=Path,
        default=Path('80_parse_examples/output/examples.xml'),
        help='Path to examples.xml from Phase 8'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('90_generate_xmldoc/output'),
        help='Output directory for XMLDoc files'
    )

    parser.add_argument(
        '--metadata-dir',
        type=Path,
        default=Path('90_generate_xmldoc/metadata'),
        help='Metadata directory for generation statistics'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed progress information'
    )

    args = parser.parse_args()

    # Create output directories
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.metadata_dir.mkdir(parents=True, exist_ok=True)

    print("=== XMLDoc Generator ===\n")

    # Initialize merger and load data
    merger = DataMerger(verbose=args.verbose)

    try:
        merger.load_api_members(args.members_file)
        merger.load_api_types(args.types_file)

        # Member details file is optional but recommended
        if args.member_details_file.exists():
            merger.load_member_details(args.member_details_file)
        else:
            print(f"Warning: Member details file not found: {args.member_details_file}")

        merger.load_enum_members(args.enums_file)

        # Examples file is optional
        if args.examples_file.exists():
            merger.load_examples(args.examples_file)
        else:
            print(f"Warning: Examples file not found: {args.examples_file}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nPlease ensure all prerequisite phases have been run:")
        print("  - Phase 02: Extract Types")
        print("  - Phase 04: Extract Type Details")
        print("  - Phase 05: Extract Type Member Details (optional)")
        print("  - Phase 06: Extract Enum Members")
        print("  - Phase 08: Parse Examples (optional)")
        return

    # Generate XMLDoc files
    generator = XMLDocGenerator(
        output_dir=args.output_dir,
        metadata_dir=args.metadata_dir,
        verbose=args.verbose
    )

    output_files = generator.generate_all(merger)
    generator.save_metadata(output_files)

    # Print summary
    print("\n=== Generation Summary ===")
    print(f"Assemblies: {generator.stats['total_assemblies']}")
    print(f"Types: {generator.stats['total_types']}")
    print(f"  - With descriptions: {generator.stats['types_with_descriptions']}")
    print(f"  - With remarks: {generator.stats['types_with_remarks']}")
    print(f"  - With examples: {generator.stats['types_with_examples']}")
    print(f"  - C# examples added: {generator.stats['examples_added']}")
    print(f"Properties: {generator.stats['total_properties']}")
    print(f"  - With parameter info: {generator.stats['properties_with_params']}")
    print(f"Methods: {generator.stats['total_methods']}")
    print(f"  - With parameter info: {generator.stats['methods_with_params']}")
    print(f"Parameters documented: {generator.stats['total_parameters_documented']}")
    print(f"Enum members: {generator.stats['total_enum_members']}")
    print(f"\nOutput directory: {args.output_dir}")
    print("\nGeneration complete!")


if __name__ == '__main__':
    main()
