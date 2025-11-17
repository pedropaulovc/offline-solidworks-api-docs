#!/usr/bin/env python3
"""
Extract API members from crawled HTML files.

This script scans the *_members_*.html files from the crawl phase and
extracts type information (properties and methods) into an XML format.
"""

import argparse
import json
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


class MemberExtractor(HTMLParser):
    """HTML parser to extract members from SolidWorks API documentation."""

    def __init__(self, url_prefix: str = "") -> None:
        super().__init__()
        self.type_name: str | None = None
        self.properties: list[dict[str, str]] = []
        self.methods: list[dict[str, str]] = []
        self.current_section: str | None = None
        self.in_title: bool = False
        self.in_link: bool = False
        self.current_link_href: str | None = None
        self.current_link_text: str = ""
        self.in_members_table: bool = False
        self.in_member_link_cell: bool = False
        self.in_member_link: bool = False
        self.url_prefix: str = url_prefix  # Prefix to add to all URLs

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)

        # Detect page title to extract type name
        if tag == "span" and attrs_dict.get("id") == "pagetitle":
            self.in_title = True

        # Detect section headers
        if tag == "h1":
            self.current_section = None

        # Detect tables in sections
        if tag == "table" and self.current_section:
            self.in_members_table = True

        # Detect member link cells (not description cells)
        if tag == "td" and attrs_dict.get("class") == "MembersLinkCell":
            self.in_member_link_cell = True

        # Detect links in member link cells only
        if tag == "a" and self.in_member_link_cell:
            href = attrs_dict.get("href", "")
            # Only process member links (not the "Top" link)
            if href and not href.startswith("#"):
                self.in_member_link = True
                self.current_link_href = href
                self.current_link_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self.in_title:
            self.in_title = False

        if tag == "table" and self.in_members_table:
            self.in_members_table = False

        if tag == "td" and self.in_member_link_cell:
            self.in_member_link_cell = False

        if tag == "a" and self.in_member_link:
            self.in_member_link = False
            # Store the member info
            if self.current_link_href and self.current_link_text:
                # Prepend the URL prefix (e.g., /sldworksapi/)
                full_url = f"{self.url_prefix}{self.current_link_href}"

                member_info = {"Name": self.current_link_text.strip(), "Url": full_url}

                if self.current_section == "properties":
                    self.properties.append(member_info)
                elif self.current_section == "methods":
                    self.methods.append(member_info)

            self.current_link_href = None
            self.current_link_text = ""

    def handle_data(self, data: str) -> None:
        text = data.strip()

        # Extract type name from title like "IAnnotationView Interface Members"
        is_interface_members_title = self.in_title and text and " Interface Members" in text
        if is_interface_members_title:
            self.type_name = text.replace(" Interface Members", "").strip()

        # Detect section headers
        if text == "Public Properties":
            self.current_section = "properties"
        elif text == "Public Methods":
            self.current_section = "methods"
        elif text in ["See Also", "Events"]:
            self.current_section = None

        # Collect link text
        if self.in_member_link:
            self.current_link_text += data


def extract_namespace_from_filename(html_file: Path) -> tuple[str | None, str | None, str | None]:
    """
    Extract namespace and assembly from the file path.

    Returns:
        (assembly, namespace, full_type_name)

    Example filename:
        SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotationView_members_...
        -> assembly: SolidWorks.Interop.sldworks (before ~)
        -> full_type: SolidWorks.Interop.sldworks.IAnnotationView (after ~ before _members_)
        -> namespace: SolidWorks.Interop.sldworks (full_type minus the last part)
    """
    # Parse filename
    filename = html_file.name

    # Split on ~ to get assembly and full type path
    if "~" in filename:
        parts = filename.split("~")

        # Assembly is the part before ~
        assembly = parts[0]

        # Extract full type name (after ~ but before _members_)
        if len(parts) > 1:
            full_type_part = parts[1].split("_members_")[0]

            # Namespace is the full type name minus the last segment (the type name itself)
            # e.g., SolidWorks.Interop.sldworks.IAnnotationView -> SolidWorks.Interop.sldworks
            # If there's no dot, the namespace is the same as assembly
            namespace = assembly
            if "." in full_type_part:
                namespace = ".".join(full_type_part.split(".")[:-1])

            return assembly, namespace, full_type_part

    return None, None, None


def extract_members_from_file(html_file: Path) -> dict[str, Any] | None:
    """Extract members from a single HTML file."""
    # Get URL prefix from parent directory
    # e.g., /sldworksapi/ for files in .../html/sldworksapi/...
    parent_dir = html_file.parent.name
    url_prefix = f"/{parent_dir}/"

    parser = MemberExtractor(url_prefix=url_prefix)

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

    # Extract namespace and assembly from file path
    assembly, namespace, full_type_name = extract_namespace_from_filename(html_file)

    return {
        "Name": parser.type_name,
        "Assembly": assembly,
        "Namespace": namespace,
        "FullTypeName": full_type_name,
        "PublicProperties": parser.properties,
        "PublicMethods": parser.methods,
        "SourceFile": str(html_file),
    }


def create_xml_output(types: list[dict[str, Any]]) -> str:
    """Create XML output from extracted type information."""
    root = ET.Element("Types")

    for type_info in types:
        type_elem = ET.SubElement(root, "Type")

        # Add type name
        name_elem = ET.SubElement(type_elem, "Name")
        name_elem.text = type_info["Name"]

        # Add assembly
        if type_info.get("Assembly"):
            assembly_elem = ET.SubElement(type_elem, "Assembly")
            assembly_elem.text = type_info["Assembly"]

        # Add namespace
        if type_info.get("Namespace"):
            namespace_elem = ET.SubElement(type_elem, "Namespace")
            namespace_elem.text = type_info["Namespace"]

        # Add properties
        if type_info["PublicProperties"]:
            props_elem = ET.SubElement(type_elem, "PublicProperties")
            for prop in type_info["PublicProperties"]:
                prop_elem = ET.SubElement(props_elem, "Property")
                prop_name = ET.SubElement(prop_elem, "Name")
                prop_name.text = prop["Name"]
                prop_url = ET.SubElement(prop_elem, "Url")
                prop_url.text = prop["Url"]

        # Add methods
        if type_info["PublicMethods"]:
            methods_elem = ET.SubElement(type_elem, "PublicMethods")
            for method in type_info["PublicMethods"]:
                method_elem = ET.SubElement(methods_elem, "Method")
                method_name = ET.SubElement(method_elem, "Name")
                method_name.text = method["Name"]
                method_url = ET.SubElement(method_elem, "Url")
                method_url.text = method["Url"]

    # Pretty print the XML
    xml_str = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="    ")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract API members from crawled HTML files")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("10_crawl_toc_pages/output/html"),
        help="Directory containing crawled HTML files",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("20_extract_types/metadata"), help="Directory to save output files"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Find all member HTML files
    member_files = list(args.input_dir.rglob("*_members_*.html"))

    if not member_files:
        print(f"No member files found in {args.input_dir}")
        return 1

    print(f"Found {len(member_files)} member files to process")

    # Extract members from each file
    types = []
    errors = []

    for html_file in member_files:
        if args.verbose:
            print(f"Processing {html_file.name}...")

        type_info = extract_members_from_file(html_file)
        if type_info:
            types.append(type_info)
        else:
            errors.append(str(html_file))

    # Sort types by name for consistent output
    types.sort(key=lambda x: x["Name"])

    # Generate XML output
    xml_output = create_xml_output(types)

    # Save XML file
    xml_file = args.output_dir / "api_members.xml"
    with open(xml_file, "w", encoding="utf-8") as f:
        f.write(xml_output)

    print("\nExtraction complete!")
    print(f"  Types extracted: {len(types)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Output saved to: {xml_file}")

    # Save summary metadata
    summary = {
        "total_files_processed": len(member_files),
        "types_extracted": len(types),
        "errors": len(errors),
        "output_file": str(xml_file),
        "error_files": errors,
    }

    summary_file = args.output_dir / "extraction_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"  Summary saved to: {summary_file}")

    if errors:
        print(f"\nWarning: {len(errors)} files had errors")
        if args.verbose:
            for error_file in errors:
                print(f"  - {error_file}")

    return 0


if __name__ == "__main__":
    exit(main())
