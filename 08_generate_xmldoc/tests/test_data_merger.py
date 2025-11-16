#!/usr/bin/env python3
"""
Unit tests for data merger.
"""

import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from data_merger import DataMerger, TypeInfo, Property, Method, EnumMember


class TestDataMerger:
    """Tests for DataMerger class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_members_xml(self, temp_dir):
        """Create a sample api_members.xml file."""
        xml_content = """<?xml version="1.0"?>
<Types>
    <Type>
        <Name>ITestType</Name>
        <Assembly>TestAssembly</Assembly>
        <Namespace>Test.Namespace</Namespace>
        <PublicProperties>
            <Property>
                <Name>TestProperty</Name>
                <Url>/test/url/property.html</Url>
            </Property>
        </PublicProperties>
        <PublicMethods>
            <Method>
                <Name>TestMethod</Name>
                <Url>/test/url/method.html</Url>
            </Method>
        </PublicMethods>
    </Type>
</Types>"""

        file_path = temp_dir / 'api_members.xml'
        file_path.write_text(xml_content, encoding='utf-8')
        return file_path

    @pytest.fixture
    def sample_types_xml(self, temp_dir):
        """Create a sample api_types.xml file."""
        xml_content = """<?xml version="1.0"?>
<Types>
    <Type>
        <Name>ITestType</Name>
        <Assembly>TestAssembly</Assembly>
        <Namespace>Test.Namespace</Namespace>
        <Description><![CDATA[Test type description]]></Description>
        <Remarks><![CDATA[Test remarks]]></Remarks>
        <Examples>
            <Example>
                <Name>Test Example</Name>
                <Language>C#</Language>
                <Url>/test/example.htm</Url>
            </Example>
        </Examples>
    </Type>
</Types>"""

        file_path = temp_dir / 'api_types.xml'
        file_path.write_text(xml_content, encoding='utf-8')
        return file_path

    @pytest.fixture
    def sample_enums_xml(self, temp_dir):
        """Create a sample enum_members.xml file."""
        xml_content = """<?xml version="1.0"?>
<EnumMembers>
    <Enum>
        <Name>TestEnum</Name>
        <Assembly>TestAssembly</Assembly>
        <Namespace>Test.Namespace</Namespace>
        <Members>
            <Member>
                <Name>Value1</Name>
                <Description><![CDATA[First value]]></Description>
            </Member>
            <Member>
                <Name>Value2</Name>
                <Description><![CDATA[Second value]]></Description>
            </Member>
        </Members>
    </Enum>
</EnumMembers>"""

        file_path = temp_dir / 'enum_members.xml'
        file_path.write_text(xml_content, encoding='utf-8')
        return file_path

    @pytest.fixture
    def sample_examples_xml(self, temp_dir):
        """Create a sample examples.xml file."""
        xml_content = """<?xml version="1.0"?>
<Examples>
    <Example>
        <Url>test/example.htm</Url>
        <Content><![CDATA[Example code content]]></Content>
    </Example>
</Examples>"""

        file_path = temp_dir / 'examples.xml'
        file_path.write_text(xml_content, encoding='utf-8')
        return file_path

    def test_load_api_members(self, sample_members_xml):
        """Test loading members from Phase 02."""
        merger = DataMerger()
        merger.load_api_members(sample_members_xml)

        assert len(merger.types) == 1

        type_key = 'Test.Namespace.ITestType'
        assert type_key in merger.types

        type_info = merger.types[type_key]
        assert type_info.name == 'ITestType'
        assert type_info.assembly == 'TestAssembly'
        assert type_info.namespace == 'Test.Namespace'
        assert len(type_info.properties) == 1
        assert len(type_info.methods) == 1

        assert type_info.properties[0].name == 'TestProperty'
        assert type_info.properties[0].url == '/test/url/property.html'
        assert type_info.methods[0].name == 'TestMethod'
        assert type_info.methods[0].url == '/test/url/method.html'

    def test_load_api_types(self, sample_types_xml):
        """Test loading type info from Phase 03."""
        merger = DataMerger()
        merger.load_api_types(sample_types_xml)

        assert len(merger.types) == 1

        type_key = 'Test.Namespace.ITestType'
        assert type_key in merger.types

        type_info = merger.types[type_key]
        assert type_info.description == 'Test type description'
        assert type_info.remarks == 'Test remarks'
        assert len(type_info.examples) == 1
        assert type_info.examples[0].name == 'Test Example'
        assert type_info.examples[0].language == 'C#'

    def test_load_enum_members(self, sample_enums_xml):
        """Test loading enum members from Phase 04."""
        merger = DataMerger()
        merger.load_enum_members(sample_enums_xml)

        assert len(merger.types) == 1

        type_key = 'Test.Namespace.TestEnum'
        assert type_key in merger.types

        type_info = merger.types[type_key]
        assert type_info.is_enum is True
        assert len(type_info.enum_members) == 2
        assert type_info.enum_members[0].name == 'Value1'
        assert type_info.enum_members[0].description == 'First value'
        assert type_info.enum_members[1].name == 'Value2'
        assert type_info.enum_members[1].description == 'Second value'

    def test_load_examples(self, sample_examples_xml):
        """Test loading examples from Phase 06."""
        merger = DataMerger()
        merger.load_examples(sample_examples_xml)

        assert len(merger.examples) == 1
        assert 'test/example.htm' in merger.examples
        assert merger.examples['test/example.htm'].content == 'Example code content'

    def test_merge_all_sources(self, sample_members_xml, sample_types_xml,
                              sample_enums_xml, sample_examples_xml):
        """Test merging data from all sources."""
        merger = DataMerger()
        merger.load_api_members(sample_members_xml)
        merger.load_api_types(sample_types_xml)
        merger.load_enum_members(sample_enums_xml)
        merger.load_examples(sample_examples_xml)

        # Should have 2 types total (ITestType + TestEnum)
        assert len(merger.types) == 2

        # Check ITestType has data from both sources
        type_key = 'Test.Namespace.ITestType'
        type_info = merger.types[type_key]
        assert type_info.description is not None  # From types.xml
        assert len(type_info.properties) == 1  # From members.xml
        assert len(type_info.methods) == 1  # From members.xml

        # Check TestEnum
        enum_key = 'Test.Namespace.TestEnum'
        enum_info = merger.types[enum_key]
        assert enum_info.is_enum is True
        assert len(enum_info.enum_members) == 2

    def test_group_by_assembly(self, sample_members_xml, sample_enums_xml):
        """Test grouping types by assembly."""
        merger = DataMerger()
        merger.load_api_members(sample_members_xml)
        merger.load_enum_members(sample_enums_xml)

        assemblies = merger.group_by_assembly()

        assert len(assemblies) == 1
        assert 'TestAssembly' in assemblies
        assert len(assemblies['TestAssembly']) == 2

        # Check that types are sorted by name
        names = [t.name for t in assemblies['TestAssembly']]
        assert names == sorted(names)

    def test_get_example_content(self, sample_examples_xml):
        """Test retrieving example content."""
        merger = DataMerger()
        merger.load_examples(sample_examples_xml)

        # Test exact match
        content = merger.get_example_content('test/example.htm')
        assert content == 'Example code content'

        # Test with leading slash
        content = merger.get_example_content('/test/example.htm')
        assert content == 'Example code content'

        # Test non-existent
        content = merger.get_example_content('nonexistent.htm')
        assert content is None

    def test_missing_file_error(self, temp_dir):
        """Test error handling for missing files."""
        merger = DataMerger()
        nonexistent = temp_dir / 'nonexistent.xml'

        with pytest.raises(FileNotFoundError):
            merger.load_api_members(nonexistent)

    def test_cdata_removal(self, temp_dir):
        """Test that CDATA markers are properly removed."""
        xml_content = """<?xml version="1.0"?>
<Types>
    <Type>
        <Name>TestType</Name>
        <Assembly>TestAssembly</Assembly>
        <Namespace>Test</Namespace>
        <Description><![CDATA[Description with <tag>]]></Description>
    </Type>
</Types>"""

        file_path = temp_dir / 'test_cdata.xml'
        file_path.write_text(xml_content, encoding='utf-8')

        merger = DataMerger()
        merger.load_api_types(file_path)

        type_info = merger.types['Test.TestType']
        # CDATA markers should be removed
        assert '<![CDATA[' not in type_info.description
        assert ']]>' not in type_info.description
        assert 'Description with <tag>' == type_info.description


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
