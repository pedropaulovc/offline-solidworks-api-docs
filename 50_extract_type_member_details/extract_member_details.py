#!/usr/bin/env python3
"""
Extract member detail information from crawled HTML files.

This script scans member HTML files from Phase 3 (30_crawl_type_members)
and extracts member details (parameters, return values, remarks) into an XML format.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# Add parent directory to path for shared module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.extraction_utils import (
    add_see_also_element,
    extract_member_name_from_filename,
    extract_namespace_from_filename,
    is_member_file,
    prettify_xml,
)
from shared.xmldoc_links import convert_links_to_see_refs, href_to_see_ref


class MemberDetailsExtractor(HTMLParser):
    """HTML parser to extract member details from SolidWorks API documentation."""

    def __init__(self, url_prefix: str = "") -> None:
        super().__init__()
        self.member_name: str | None = None
        self.type_name: str | None = None
        self.description: str = ""
        self.signature: str = ""
        self.parameters: list[dict[str, str]] = []
        self.return_value: str = ""
        self.examples: list[dict[str, str]] = []
        self.remarks: str = ""
        self.see_also: list[dict[str, str]] = []

        # State tracking
        self.in_pagetitle: bool = False
        self.in_description: bool = False
        self.in_h1: bool = False
        self.in_h4: bool = False
        self.current_section: str | None = None
        self.in_syntax_section: bool = False
        self.in_parameters_section: bool = False
        self.in_return_section: bool = False
        self.in_example_section: bool = False
        self.in_remarks_section: bool = False
        self.in_see_also_section: bool = False
        self.in_see_also_link: bool = False
        self.current_seealso_href: str | None = None
        self.current_seealso_text: str = ""
        self.in_link: bool = False
        self.current_link_href: str | None = None
        self.current_link_text: str = ""
        self.url_prefix: str = url_prefix

        # For collecting description text after pagetitle
        self.seen_pagetitle: bool = False
        self.seen_first_h1: bool = False
        self.description_parts: list[str] = []

        # For collecting parameters
        self.in_param_dt: bool = False
        self.in_param_dd: bool = False
        self.current_param_name: str = ""
        self.current_param_desc_parts: list[str] = []

        # For collecting signature from C# syntax
        self.in_cs_syntax: bool = False
        self.in_syntax_table: bool = False
        self.syntax_depth: int = 0
        self.signature_parts: list[str] = []

        # For collecting return value
        self.return_parts: list[str] = []
        self.return_depth: int = 0

        # For collecting remarks content
        self.remarks_parts: list[str] = []
        self.remarks_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)

        # Detect page title
        if tag == "span" and attrs_dict.get("id") == "pagetitle":
            self.in_pagetitle = True
            return

        # Track when we're inside an h1 tag (for section detection)
        if tag == "h1":
            self.in_h1 = True
            # Track when we've seen the first h1 (stops description collection)
            if self.seen_pagetitle and not self.seen_first_h1:
                self.seen_first_h1 = True
                self.in_description = False
            return

        # Track when we're inside an h4 tag
        if tag == "h4":
            self.in_h4 = True
            return

        # Detect C# syntax section for signature extraction
        if tag == "div" and attrs_dict.get("id") == "Syntax_CS":
            self.in_cs_syntax = True
            return

        # Track when we're in a syntax table
        if self.in_cs_syntax and tag == "table" and "syntaxtable" in attrs_dict.get("class", ""):
            self.in_syntax_table = True
            self.syntax_depth = 0
            return

        # Collect signature from pre tag in C# syntax
        if self.in_syntax_table and tag == "pre":
            self.syntax_depth += 1

        # Collect all HTML tags in description section
        if self.in_description and not self.in_pagetitle:
            attrs_str = ""
            if attrs:
                attrs_str = " " + " ".join([f'{k}="{v}"' for k, v in attrs])
            self.description_parts.append(f"<{tag}{attrs_str}>")

        # Detect links in example section
        # Only collect links to example files (not references to other types)
        if self.in_example_section and tag == "a":
            href = attrs_dict.get("href", "")
            # Example links contain "Example" or "_Example_" in the filename
            # and typically end with .htm (not .html for type pages)
            is_example_link = href and ("Example" in href or "_Example_" in href) and href.endswith(".htm")
            if href and not href.startswith("#") and is_example_link:
                self.in_link = True
                self.current_link_href = href
                self.current_link_text = ""

        # Detect links in See Also section (collect every link, not just examples)
        if self.in_see_also_section and tag == "a":
            href = attrs_dict.get("href", "")
            if href and not href.startswith("#"):
                self.in_see_also_link = True
                self.current_seealso_href = href
                self.current_seealso_text = ""

        # Detect parameters section (dl/dt/dd structure)
        if self.in_parameters_section:
            if tag == "dt":
                # Save previous parameter if any
                if self.current_param_name:
                    param_desc = "".join(self.current_param_desc_parts).strip()
                    param_desc = convert_links_to_see_refs(param_desc)
                    self.parameters.append({"Name": self.current_param_name, "Description": param_desc})
                    self.current_param_name = ""
                    self.current_param_desc_parts = []

                self.in_param_dt = True
            elif tag == "dd":
                self.in_param_dd = True
            else:
                # Collect HTML tags in parameter description
                if self.in_param_dd:
                    attrs_str = ""
                    if attrs:
                        attrs_str = " " + " ".join([f'{k}="{v}"' for k, v in attrs])
                    self.current_param_desc_parts.append(f"<{tag}{attrs_str}>")

        # Collect all HTML tags in return value section.
        # Depth is tracked on <div> nesting only: the section is a single
        # wrapper <div> and ends when that wrapper closes. Counting every tag
        # is fragile (void elements like <br> never emit an end tag, and the
        # section-header tag desyncs the count), which truncated long sections.
        if self.in_return_section and not self.in_h4:
            if tag == "div":
                self.return_depth += 1
            attrs_str = ""
            if attrs:
                attrs_str = " " + " ".join([f'{k}="{v}"' for k, v in attrs])
            self.return_parts.append(f"<{tag}{attrs_str}>")

        # Collect all HTML tags in remarks section (see return-section note above)
        if self.in_remarks_section and not self.in_h1:
            if tag == "div":
                self.remarks_depth += 1
            attrs_str = ""
            if attrs:
                attrs_str = " " + " ".join([f'{k}="{v}"' for k, v in attrs])
            self.remarks_parts.append(f"<{tag}{attrs_str}>")

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self.in_pagetitle:
            self.in_pagetitle = False
            self.seen_pagetitle = True
            self.in_description = True
            return

        # Track closing tags in description section
        if self.in_description and not self.in_pagetitle:
            self.description_parts.append(f"</{tag}>")

        # Handle end of link in example section
        if tag == "a" and self.in_link:
            self.in_link = False
            if self.current_link_href and self.current_link_text:
                # Parse example info from link text
                # Format: "Create Advanced Hole Feature (VBA)"
                example_info = self._parse_example_link(self.current_link_text, self.current_link_href)
                if example_info:
                    self.examples.append(example_info)

            self.current_link_href = None
            self.current_link_text = ""

        # Handle end of link in See Also section
        if tag == "a" and self.in_see_also_link:
            self.in_see_also_link = False
            if self.current_seealso_href and self.current_seealso_text.strip():
                attr, value = href_to_see_ref(self.current_seealso_href)
                self.see_also.append(
                    {"attr": attr, "value": value, "label": self.current_seealso_text.strip()}
                )
            self.current_seealso_href = None
            self.current_seealso_text = ""

        # Close h1 tag - might signal end of section header
        if tag == "h1":
            self.in_h1 = False

        # Close h4 tag
        if tag == "h4":
            self.in_h4 = False

        # End C# syntax section
        if tag == "div" and self.in_cs_syntax:
            self.in_cs_syntax = False
            self.in_syntax_table = False

        # Track closing tags in syntax pre
        if self.in_syntax_table and tag == "pre":
            self.syntax_depth -= 1

        # Close parameters section elements
        if tag == "dt" and self.in_param_dt:
            self.in_param_dt = False
        elif tag == "dd" and self.in_param_dd:
            self.in_param_dd = False
        elif tag == "dl" and self.in_parameters_section:
            # Save last parameter if any
            if self.current_param_name:
                param_desc = "".join(self.current_param_desc_parts).strip()
                param_desc = convert_links_to_see_refs(param_desc)
                self.parameters.append({"Name": self.current_param_name, "Description": param_desc})
                self.current_param_name = ""
                self.current_param_desc_parts = []
        else:
            # Collect closing HTML tags in parameter description
            if self.in_param_dd:
                self.current_param_desc_parts.append(f"</{tag}>")

        # Track closing tags in return value section (div-only depth)
        if self.in_return_section and not self.in_h4:
            self.return_parts.append(f"</{tag}>")
            if tag == "div":
                self.return_depth -= 1
                # The wrapper <div> closing (depth back to 0) ends the section
                if self.return_depth <= 0:
                    self.in_return_section = False

        # Track closing tags in remarks section (div-only depth)
        if self.in_remarks_section and not self.in_h1:
            self.remarks_parts.append(f"</{tag}>")
            if tag == "div":
                self.remarks_depth -= 1
                # The wrapper <div> closing (depth back to 0) ends the section
                if self.remarks_depth <= 0:
                    self.in_remarks_section = False

    def handle_data(self, data: str) -> None:
        text = data.strip()

        # Capture member and type names from pagetitle
        # Format: "MemberName Method/Property (TypeName)"
        if self.in_pagetitle and text:
            # Parse: "InsertCavity3 Method (IAssemblyDoc)"
            match = re.match(r"(.+?)\s+(Method|Property)\s+\((.+?)\)", text)
            if match:
                self.member_name = match.group(1).strip()
                self.type_name = match.group(3).strip()

        # Capture description (text between pagetitle and first h1)
        if self.in_description and data and not self.in_pagetitle:
            self.description_parts.append(data)

        # Detect section headers (only when inside h1 tags)
        if self.in_h1:
            if text == ".NET Syntax":
                self.current_section = "syntax"
                self.in_syntax_section = True
                self.in_parameters_section = False
                self.in_return_section = False
                self.in_example_section = False
                self.in_remarks_section = False
            elif text == "Example" or text == "Examples":
                self.current_section = "example"
                self.in_syntax_section = False
                self.in_parameters_section = False
                self.in_return_section = False
                self.in_example_section = True
                self.in_remarks_section = False
            elif text == "Remarks":
                self.current_section = "remarks"
                self.in_syntax_section = False
                self.in_parameters_section = False
                self.in_return_section = False
                self.in_example_section = False
                self.in_remarks_section = True
                self.in_see_also_section = False
            elif text == "See Also":
                # Collect the cross-reference links in this section
                self.current_section = "see_also"
                self.in_syntax_section = False
                self.in_parameters_section = False
                self.in_return_section = False
                self.in_example_section = False
                self.in_remarks_section = False
                self.in_see_also_section = True
            elif text == "Availability":
                # End current section - turn off all section flags
                self.in_syntax_section = False
                self.in_parameters_section = False
                self.in_return_section = False
                self.in_example_section = False
                self.in_remarks_section = False
                self.in_see_also_section = False
                self.current_section = None

        # Detect "Parameters", "Return Value", and "Property Value" headers (h4 tags)
        if self.in_h4:
            if text == "Parameters":
                self.in_parameters_section = True
                self.in_return_section = False
            elif text == "Return Value" or text == "Property Value":
                self.in_parameters_section = False
                self.in_return_section = True
                self.return_depth = 0

        # Collect signature from C# syntax pre tag
        if self.in_syntax_table and self.syntax_depth > 0 and data:
            self.signature_parts.append(data)

        # Collect parameter name (from dt tag, remove <i> wrapper)
        if self.in_param_dt and data:
            self.current_param_name = data.strip()

        # Collect parameter description (from dd tag)
        if self.in_param_dd and data:
            self.current_param_desc_parts.append(data)

        # Collect link text in example section
        if self.in_link and data:
            self.current_link_text += data

        # Collect link text in See Also section
        if self.in_see_also_link and data:
            self.current_seealso_text += data

        # Collect return value content
        if self.in_return_section and data and not self.in_h4:
            self.return_parts.append(data)

        # Collect remarks content with proper spacing
        if self.in_remarks_section and data and not self.in_h1:
            self.remarks_parts.append(data)

    def get_description(self) -> str:
        """Get the cleaned description text (with link conversion)."""
        description_html = "".join(self.description_parts).strip()
        description_html = convert_links_to_see_refs(description_html)
        return description_html

    def get_signature(self) -> str:
        """
        Get the cleaned signature from C# syntax without the return type.

        Converts: "System.bool AccessSelections(System.object TopDoc, System.object Component)"
        To: "AccessSelections(System.object TopDoc, System.object Component)"
        """
        _, signature = self._split_signature()
        return signature

    def get_return_type(self) -> str:
        """
        Get the return type (leading type token) from the C# syntax signature.

        Converts: "System.bool AccessSelections(System.object TopDoc, ...)"
        To: "System.bool"

        Returns an empty string when the signature has no separable return type.
        """
        return_type, _ = self._split_signature()
        return return_type

    def _split_signature(self) -> tuple[str, str]:
        """
        Split the raw C# syntax into (return_type, name_with_params).

        Returns ("", full_signature) when a return type cannot be separated.
        """
        signature = "".join(self.signature_parts).strip()
        # Clean up extra whitespace
        signature = re.sub(r"\s+", " ", signature)

        # Pattern: "ReturnType MethodName(...)" -> ("ReturnType", "MethodName(...)")
        # Match everything up to and including the first space before the method name
        match = re.match(r"^([\w\.\[\]<>,\s]+?)\s+(.+)$", signature)
        if match:
            return match.group(1).strip(), match.group(2).strip()

        return "", signature

    def get_return_value(self) -> str:
        """Get the cleaned return value description."""
        return_html = "".join(self.return_parts).strip()
        return_html = convert_links_to_see_refs(return_html)
        return return_html

    def get_remarks(self) -> str:
        """Get the remarks content (may include HTML)."""
        remarks_html = "".join(self.remarks_parts).strip()
        remarks_html = convert_links_to_see_refs(remarks_html)
        return remarks_html

    def _parse_example_link(self, link_text: str, href: str) -> dict | None:
        """
        Parse example link text to extract name and language.

        Expected format: "Create Advanced Hole Feature (VBA)"
        or "Create Advanced Hole Feature Example"
        """
        # Match pattern: "Name (Language)" or just "Name"
        match = re.match(r"(.+?)\s*\(([^)]+)\)\s*$", link_text)

        if match:
            name = match.group(1).strip()
            language = match.group(2).strip()
        else:
            # No language in parentheses, try to infer from filename
            name = link_text.strip()
            language = self._infer_language_from_filename(href)

        # Prepend URL prefix
        full_url = f"{self.url_prefix}{href}"

        return {"Name": name, "Language": language, "Url": full_url}

    def _infer_language_from_filename(self, filename: str) -> str:
        """Infer language from filename patterns."""
        from shared.extraction_utils import infer_language_from_filename
        return infer_language_from_filename(filename)


def extract_member_details_from_file(html_file: Path) -> dict[str, Any] | None:
    """Extract member details from a single HTML file."""
    # Get URL prefix from parent directory
    parent_dir = html_file.parent.name
    url_prefix = f"/{parent_dir}/"

    parser = MemberDetailsExtractor(url_prefix=url_prefix)

    try:
        with open(html_file, encoding="utf-8") as f:
            content = f.read()
            parser.feed(content)
    except Exception as e:
        print(f"Error parsing {html_file}: {e}")
        return None

    if not parser.member_name:
        print(f"Warning: Could not extract member name from {html_file}")
        return None

    # Extract namespace, assembly, and type name from file path
    assembly, namespace, type_name = extract_namespace_from_filename(html_file)

    # Verify member name from filename matches
    filename_member = extract_member_name_from_filename(html_file)

    return {
        "Assembly": assembly,
        "Type": f"{namespace}.{type_name}" if namespace and type_name else None,
        "Name": parser.member_name,
        "Signature": parser.get_signature(),
        "ReturnType": parser.get_return_type(),
        "Description": parser.get_description(),
        "Parameters": parser.parameters,
        "Returns": parser.get_return_value(),
        "Examples": parser.examples,
        "Remarks": parser.get_remarks(),
        "SeeAlso": parser.see_also,
        "SourceFile": str(html_file),
    }


def create_xml_output(members: list[dict[str, Any]]) -> str:
    """Create XML output from extracted member information."""
    root = ET.Element("Members")

    for member_info in members:
        member_elem = ET.SubElement(root, "Member")

        # Add assembly
        if member_info.get("Assembly"):
            assembly_elem = ET.SubElement(member_elem, "Assembly")
            assembly_elem.text = member_info["Assembly"]

        # Add type
        if member_info.get("Type"):
            type_elem = ET.SubElement(member_elem, "Type")
            type_elem.text = member_info["Type"]

        # Add member name
        name_elem = ET.SubElement(member_elem, "Name")
        name_elem.text = member_info["Name"]

        # Add signature
        if member_info.get("Signature"):
            sig_elem = ET.SubElement(member_elem, "Signature")
            sig_elem.text = member_info["Signature"]

        # Add return type
        if member_info.get("ReturnType"):
            return_type_elem = ET.SubElement(member_elem, "ReturnType")
            return_type_elem.text = member_info["ReturnType"]

        # Add description (wrap in CDATA to preserve any XMLDoc markup)
        if member_info.get("Description"):
            desc_elem = ET.SubElement(member_elem, "Description")
            desc_elem.text = member_info["Description"]
            desc_elem.set("__cdata__", "true")

        # Add parameters
        if member_info.get("Parameters"):
            params_elem = ET.SubElement(member_elem, "Parameters")
            for param in member_info["Parameters"]:
                param_elem = ET.SubElement(params_elem, "Parameter")

                param_name = ET.SubElement(param_elem, "Name")
                param_name.text = param["Name"]

                if param.get("Description"):
                    param_desc = ET.SubElement(param_elem, "Description")
                    param_desc.text = param["Description"]
                    param_desc.set("__cdata__", "true")

        # Add return value (wrap in CDATA to preserve any XMLDoc markup)
        if member_info.get("Returns"):
            returns_elem = ET.SubElement(member_elem, "Returns")
            returns_elem.text = member_info["Returns"]
            returns_elem.set("__cdata__", "true")

        # Add examples
        if member_info.get("Examples"):
            examples_elem = ET.SubElement(member_elem, "Examples")
            for example in member_info["Examples"]:
                example_elem = ET.SubElement(examples_elem, "Example")

                ex_name = ET.SubElement(example_elem, "Name")
                ex_name.text = example["Name"]

                ex_lang = ET.SubElement(example_elem, "Language")
                ex_lang.text = example["Language"]

                ex_url = ET.SubElement(example_elem, "Url")
                ex_url.text = example["Url"]

        # Add remarks (wrap in CDATA to preserve any XMLDoc markup)
        if member_info.get("Remarks"):
            remarks_elem = ET.SubElement(member_elem, "Remarks")
            remarks_elem.text = member_info["Remarks"]
            remarks_elem.set("__cdata__", "true")

        # Add See Also cross-references
        add_see_also_element(member_elem, member_info.get("SeeAlso", []))

    # Pretty print the XML with CDATA sections
    return prettify_xml(root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract member details from crawled HTML files")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("30_crawl_type_members/output/html"),
        help="Directory containing crawled member HTML files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("50_extract_type_member_details/metadata"),
        help="Directory to save output files",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Find all member HTML files
    all_html_files = list(args.input_dir.rglob("*.html"))
    member_files = [f for f in all_html_files if is_member_file(f)]

    if not member_files:
        print(f"No member files found in {args.input_dir}")
        return 1

    print(f"Found {len(member_files)} member files to process (out of {len(all_html_files)} total HTML files)")

    # Extract member details from each file
    members = []
    errors = []

    for html_file in member_files:
        if args.verbose:
            print(f"Processing {html_file.name}...")

        member_info = extract_member_details_from_file(html_file)
        if member_info:
            members.append(member_info)
        else:
            errors.append(str(html_file))

    # Sort members by type and name for consistent output
    members.sort(key=lambda x: (str(x.get("Type", "")), str(x.get("Name", ""))))

    # Generate XML output
    xml_output = create_xml_output(members)

    # Save XML file
    xml_file = args.output_dir / "api_member_details.xml"
    with open(xml_file, "w", encoding="utf-8") as f:
        f.write(xml_output)

    print("\nExtraction complete!")
    print(f"  Members extracted: {len(members)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Output saved to: {xml_file}")

    # Calculate statistics
    members_with_params = sum(1 for m in members if m.get("Parameters"))
    members_with_returns = sum(1 for m in members if m.get("Returns"))
    members_with_examples = sum(1 for m in members if m.get("Examples"))
    members_with_remarks = sum(1 for m in members if m.get("Remarks"))

    # Save summary metadata
    summary = {
        "total_files_processed": len(member_files),
        "members_extracted": len(members),
        "members_with_parameters": members_with_params,
        "members_with_return_values": members_with_returns,
        "members_with_examples": members_with_examples,
        "members_with_remarks": members_with_remarks,
        "errors": len(errors),
        "output_file": str(xml_file),
        "error_files": errors,
    }

    summary_file = args.output_dir / "extraction_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"  Members with parameters: {members_with_params}")
    print(f"  Members with return values: {members_with_returns}")
    print(f"  Members with examples: {members_with_examples}")
    print(f"  Members with remarks: {members_with_remarks}")
    print(f"  Summary saved to: {summary_file}")

    if errors:
        print(f"\nWarning: {len(errors)} files had errors")
        if args.verbose:
            for error_file in errors:
                print(f"  - {error_file}")

    return 0


if __name__ == "__main__":
    exit(main())
