#!/usr/bin/env python3
"""
Extract type information from crawled HTML files.

This script scans type HTML files (excluding *_members_* and *_namespace_*)
from the crawl phase and extracts type information (description, examples,
remarks) into an XML format.
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


class TypeInfoExtractor(HTMLParser):
    """HTML parser to extract type information from SolidWorks API documentation."""

    def __init__(self, url_prefix: str = "") -> None:
        super().__init__()
        self.type_name: str | None = None
        self.description: str = ""
        self.examples: list[dict[str, str]] = []
        self.remarks: str = ""

        # State tracking
        self.in_pagetitle: bool = False
        self.in_description: bool = False
        self.in_h1: bool = False
        self.current_section: str | None = None
        self.in_example_section: bool = False
        self.in_remarks_section: bool = False
        self.in_link: bool = False
        self.current_link_href: str | None = None
        self.current_link_text: str = ""
        self.url_prefix: str = url_prefix

        # For collecting description text after pagetitle
        self.seen_pagetitle: bool = False
        self.seen_first_h1: bool = False
        self.description_parts: list[str] = []
        self.description_depth: int = 0

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
                self.description_depth = 0
            return

        # Collect all HTML tags in description section (like we do for remarks)
        if self.in_description and not self.in_pagetitle:
            self.description_depth += 1
            # Reconstruct HTML tags for description
            attrs_str = ""
            if attrs:
                attrs_str = " " + " ".join([f'{k}="{v}"' for k, v in attrs])
            self.description_parts.append(f"<{tag}{attrs_str}>")

        # Detect Example section
        if tag == "h1" and not self.current_section:
            # We'll check the text content in handle_data
            pass

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

        # Collect all HTML tags in remarks section
        if self.in_remarks_section:
            self.remarks_depth += 1
            # Reconstruct HTML tags for remarks
            attrs_str = ""
            if attrs:
                attrs_str = " " + " ".join([f'{k}="{v}"' for k, v in attrs])
            self.remarks_parts.append(f"<{tag}{attrs_str}>")

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self.in_pagetitle:
            self.in_pagetitle = False
            self.seen_pagetitle = True
            self.in_description = True
            self.description_depth = 0
            return

        # Track closing tags in description section
        if self.in_description and not self.in_pagetitle:
            self.description_depth -= 1
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

        # Close h1 tag - might signal end of section header
        if tag == "h1":
            self.in_h1 = False

        # Track closing tags in remarks section
        if self.in_remarks_section:
            self.remarks_depth -= 1
            self.remarks_parts.append(f"</{tag}>")

            # If we're back to depth 0 and see a closing div, end remarks
            if self.remarks_depth == 0 and tag == "div":
                self.in_remarks_section = False

    def handle_data(self, data: str) -> None:
        text = data.strip()

        # Capture type name from pagetitle
        if self.in_pagetitle and text:
            # Remove " Interface" or " Class" suffix if present
            self.type_name = text.replace(" Interface", "").replace(" Class", "").strip()

        # Capture description (text between pagetitle and first h1)
        # Use original data (not stripped) to preserve spacing
        if self.in_description and data and not self.in_pagetitle:
            self.description_parts.append(data)

        # Detect section headers (only when inside h1 tags)
        if self.in_h1:
            if text == "Example" or text == "Examples":
                self.current_section = "example"
                self.in_example_section = True
                self.in_remarks_section = False
            elif text == "Remarks":
                self.current_section = "remarks"
                self.in_example_section = False
                self.in_remarks_section = True
            elif text in ["See Also", "Accessors", "Access Diagram", ".NET Syntax", "Members"]:
                # End current section - turn off all section flags
                self.in_example_section = False
                self.in_remarks_section = False
                self.current_section = None

        # Collect link text in example section
        if self.in_link and data:
            self.current_link_text += data

        # Collect remarks content with proper spacing
        # Use original data (not stripped) to preserve spacing
        # Don't collect h1 heading text
        if self.in_remarks_section and data and not self.in_h1:
            self.remarks_parts.append(data)

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
        filename_lower = filename.lower()

        if "vbnet" in filename_lower or "_net.htm" in filename_lower:
            return "VB.NET"
        elif "_vb.htm" in filename_lower or "vba" in filename_lower:
            return "VBA"
        elif "csharp" in filename_lower or "_cs.htm" in filename_lower:
            return "C#"
        elif "cpp" in filename_lower:
            return "C++"
        else:
            return "Unknown"

    def get_description(self) -> str:
        """Get the cleaned description text (with link conversion)."""
        description_html = "".join(self.description_parts).strip()

        # Clean up the HTML - convert <a> tags to <see cref="...">
        description_html = convert_links_to_see_refs(description_html)

        return description_html

    def get_remarks(self) -> str:
        """Get the remarks content (may include HTML)."""
        remarks_html = "".join(self.remarks_parts).strip()

        # Clean up the HTML - convert <a> tags to <see cref="...">
        remarks_html = convert_links_to_see_refs(remarks_html)

        return remarks_html


def extract_namespace_from_filename(html_file: Path) -> tuple[str | None, str | None, str | None]:
    """
    Extract namespace and assembly from the file path.

    Returns:
        (assembly, namespace, type_name)

    Example filename:
        SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData_...
        -> assembly: SolidWorks.Interop.sldworks (before ~)
        -> full_type: SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData (after ~ before _)
        -> namespace: SolidWorks.Interop.sldworks
        -> type_name: IAdvancedHoleFeatureData
    """
    filename = html_file.name

    # Split on ~ to get assembly and full type path
    if "~" in filename:
        parts = filename.split("~")

        # Assembly is the part before ~
        assembly = parts[0]

        # Extract full type name (after ~ but before the hash)
        if len(parts) > 1:
            # Remove hash and extension: ...IAdvancedHoleFeatureData_84c83747_84c83747.htmll.html
            # Pattern: TypeName_hash_hash.htmll.html
            type_part = parts[1].split("_")[0]

            # Namespace is the full type name minus the last segment (the type name itself)
            if "." in type_part:
                namespace_parts = type_part.split(".")
                type_name = namespace_parts[-1]
                namespace = ".".join(namespace_parts[:-1])
            else:
                # If there's no dot, the namespace is the same as assembly
                namespace = assembly
                type_name = type_part

            return assembly, namespace, type_name

    return None, None, None


def extract_type_info_from_file(html_file: Path) -> dict[str, Any] | None:
    """Extract type information from a single HTML file."""
    # Get URL prefix from parent directory
    parent_dir = html_file.parent.name
    url_prefix = f"/{parent_dir}/"

    parser = TypeInfoExtractor(url_prefix=url_prefix)

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
    assembly, namespace, type_name = extract_namespace_from_filename(html_file)

    return {
        "Name": parser.type_name,
        "Assembly": assembly,
        "Namespace": namespace,
        "Description": parser.get_description(),
        "Examples": parser.examples,
        "Remarks": parser.get_remarks(),
        "SourceFile": str(html_file),
    }


def _wrap_cdata_sections(xml_str: str) -> str:
    """
    Wrap content of elements marked with __cdata__="true" in CDATA sections.

    This is a post-processing step since ElementTree doesn't natively support CDATA.
    Handles both Description and Remarks elements.
    """
    import html as html_module

    # Pattern to find elements marked with __cdata__="true"
    # Matches: <Description __cdata__="true">content</Description>
    #      or: <Remarks __cdata__="true">content</Remarks>
    pattern = r'<(Description|Remarks) __cdata__="true">(.*?)</\1>'

    def replace_with_cdata(match: re.Match[str]) -> str:
        tag_name = match.group(1)
        content = match.group(2)
        # Unescape XML entities since CDATA doesn't need escaping
        content = html_module.unescape(content)
        return f"<{tag_name}><![CDATA[{content}]]></{tag_name}>"

    return re.sub(pattern, replace_with_cdata, xml_str, flags=re.DOTALL)


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

        # Add description (always wrap in CDATA to preserve any XMLDoc markup)
        if type_info.get("Description"):
            desc_elem = ET.SubElement(type_elem, "Description")
            desc_elem.text = type_info["Description"]
            desc_elem.set("__cdata__", "true")

        # Add examples
        if type_info.get("Examples"):
            examples_elem = ET.SubElement(type_elem, "Examples")
            for example in type_info["Examples"]:
                example_elem = ET.SubElement(examples_elem, "Example")

                ex_name = ET.SubElement(example_elem, "Name")
                ex_name.text = example["Name"]

                ex_lang = ET.SubElement(example_elem, "Language")
                ex_lang.text = example["Language"]

                ex_url = ET.SubElement(example_elem, "Url")
                ex_url.text = example["Url"]

        # Add remarks (always wrap in CDATA to preserve any XMLDoc markup)
        if type_info.get("Remarks"):
            remarks_elem = ET.SubElement(type_elem, "Remarks")
            remarks_elem.text = type_info["Remarks"]
            remarks_elem.set("__cdata__", "true")

    # Pretty print the XML
    xml_str = ET.tostring(root, encoding="unicode")

    # Post-process to add CDATA sections for Remarks elements
    # Replace marked elements with CDATA wrapped content
    xml_str = _wrap_cdata_sections(xml_str)

    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="    ")


def is_type_file(html_file: Path) -> bool:
    """
    Check if the HTML file is a type file (not members or namespace).

    Type files don't have _members_ or _namespace_ in their name.
    """
    filename = html_file.name.lower()

    # Exclude members and namespace files
    if "_members_" in filename or "_namespace_" in filename:
        return False

    # Exclude special files
    if filename.startswith("functionalcategories") or filename.startswith("releasenotes"):
        return False

    # Exclude help_list files
    if filename.startswith("help_list"):
        return False

    # Must have the typical type file pattern: Assembly~Namespace.Type_hash_hash.html
    if "~" in filename and ".html" in filename:
        return True

    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract type information from crawled HTML files")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("01-crawl-toc-pages/output/html"),
        help="Directory containing crawled HTML files",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("03-extract-type-info/metadata"), help="Directory to save output files"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Find all type HTML files (excluding members and namespace files)
    all_html_files = list(args.input_dir.rglob("*.html"))
    type_files = [f for f in all_html_files if is_type_file(f)]

    if not type_files:
        print(f"No type files found in {args.input_dir}")
        return 1

    print(f"Found {len(type_files)} type files to process (out of {len(all_html_files)} total HTML files)")

    # Extract type info from each file
    types = []
    errors = []

    for html_file in type_files:
        if args.verbose:
            print(f"Processing {html_file.name}...")

        type_info = extract_type_info_from_file(html_file)
        if type_info:
            types.append(type_info)
        else:
            errors.append(str(html_file))

    # Sort types by name for consistent output
    types.sort(key=lambda x: str(x.get("Name", "")))

    # Generate XML output
    xml_output = create_xml_output(types)

    # Save XML file
    xml_file = args.output_dir / "api_types.xml"
    with open(xml_file, "w", encoding="utf-8") as f:
        f.write(xml_output)

    print("\nExtraction complete!")
    print(f"  Types extracted: {len(types)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Output saved to: {xml_file}")

    # Save summary metadata
    summary = {
        "total_files_processed": len(type_files),
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
