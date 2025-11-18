#!/usr/bin/env python3
"""
Data merger for combining outputs from phases 02, 04, 05, 06, and 08.

This module reads XML files from:
- Phase 02: api_members.xml (properties and methods)
- Phase 04: api_types.xml (type descriptions, examples, remarks)
- Phase 05: api_member_details.xml (member descriptions, parameters, returns, remarks)
- Phase 06: enum_members.xml (enumeration members)
- Phase 08: examples.xml (example code content)

And merges them into a unified data structure organized by assembly.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Parameter:
    """Represents a parameter with name, type, and description."""
    name: str
    type: str
    description: Optional[str] = None


@dataclass
class Property:
    """Represents a property member."""
    name: str
    url: str
    summary: Optional[str] = None
    value: Optional[str] = None
    remarks: Optional[str] = None
    availability: Optional[str] = None
    parameter_types: Optional[list[str]] = None  # For indexed properties (just types for signature)
    parameters: Optional[list[Parameter]] = None  # Full parameter info with descriptions


@dataclass
class Method:
    """Represents a method member."""
    name: str
    url: str
    summary: Optional[str] = None
    returns: Optional[str] = None
    remarks: Optional[str] = None
    availability: Optional[str] = None
    parameter_types: Optional[list[str]] = None  # Parameter types for signature
    parameters: Optional[list[Parameter]] = None  # Full parameter info with descriptions


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


def parse_signature_parameters(signature: str) -> Optional[list[str]]:
    """
    Parse a method signature to extract parameter types.

    Args:
        signature: The full method signature from Phase 05
                  Example: "System.int MethodName( System.string param1, out System.int param2 )"

    Returns:
        List of parameter type strings, or None if no parameters or parse error

    Examples:
        >>> parse_signature_parameters("void Method()")
        None
        >>> parse_signature_parameters("void Method( System.string param1 )")
        ['System.String']
        >>> parse_signature_parameters("void Method( System.string p1, out System.int p2 )")
        ['System.String', 'System.Int32@']
    """
    if not signature:
        return None

    # Extract the part in parentheses
    match = re.search(r'\((.*?)\)', signature)
    if not match:
        return None

    params_str = match.group(1).strip()
    if not params_str:
        return None

    # Split by comma (but be careful with generics and nested types)
    parameters = []
    current_param = ""
    depth = 0  # Track nesting depth for generics

    for char in params_str + ',':
        if char == '<':
            depth += 1
            current_param += char
        elif char == '>':
            depth -= 1
            current_param += char
        elif char == ',' and depth == 0:
            # End of current parameter
            param = current_param.strip()
            if param:
                param_type = extract_parameter_type(param)
                if param_type:
                    parameters.append(param_type)
            current_param = ""
        else:
            current_param += char

    return parameters if parameters else None


def extract_parameter_type(param_str: str) -> Optional[str]:
    """
    Extract the type from a parameter string.

    Args:
        param_str: Parameter string like "System.string paramName" or "out System.int paramName"

    Returns:
        The parameter type in XMLDoc format

    Examples:
        >>> extract_parameter_type("System.string paramName")
        'System.String'
        >>> extract_parameter_type("out System.int paramName")
        'System.Int32@'
        >>> extract_parameter_type("ref System.bool paramName")
        'System.Boolean@'
    """
    param_str = param_str.strip()
    if not param_str:
        return None

    # Check for out/ref/in modifiers
    is_byref = False
    if param_str.startswith('out ') or param_str.startswith('ref ') or param_str.startswith('in '):
        is_byref = True
        param_str = re.sub(r'^(out|ref|in)\s+', '', param_str)

    # Split by whitespace to separate type from parameter name
    # Take everything except the last token (which is the parameter name)
    tokens = param_str.split()
    if not tokens:
        return None

    # The type is everything except the last token (parameter name)
    type_str = ' '.join(tokens[:-1]) if len(tokens) > 1 else tokens[0]

    # Normalize .NET types
    type_str = normalize_dotnet_type(type_str)

    # Add byref marker
    if is_byref:
        type_str += '@'

    return type_str


def normalize_dotnet_type(type_str: str) -> str:
    """
    Normalize .NET type names to their standard format.

    Args:
        type_str: Type string like "System.int" or "System.string"

    Returns:
        Normalized type string like "System.Int32" or "System.String"
    """
    # Mapping of common type variations
    type_mapping = {
        'System.int': 'System.Int32',
        'System.uint': 'System.UInt32',
        'System.short': 'System.Int16',
        'System.ushort': 'System.UInt16',
        'System.long': 'System.Int64',
        'System.ulong': 'System.UInt64',
        'System.byte': 'System.Byte',
        'System.sbyte': 'System.SByte',
        'System.bool': 'System.Boolean',
        'System.char': 'System.Char',
        'System.float': 'System.Single',
        'System.double': 'System.Double',
        'System.decimal': 'System.Decimal',
        'System.string': 'System.String',
        'System.object': 'System.Object',
        'System.void': 'System.Void',
    }

    return type_mapping.get(type_str, type_str)


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

    def load_member_details(self, member_details_file: Path) -> None:
        """
        Load member details from Phase 05 output.

        This enriches existing properties and methods with detailed information
        including descriptions, parameters, return values, and remarks.

        Args:
            member_details_file: Path to api_member_details.xml

        Raises:
            FileNotFoundError: If the file doesn't exist
            ET.ParseError: If the XML is malformed
        """
        self.log(f"Loading member details from {member_details_file}...")

        if not member_details_file.exists():
            raise FileNotFoundError(f"Member details file not found: {member_details_file}")

        tree = ET.parse(member_details_file)
        root = tree.getroot()

        members_enriched = 0
        members_not_found = 0

        for member_elem in root.findall('Member'):
            type_name = member_elem.findtext('Type', '').strip()
            member_name = member_elem.findtext('Name', '').strip()

            if not type_name or not member_name:
                continue

            # Extract namespace and class name from full type name
            # Format: "Namespace.ClassName" or just "ClassName"
            if '.' in type_name:
                parts = type_name.rsplit('.', 1)
                namespace = parts[0]
                class_name = parts[1]
            else:
                # No namespace in type name, skip
                continue

            type_key = type_name  # Using full type name as key

            # Find the type in our types dictionary
            if type_key not in self.types:
                members_not_found += 1
                continue

            type_info = self.types[type_key]

            # Extract member details
            description = member_elem.findtext('Description', '').strip()
            returns = member_elem.findtext('Returns', '').strip()
            remarks = member_elem.findtext('Remarks', '').strip()
            signature = member_elem.findtext('Signature', '').strip()

            # Remove CDATA markers if present
            if description:
                description = description.replace('<![CDATA[', '').replace(']]>', '').strip()
            if returns:
                returns = returns.replace('<![CDATA[', '').replace(']]>', '').strip()
            if remarks:
                remarks = remarks.replace('<![CDATA[', '').replace(']]>', '').strip()

            # Parse signature to extract parameter types for XMLDoc ID
            parameter_types = None
            if signature:
                parameter_types = parse_signature_parameters(signature)

            # Parse <Parameters> element to get full parameter info
            parameters = []
            params_elem = member_elem.find('Parameters')
            if params_elem is not None:
                for param_elem in params_elem.findall('Parameter'):
                    param_name = param_elem.findtext('Name', '').strip()
                    param_desc = param_elem.findtext('Description', '').strip()

                    if param_desc:
                        param_desc = param_desc.replace('<![CDATA[', '').replace(']]>', '').strip()

                    if param_name:
                        # Find the parameter type from signature
                        param_type = None
                        if parameter_types:
                            # Match parameter by position (assuming order matches)
                            param_index = len(parameters)
                            if param_index < len(parameter_types):
                                param_type = parameter_types[param_index]

                        if param_type:
                            parameters.append(Parameter(
                                name=param_name,
                                type=param_type,
                                description=param_desc if param_desc else None
                            ))

            parameters = parameters if parameters else None

            # Try to find matching property (may be multiple with same name)
            found = False
            for prop in type_info.properties:
                if prop.name == member_name:
                    # Enrich property with details
                    if description:
                        prop.summary = description
                    if returns:
                        prop.value = returns
                    if remarks:
                        prop.remarks = remarks
                    if parameter_types:
                        prop.parameter_types = parameter_types
                    if parameters:
                        prop.parameters = parameters
                    found = True
                    # Note: Don't break - enrich ALL properties with this name

            # If not a property, try methods (may be multiple with same name)
            if not found:
                for method in type_info.methods:
                    if method.name == member_name:
                        # Enrich method with details
                        if description:
                            method.summary = description
                        if returns:
                            method.returns = returns
                        if remarks:
                            method.remarks = remarks
                        if parameter_types:
                            method.parameter_types = parameter_types
                        if parameters:
                            method.parameters = parameters
                        found = True
                        # Note: Don't break - enrich ALL methods with this name

            if found:
                members_enriched += 1
            else:
                members_not_found += 1

        self.log(f"Enriched {members_enriched} members with detailed information")
        if members_not_found > 0:
            self.log(f"  ({members_not_found} member details could not be matched)")

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
