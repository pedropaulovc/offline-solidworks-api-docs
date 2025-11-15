"""
Tests for the member extraction script.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))
from extract_members import create_xml_output, extract_members_from_file


class TestMemberExtractor:
    """Test the HTML parser."""

    def test_parse_sample_html(self, tmp_path: Path) -> None:
        """Test parsing a sample member HTML file."""
        # Create a sample HTML file
        sample_html = """
        <html>
            <div id="pagetop">
                <span id="pagetitle">ITestInterface Interface Members</span>
            </div>
            <h1>Public Properties</h1>
            <table class="FilteredItemListTable">
                <tr>
                    <td class="imageCell"><img src="Property.gif"></td>
                    <td class="MembersLinkCell"><a href="test~Property1.html">Property1</a></td>
                    <td class="MembersDescriptionCell">Description with <a href="other.html">link</a></td>
                </tr>
                <tr>
                    <td class="imageCell"><img src="Property.gif"></td>
                    <td class="MembersLinkCell"><a href="test~Property2.html">Property2</a></td>
                    <td class="MembersDescriptionCell">Another property</td>
                </tr>
            </table>
            <h1>Public Methods</h1>
            <table class="FilteredItemListTable">
                <tr>
                    <td class="imageCell"><img src="Method.gif"></td>
                    <td class="MembersLinkCell"><a href="test~Method1.html">Method1</a></td>
                    <td class="MembersDescriptionCell">Method description</td>
                </tr>
            </table>
        </html>
        """

        # Create directory structure to simulate real file paths
        api_dir = tmp_path / "testapi"
        api_dir.mkdir()
        test_file = api_dir / "Test.Namespace~Test.Namespace.ITestInterface_members_abc123.html"
        test_file.write_text(sample_html)

        # Extract members
        result = extract_members_from_file(test_file)

        # Verify results
        assert result is not None
        assert result["Name"] == "ITestInterface"
        assert result["Assembly"] == "Test.Namespace"
        assert result["Namespace"] == "Test.Namespace"
        assert result["FullTypeName"] == "Test.Namespace.ITestInterface"
        assert len(result["PublicProperties"]) == 2
        assert len(result["PublicMethods"]) == 1

        # Verify property details
        assert result["PublicProperties"][0]["Name"] == "Property1"
        assert result["PublicProperties"][0]["Url"] == "/testapi/test~Property1.html"
        assert result["PublicProperties"][1]["Name"] == "Property2"

        # Verify method details
        assert result["PublicMethods"][0]["Name"] == "Method1"
        assert result["PublicMethods"][0]["Url"] == "/testapi/test~Method1.html"

    def test_ignore_description_links(self, tmp_path: Path) -> None:
        """Test that links in description cells are ignored."""
        sample_html = """
        <html>
            <div id="pagetop">
                <span id="pagetitle">ITestInterface Interface Members</span>
            </div>
            <h1>Public Properties</h1>
            <table class="FilteredItemListTable">
                <tr>
                    <td class="imageCell"><img src="Property.gif"></td>
                    <td class="MembersLinkCell"><a href="test~Property1.html">Property1</a></td>
                    <td class="MembersDescriptionCell">Gets the <a href="other~Type.html">Type</a> information</td>
                </tr>
            </table>
        </html>
        """

        api_dir = tmp_path / "testapi"
        api_dir.mkdir()
        test_file = api_dir / "Test.Namespace~Test.Namespace.ITestInterface_members_abc.html"
        test_file.write_text(sample_html)
        result = extract_members_from_file(test_file)

        # Should only have one property, not include the link from description
        assert result is not None
        assert len(result["PublicProperties"]) == 1
        assert result["PublicProperties"][0]["Name"] == "Property1"


class TestXMLGeneration:
    """Test XML output generation."""

    def test_create_xml_output(self) -> None:
        """Test creating XML from type information."""
        # Example filename: SolidWorks.Interop~SolidWorks.Interop.subnamespace.ITestType_members_...
        # Assembly is before ~, Namespace is derived from full type name
        types = [
            {
                "Name": "ITestType",
                "Assembly": "SolidWorks.Interop",  # From before ~ in filename
                "Namespace": "SolidWorks.Interop.subnamespace",  # From full type name minus last part
                "PublicProperties": [
                    {"Name": "Prop1", "Url": "/sldworksapi/url1.html"},
                    {"Name": "Prop2", "Url": "/sldworksapi/url2.html"},
                ],
                "PublicMethods": [
                    {"Name": "Method1", "Url": "/sldworksapi/url3.html"},
                ],
            }
        ]

        xml_str = create_xml_output(types)

        # Parse the XML to verify structure
        root = ET.fromstring(xml_str)

        assert root.tag == "Types"
        assert len(root.findall("Type")) == 1

        type_elem = root.find("Type")
        assert type_elem is not None
        name_elem = type_elem.find("Name")
        assert name_elem is not None and name_elem.text == "ITestType"
        assembly_elem = type_elem.find("Assembly")
        assert assembly_elem is not None and assembly_elem.text == "SolidWorks.Interop"
        namespace_elem = type_elem.find("Namespace")
        assert namespace_elem is not None and namespace_elem.text == "SolidWorks.Interop.subnamespace"

        # Check properties
        props = type_elem.find("PublicProperties")
        assert props is not None
        prop_list = props.findall("Property")
        assert len(prop_list) == 2
        prop1_name = prop_list[0].find("Name")
        assert prop1_name is not None and prop1_name.text == "Prop1"
        prop1_url = prop_list[0].find("Url")
        assert prop1_url is not None and prop1_url.text == "/sldworksapi/url1.html"

        # Check methods
        methods = type_elem.find("PublicMethods")
        assert methods is not None
        method_list = methods.findall("Method")
        assert len(method_list) == 1
        method1_name = method_list[0].find("Name")
        assert method1_name is not None and method1_name.text == "Method1"
        method1_url = method_list[0].find("Url")
        assert method1_url is not None and method1_url.text == "/sldworksapi/url3.html"

    def test_xml_no_members(self) -> None:
        """Test XML generation for types with no members."""
        types = [
            {
                "Name": "IEmptyType",
                "Assembly": "SolidWorks.Interop.empty",
                "Namespace": "SolidWorks.Interop.empty",
                "PublicProperties": [],
                "PublicMethods": [],
            }
        ]

        xml_str = create_xml_output(types)
        root = ET.fromstring(xml_str)

        type_elem = root.find("Type")
        assert type_elem is not None
        name_elem = type_elem.find("Name")
        assert name_elem is not None and name_elem.text == "IEmptyType"
        assembly_elem = type_elem.find("Assembly")
        assert assembly_elem is not None and assembly_elem.text == "SolidWorks.Interop.empty"
        namespace_elem = type_elem.find("Namespace")
        assert namespace_elem is not None and namespace_elem.text == "SolidWorks.Interop.empty"
        # Should not have Properties or Methods elements
        assert type_elem.find("PublicProperties") is None
        assert type_elem.find("PublicMethods") is None
