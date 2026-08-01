#!/usr/bin/env python3
"""
Generate XMLDoc files from merged API documentation data.

This script combines data from phases 20, 40, 50, 60, and 80 to generate
standard XMLDoc files (one per assembly) that can be used for IntelliSense
in Visual Studio and other IDEs.

Usage:
    uv run python 90_export_xmldoc/generate_xmldoc.py
    uv run python 90_export_xmldoc/generate_xmldoc.py --verbose
    uv run python 90_export_xmldoc/generate_xmldoc.py --output-dir custom/path
"""

import argparse
import html
import json
import re
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.line_endings import normalize_tree  # noqa: E402
from typing import Any

from data_merger import DataMerger, ExampleReference, TypeInfo
from id_generator import XMLDocIDGenerator

SW_NAMESPACE = 'urn:solidworks:offline-xmldoc:1'
SW_PREFIX = f'{{{SW_NAMESPACE}}}'
ET.register_namespace('sw', SW_NAMESPACE)


def sw_tag(name: str) -> str:
    """Return a namespaced extension element name."""
    return f'{SW_PREFIX}{name}'


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


def set_cdata_content(element: ET.Element, content: str) -> None:
    """
    Set element content using CDATA to prevent XML escaping.

    ElementTree does not write CDATA sections directly, so a marker is
    replaced after serialization.
    """
    if not content:
        return

    # CDATA cannot contain its own terminator. Split it before serialization.
    safe_content = content.replace(']]>', ']]]]><![CDATA[>')
    element.text = f"__CDATA_START__{safe_content}__CDATA_END__"
    element.set("__cdata__", "true")


def set_code_content(element: ET.Element, code: str) -> None:
    """Set code content using CDATA."""
    set_cdata_content(element, code)


class XMLDocGenerator:
    """
    Generates XMLDoc files from merged API documentation.
    """

    def __init__(self, output_dir: Path, metadata_dir: Path,
                 guide_dirs: list[Path] | None = None, verbose: bool = False):
        """
        Initialize the XMLDoc generator.

        Args:
            output_dir: Directory for generated XMLDoc files
            metadata_dir: Directory for metadata files
            verbose: If True, print detailed progress information
        """
        self.output_dir = output_dir
        self.metadata_dir = metadata_dir
        self.guide_dirs = [path for path in (guide_dirs or []) if path.exists()]
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
            'examples_cataloged': 0,
            'guide_pages': 0,
            'members_with_signatures': 0,
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

        if self.guide_dirs:
            output_files['guides'] = self.generate_guides_xmldoc()

        if self.merger.examples:
            output_files['examples'] = self.generate_examples_xmldoc()

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

        output_file = self.output_dir / f"{assembly_name}.xml"
        return self._write_xml_document(doc, output_file)

    def _write_xml_document(self, doc: ET.Element, output_file: Path) -> Path:
        """Serialize one XMLDoc document with deterministic formatting."""
        xml_str = ET.tostring(doc, encoding='unicode')

        # Replace CDATA markers with actual CDATA sections before parsing
        xml_str = self._process_cdata_markers(xml_str)

        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ')

        # Remove extra blank lines
        lines = [line for line in pretty_xml.split('\n') if line.strip()]
        pretty_xml = '\n'.join(lines)

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

        # Pattern to find ordinary or namespaced elements with CDATA markers.
        # The content between markers will be HTML-escaped, so we need to unescape it.
        pattern = (
            r'<(?P<tag>[A-Za-z_][\w:.-]*)(?P<before>[^>]*?)\s'
            r'__cdata__="true"(?P<after>[^>]*)>'
            r'__CDATA_START__(?P<content>.*?)__CDATA_END__'
            r'</(?P=tag)>'
        )

        def replace_cdata(match):
            # Get the content between markers (will be HTML-escaped)
            content = match.group('content')
            # Unescape the HTML entities
            content = html_module.unescape(content)
            # Return with proper CDATA wrapper
            tag = match.group('tag')
            attributes = f"{match.group('before')}{match.group('after')}".rstrip()
            return f'<{tag}{attributes}><![CDATA[{content}]]></{tag}>'

        # Replace all CDATA markers
        xml_str = re.sub(pattern, replace_cdata, xml_str, flags=re.DOTALL)

        return xml_str

    def _guide_title(self, content: str, fallback: str) -> str:
        """Extract the first Markdown H1 title, falling back to the filename."""
        for line in content.splitlines():
            if line.startswith('# '):
                return line[2:].strip()
        return fallback

    def _example_links(self):
        """Yield every API member and its attached example references."""
        for type_info in sorted(self.merger.types.values(), key=lambda item: f'{item.namespace}.{item.name}'):
            type_id = self.id_gen.generate_type_id(type_info.namespace, type_info.name)
            yield type_id, type_info.examples

            for prop in type_info.properties:
                prop_id = self.id_gen.generate_property_id(
                    type_info.namespace,
                    type_info.name,
                    prop.name,
                    parameters=getattr(prop, 'parameter_types', None),
                )
                yield prop_id, prop.examples

            for method in type_info.methods:
                method_id = self.id_gen.generate_method_id(
                    type_info.namespace,
                    type_info.name,
                    method.name,
                    parameters=getattr(method, 'parameter_types', None),
                )
                yield method_id, method.examples

    def _infer_example_language(self, url: str) -> str:
        """Infer a language for an orphan example when no API ref has it."""
        upper_url = url.upper()
        if 'CPLUSPLUS' in upper_url or 'CPP' in upper_url:
            return 'C++ COM'
        if 'VBNET' in upper_url:
            return 'VB.NET'
        if upper_url.endswith('_VB.HTM'):
            return 'VBA'
        if 'CSHARP' in upper_url:
            return 'C#'
        return 'Unknown'

    def add_example_refs(self, member: ET.Element, references: list) -> None:
        """Link a real XMLDoc member to all of its examples."""
        if not self.merger:
            return
        for example_ref in references:
            if self.merger.get_example_content(example_ref.url):
                ET.SubElement(member, sw_tag('example-ref'), {
                    'id': example_ref.url.lstrip('/'),
                    'language': example_ref.language,
                    'source': example_ref.url,
                })

    def generate_guides_xmldoc(self) -> Path:
        """Write conceptual/how-to Markdown pages into a companion XMLDoc."""
        doc = ET.Element('doc')
        assembly = ET.SubElement(doc, 'assembly')
        ET.SubElement(assembly, 'name').text = 'SolidWorks.Interop.guides'
        ET.SubElement(doc, 'members')
        guides = ET.SubElement(doc, sw_tag('guides'), {'format': 'markdown'})

        for index, guide_dir in enumerate(self.guide_dirs, start=1):
            root_label = f'root{index}'
            for guide_path in sorted(guide_dir.rglob('*.md')):
                relative_path = guide_path.relative_to(guide_dir).as_posix()
                content = guide_path.read_text(encoding='utf-8')
                guide = ET.SubElement(guides, sw_tag('guide'), {
                    'id': f'{root_label}/{relative_path}',
                    'title': self._guide_title(content, guide_path.stem),
                    'source': relative_path,
                    'root': root_label,
                })
                content_elem = ET.SubElement(guide, sw_tag('content'), {
                    'format': 'markdown'
                })
                set_cdata_content(content_elem, content)
                self.stats['guide_pages'] += 1

        output_file = self.output_dir / 'SolidWorks.Interop.guides.xml'
        return self._write_xml_document(doc, output_file)

    def generate_examples_xmldoc(self) -> Path:
        """Write all recovered examples and language metadata to a catalog."""
        doc = ET.Element('doc')
        assembly = ET.SubElement(doc, 'assembly')
        ET.SubElement(assembly, 'name').text = 'SolidWorks.Interop.examples'
        ET.SubElement(doc, 'members')
        examples_elem = ET.SubElement(doc, sw_tag('examples'))

        examples = {}
        for member_id, references in self._example_links():
            for example_ref in references:
                content = self.merger.get_example_content(example_ref.url)
                if not content:
                    continue

                key = example_ref.url.lstrip('/')
                if key not in examples:
                    examples[key] = {
                        'ref': example_ref,
                        'content': content,
                        'member_ids': [],
                    }
                if member_id not in examples[key]['member_ids']:
                    examples[key]['member_ids'].append(member_id)

        # Preserve any parsed example content that is not linked from a type or
        # member. This keeps the catalog complete even when the source docs have
        # an orphaned example page.
        for url, example_content in self.merger.examples.items():
            key = url.lstrip('/')
            if key not in examples:
                examples[key] = {
                    'ref': ExampleReference(
                        name=Path(url).stem,
                        language=self._infer_example_language(url),
                        url=url,
                    ),
                    'content': example_content.content,
                    'member_ids': [],
                }

        for key in sorted(examples):
            item = examples[key]
            example_ref = item['ref']
            example = ET.SubElement(examples_elem, sw_tag('example'), {
                'id': key,
                'title': example_ref.name,
                'language': example_ref.language,
                'source': example_ref.url,
            })
            for member_id in item['member_ids']:
                ET.SubElement(example, sw_tag('applies-to'), {'cref': member_id})
            content_elem = ET.SubElement(example, sw_tag('content'), {
                'format': 'solidworks-example'
            })
            set_cdata_content(content_elem, item['content'])
            self.stats['examples_cataloged'] += 1

        output_file = self.output_dir / 'SolidWorks.Interop.examples.xml'
        return self._write_xml_document(doc, output_file)

    def add_signature(self, member: ET.Element, data: Any, kind: str) -> None:
        """Add the complete Phase 50 signature as a machine-readable extension."""
        signature = getattr(data, 'signature', None)
        return_type = getattr(data, 'return_type', None)
        if not signature and not return_type:
            return

        full_signature = ' '.join(
            part for part in (return_type, signature) if part
        )
        signature_elem = ET.SubElement(member, sw_tag('signature'), {
            'kind': kind,
            'display': full_signature,
        })
        if return_type:
            signature_elem.set('return-type', return_type)

        for parameter in getattr(data, 'parameters', None) or []:
            attrs = {'name': parameter.name, 'type': parameter.type}
            if parameter.type.endswith('@'):
                attrs['direction'] = 'byref'
            ET.SubElement(signature_elem, sw_tag('parameter'), attrs)

        self.stats['members_with_signatures'] += 1

    def add_see_also(self, member: ET.Element, see_also: list) -> None:
        """
        Add ``<seealso>`` cross-reference elements to a member element.

        Args:
            member: The <member> XML element
            see_also: List of SeeAlsoRef objects (attr is "cref" or "href")
        """
        for ref in see_also or []:
            seealso_elem = ET.SubElement(member, 'seealso')
            seealso_elem.set(ref.attr, ref.value)
            if ref.label:
                seealso_elem.text = ref.label

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

        # Keep C# examples in standard XMLDoc form for IntelliSense. All
        # languages are emitted in the companion examples catalog below.
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
                        example_elem.set(f'{SW_PREFIX}language', example_ref.language)
                        example_elem.set(f'{SW_PREFIX}source', example_ref.url)
                        example_elem.set(f'{SW_PREFIX}title', example_ref.name)

                        # Parse content manually since Phase 06 content has <code> tags
                        # but the code inside contains special characters
                        self._add_example_content(example_elem, content)

                        self.stats['examples_added'] += 1
                        self.log(f"  Added C# example: {example_ref.name}")

        self.add_example_refs(type_member, type_info.examples)

        # Add See Also cross-references
        self.add_see_also(type_member, type_info.see_also)

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
        self.add_example_refs(member, prop.examples)

        # Add summary if available
        if hasattr(prop, 'summary') and prop.summary:
            summary = ET.SubElement(member, 'summary')
            set_element_content(summary, prop.summary)
        else:
            # Placeholder summary
            summary = ET.SubElement(member, 'summary')
            summary.text = f"Gets or sets {prop.name}."

        self.add_signature(member, prop, 'property')

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

        # Add See Also cross-references
        self.add_see_also(member, getattr(prop, 'see_also', []))

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
        self.add_example_refs(member, method.examples)

        # Add summary if available
        if hasattr(method, 'summary') and method.summary:
            summary = ET.SubElement(member, 'summary')
            set_element_content(summary, method.summary)
        else:
            # Placeholder summary
            summary = ET.SubElement(member, 'summary')
            summary.text = f"{method.name} method."

        self.add_signature(member, method, 'method')

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

        # Add See Also cross-references
        self.add_see_also(member, getattr(method, 'see_also', []))

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
            'statistics': self.stats,
            'output_files': {name: path.as_posix() for name, path in output_files.items()},
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
            'output_directory': self.output_dir.as_posix(),
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
  uv run python 90_export_xmldoc/generate_xmldoc.py

  # Generate with verbose output
  uv run python 90_export_xmldoc/generate_xmldoc.py --verbose

  # Generate with custom output directory
  uv run python 90_export_xmldoc/generate_xmldoc.py --output-dir custom/path
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
        '--guide-dir',
        type=Path,
        action='append',
        help='Markdown guide directory to embed; may be repeated'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('90_export_xmldoc/output'),
        help='Output directory for XMLDoc files'
    )

    parser.add_argument(
        '--metadata-dir',
        type=Path,
        default=Path('90_export_xmldoc/metadata'),
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
    guide_dirs = args.guide_dir
    if guide_dirs is None:
        guide_dirs = [
            Path('110_extract_docs_md/output/markdown'),
            Path('115_crawl_referenced_pages/output/markdown'),
        ]

    generator = XMLDocGenerator(
        output_dir=args.output_dir,
        metadata_dir=args.metadata_dir,
        guide_dirs=guide_dirs,
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
    print(f"  - Examples cataloged: {generator.stats['examples_cataloged']}")
    print(f"Guide pages: {generator.stats['guide_pages']}")
    print(f"Members with signatures: {generator.stats['members_with_signatures']}")
    print(f"Properties: {generator.stats['total_properties']}")
    print(f"  - With parameter info: {generator.stats['properties_with_params']}")
    print(f"Methods: {generator.stats['total_methods']}")
    print(f"  - With parameter info: {generator.stats['methods_with_params']}")
    print(f"Parameters documented: {generator.stats['total_parameters_documented']}")
    print(f"Enum members: {generator.stats['total_enum_members']}")
    changed, scanned = normalize_tree(Path(args.output_dir))
    print(f"Normalised line endings to CRLF: {changed} of {scanned} files rewritten")

    print(f"\nOutput directory: {args.output_dir}")
    print("\nGeneration complete!")


if __name__ == '__main__':
    main()
