#!/usr/bin/env python3
"""
Unit tests for type information extraction.
"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from extract_type_info import (
    TypeInfoExtractor,
    extract_namespace_from_filename,
    is_type_file
)


class TestTypeInfoExtractor(unittest.TestCase):
    """Test the TypeInfoExtractor HTML parser."""

    def test_basic_type_extraction(self):
        """Test extracting basic type information."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">IAdvancedHoleFeatureData Interface</span>
        </div>
        <div id="mainbody">
            Allows access to the Advanced Hole feature data.
            <h1>.NET Syntax</h1>
        </div>
        </html>
        """

        parser = TypeInfoExtractor()
        parser.feed(html)

        self.assertEqual(parser.type_name, "IAdvancedHoleFeatureData")
        self.assertIn("Advanced Hole feature data", parser.get_description())

    def test_description_with_links_converted_to_see_cref(self):
        """Test that links in description are converted to XMLDoc <see cref> format (IDocumentSpecification bug)."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">IDocumentSpecification Interface</span>
        </div>
        <div id="mainbody">
            <br>Allows you to specify how to open a model document. Use this interface's properties before calling <a href="SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~OpenDoc7.html">ISldWorks::OpenDoc7</a> to specify how you want to open a model document.
            <h1>.NET Syntax</h1>
        </div>
        </html>
        """

        parser = TypeInfoExtractor()
        parser.feed(html)

        description = parser.get_description()

        # Should convert HTML link to XMLDoc see cref
        self.assertIn('<see cref="SOLIDWORKS.Interop.sldworks.ISldWorks.OpenDoc7">ISldWorks::OpenDoc7</see>', description)
        # Should preserve :: in the see tag body
        self.assertIn("ISldWorks::OpenDoc7</see>", description)
        # Should not contain the original HTML anchor tag
        self.assertNotIn("<a href=", description)

    def test_example_extraction(self):
        """Test extracting examples from type documentation."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">IAdvancedHoleFeatureData Interface</span>
        </div>
        <div id="mainbody">
            Test description
            <h1>Example</h1>
            <div id="exampleSection">
                <a href="Create_Advanced_Hole_Example_VB.htm">Create Advanced Hole Feature (VBA)</a>
                <br>
                <a href="Create_Advanced_Hole_Example_VBNET.htm">Create Advanced Hole Feature (VB.NET)</a>
            </div>
        </div>
        </html>
        """

        parser = TypeInfoExtractor(url_prefix="/sldworksapi/")
        parser.feed(html)

        self.assertEqual(len(parser.examples), 2)
        self.assertEqual(parser.examples[0]["Name"], "Create Advanced Hole Feature")
        self.assertEqual(parser.examples[0]["Language"], "VBA")
        self.assertEqual(parser.examples[0]["Url"], "/sldworksapi/Create_Advanced_Hole_Example_VB.htm")
        self.assertEqual(parser.examples[1]["Language"], "VB.NET")

    def test_remarks_extraction(self):
        """Test extracting remarks section."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">IAdvancedHoleFeatureData Interface</span>
        </div>
        <div id="mainbody">
            Test description
            <h1>Remarks</h1>
            <div id="remarksSection">
                <p>To create an Advanced Hole feature, see the remarks.</p>
            </div>
        </div>
        </html>
        """

        parser = TypeInfoExtractor()
        parser.feed(html)

        remarks = parser.get_remarks()
        self.assertIn("Advanced Hole feature", remarks)

    def test_remarks_with_links_converted_to_see_cref(self):
        """Test that links in remarks are converted to XMLDoc <see cref> format."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">IAdvancedHoleFeatureData Interface</span>
        </div>
        <div id="mainbody">
            Test description
            <h1>Remarks</h1>
            <div id="remarksSection">
                <p>To create an Advanced Hole feature, see the&nbsp;<a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~AdvancedHole.html">IFeatureManager::AdvancedHole</a>&nbsp;Remarks.&nbsp;</p>
            </div>
        </div>
        </html>
        """

        parser = TypeInfoExtractor()
        parser.feed(html)

        remarks = parser.get_remarks()

        # Should convert HTML link to XMLDoc see cref
        self.assertIn('<see cref="SolidWorks.Interop.sldworks.IFeatureManager.AdvancedHole">IFeatureManager::AdvancedHole</see>', remarks)
        # Should preserve :: in the see tag body
        self.assertIn("IFeatureManager::AdvancedHole</see>", remarks)
        # Should clean up &nbsp; entities
        self.assertNotIn("&nbsp;", remarks)
        # Should not contain the original HTML anchor tag
        self.assertNotIn("<a href=", remarks)

    def test_language_inference_from_filename(self):
        """Test inferring programming language from filename."""
        parser = TypeInfoExtractor()

        self.assertEqual(parser._infer_language_from_filename("Example_VB.htm"), "VBA")
        self.assertEqual(parser._infer_language_from_filename("Example_VBNET.htm"), "VB.NET")
        self.assertEqual(parser._infer_language_from_filename("Example_CSharp.htm"), "C#")
        self.assertEqual(parser._infer_language_from_filename("Example_CPP.htm"), "C++")

    def test_accessors_section_not_collected_as_examples(self):
        """Test that links in Accessors section are not collected as examples (ICrossBreakFeatureData bug)."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">ICrossBreakFeatureData Interface</span>
        </div>
        <div id="mainbody">
            Gets or sets cross break feature data.
            <h1>Example</h1>
            <div id="exampleSection">
                <a href="Get_Cross_Break_Example_CSharp.htm">Get Cross Break Feature Data in Sheet Metal Part (C#)</a>
                <br>
                <a href="Get_Cross_Break_Example_VBNET.htm">Get Cross Break Feature Data in Sheet Metal Part (VB.NET)</a>
                <br>
                <a href="Get_Cross_Break_Example_VB.htm">Get Cross Break Feature Data in Sheet Metal Part (VBA)</a>
            </div>
            <h1>Accessors</h1>
            <div id="accessorsSection">
                <a href="IFeature~GetDefinition.html">IFeature::GetDefinition</a> and
                <a href="IFeature~IGetDefinition.html">IFeature::IGetDefinition</a>
            </div>
            <h1>Access Diagram</h1>
            <div id="swobjectmodelSection">
                <p><a href="SWObjectModel.pdf#CrossBreakFeatureData" target="_blank">CrossBreakFeatureData</a></p>
            </div>
            <h1>See Also</h1>
            <div id="seealsoSection">
                <a href="ICrossBreakFeatureData_members.html">ICrossBreakFeatureData Members</a>
            </div>
        </div>
        </html>
        """

        parser = TypeInfoExtractor(url_prefix="/sldworksapi/")
        parser.feed(html)

        # Should only have 3 examples from the Example section
        self.assertEqual(len(parser.examples), 3)
        self.assertEqual(parser.examples[0]["Name"], "Get Cross Break Feature Data in Sheet Metal Part")
        self.assertEqual(parser.examples[0]["Language"], "C#")
        self.assertEqual(parser.examples[1]["Language"], "VB.NET")
        self.assertEqual(parser.examples[2]["Language"], "VBA")

        # Verify no links from Accessors, Access Diagram, or See Also sections were collected
        example_urls = [ex["Url"] for ex in parser.examples]
        self.assertNotIn("/sldworksapi/IFeature~GetDefinition.html", example_urls)
        self.assertNotIn("/sldworksapi/IFeature~IGetDefinition.html", example_urls)
        self.assertNotIn("/sldworksapi/SWObjectModel.pdf#CrossBreakFeatureData", example_urls)
        self.assertNotIn("/sldworksapi/ICrossBreakFeatureData_members.html", example_urls)


    def test_cdata_wrapping_in_xml_output(self):
        """Test that descriptions and remarks are wrapped in CDATA in final XML output."""
        from extract_type_info import create_xml_output

        types = [
            {
                "Name": "ITestType",
                "Assembly": "Test.Assembly",
                "Namespace": "Test.Namespace",
                "Description": "Test description with <see cref=\"SomeType\">link</see> inside.",
                "PublicProperties": [],
                "PublicMethods": [],
                "Remarks": "Test remarks with <see cref=\"SomeMethod\">method link</see> inside."
            }
        ]

        xml_output = create_xml_output(types)

        # Verify CDATA sections are present
        self.assertIn("<Description><![CDATA[", xml_output)
        self.assertIn("<Remarks><![CDATA[", xml_output)

        # Verify see tags are preserved inside CDATA
        self.assertIn('<see cref="SomeType">link</see>', xml_output)
        self.assertIn('<see cref="SomeMethod">method link</see>', xml_output)

        # Verify no __cdata__ attributes in final output
        self.assertNotIn('__cdata__="true"', xml_output)

    def test_non_type_links_converted_to_see_href(self):
        """Test that non-type links (guide pages) are converted to <see href> format (IPLMObjectSpecification bug)."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">IPLMObjectSpecification Interface</span>
        </div>
        <div id="mainbody">
            Allows access to a <a href="../sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm">SOLIDWORKS Design connected to the 3DEXPERIENCE platform</a> document specification.
            <h1>.NET Syntax</h1>
        </div>
        </html>
        """

        parser = TypeInfoExtractor()
        parser.feed(html)

        description = parser.get_description()

        # Should convert non-type link to XMLDoc see href
        self.assertIn('<see href="https://help.solidworks.com/2026/english/api/sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm">', description)
        # Should preserve link text
        self.assertIn('SOLIDWORKS Design connected to the 3DEXPERIENCE platform</see>', description)
        # Should not contain the original HTML anchor tag
        self.assertNotIn("<a href=", description)

    def test_type_links_with_path_prefix_converted_to_see_cref(self):
        """Test that type reference links with path prefixes are converted to <see cref> (swZonalSectionViewZones_e bug)."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">swZonalSectionViewZones_e Enumeration</span>
        </div>
        <div id="mainbody">
            Test description
            <h1>Remarks</h1>
            <div id="remarksSection">
                Descriptions appear in <a href="../sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISectionViewData~SectionedZones.html">ISectionViewData::SectionedZones</a>.
            </div>
        </div>
        </html>
        """

        parser = TypeInfoExtractor()
        parser.feed(html)

        remarks = parser.get_remarks()

        # Should convert type reference to XMLDoc see cref (not href!)
        self.assertIn('<see cref="SolidWorks.Interop.sldworks.ISectionViewData.SectionedZones">', remarks)
        # Should preserve :: in link text
        self.assertIn('ISectionViewData::SectionedZones</see>', remarks)
        # Should NOT use href for type references
        self.assertNotIn('<see href=', remarks)

    def test_enum_member_extraction(self):
        """Test extracting enum members with descriptions (swTangencyType_e example)."""
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
                    <tr>
                        <td class="MemberNameCell"><strong>swTangencyAllFaces</strong></td>
                        <td class="DescriptionCell">3 = Makes the adjacent faces tangent; see <a href="SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swTwistControlType_e.html">swTwistControlType_e</a></td>
                    </tr>
                </table>
            </div>
        </div>
        </html>
        """

        parser = TypeInfoExtractor()
        parser.feed(html)

        # Should extract 3 enum members
        self.assertEqual(len(parser.enum_members), 3)

        # Check first member
        self.assertEqual(parser.enum_members[0]["Name"], "swMinimumTwist")
        self.assertIn("10 = Prevents", parser.enum_members[0]["Description"])

        # Check second member
        self.assertEqual(parser.enum_members[1]["Name"], "swTangencyNone")
        self.assertEqual(parser.enum_members[1]["Description"], "0")

        # Check third member has link converted to see cref
        self.assertEqual(parser.enum_members[2]["Name"], "swTangencyAllFaces")
        self.assertIn('<see cref="SolidWorks.Interop.swconst.swTwistControlType_e">', parser.enum_members[2]["Description"])
        self.assertIn('swTwistControlType_e</see>', parser.enum_members[2]["Description"])

    def test_remarks_not_triggered_by_text_in_cells(self):
        """Test that 'Remarks' text in member descriptions doesn't trigger remarks section (swWzdHoleStandardFastenerTypes_e bug)."""
        html = """
        <html>
        <div id="pagetop">
            <span id="pagetitle">swTest Enumeration</span>
        </div>
        <div id="mainbody">
            Test enum.
            <h1>Members</h1>
            <div id="enummembersSection">
                <table class="FilteredItemListTable">
                    <tr><th>Member</th><th>Description</th></tr>
                    <tr>
                        <td class="MemberNameCell"><strong>swObsoleteMember</strong></td>
                        <td class="DescriptionCell">Obsolete; see <strong>Remarks</strong></td>
                    </tr>
                    <tr>
                        <td class="MemberNameCell"><strong>swValidMember</strong></td>
                        <td class="DescriptionCell">Valid member</td>
                    </tr>
                </table>
            </div>
            <h1>Remarks</h1>
            <div id="remarksSection">This is the actual remarks content.</div>
        </div>
        </html>
        """

        parser = TypeInfoExtractor()
        parser.feed(html)

        # Should extract 2 members
        self.assertEqual(len(parser.enum_members), 2)

        # Remarks should only contain actual remarks, not member descriptions
        remarks = parser.get_remarks()
        self.assertEqual(remarks.strip(), "This is the actual remarks content.")

        # Remarks should NOT contain member names or descriptions
        self.assertNotIn("swObsoleteMember", remarks)
        self.assertNotIn("swValidMember", remarks)

        # Remarks should NOT contain the h1 heading text
        self.assertNotIn("Remarks\n", remarks)


class TestFilenameExtraction(unittest.TestCase):
    """Test extracting metadata from filenames."""

    def test_extract_namespace_from_filename(self):
        """Test extracting assembly, namespace, and type name from filename."""
        # Create a mock Path object
        test_file = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData_84c83747_84c83747.htmll.html")

        assembly, namespace, type_name = extract_namespace_from_filename(test_file)

        self.assertEqual(assembly, "SolidWorks.Interop.sldworks")
        self.assertEqual(namespace, "SolidWorks.Interop.sldworks")
        self.assertEqual(type_name, "IAdvancedHoleFeatureData")

    def test_extract_namespace_different_assembly(self):
        """Test with different assembly and namespace."""
        test_file = Path("SolidWorks.Interop.dsgnchk~SolidWorks.Interop.dsgnchk.ISWDesignCheck_8a2a04ee_8a2a04ee.htmll.html")

        assembly, namespace, type_name = extract_namespace_from_filename(test_file)

        self.assertEqual(assembly, "SolidWorks.Interop.dsgnchk")
        self.assertEqual(namespace, "SolidWorks.Interop.dsgnchk")
        self.assertEqual(type_name, "ISWDesignCheck")


class TestFileFiltering(unittest.TestCase):
    """Test filtering type files from other files."""

    def test_is_type_file_valid(self):
        """Test identifying valid type files."""
        valid_file = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData_84c83747.html")
        self.assertTrue(is_type_file(valid_file))

    def test_is_type_file_members(self):
        """Test rejecting members files."""
        members_file = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData_members_84c83747.html")
        self.assertFalse(is_type_file(members_file))

    def test_is_type_file_namespace(self):
        """Test rejecting namespace files."""
        namespace_file = Path("SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks_namespace_84c83747.html")
        self.assertFalse(is_type_file(namespace_file))

    def test_is_type_file_special(self):
        """Test rejecting special files."""
        self.assertFalse(is_type_file(Path("FunctionalCategories-sldworksapi_123.html")))
        self.assertFalse(is_type_file(Path("ReleaseNotes-sldworksapi_456.html")))
        self.assertFalse(is_type_file(Path("help_list_789.html")))

    def test_is_type_file_without_tilde(self):
        """Test rejecting files without tilde separator."""
        invalid_file = Path("SomeRandomFile.html")
        self.assertFalse(is_type_file(invalid_file))


if __name__ == "__main__":
    unittest.main()
