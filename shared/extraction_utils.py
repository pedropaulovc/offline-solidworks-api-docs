#!/usr/bin/env python3
"""
Shared utilities for extracting documentation from HTML files.

This module provides common functions for parsing SolidWorks API HTML
documentation and generating XML output.
"""

import re
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def extract_namespace_from_filename(html_file: Path) -> tuple[str | None, str | None, str | None]:
    """
    Extract assembly, namespace, and type name from the file path.

    Returns:
        (assembly, namespace, type_name)

    Example filename for type:
        SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData_...
        -> assembly: SolidWorks.Interop.sldworks (before ~)
        -> full_type: SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData (after ~ before _)
        -> namespace: SolidWorks.Interop.sldworks
        -> type_name: IAdvancedHoleFeatureData

    Example filename for member:
        SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData~AccessSelections.html
        -> assembly: SolidWorks.Interop.sldworks
        -> namespace: SolidWorks.Interop.sldworks
        -> type_name: IAdvancedHoleFeatureData
    """
    filename = html_file.name

    # Split on ~ to get assembly and full type path
    if "~" in filename:
        parts = filename.split("~")

        # Assembly is the part before first ~
        assembly = parts[0]

        # Extract full type name (after first ~ but before second ~ or hash)
        if len(parts) >= 2:
            # For member files: parts[1] is the full type path
            # For type files: parts[1] contains type name followed by hash
            type_part = parts[1]

            # Remove hash and extension if present
            # Pattern: TypeName_hash_hash.html or TypeName.html
            if "_" in type_part:
                type_part = type_part.split("_")[0]
            elif ".html" in type_part:
                type_part = type_part.replace(".html", "")

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


def extract_member_name_from_filename(html_file: Path) -> str | None:
    """
    Extract member name from a member HTML file.

    Example:
        SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData~AccessSelections.html
        -> AccessSelections
    """
    filename = html_file.name

    # Member files have format: Assembly~Namespace.Type~Member.html
    if "~" in filename:
        parts = filename.split("~")
        if len(parts) >= 3:
            # Member name is after the second ~
            member_part = parts[2].replace(".html", "")
            return member_part

    return None


def wrap_cdata_sections(xml_str: str) -> str:
    """
    Wrap content of elements marked with __cdata__="true" in CDATA sections.

    This is a post-processing step since ElementTree doesn't natively support CDATA.
    Handles Description, Remarks, and Returns elements.
    """
    import html as html_module

    # Pattern to find elements marked with __cdata__="true"
    # Matches: <Description __cdata__="true">content</Description>
    #      or: <Remarks __cdata__="true">content</Remarks>
    #      or: <Returns __cdata__="true">content</Returns>
    pattern = r'<(Description|Remarks|Returns) __cdata__="true">(.*?)</\1>'

    def replace_with_cdata(match: re.Match[str]) -> str:
        tag_name = match.group(1)
        content = match.group(2)
        # Unescape XML entities since CDATA doesn't need escaping
        content = html_module.unescape(content)
        return f"<{tag_name}><![CDATA[{content}]]></{tag_name}>"

    return re.sub(pattern, replace_with_cdata, xml_str, flags=re.DOTALL)


def prettify_xml(root: ET.Element) -> str:
    """
    Convert an ElementTree to a pretty-printed XML string.

    Automatically wraps elements marked with __cdata__="true" in CDATA sections.
    """
    xml_str = ET.tostring(root, encoding="unicode")

    # Post-process to add CDATA sections for marked elements
    xml_str = wrap_cdata_sections(xml_str)

    # Pretty print
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="    ")


def is_type_file(html_file: Path) -> bool:
    """
    Check if the HTML file is a type file (not members or namespace).

    Type files don't have _members_ or _namespace_ in their name and must have
    only one ~ separator (Assembly~Namespace.Type pattern).
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

    # Must have the typical type file pattern: Assembly~Namespace.Type_hash.html
    # Type files have exactly one ~ (members have two: Assembly~Namespace.Type~Member.html)
    if "~" not in filename or ".html" not in filename:
        return False

    # Count ~ characters - type files should have exactly 1
    tilde_count = filename.count("~")
    return tilde_count == 1


def is_member_file(html_file: Path) -> bool:
    """
    Check if the HTML file is a member file (property or method).

    Member files have format: Assembly~Namespace.Type~Member.html
    """
    filename = html_file.name.lower()

    # Exclude special files
    if filename.startswith("functionalcategories") or filename.startswith("releasenotes"):
        return False

    # Exclude help_list files
    if filename.startswith("help_list"):
        return False

    # Exclude _members_ files (these are member list pages, not individual members)
    if "_members_" in filename:
        return False

    # Must have the typical member file pattern: Assembly~Namespace.Type~Member.html
    # Member files have exactly two ~ characters
    if ".html" not in filename:
        return False

    tilde_count = filename.count("~")
    return tilde_count == 2


def infer_language_from_filename(filename: str) -> str:
    """Infer programming language from filename patterns."""
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
