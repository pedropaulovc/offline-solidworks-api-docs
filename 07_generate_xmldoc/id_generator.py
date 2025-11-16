#!/usr/bin/env python3
"""
XMLDoc ID string generator following Microsoft's rules.

Implements the ID string generation rules as defined in:
https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/xmldoc/

ID strings uniquely identify types and members in XMLDoc comments.
"""

import re
from typing import Optional


class XMLDocIDGenerator:
    """
    Generates XMLDoc ID strings following Microsoft's rules.

    ID format: {prefix}:{fully_qualified_name}[(parameters)]

    Prefixes:
    - T: Type (class, interface, struct, enum, delegate)
    - P: Property
    - M: Method
    - F: Field (includes enum members)
    - E: Event
    - N: Namespace
    """

    # Mapping of .NET intrinsic types to their full names
    INTRINSIC_TYPES = {
        'int': 'System.Int32',
        'uint': 'System.UInt32',
        'short': 'System.Int16',
        'ushort': 'System.UInt16',
        'long': 'System.Int64',
        'ulong': 'System.UInt64',
        'byte': 'System.Byte',
        'sbyte': 'System.SByte',
        'bool': 'System.Boolean',
        'char': 'System.Char',
        'float': 'System.Single',
        'double': 'System.Double',
        'decimal': 'System.Decimal',
        'string': 'System.String',
        'object': 'System.Object',
        'void': 'System.Void',
    }

    @staticmethod
    def generate_type_id(namespace: str, type_name: str) -> str:
        """
        Generate ID for a type (class, interface, struct, enum, delegate).

        Format: T:Namespace.TypeName

        Args:
            namespace: The fully qualified namespace
            type_name: The type name (without namespace)

        Returns:
            XMLDoc ID string for the type

        Examples:
            >>> XMLDocIDGenerator.generate_type_id('SolidWorks.Interop.sldworks', 'IModelDoc2')
            'T:SolidWorks.Interop.sldworks.IModelDoc2'
        """
        return f"T:{namespace}.{type_name}"

    @staticmethod
    def generate_property_id(namespace: str, type_name: str, property_name: str,
                            parameters: Optional[list[str]] = None) -> str:
        """
        Generate ID for a property.

        Format: P:Namespace.TypeName.PropertyName
        Format (indexed): P:Namespace.TypeName.PropertyName(Type1,Type2)

        Args:
            namespace: The fully qualified namespace
            type_name: The type name (without namespace)
            property_name: The property name
            parameters: Optional list of parameter types for indexed properties

        Returns:
            XMLDoc ID string for the property

        Examples:
            >>> XMLDocIDGenerator.generate_property_id('System', 'String', 'Length')
            'P:System.String.Length'
            >>> XMLDocIDGenerator.generate_property_id('System', 'String', 'Chars', ['System.Int32'])
            'P:System.String.Chars(System.Int32)'
        """
        fqn = f"{namespace}.{type_name}.{property_name}"

        if parameters:
            params_str = ','.join(parameters)
            return f"P:{fqn}({params_str})"

        return f"P:{fqn}"

    @staticmethod
    def generate_method_id(namespace: str, type_name: str, method_name: str,
                          parameters: Optional[list[str]] = None) -> str:
        """
        Generate ID for a method.

        Format: M:Namespace.TypeName.MethodName
        Format (with params): M:Namespace.TypeName.MethodName(Type1,Type2)

        Special method names:
        - Constructor: #ctor
        - Finalizer: #dtor (Finalize)
        - Operator: op_OperatorName

        Args:
            namespace: The fully qualified namespace
            type_name: The type name (without namespace)
            method_name: The method name (or #ctor for constructor)
            parameters: Optional list of parameter types

        Returns:
            XMLDoc ID string for the method

        Examples:
            >>> XMLDocIDGenerator.generate_method_id('System', 'String', 'ToLower')
            'M:System.String.ToLower'
            >>> XMLDocIDGenerator.generate_method_id('System', 'String', 'Substring', ['System.Int32'])
            'M:System.String.Substring(System.Int32)'
            >>> XMLDocIDGenerator.generate_method_id('System', 'String', '#ctor')
            'M:System.String.#ctor'
        """
        fqn = f"{namespace}.{type_name}.{method_name}"

        if parameters:
            params_str = ','.join(parameters)
            return f"M:{fqn}({params_str})"

        return f"M:{fqn}"

    @staticmethod
    def generate_field_id(namespace: str, type_name: str, field_name: str) -> str:
        """
        Generate ID for a field (includes enum members).

        Format: F:Namespace.TypeName.FieldName

        Args:
            namespace: The fully qualified namespace
            type_name: The type name (without namespace)
            field_name: The field name

        Returns:
            XMLDoc ID string for the field

        Examples:
            >>> XMLDocIDGenerator.generate_field_id('System', 'String', 'Empty')
            'F:System.String.Empty'
        """
        return f"F:{namespace}.{type_name}.{field_name}"

    @staticmethod
    def generate_event_id(namespace: str, type_name: str, event_name: str) -> str:
        """
        Generate ID for an event.

        Format: E:Namespace.TypeName.EventName

        Args:
            namespace: The fully qualified namespace
            type_name: The type name (without namespace)
            event_name: The event name

        Returns:
            XMLDoc ID string for the event

        Examples:
            >>> XMLDocIDGenerator.generate_event_id('System', 'AppDomain', 'AssemblyLoad')
            'E:System.AppDomain.AssemblyLoad'
        """
        return f"E:{namespace}.{type_name}.{event_name}"

    @staticmethod
    def encode_parameter_type(type_str: str) -> str:
        """
        Encode a parameter type according to XMLDoc rules.

        Rules:
        - Intrinsic types -> full type name (int -> System.Int32)
        - BYREF (@) for ref/out parameters
        - PTR (*) for pointer types
        - [] for arrays
        - Generic types with backtick (List`1)

        Args:
            type_str: The type string to encode

        Returns:
            Encoded type string

        Examples:
            >>> XMLDocIDGenerator.encode_parameter_type('int')
            'System.Int32'
            >>> XMLDocIDGenerator.encode_parameter_type('string')
            'System.String'
            >>> XMLDocIDGenerator.encode_parameter_type('int[]')
            'System.Int32[]'
            >>> XMLDocIDGenerator.encode_parameter_type('ref int')
            'System.Int32@'
        """
        # Remove whitespace
        type_str = type_str.strip()

        # Handle ref/out parameters (BYREF)
        is_byref = False
        if type_str.startswith('ref ') or type_str.startswith('out ') or type_str.startswith('in '):
            is_byref = True
            type_str = re.sub(r'^(ref|out|in)\s+', '', type_str)

        # Handle arrays
        array_suffix = ''
        if type_str.endswith('[]'):
            array_suffix = '[]'
            type_str = type_str[:-2]
        elif match := re.search(r'\[([,\d:]*)\]$', type_str):
            array_suffix = match.group(0)
            type_str = type_str[:match.start()]

        # Handle pointers
        pointer_suffix = ''
        if type_str.endswith('*'):
            pointer_suffix = '*'
            type_str = type_str[:-1].strip()

        # Convert intrinsic types to full names
        if type_str in XMLDocIDGenerator.INTRINSIC_TYPES:
            type_str = XMLDocIDGenerator.INTRINSIC_TYPES[type_str]

        # Reconstruct with proper order: base type, pointer, array, byref
        result = type_str + pointer_suffix + array_suffix

        if is_byref:
            result += '@'

        return result

    @staticmethod
    def parse_url_for_parameters(url: str) -> Optional[list[str]]:
        """
        Parse a URL to extract parameter information if present.

        SolidWorks API URLs may contain parameter information in the URL itself.
        This is a best-effort extraction.

        Args:
            url: The member URL from the crawled documentation

        Returns:
            List of parameter type strings, or None if no parameters

        Note:
            For COM interop types like SolidWorks API, parameter information
            is typically not encoded in URLs. This method may return None
            for most cases, and parameters may need to be inferred from
            actual API metadata or left empty.
        """
        # COM interop APIs typically don't encode parameters in URLs
        # This would need to be enhanced with actual API metadata if available
        return None
