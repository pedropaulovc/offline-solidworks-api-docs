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
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from html.parser import HTMLParser


class TypeInfoExtractor(HTMLParser):
    """HTML parser to extract type information from SolidWorks API documentation."""

    def __init__(self, url_prefix=""):
        super().__init__()
        self.type_name = None
        self.description = ""
        self.examples = []
        self.remarks = ""

        # State tracking
        self.in_pagetitle = False
        self.in_description = False
        self.current_section = None
        self.in_example_section = False
        self.in_remarks_section = False
        self.in_link = False
        self.current_link_href = None
        self.current_link_text = ""
        self.url_prefix = url_prefix

        # For collecting description text after pagetitle
        self.seen_pagetitle = False
        self.seen_first_h1 = False
        self.description_parts = []
        self.description_depth = 0

        # For collecting remarks content
        self.remarks_parts = []
        self.remarks_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Detect page title
        if tag == "span" and attrs_dict.get("id") == "pagetitle":
            self.in_pagetitle = True
            return

        # Track when we've seen the first h1 (stops description collection)
        if tag == "h1" and self.seen_pagetitle and not self.seen_first_h1:
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
            is_example_link = ("Example" in href or "_Example_" in href) and href.endswith(".htm")
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

    def handle_endtag(self, tag):
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
                example_info = self._parse_example_link(
                    self.current_link_text,
                    self.current_link_href
                )
                if example_info:
                    self.examples.append(example_info)

            self.current_link_href = None
            self.current_link_text = ""

        # Close h1 tag - might signal end of section header
        if tag == "h1":
            pass

        # Track closing tags in remarks section
        if self.in_remarks_section:
            self.remarks_depth -= 1
            self.remarks_parts.append(f"</{tag}>")

            # If we're back to depth 0 and see a closing div, end remarks
            if self.remarks_depth == 0 and tag == "div":
                self.in_remarks_section = False

    def handle_data(self, data):
        text = data.strip()

        # Capture type name from pagetitle
        if self.in_pagetitle and text:
            # Remove " Interface" or " Class" suffix if present
            self.type_name = text.replace(" Interface", "").replace(" Class", "").strip()

        # Capture description (text between pagetitle and first h1)
        # Use original data (not stripped) to preserve spacing
        if self.in_description and data and not self.in_pagetitle:
            self.description_parts.append(data)

        # Detect section headers
        if text == "Example" or text == "Examples":
            self.current_section = "example"
            self.in_example_section = True
            self.in_remarks_section = False
        elif text == "Remarks":
            self.current_section = "remarks"
            self.in_example_section = False
            self.in_remarks_section = True
        elif text in ["See Also", "Accessors", "Access Diagram", ".NET Syntax"]:
            # End current section - turn off all section flags
            self.in_example_section = False
            self.in_remarks_section = False
            self.current_section = None

        # Collect link text in example section
        if self.in_link and data:
            self.current_link_text += data

        # Collect remarks content with proper spacing
        # Use original data (not stripped) to preserve spacing
        if self.in_remarks_section and data:
            self.remarks_parts.append(data)

    def _parse_example_link(self, link_text: str, href: str) -> Optional[Dict]:
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

        return {
            "Name": name,
            "Language": language,
            "Url": full_url
        }

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
        description_html = self._convert_links_to_see_refs(description_html)

        return description_html

    def get_remarks(self) -> str:
        """Get the remarks content (may include HTML)."""
        remarks_html = "".join(self.remarks_parts).strip()

        # Clean up the HTML - convert <a> tags to <see cref="...">
        remarks_html = self._convert_links_to_see_refs(remarks_html)

        return remarks_html

    def _convert_links_to_see_refs(self, html: str) -> str:
        """
        Convert HTML anchor tags to XML <see cref="..."> or <see href="..."> tags.

        Type references:
        <a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~AdvancedHole.html">IFeatureManager::AdvancedHole</a>
        becomes:
        <see cref="SolidWorks.Interop.sldworks.IFeatureManager.AdvancedHole">IFeatureManager::AdvancedHole</see>

        Non-type references (guide pages):
        <a href="../sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm">SOLIDWORKS Design</a>
        becomes:
        <see href="https://help.solidworks.com/2026/english/api/sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm">SOLIDWORKS Design</see>
        """
        # Pattern to match anchor tags with SolidWorks API links
        # Matches: <a href="Assembly~Namespace.Type~Member.html">LinkText</a>
        # Or: <a href="Assembly~Namespace.Type.html">LinkText</a>
        pattern = r'<a\s+[^>]*?href="([^"]+?\.html?)"[^>]*?>([^<]+?)</a>'

        def replace_link(match):
            href = match.group(1)
            link_text = match.group(2)  # Don't strip - preserve spacing

            # Parse the href to extract the full type/member path
            # Format: Assembly~Namespace.Type~Member.html or Namespace.Type.html
            cref = self._parse_href_to_cref(href)

            # Prepare spacing preservation
            clean_text = link_text.strip()
            leading_space = len(link_text) - len(link_text.lstrip())
            trailing_space = len(link_text) - len(link_text.rstrip())
            prefix = link_text[:leading_space] if leading_space else ""
            suffix = link_text[-trailing_space:] if trailing_space else ""

            if cref:
                # Type reference - use <see cref="...">
                return f'{prefix}<see cref="{cref}">{clean_text}</see>{suffix}'
            else:
                # Non-type reference (e.g., guide page) - use <see href="...">
                full_url = self._convert_to_full_url(href)
                return f'{prefix}<see href="{full_url}">{clean_text}</see>{suffix}'

        result = re.sub(pattern, replace_link, html)

        # Clean up HTML entities
        result = result.replace("&nbsp;", " ")
        result = result.replace("&amp;", "&")
        result = result.replace("&lt;", "<")
        result = result.replace("&gt;", ">")

        # Clean up remaining HTML tags (like <p>, <div>, etc.)
        # Keep <see cref="..."> and </see> tags
        result = re.sub(r'<(?!/?see[\s>])[^>]+>', '', result)

        return result.strip()

    def _parse_href_to_cref(self, href: str) -> Optional[str]:
        """
        Parse an href to extract the cref value for type references only.

        Examples:
        - "SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~AdvancedHole.html"
          -> "SolidWorks.Interop.sldworks.IFeatureManager.AdvancedHole"
        - "../sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISectionViewData~SectionedZones.html"
          -> "SolidWorks.Interop.sldworks.ISectionViewData.SectionedZones"
        - "https://example.com/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html"
          -> "SolidWorks.Interop.sldworks.IFeature"

        Non-type references (guide pages) return None:
        - "../sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm" -> None
        """
        # Extract filename from path (handle URLs and relative paths)
        # If it has slashes, extract the filename part after the last slash
        if "/" in href or "\\" in href:
            filename = href.split("/")[-1].split("\\")[-1]
        else:
            filename = href

        # Remove .html extension
        filename = filename.replace(".html", "").replace(".htm", "")

        # Check if this filename matches type reference pattern (has ~ separator)
        # Type references have format: Assembly~Namespace.Type~Member or Namespace.Type
        if "~" not in filename and "." not in filename:
            # No namespace/type pattern
            return None

        # Split by ~ to get parts
        parts = filename.split("~")

        if len(parts) >= 2:
            # Format: Assembly~Namespace.Type~Member or Assembly~Namespace.Type
            # We want the part after the first ~
            # Join parts after the first one with dots
            cref_parts = parts[1:]
            cref = ".".join(cref_parts)
            return cref
        elif len(parts) == 1 and "." in parts[0]:
            # Simple case: just Namespace.Type (no path separators allowed)
            # Make sure it's not a file path like "Overview.SOLIDWORKS"
            if "/" not in href and "\\" not in href and ".." not in href:
                return parts[0]
            else:
                return None
        else:
            return None

    def _convert_to_full_url(self, href: str) -> str:
        """
        Convert a relative URL to a full URL.

        Examples:
        - "../sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm"
          -> "https://help.solidworks.com/2026/english/api/sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm"
        - "https://example.com/page.htm" (already full)
          -> "https://example.com/page.htm"
        """
        # If already a full URL, return as-is
        if href.startswith("http://") or href.startswith("https://"):
            return href

        # Base URL for SolidWorks API documentation
        base_url = "https://help.solidworks.com/2026/english/api/sldworksapi/"

        # Handle relative paths
        if href.startswith("../"):
            # Remove leading ../ and construct from api/ level
            clean_href = href.replace("../", "", 1)
            return f"https://help.solidworks.com/2026/english/api/{clean_href}"
        else:
            # Relative to current directory (sldworksapi)
            return f"{base_url}{href}"


def extract_namespace_from_filename(html_file: Path) -> tuple:
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
    if '~' in filename:
        parts = filename.split('~')

        # Assembly is the part before ~
        assembly = parts[0]

        # Extract full type name (after ~ but before the hash)
        if len(parts) > 1:
            # Remove hash and extension: ...IAdvancedHoleFeatureData_84c83747_84c83747.htmll.html
            # Pattern: TypeName_hash_hash.htmll.html
            type_part = parts[1].split('_')[0]

            # Namespace is the full type name minus the last segment (the type name itself)
            if '.' in type_part:
                namespace_parts = type_part.split('.')
                type_name = namespace_parts[-1]
                namespace = '.'.join(namespace_parts[:-1])
            else:
                # If there's no dot, the namespace is the same as assembly
                namespace = assembly
                type_name = type_part

            return assembly, namespace, type_name

    return None, None, None


def extract_type_info_from_file(html_file: Path) -> Optional[Dict]:
    """Extract type information from a single HTML file."""
    # Get URL prefix from parent directory
    parent_dir = html_file.parent.name
    url_prefix = f"/{parent_dir}/"

    parser = TypeInfoExtractor(url_prefix=url_prefix)

    try:
        with open(html_file, 'r', encoding='utf-8') as f:
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
        "SourceFile": str(html_file)
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

    def replace_with_cdata(match):
        tag_name = match.group(1)
        content = match.group(2)
        # Unescape XML entities since CDATA doesn't need escaping
        content = html_module.unescape(content)
        return f'<{tag_name}><![CDATA[{content}]]></{tag_name}>'

    return re.sub(pattern, replace_with_cdata, xml_str, flags=re.DOTALL)


def create_xml_output(types: List[Dict]) -> str:
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
    xml_str = ET.tostring(root, encoding='unicode')

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


def main():
    parser = argparse.ArgumentParser(
        description="Extract type information from crawled HTML files"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("01-crawl-toc-pages/output/html"),
        help="Directory containing crawled HTML files"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("03-extract-type-info/metadata"),
        help="Directory to save output files"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

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
    types.sort(key=lambda x: x["Name"])

    # Generate XML output
    xml_output = create_xml_output(types)

    # Save XML file
    xml_file = args.output_dir / "api_types.xml"
    with open(xml_file, 'w', encoding='utf-8') as f:
        f.write(xml_output)

    print(f"\nExtraction complete!")
    print(f"  Types extracted: {len(types)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Output saved to: {xml_file}")

    # Save summary metadata
    summary = {
        "total_files_processed": len(type_files),
        "types_extracted": len(types),
        "errors": len(errors),
        "output_file": str(xml_file),
        "error_files": errors
    }

    summary_file = args.output_dir / "extraction_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
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
