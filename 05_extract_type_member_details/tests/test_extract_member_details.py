#!/usr/bin/env python3
"""
Unit tests for member details extraction.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from textwrap import dedent

import pytest

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.extraction_utils import extract_member_name_from_filename, extract_namespace_from_filename, is_member_file

# Import from the parent directory (05_extract_type_member_details)
from extract_member_details import MemberDetailsExtractor, create_xml_output, extract_member_details_from_file


class TestMemberFiltering:
    """Test member file identification."""

    def test_is_member_file_valid(self):
        """Test that valid member files are identified."""
        member_file = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~GetTitle.html")
        assert is_member_file(member_file)

    def test_is_member_file_type_file(self):
        """Test that type files are not identified as members."""
        type_file = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2_hash.html")
        assert not is_member_file(type_file)

    def test_is_member_file_members_page(self):
        """Test that _members_ files are excluded."""
        members_page = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2_members_hash.html")
        assert not is_member_file(members_page)

    def test_is_member_file_special_files(self):
        """Test that special files are excluded."""
        assert not is_member_file(Path("FunctionalCategories.html"))
        assert not is_member_file(Path("help_list.html"))


class TestFilenameExtraction:
    """Test filename parsing functions."""

    def test_extract_namespace_from_member_file(self):
        """Test namespace extraction from member filename."""
        html_file = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~GetTitle.html")
        assembly, namespace, type_name = extract_namespace_from_filename(html_file)

        assert assembly == "SolidWorks.Interop.sldworks"
        assert namespace == "SolidWorks.Interop.sldworks"
        assert type_name == "IModelDoc2"

    def test_extract_member_name(self):
        """Test member name extraction from filename."""
        html_file = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~GetTitle.html")
        member_name = extract_member_name_from_filename(html_file)

        assert member_name == "GetTitle"

    def test_extract_member_name_with_numbers(self):
        """Test member name extraction with version numbers."""
        html_file = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAssemblyDoc~InsertCavity3.html")
        member_name = extract_member_name_from_filename(html_file)

        assert member_name == "InsertCavity3"


class TestMemberDetailsExtractor:
    """Test the HTML parser for member details."""

    def test_extract_member_name_from_pagetitle(self):
        """Test extraction of member name from page title."""
        html = """
        <div id="pagetop">
            <span id="pagetitle">CheckAgainstExistingFile Method (ISWDesignCheck)</span>
        </div>
        """
        parser = MemberDetailsExtractor()
        parser.feed(html)

        assert parser.member_name == "CheckAgainstExistingFile"
        assert parser.type_name == "ISWDesignCheck"

    def test_extract_property_from_pagetitle(self):
        """Test extraction of property name from page title."""
        html = """
        <div id="pagetop">
            <span id="pagetitle">Visible Property (IModelDoc2)</span>
        </div>
        """
        parser = MemberDetailsExtractor()
        parser.feed(html)

        assert parser.member_name == "Visible"
        assert parser.type_name == "IModelDoc2"

    def test_extract_description(self):
        """Test extraction of member description."""
        html = """
        <div id="pagetop">
            <span id="pagetitle">CheckAgainstExistingFile Method (ISWDesignCheck)</span>
        </div>
        <div id="pagebody">
            <br> Validates an active document.
            <h1>.NET Syntax</h1>
        </div>
        """
        parser = MemberDetailsExtractor()
        parser.feed(html)

        assert "Validates an active document" in parser.get_description()

    def test_extract_signature(self):
        """Test extraction of C# signature (without return type)."""
        html = """
        <h1>.NET Syntax</h1>
        <div id="syntaxSection">
            <div id="Syntax_CS">
                <table class="syntaxtable">
                    <tbody>
                        <tr><td><pre>void CheckAgainstExistingFile()</pre></td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        """
        parser = MemberDetailsExtractor()
        parser.feed(html)

        assert parser.get_signature() == "CheckAgainstExistingFile()"

    def test_extract_signature_with_params(self):
        """Test extraction of signature with parameters (without return type)."""
        html = """
        <h1>.NET Syntax</h1>
        <div id="syntaxSection">
            <div id="Syntax_CS">
                <table class="syntaxtable">
                    <tbody>
                        <tr><td><pre>System.bool AccessSelections(System.object TopDoc, System.object Component)</pre></td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        """
        parser = MemberDetailsExtractor()
        parser.feed(html)

        assert parser.get_signature() == "AccessSelections(System.object TopDoc, System.object Component)"

    def test_extract_parameters(self):
        """Test extraction of parameter information."""
        html = """
        <h4>Parameters</h4>
        <dl>
            <dt><i>TopDoc</i></dt>
            <dd>IModelDoc2 for the part</dd>
            <dt><i>Component</i></dt>
            <dd>Null or Nothing</dd>
        </dl>
        """
        parser = MemberDetailsExtractor()
        parser.in_parameters_section = True
        parser.feed(html)

        assert len(parser.parameters) == 2
        assert parser.parameters[0]["Name"] == "TopDoc"
        assert "IModelDoc2" in parser.parameters[0]["Description"]
        assert parser.parameters[1]["Name"] == "Component"
        assert "Null" in parser.parameters[1]["Description"]

    def test_extract_return_value(self):
        """Test extraction of return value description."""
        html = """
        <h4>Return Value</h4>
        <div>True if the selections are successfully accessed, false if not</div>
        """
        parser = MemberDetailsExtractor()
        parser.in_return_section = True
        parser.return_depth = 0
        parser.feed(html)

        assert "True if" in parser.get_return_value()
        assert "false if not" in parser.get_return_value()

    def test_extract_remarks(self):
        """Test extraction of remarks section."""
        html = """
        <h1>Remarks</h1>
        <div id="remarksSection">
            <p>This method launches a dialog from which to choose a file.</p>
        </div>
        """
        parser = MemberDetailsExtractor()
        parser.in_remarks_section = True
        parser.remarks_depth = 0
        parser.feed(html)

        assert "dialog" in parser.get_remarks()


class TestXMLGeneration:
    """Test XML output generation."""

    def test_create_xml_output_basic(self):
        """Test basic XML output generation."""
        members = [
            {
                "Assembly": "SolidWorks.Interop.sldworks",
                "Type": "SolidWorks.Interop.sldworks.IModelDoc2",
                "Name": "GetTitle",
                "Signature": "GetTitle()",
                "Description": "Gets the document title.",
                "Parameters": [],
                "Returns": "Document title",
                "Remarks": "",
            }
        ]

        xml_output = create_xml_output(members)

        # Parse the output to verify structure
        root = ET.fromstring(xml_output)
        assert root.tag == "Members"

        member = root.find("Member")
        assert member is not None
        assert member.find("Assembly").text == "SolidWorks.Interop.sldworks"
        assert member.find("Type").text == "SolidWorks.Interop.sldworks.IModelDoc2"
        assert member.find("Name").text == "GetTitle"
        assert member.find("Signature").text == "GetTitle()"

    def test_create_xml_output_with_parameters(self):
        """Test XML output with parameters."""
        members = [
            {
                "Assembly": "SolidWorks.Interop.sldworks",
                "Type": "SolidWorks.Interop.sldworks.IModelDoc2",
                "Name": "Save",
                "Signature": "Save(string filename)",
                "Description": "Saves the document.",
                "Parameters": [{"Name": "filename", "Description": "Path to save the file"}],
                "Returns": "True if successful",
                "Remarks": "",
            }
        ]

        xml_output = create_xml_output(members)

        root = ET.fromstring(xml_output)
        member = root.find("Member")
        params = member.find("Parameters")

        assert params is not None
        param = params.find("Parameter")
        assert param.find("Name").text == "filename"

    def test_create_xml_output_cdata_wrapping(self):
        """Test that descriptions/returns/remarks are wrapped in CDATA."""
        members = [
            {
                "Assembly": "SolidWorks.Interop.sldworks",
                "Type": "SolidWorks.Interop.sldworks.IModelDoc2",
                "Name": "GetTitle",
                "Signature": "string GetTitle()",
                "Description": "Gets the <b>document</b> title.",
                "Parameters": [],
                "Returns": "Document <i>title</i>",
                "Remarks": "See <see cref=\"IModelDoc2.Save\">Save</see> method.",
            }
        ]

        xml_output = create_xml_output(members)

        # Verify CDATA is present
        assert "<![CDATA[" in xml_output
        assert "Gets the <b>document</b> title." in xml_output


class TestIntegration:
    """Integration tests for the full extraction pipeline."""

    @pytest.fixture
    def sample_member_html(self, tmp_path):
        """Create a sample member HTML file."""
        html_content = dedent(
            """
            <xml>
            <mshelp:keyword index="F" term="Test.Member">
            </mshelp:keyword></xml>

            <div id="pagetop">
                <span id="pagetitle">GetTitle Method (IModelDoc2)</span>
            </div>

            <div id="pagebody">
                <br> Gets the document title.

                <h1>.NET Syntax</h1>
                <div id="syntaxSection">
                    <div id="Syntax_CS">
                        <table class="syntaxtable">
                            <tbody>
                                <tr><td><pre>string GetTitle()</pre></td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <h4>Return Value</h4>
                <div>The document title as a string</div>

                <h1>Remarks</h1>
                <div id="remarksSection">
                    <p>This method returns the title of the current document.</p>
                </div>
            </div>
            """
        )

        html_file = tmp_path / "SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~GetTitle.html"
        html_file.write_text(html_content)
        return html_file

    def test_extract_from_file(self, sample_member_html):
        """Test extracting member details from a file."""
        member_info = extract_member_details_from_file(sample_member_html)

        assert member_info is not None
        assert member_info["Assembly"] == "SolidWorks.Interop.sldworks"
        assert member_info["Type"] == "SolidWorks.Interop.sldworks.IModelDoc2"
        assert member_info["Name"] == "GetTitle"
        assert member_info["Signature"] == "GetTitle()"
        assert "document title" in member_info["Description"].lower()
        assert "string" in member_info["Returns"].lower()
        assert "returns the title" in member_info["Remarks"].lower()
