#!/usr/bin/env python3
"""
Data merger for combining outputs from phases 02, 03, 04, and 06.

This module reads XML files from:
- Phase 02: api_members.xml (properties and methods)
- Phase 03: api_types.xml (type descriptions, examples, remarks)
- Phase 04: enum_members.xml (enumeration members)
- Phase 06: examples.xml (example code content)

And merges them into a unified data structure organized by assembly.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Property:
    """Represents a property member."""
    name: str
    url: str
    summary: Optional[str] = None
    value: Optional[str] = None
    remarks: Optional[str] = None
    availability: Optional[str] = None


@dataclass
class Method:
    """Represents a method member."""
    name: str
    url: str
    summary: Optional[str] = None
    returns: Optional[str] = None
    remarks: Optional[str] = None
    availability: Optional[str] = None


@dataclass
class EnumMember:
    """Represents an enumeration member."""
    name: str
    description: str


@dataclass
class ExampleReference:
    """Represents an example reference."""
    name: str
    language: str
    url: str


@dataclass
class TypeInfo:
    """Represents a complete type with all its members and documentation."""
    name: str
    assembly: str
    namespace: str
    description: Optional[str] = None
    remarks: Optional[str] = None
    properties: list[Property] = field(default_factory=list)
    methods: list[Method] = field(default_factory=list)
    enum_members: list[EnumMember] = field(default_factory=list)
    examples: list[ExampleReference] = field(default_factory=list)
    is_enum: bool = False


@dataclass
class ExampleContent:
    """Represents example code content."""
    url: str
    content: str


class DataMerger:
    """
    Merges data from multiple phase outputs into a unified structure.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize the data merger.

        Args:
            verbose: If True, print detailed progress information
        """
        self.verbose = verbose
        self.types: dict[str, TypeInfo] = {}
        self.examples: dict[str, ExampleContent] = {}

    def log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def load_api_members(self, members_file: Path) -> None:
        """
        Load properties and methods from Phase 02 output.

        Args:
            members_file: Path to api_members.xml

        Raises:
            FileNotFoundError: If the file doesn't exist
            ET.ParseError: If the XML is malformed
        """
        self.log(f"Loading members from {members_file}...")

        if not members_file.exists():
            raise FileNotFoundError(f"Members file not found: {members_file}")

        tree = ET.parse(members_file)
        root = tree.getroot()

        members_count = 0
        for type_elem in root.findall('Type'):
            name = type_elem.findtext('Name', '').strip()
            assembly = type_elem.findtext('Assembly', '').strip()
            namespace = type_elem.findtext('Namespace', '').strip()

            if not name or not assembly or not namespace:
                continue

            # Create type info if it doesn't exist
            type_key = f"{namespace}.{name}"
            if type_key not in self.types:
                self.types[type_key] = TypeInfo(
                    name=name,
                    assembly=assembly,
                    namespace=namespace
                )

            type_info = self.types[type_key]

            # Load properties
            properties_elem = type_elem.find('PublicProperties')
            if properties_elem is not None:
                for prop_elem in properties_elem.findall('Property'):
                    prop_name = prop_elem.findtext('Name', '').strip()
                    prop_url = prop_elem.findtext('Url', '').strip()

                    if prop_name and prop_url:
                        type_info.properties.append(Property(
                            name=prop_name,
                            url=prop_url
                        ))
                        members_count += 1

            # Load methods
            methods_elem = type_elem.find('PublicMethods')
            if methods_elem is not None:
                for method_elem in methods_elem.findall('Method'):
                    method_name = method_elem.findtext('Name', '').strip()
                    method_url = method_elem.findtext('Url', '').strip()

                    if method_name and method_url:
                        type_info.methods.append(Method(
                            name=method_name,
                            url=method_url
                        ))
                        members_count += 1

        self.log(f"Loaded {len(self.types)} types with {members_count} members")

    def load_api_types(self, types_file: Path) -> None:
        """
        Load type descriptions, examples, and remarks from Phase 03 output.

        Args:
            types_file: Path to api_types.xml

        Raises:
            FileNotFoundError: If the file doesn't exist
            ET.ParseError: If the XML is malformed
        """
        self.log(f"Loading type info from {types_file}...")

        if not types_file.exists():
            raise FileNotFoundError(f"Types file not found: {types_file}")

        tree = ET.parse(types_file)
        root = tree.getroot()

        types_with_info = 0
        for type_elem in root.findall('Type'):
            name = type_elem.findtext('Name', '').strip()
            assembly = type_elem.findtext('Assembly', '').strip()
            namespace = type_elem.findtext('Namespace', '').strip()

            if not name or not assembly or not namespace:
                continue

            # Create type info if it doesn't exist
            type_key = f"{namespace}.{name}"
            if type_key not in self.types:
                self.types[type_key] = TypeInfo(
                    name=name,
                    assembly=assembly,
                    namespace=namespace
                )

            type_info = self.types[type_key]

            # Load description
            description = type_elem.findtext('Description', '').strip()
            if description:
                # Remove CDATA markers if present
                description = description.replace('<![CDATA[', '').replace(']]>', '')
                type_info.description = description
                types_with_info += 1

            # Load remarks
            remarks = type_elem.findtext('Remarks', '').strip()
            if remarks:
                # Remove CDATA markers if present
                remarks = remarks.replace('<![CDATA[', '').replace(']]>', '')
                type_info.remarks = remarks

            # Load examples
            examples_elem = type_elem.find('Examples')
            if examples_elem is not None:
                for example_elem in examples_elem.findall('Example'):
                    example_name = example_elem.findtext('Name', '').strip()
                    example_lang = example_elem.findtext('Language', '').strip()
                    example_url = example_elem.findtext('Url', '').strip()

                    if example_name and example_url:
                        type_info.examples.append(ExampleReference(
                            name=example_name,
                            language=example_lang or 'Unknown',
                            url=example_url
                        ))

        self.log(f"Loaded descriptions for {types_with_info} types")

    def load_enum_members(self, enums_file: Path) -> None:
        """
        Load enumeration members from Phase 04 output.

        Args:
            enums_file: Path to enum_members.xml

        Raises:
            FileNotFoundError: If the file doesn't exist
            ET.ParseError: If the XML is malformed
        """
        self.log(f"Loading enum members from {enums_file}...")

        if not enums_file.exists():
            raise FileNotFoundError(f"Enums file not found: {enums_file}")

        tree = ET.parse(enums_file)
        root = tree.getroot()

        enums_count = 0
        for enum_elem in root.findall('Enum'):
            name = enum_elem.findtext('Name', '').strip()
            assembly = enum_elem.findtext('Assembly', '').strip()
            namespace = enum_elem.findtext('Namespace', '').strip()

            if not name or not assembly or not namespace:
                continue

            # Create type info if it doesn't exist
            type_key = f"{namespace}.{name}"
            if type_key not in self.types:
                self.types[type_key] = TypeInfo(
                    name=name,
                    assembly=assembly,
                    namespace=namespace,
                    is_enum=True
                )

            type_info = self.types[type_key]
            type_info.is_enum = True

            # Load enum members
            members_elem = enum_elem.find('Members')
            if members_elem is not None:
                for member_elem in members_elem.findall('Member'):
                    member_name = member_elem.findtext('Name', '').strip()
                    member_desc = member_elem.findtext('Description', '').strip()

                    if member_name:
                        # Remove CDATA markers if present
                        member_desc = member_desc.replace('<![CDATA[', '').replace(']]>', '')
                        type_info.enum_members.append(EnumMember(
                            name=member_name,
                            description=member_desc
                        ))

                enums_count += 1

        self.log(f"Loaded {enums_count} enums")

    def load_examples(self, examples_file: Path) -> None:
        """
        Load example code content from Phase 06 output.

        Args:
            examples_file: Path to examples.xml

        Raises:
            FileNotFoundError: If the file doesn't exist
            ET.ParseError: If the XML is malformed
        """
        self.log(f"Loading examples from {examples_file}...")

        if not examples_file.exists():
            raise FileNotFoundError(f"Examples file not found: {examples_file}")

        tree = ET.parse(examples_file)
        root = tree.getroot()

        for example_elem in root.findall('Example'):
            url = example_elem.findtext('Url', '').strip()
            content = example_elem.findtext('Content', '').strip()

            if url:
                # Remove CDATA markers if present
                content = content.replace('<![CDATA[', '').replace(']]>', '')
                self.examples[url] = ExampleContent(url=url, content=content)

        self.log(f"Loaded {len(self.examples)} example files")

    def group_by_assembly(self) -> dict[str, list[TypeInfo]]:
        """
        Group all types by their assembly.

        Returns:
            Dictionary mapping assembly name to list of TypeInfo objects
        """
        assemblies: dict[str, list[TypeInfo]] = {}

        for type_info in self.types.values():
            if type_info.assembly not in assemblies:
                assemblies[type_info.assembly] = []
            assemblies[type_info.assembly].append(type_info)

        # Sort types within each assembly by name
        for assembly in assemblies:
            assemblies[assembly].sort(key=lambda t: t.name)

        return assemblies

    def get_example_content(self, url: str) -> Optional[str]:
        """
        Get the content for an example URL.

        Args:
            url: The example URL

        Returns:
            Example content if found, None otherwise
        """
        # Normalize URL (remove leading slash if present)
        normalized_url = url.lstrip('/')

        if normalized_url in self.examples:
            return self.examples[normalized_url].content

        # Try with different variations
        for example_url in self.examples:
            if example_url.endswith(normalized_url) or normalized_url.endswith(example_url):
                return self.examples[example_url].content

        return None
