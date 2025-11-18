"""
Data Loader for Phase 120: Export LLM-Friendly Documentation

This module loads and merges XML data from phases 20, 40, 50, 60, and 80
to create a complete representation of the API.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from models import (
    TypeInfo, Property, Method, EnumMember, Parameter,
    ExampleReference, ExampleContent
)


class DataLoader:
    """Loads and merges API data from multiple phases."""

    def __init__(self):
        """Initialize the data loader."""
        self.types: Dict[str, TypeInfo] = {}  # Key: fully qualified type name
        self.examples: Dict[str, ExampleContent] = {}  # Key: URL

    def load_all(self,
                 phase20_path: str,
                 phase40_path: str,
                 phase50_path: str,
                 phase60_path: str,
                 phase80_path: str) -> Dict[str, TypeInfo]:
        """
        Load and merge all data from the five phases.

        Args:
            phase20_path: Path to Phase 20 XML (type listings)
            phase40_path: Path to Phase 40 XML (type details)
            phase50_path: Path to Phase 50 XML (member details)
            phase60_path: Path to Phase 60 XML (enum members)
            phase80_path: Path to Phase 80 XML (examples)

        Returns:
            Dictionary mapping fully qualified type names to TypeInfo objects
        """
        # Step 1: Load type listings from Phase 20
        self._load_phase20(phase20_path)

        # Step 2: Load examples from Phase 80 (so we can reference them later)
        self._load_phase80(phase80_path)

        # Step 3: Enrich with type details from Phase 40
        self._load_phase40(phase40_path)

        # Step 4: Add member details from Phase 50
        self._load_phase50(phase50_path)

        # Step 5: Add enum members from Phase 60
        self._load_phase60(phase60_path)

        return self.types

    def _load_phase20(self, xml_path: str):
        """
        Load type listings from Phase 20.

        Creates basic TypeInfo objects for each type.
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for type_elem in root.findall('Type'):
            name = type_elem.find('Name').text
            assembly = type_elem.find('Assembly').text
            namespace = type_elem.find('Namespace').text

            fqn = f"{namespace}.{name}"

            # Only create if not already exists (to avoid duplicates)
            if fqn not in self.types:
                self.types[fqn] = TypeInfo(
                    name=name,
                    assembly=assembly,
                    namespace=namespace
                )

    def _load_phase40(self, xml_path: str):
        """
        Load type details from Phase 40.

        Adds descriptions, remarks, and example references.
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for type_elem in root.findall('Type'):
            name = type_elem.find('Name').text
            namespace = type_elem.find('Namespace').text
            fqn = f"{namespace}.{name}"

            # Get or create TypeInfo
            if fqn not in self.types:
                assembly = type_elem.find('Assembly').text
                self.types[fqn] = TypeInfo(
                    name=name,
                    assembly=assembly,
                    namespace=namespace
                )

            type_info = self.types[fqn]

            # Add description
            desc_elem = type_elem.find('Description')
            if desc_elem is not None and desc_elem.text:
                type_info.description = desc_elem.text.strip()

            # Add remarks
            remarks_elem = type_elem.find('Remarks')
            if remarks_elem is not None and remarks_elem.text:
                type_info.remarks = remarks_elem.text.strip()

            # Add example references
            examples_elem = type_elem.find('Examples')
            if examples_elem is not None:
                for example_elem in examples_elem.findall('Example'):
                    name_elem = example_elem.find('Name')
                    lang_elem = example_elem.find('Language')
                    url_elem = example_elem.find('Url')

                    if all([name_elem is not None, lang_elem is not None, url_elem is not None]):
                        example_ref = ExampleReference(
                            name=name_elem.text.strip(),
                            language=lang_elem.text.strip(),
                            url=url_elem.text.strip()
                        )
                        type_info.examples.append(example_ref)

    def _load_phase50(self, xml_path: str):
        """
        Load member details from Phase 50.

        Adds properties and methods with their parameters, returns, remarks.
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for member_elem in root.findall('Member'):
            type_name = member_elem.find('Type').text

            if type_name not in self.types:
                # Skip members for types we don't have
                continue

            type_info = self.types[type_name]

            # Extract member information
            name = member_elem.find('Name').text
            signature = member_elem.find('Signature').text if member_elem.find('Signature') is not None else ""

            desc_elem = member_elem.find('Description')
            description = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

            returns_elem = member_elem.find('Returns')
            returns = returns_elem.text.strip() if returns_elem is not None and returns_elem.text else ""

            remarks_elem = member_elem.find('Remarks')
            remarks = remarks_elem.text.strip() if remarks_elem is not None and remarks_elem.text else ""

            # Parse parameters
            parameters = []
            params_elem = member_elem.find('Parameters')
            if params_elem is not None:
                for param_elem in params_elem.findall('Parameter'):
                    param_name = param_elem.find('Name').text
                    param_desc_elem = param_elem.find('Description')
                    param_desc = param_desc_elem.text.strip() if param_desc_elem is not None and param_desc_elem.text else ""

                    parameters.append(Parameter(
                        name=param_name,
                        description=param_desc
                    ))

            # Determine if this is a property or method based on signature
            is_property = '(' not in signature

            if is_property:
                prop = Property(
                    name=name,
                    description=description,
                    parameters=parameters,
                    returns=returns,
                    remarks=remarks,
                    signature=signature
                )
                type_info.properties.append(prop)
            else:
                method = Method(
                    name=name,
                    description=description,
                    parameters=parameters,
                    returns=returns,
                    remarks=remarks,
                    signature=signature
                )
                type_info.methods.append(method)

    def _load_phase60(self, xml_path: str):
        """
        Load enumeration members from Phase 60.

        Adds enum members to enum types.
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for enum_elem in root.findall('Enum'):
            name = enum_elem.find('Name').text
            namespace = enum_elem.find('Namespace').text
            fqn = f"{namespace}.{name}"

            if fqn not in self.types:
                # Create type if it doesn't exist
                assembly = enum_elem.find('Assembly').text
                self.types[fqn] = TypeInfo(
                    name=name,
                    assembly=assembly,
                    namespace=namespace
                )

            type_info = self.types[fqn]

            # Add enum members
            members_elem = enum_elem.find('Members')
            if members_elem is not None:
                for member_elem in members_elem.findall('Member'):
                    member_name = member_elem.find('Name').text
                    desc_elem = member_elem.find('Description')
                    member_desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

                    enum_member = EnumMember(
                        name=member_name,
                        description=member_desc
                    )
                    type_info.enum_members.append(enum_member)

    def _load_phase80(self, xml_path: str):
        """
        Load example content from Phase 80.

        Stores example content indexed by URL.
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for example_elem in root.findall('Example'):
            url_elem = example_elem.find('Url')
            content_elem = example_elem.find('Content')

            if url_elem is not None and content_elem is not None:
                url = url_elem.text.strip()
                content = content_elem.text if content_elem.text else ""

                # Extract title from content (first line usually)
                lines = content.strip().split('\n')
                title = lines[0].strip() if lines else ""

                self.examples[url] = ExampleContent(
                    url=url,
                    content=content,
                    title=title
                )

    def get_example_content(self, url: str) -> ExampleContent:
        """
        Get the full example content for a given URL.

        Args:
            url: The example URL

        Returns:
            ExampleContent object or None if not found
        """
        return self.examples.get(url)

    def get_types_by_assembly(self) -> Dict[str, List[TypeInfo]]:
        """
        Group types by assembly.

        Returns:
            Dictionary mapping assembly names to lists of TypeInfo objects
        """
        by_assembly = defaultdict(list)
        for type_info in self.types.values():
            by_assembly[type_info.assembly].append(type_info)

        return dict(by_assembly)


def main():
    """Main function for testing the data loader."""
    import argparse

    parser = argparse.ArgumentParser(description='Load and merge API data')
    parser.add_argument('--phase20', default='20_extract_types/metadata/api_members.xml')
    parser.add_argument('--phase40', default='40_extract_type_details/metadata/api_types.xml')
    parser.add_argument('--phase50', default='50_extract_type_member_details/metadata/api_member_details.xml')
    parser.add_argument('--phase60', default='60_extract_enum_members/metadata/enum_members.xml')
    parser.add_argument('--phase80', default='80_parse_examples/output/examples.xml')

    args = parser.parse_args()

    loader = DataLoader()
    types = loader.load_all(
        args.phase20,
        args.phase40,
        args.phase50,
        args.phase60,
        args.phase80
    )

    print(f"Loaded {len(types)} types")
    print(f"Loaded {len(loader.examples)} examples")

    # Print statistics
    by_assembly = loader.get_types_by_assembly()
    print(f"\nTypes by assembly:")
    for assembly, types_list in sorted(by_assembly.items()):
        print(f"  {assembly}: {len(types_list)} types")

    # Print sample type
    if types:
        sample_type = list(types.values())[0]
        print(f"\nSample type: {sample_type.fully_qualified_name}")
        print(f"  Description: {sample_type.description[:100] if sample_type.description else 'N/A'}...")
        print(f"  Properties: {len(sample_type.properties)}")
        print(f"  Methods: {len(sample_type.methods)}")
        print(f"  Enum members: {len(sample_type.enum_members)}")
        print(f"  Examples: {len(sample_type.examples)}")


if __name__ == '__main__':
    main()
