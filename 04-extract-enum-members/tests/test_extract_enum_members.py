#!/usr/bin/env python3
"""
Unit tests for enum member extraction.
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from extract_enum_members import EnumMemberExtractor, create_xml_output, extract_namespace_from_filename, is_enum_file


class TestEnumMemberExtractor(unittest.TestCase):
    """Test the EnumMemberExtractor HTML parser."""

    def test_basic_enum_member_extraction(self) -> None:
        """Test extracting basic enum members."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">swTangencyType_e Enumeration</span>
        </div>
        <div id="mainbody">
            Tangency options for lofts.
            <h1>Members</h1>
            <div id="enummembersSection">
                <table class="FilteredItemListTable">
                    <tr><th>Member</th><th>Description</th></tr>
                    <tr>
                        <td class="MemberNameCell"><strong>swMinimumTwist</strong></td>
                        <td class="DescriptionCell">10 = Prevents the profile from becoming self-intersecting</td>
                    </tr>
                    <tr>
                        <td class="MemberNameCell"><strong>swTangencyNone</strong></td>
                        <td class="DescriptionCell">0</td>
                    </tr>
                </table>
            </div>
        </div>
        </html>
        """

        parser = EnumMemberExtractor()
        parser.feed(html)

        self.assertEqual(parser.type_name, "swTangencyType_e")
        self.assertEqual(len(parser.enum_members), 2)
        self.assertEqual(parser.enum_members[0]["Name"], "swMinimumTwist")
        self.assertIn("10 = Prevents", parser.enum_members[0]["Description"])
        self.assertEqual(parser.enum_members[1]["Name"], "swTangencyNone")
        self.assertEqual(parser.enum_members[1]["Description"], "0")

    def test_enum_members_with_links(self) -> None:
        """Test that links in member descriptions are converted to XMLDoc format."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">swTest_e Enumeration</span>
        </div>
        <div id="mainbody">
            <h1>Members</h1>
            <div id="enummembersSection">
                <table class="FilteredItemListTable">
                    <tr><th>Member</th><th>Description</th></tr>
                    <tr>
                        <td class="MemberNameCell"><strong>swTestMember</strong></td>
                        <td class="DescriptionCell">See <a href="SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swOtherType_e.html">swOtherType_e</a></td>
                    </tr>
                </table>
            </div>
        </div>
        </html>
        """

        parser = EnumMemberExtractor()
        parser.feed(html)

        self.assertEqual(len(parser.enum_members), 1)
        self.assertIn('<see cref="SolidWorks.Interop.swconst.swOtherType_e">', parser.enum_members[0]["Description"])
        self.assertIn("swOtherType_e</see>", parser.enum_members[0]["Description"])

    def test_empty_enum(self) -> None:
        """Test enum with no members."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">swEmpty_e Enumeration</span>
        </div>
        <div id="mainbody">
            Test description.
        </div>
        </html>
        """

        parser = EnumMemberExtractor()
        parser.feed(html)

        self.assertEqual(parser.type_name, "swEmpty_e")
        self.assertEqual(len(parser.enum_members), 0)


class TestFileFiltering(unittest.TestCase):
    """Test filtering enum files from other files."""

    def test_is_enum_file_valid(self) -> None:
        """Test identifying valid enum files."""
        valid_file = Path("SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swTangencyType_e_84c83747.html")
        self.assertTrue(is_enum_file(valid_file))

    def test_is_enum_file_not_enum(self) -> None:
        """Test rejecting non-enum type files."""
        non_enum_file = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature_84c83747.html")
        self.assertFalse(is_enum_file(non_enum_file))

    def test_is_enum_file_members(self) -> None:
        """Test rejecting members files."""
        members_file = Path(
            "SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swTangencyType_e_members_84c83747.html"
        )
        self.assertFalse(is_enum_file(members_file))

    def test_is_enum_file_namespace(self) -> None:
        """Test rejecting namespace files."""
        namespace_file = Path("SolidWorks.Interop.swconst~SolidWorks.Interop.swconst_namespace_84c83747.html")
        self.assertFalse(is_enum_file(namespace_file))


class TestFilenameExtraction(unittest.TestCase):
    """Test extracting metadata from filenames."""

    def test_extract_namespace_from_filename(self) -> None:
        """Test extracting assembly, namespace, and type name from filename."""
        test_file = Path("SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swTangencyType_e_84c83747.html")

        assembly, namespace, type_name = extract_namespace_from_filename(test_file)

        self.assertEqual(assembly, "SolidWorks.Interop.swconst")
        self.assertEqual(namespace, "SolidWorks.Interop.swconst")
        self.assertEqual(type_name, "swTangencyType_e")


class TestXMLOutput(unittest.TestCase):
    """Test XML output generation."""

    def test_xml_output_with_members(self) -> None:
        """Test creating XML output with enum members."""
        enums = [
            {
                "Name": "swTest_e",
                "Assembly": "Test.Assembly",
                "Namespace": "Test.Namespace",
                "Members": [
                    {"Name": "swMember1", "Description": "Description 1"},
                    {"Name": "swMember2", "Description": 'Description with <see cref="Test.Type">link</see>'},
                ],
            }
        ]

        xml_output = create_xml_output(enums)

        # Verify structure
        self.assertIn("<EnumMembers>", xml_output)
        self.assertIn("<Enum>", xml_output)
        self.assertIn("<Name>swTest_e</Name>", xml_output)
        self.assertIn("<Assembly>Test.Assembly</Assembly>", xml_output)
        self.assertIn("<Namespace>Test.Namespace</Namespace>", xml_output)
        self.assertIn("<Members>", xml_output)
        self.assertIn("<Member>", xml_output)
        self.assertIn("<Name>swMember1</Name>", xml_output)
        self.assertIn("<Description><![CDATA[Description 1]]></Description>", xml_output)
        self.assertIn('<see cref="Test.Type">link</see>', xml_output)


if __name__ == "__main__":
    unittest.main()
