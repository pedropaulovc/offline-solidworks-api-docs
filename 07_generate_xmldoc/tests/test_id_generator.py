#!/usr/bin/env python3
"""
Unit tests for XMLDoc ID generator.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from id_generator import XMLDocIDGenerator


class TestXMLDocIDGenerator:
    """Tests for XMLDocIDGenerator class."""

    def test_generate_type_id(self):
        """Test type ID generation."""
        result = XMLDocIDGenerator.generate_type_id(
            'SolidWorks.Interop.sldworks',
            'IModelDoc2'
        )
        assert result == 'T:SolidWorks.Interop.sldworks.IModelDoc2'

    def test_generate_property_id_simple(self):
        """Test simple property ID generation."""
        result = XMLDocIDGenerator.generate_property_id(
            'System',
            'String',
            'Length'
        )
        assert result == 'P:System.String.Length'

    def test_generate_property_id_indexed(self):
        """Test indexed property ID generation."""
        result = XMLDocIDGenerator.generate_property_id(
            'System',
            'String',
            'Chars',
            parameters=['System.Int32']
        )
        assert result == 'P:System.String.Chars(System.Int32)'

    def test_generate_property_id_multiple_params(self):
        """Test indexed property with multiple parameters."""
        result = XMLDocIDGenerator.generate_property_id(
            'MyNamespace',
            'MyClass',
            'Item',
            parameters=['System.Int32', 'System.String']
        )
        assert result == 'P:MyNamespace.MyClass.Item(System.Int32,System.String)'

    def test_generate_method_id_simple(self):
        """Test simple method ID generation."""
        result = XMLDocIDGenerator.generate_method_id(
            'System',
            'String',
            'ToLower'
        )
        assert result == 'M:System.String.ToLower'

    def test_generate_method_id_with_params(self):
        """Test method ID with parameters."""
        result = XMLDocIDGenerator.generate_method_id(
            'System',
            'String',
            'Substring',
            parameters=['System.Int32']
        )
        assert result == 'M:System.String.Substring(System.Int32)'

    def test_generate_method_id_constructor(self):
        """Test constructor ID generation."""
        result = XMLDocIDGenerator.generate_method_id(
            'System',
            'String',
            '#ctor'
        )
        assert result == 'M:System.String.#ctor'

    def test_generate_method_id_multiple_params(self):
        """Test method ID with multiple parameters."""
        result = XMLDocIDGenerator.generate_method_id(
            'System',
            'String',
            'Substring',
            parameters=['System.Int32', 'System.Int32']
        )
        assert result == 'M:System.String.Substring(System.Int32,System.Int32)'

    def test_generate_field_id(self):
        """Test field ID generation."""
        result = XMLDocIDGenerator.generate_field_id(
            'System',
            'String',
            'Empty'
        )
        assert result == 'F:System.String.Empty'

    def test_generate_event_id(self):
        """Test event ID generation."""
        result = XMLDocIDGenerator.generate_event_id(
            'System',
            'AppDomain',
            'AssemblyLoad'
        )
        assert result == 'E:System.AppDomain.AssemblyLoad'

    def test_encode_parameter_type_intrinsic(self):
        """Test encoding intrinsic types."""
        assert XMLDocIDGenerator.encode_parameter_type('int') == 'System.Int32'
        assert XMLDocIDGenerator.encode_parameter_type('string') == 'System.String'
        assert XMLDocIDGenerator.encode_parameter_type('bool') == 'System.Boolean'
        assert XMLDocIDGenerator.encode_parameter_type('double') == 'System.Double'

    def test_encode_parameter_type_array(self):
        """Test encoding array types."""
        result = XMLDocIDGenerator.encode_parameter_type('int[]')
        assert result == 'System.Int32[]'

        result = XMLDocIDGenerator.encode_parameter_type('string[]')
        assert result == 'System.String[]'

    def test_encode_parameter_type_byref(self):
        """Test encoding BYREF (ref/out) parameters."""
        result = XMLDocIDGenerator.encode_parameter_type('ref int')
        assert result == 'System.Int32@'

        result = XMLDocIDGenerator.encode_parameter_type('out string')
        assert result == 'System.String@'

        result = XMLDocIDGenerator.encode_parameter_type('in bool')
        assert result == 'System.Boolean@'

    def test_encode_parameter_type_byref_array(self):
        """Test encoding BYREF array parameters."""
        result = XMLDocIDGenerator.encode_parameter_type('ref int[]')
        assert result == 'System.Int32[]@'

    def test_encode_parameter_type_pointer(self):
        """Test encoding pointer types."""
        result = XMLDocIDGenerator.encode_parameter_type('int*')
        assert result == 'System.Int32*'

    def test_encode_parameter_type_custom(self):
        """Test encoding custom types (pass-through)."""
        result = XMLDocIDGenerator.encode_parameter_type('MyNamespace.MyClass')
        assert result == 'MyNamespace.MyClass'

    def test_encode_parameter_type_custom_array(self):
        """Test encoding custom type arrays."""
        result = XMLDocIDGenerator.encode_parameter_type('MyNamespace.MyClass[]')
        assert result == 'MyNamespace.MyClass[]'

    def test_solidworks_type_id(self):
        """Test realistic SolidWorks type IDs."""
        result = XMLDocIDGenerator.generate_type_id(
            'SolidWorks.Interop.sldworks',
            'IAdvancedHoleElementData'
        )
        assert result == 'T:SolidWorks.Interop.sldworks.IAdvancedHoleElementData'

    def test_solidworks_property_id(self):
        """Test realistic SolidWorks property IDs."""
        result = XMLDocIDGenerator.generate_property_id(
            'SolidWorks.Interop.sldworks',
            'IAdvancedHoleElementData',
            'BlindDepth'
        )
        assert result == 'P:SolidWorks.Interop.sldworks.IAdvancedHoleElementData.BlindDepth'

    def test_solidworks_method_id(self):
        """Test realistic SolidWorks method IDs."""
        result = XMLDocIDGenerator.generate_method_id(
            'SolidWorks.Interop.sldworks',
            'IModelDoc2',
            'SaveAs'
        )
        assert result == 'M:SolidWorks.Interop.sldworks.IModelDoc2.SaveAs'

    def test_enum_member_id(self):
        """Test enum member ID (as field)."""
        result = XMLDocIDGenerator.generate_field_id(
            'SolidWorks.Interop.swconst',
            'swDocumentTypes_e',
            'swDocPART'
        )
        assert result == 'F:SolidWorks.Interop.swconst.swDocumentTypes_e.swDocPART'

    def test_no_whitespace_in_ids(self):
        """Ensure IDs never contain whitespace."""
        ids = [
            XMLDocIDGenerator.generate_type_id('A.B', 'C'),
            XMLDocIDGenerator.generate_property_id('A.B', 'C', 'D'),
            XMLDocIDGenerator.generate_method_id('A.B', 'C', 'D'),
            XMLDocIDGenerator.generate_field_id('A.B', 'C', 'D'),
            XMLDocIDGenerator.generate_event_id('A.B', 'C', 'D'),
        ]

        for id_str in ids:
            assert ' ' not in id_str, f"ID contains whitespace: {id_str}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
