#!/usr/bin/env python3
"""
Shared utilities for converting HTML links to XMLDoc format.

This module provides functions to convert HTML anchor tags to XMLDoc <see cref>
and <see href> tags for IntelliSense documentation.
"""

import re


def convert_links_to_see_refs(html: str) -> str:
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
        cref = parse_href_to_cref(href)

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
            full_url = convert_to_full_url(href)
            return f'{prefix}<see href="{full_url}">{clean_text}</see>{suffix}'

    result = re.sub(pattern, replace_link, html)

    # Clean up HTML entities
    result = result.replace("&nbsp;", " ")
    result = result.replace("&amp;", "&")
    result = result.replace("&lt;", "<")
    result = result.replace("&gt;", ">")

    # Clean up remaining HTML tags (like <p>, <div>, etc.)
    # Keep <see cref="..."> and </see> tags
    result = re.sub(r"<(?!/?see[\s>])[^>]+>", "", result)

    return result.strip()


def parse_href_to_cref(href: str) -> str | None:
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


def convert_to_full_url(href: str) -> str:
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
