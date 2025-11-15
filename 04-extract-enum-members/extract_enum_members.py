#!/usr/bin/env python3
"""
Extract enum members from crawled HTML files.

This script scans enum type HTML files and extracts member names and descriptions
into an XML format separate from the type definitions.
"""

import argparse
import json
import re
import sys
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# Add parent directory to path for shared module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.xmldoc_links import convert_links_to_see_refs


class EnumMemberExtractor(HTMLParser):
    """HTML parser to extract enum member information from SolidWorks API documentation."""

    def __init__(self) -> None:
        super().__init__()
        self.type_name: str | None = None
        self.enum_members: list[dict[str, str]] = []

        # State tracking
        self.in_pagetitle: bool = False
        self.in_members_section: bool = False
        self.in_members_table: bool = False
        self.in_member_row: bool = False
        self.in_member_name_cell: bool = False
        self.in_member_desc_cell: bool = False
        self.current_member_name: str | None = None
        self.current_member_desc_parts: list[str] = []
        self.member_desc_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)

        # Detect page title
        if tag == "span" and attrs_dict.get("id") == "pagetitle":
            self.in_pagetitle = True
            return

        # Detect members table (enum members)
        is_enum_members_table = self.in_members_section and tag == "table" and attrs_dict.get("class") == "FilteredItemListTable"
        if is_enum_members_table:
            self.in_members_table = True
            return

        # Detect table row in members table
        if self.in_members_table and tag == "tr":
            self.in_member_row = True
            self.current_member_name = None
            self.current_member_desc_parts = []
            return

        # Detect member name cell and description cell
        if self.in_member_row and tag == "td":
            cell_class = attrs_dict.get("class", "")
            if cell_class == "MemberNameCell":
                self.in_member_name_cell = True
            elif cell_class == "DescriptionCell":
                self.in_member_desc_cell = True
                self.member_desc_depth = 0
            return

        # Collect HTML tags in member description cell (for link conversion)
        if self.in_member_desc_cell:
            self.member_desc_depth += 1
            attrs_str = ""
            if attrs:
                attrs_str = " " + " ".join([f'{k}="{v}"' for k, v in attrs])
            self.current_member_desc_parts.append(f"<{tag}{attrs_str}>")

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self.in_pagetitle:
            self.in_pagetitle = False
            return

        # Handle end of member description cell
        if tag == "td" and self.in_member_desc_cell:
            self.in_member_desc_cell = False
            self.member_desc_depth -= 1
            self.current_member_desc_parts.append(f"</{tag}>")
            return

        # Handle end of member name cell
        if tag == "td" and self.in_member_name_cell:
            self.in_member_name_cell = False
            return

        # Handle end of table row - save the member
        if tag == "tr" and self.in_member_row:
            self.in_member_row = False
            # Only save if we have both name and description (skip header row)
            if self.current_member_name and self.current_member_desc_parts:
                # Convert description HTML (including links) to XMLDoc format
                desc_html = "".join(self.current_member_desc_parts).strip()
                desc_clean = convert_links_to_see_refs(desc_html)

                self.enum_members.append({"Name": self.current_member_name, "Description": desc_clean})
            return

        # Handle end of members table
        if tag == "table" and self.in_members_table:
            self.in_members_table = False
            return

        # Track closing tags in member description cell
        if self.in_member_desc_cell:
            self.member_desc_depth -= 1
            self.current_member_desc_parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        text = data.strip()

        # Capture type name from pagetitle
        if self.in_pagetitle and text:
            # Remove " Enumeration" suffix if present
            self.type_name = text.replace(" Enumeration", "").strip()

        # Detect Members section header (only in h1 tags - but we simplify here)
        if text == "Members":
            self.in_members_section = True

        # Collect member name (appears in <strong> tag within MemberNameCell)
        # Member names are in <strong> tags, so just collect the text
        should_collect_member_name = self.in_member_name_cell and text and not self.current_member_name
        if should_collect_member_name:
            self.current_member_name = text

        # Collect member description (appears in DescriptionCell)
        if self.in_member_desc_cell and data:
            self.current_member_desc_parts.append(data)


def extract_namespace_from_filename(html_file: Path) -> tuple[str, str, str]:
    """
    Extract namespace and assembly from the file path.

    Returns:
        tuple[str, str, str]: (assembly, namespace, type_name)
    """
    # Example filename format:
    # SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData_84c83747.html
    # Or with double extension: SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swTangencyType_e_359c36b2_359c36b2.htmll.html
    filename = html_file.name

    # Remove all extensions (.html, .htmll.html, etc.)
    while "." in filename and any(filename.endswith(ext) for ext in [".html", ".htmll", ".htm"]):
        filename = filename.rsplit(".", 1)[0]

    # Remove hash suffixes (underscore followed by hex digits)
    # Keep removing until we don't have hash pattern
    while re.search(r"_[0-9a-f]{8}$", filename):
        filename = filename.rsplit("_", 1)[0]

    name_part = filename

    # Split by tilde to get assembly and rest
    if "~" in name_part:
        assembly_part, rest = name_part.split("~", 1)
        assembly = assembly_part

        # The rest contains namespace.type
        # The namespace is everything up to the last dot
        if "." in rest:
            parts = rest.rsplit(".", 1)
            namespace = parts[0]
            type_name = parts[1]
        else:
            namespace = assembly
            type_name = rest
    else:
        # No tilde separator - use filename as type name
        assembly = ""
        namespace = ""
        type_name = name_part

    return assembly, namespace, type_name


def is_enum_file(html_file: Path) -> bool:
    """
    Check if the HTML file is an enum file.

    Enum files typically have "_e" suffix in the type name and don't have
    _members_ or _namespace_ in their name.
    """
    filename = html_file.name.lower()

    # Exclude members and namespace files
    if "_members_" in filename or "_namespace_" in filename:
        return False

    # Exclude special files
    special_prefixes = ["functionalcategories", "releasenotes", "help_list"]
    if any(filename.startswith(prefix) for prefix in special_prefixes):
        return False

    # Must have tilde separator (indicating it's a type file)
    if "~" not in filename:
        return False

    # Check if it's an enum by looking at the type name
    _, _, type_name = extract_namespace_from_filename(html_file)
    return type_name.endswith("_e")


def extract_enum_members_from_file(html_file: Path) -> dict | None:
    """Extract enum members from a single HTML file."""
    parser = EnumMemberExtractor()

    try:
        with open(html_file, encoding="utf-8") as f:
            content = f.read()
            parser.feed(content)
    except Exception as e:
        print(f"Error parsing {html_file}: {e}")
        return None

    if not parser.type_name:
        print(f"Warning: Could not extract type name from {html_file}")
        return None

    # Only return if we found members
    if not parser.enum_members:
        return None

    # Extract namespace and assembly from file path
    assembly, namespace, type_name = extract_namespace_from_filename(html_file)

    return {
        "Name": parser.type_name,
        "Assembly": assembly,
        "Namespace": namespace,
        "Members": parser.enum_members,
        "SourceFile": str(html_file),
    }


def _wrap_cdata_sections(xml_str: str) -> str:
    """
    Wrap content of Description elements in CDATA sections.

    This is a post-processing step since ElementTree doesn't natively support CDATA.
    """
    import html as html_module

    # Pattern to find Description elements marked with __cdata__="true"
    pattern = r'<Description __cdata__="true">(.*?)</Description>'

    def replace_with_cdata(match: re.Match[str]) -> str:
        content = match.group(1)
        # Unescape XML entities since CDATA doesn't need escaping
        content = html_module.unescape(content)
        return f"<Description><![CDATA[{content}]]></Description>"

    return re.sub(pattern, replace_with_cdata, xml_str, flags=re.DOTALL)


def create_xml_output(enums: list[dict[str, Any]]) -> str:
    """Create XML output from extracted enum member information."""
    root = ET.Element("EnumMembers")

    for enum_info in enums:
        enum_elem = ET.SubElement(root, "Enum")

        # Add enum name
        name_elem = ET.SubElement(enum_elem, "Name")
        name_elem.text = enum_info["Name"]

        # Add assembly
        if enum_info.get("Assembly"):
            assembly_elem = ET.SubElement(enum_elem, "Assembly")
            assembly_elem.text = enum_info["Assembly"]

        # Add namespace
        if enum_info.get("Namespace"):
            namespace_elem = ET.SubElement(enum_elem, "Namespace")
            namespace_elem.text = enum_info["Namespace"]

        # Add members
        if enum_info.get("Members"):
            members_elem = ET.SubElement(enum_elem, "Members")
            for member in enum_info["Members"]:
                member_elem = ET.SubElement(members_elem, "Member")

                mem_name = ET.SubElement(member_elem, "Name")
                mem_name.text = member["Name"]

                mem_desc = ET.SubElement(member_elem, "Description")
                mem_desc.text = member["Description"]
                mem_desc.set("__cdata__", "true")

    # Pretty print the XML
    xml_str = ET.tostring(root, encoding="unicode")

    # Post-process to add CDATA sections for Description elements
    xml_str = _wrap_cdata_sections(xml_str)

    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="    ")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract enum members from SolidWorks API HTML files")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("01-crawl-toc-pages/output/html"),
        help="Input directory containing HTML files (default: 01-crawl-toc-pages/output/html)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("04-extract-enum-members/metadata/enum_members.xml"),
        help="Output XML file (default: 04-extract-enum-members/metadata/enum_members.xml)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")

    args = parser.parse_args()

    # Find all HTML files
    html_dirs = list(args.input_dir.glob("*"))
    all_html_files = []
    for html_dir in html_dirs:
        if html_dir.is_dir():
            all_html_files.extend(html_dir.glob("*.html"))

    # Filter to enum files only
    enum_files = [f for f in all_html_files if is_enum_file(f)]

    if not enum_files:
        print(f"No enum files found in {args.input_dir}")
        return 1

    print(f"Found {len(enum_files)} enum files to process (out of {len(all_html_files)} total HTML files)")

    # Extract enum members from each file
    enums: list[dict[str, Any]] = []
    errors: list[str] = []

    for html_file in enum_files:
        if args.verbose:
            print(f"Processing {html_file.name}...")

        enum_info = extract_enum_members_from_file(html_file)
        if enum_info:
            enums.append(enum_info)
        else:
            if args.verbose:
                print(f"  No members found in {html_file.name}")

    # Sort enums by name for consistent output
    enums.sort(key=lambda x: x["Name"])

    # Create output directory if it doesn't exist
    args.output_file.parent.mkdir(parents=True, exist_ok=True)

    # Generate XML
    xml_output = create_xml_output(enums)

    # Write to file
    with open(args.output_file, "w", encoding="utf-8") as f:
        f.write(xml_output)

    # Write summary
    summary = {
        "total_files_processed": len(enum_files),
        "enums_with_members": len(enums),
        "enums_without_members": len(enum_files) - len(enums),
        "errors": len(errors),
        "output_file": str(args.output_file),
        "error_files": errors,
    }

    summary_file = args.output_file.parent / "extraction_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\nExtraction complete!")
    print(f"  Enums with members: {len(enums)}")
    print(f"  Enums without members: {len(enum_files) - len(enums)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Output saved to: {args.output_file}")
    print(f"  Summary saved to: {summary_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
