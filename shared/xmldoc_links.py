#!/usr/bin/env python3
"""
Shared utilities for converting HTML links to XMLDoc format.

This module provides functions to convert HTML anchor tags to XMLDoc <see cref>
and <see href> tags for IntelliSense documentation.
"""

import re
from html.parser import HTMLParser


# Block-level tags that introduce a paragraph break (blank line) in markdown.
_PARAGRAPH_TAGS = {"p", "div", "blockquote"}

# Distinct open/close sentinels for emphasis. Using placeholders (rather than
# emitting ``**``/``*`` directly) lets us relocate whitespace out of an emphasis
# span before committing to the markers, without confusing them with literal
# asterisks that appear in the source text (e.g. "*not*"). Resolved in
# :func:`html_to_markdown`.
_B_OPEN, _B_CLOSE = "\x01", "\x02"
_I_OPEN, _I_CLOSE = "\x03", "\x04"


def _is_bold_span(attrs: dict[str, str]) -> bool:
    """True if a ``<span>``'s inline style makes its text bold."""
    style = attrs.get("style", "").lower()
    return "font-weight" in style and "bold" in style


class _HtmlToMarkdown(HTMLParser):
    """Convert an HTML fragment to markdown, passing ``<see>`` tags through verbatim.

    The SolidWorks help text uses ``<p>``/``<ul>``/``<ol>``/``<li>``/``<h4>``/
    ``<strong>`` etc. to structure remarks, parameter descriptions and return
    values. Stripping those tags outright (the old behaviour) flattened lists and
    paragraphs into run-on text. This converter preserves the structure as
    markdown so both the XMLDoc and the LLM-markdown exports render it correctly.

    ``<a>`` tags are expected to have already been rewritten to ``<see cref>`` /
    ``<see href>`` by :func:`convert_links_to_see_refs`; those are re-emitted
    unchanged so downstream stages can resolve them.
    """

    def __init__(self) -> None:
        # convert_charrefs=True decodes entities (&nbsp;, &lt;, …) into the text
        # stream delivered to handle_data, matching the old manual unescaping.
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        # Stack of open ordered/unordered lists. Each frame tracks its running
        # item counter (for ``<ol>`` numbering), ``base_indent`` (the column its
        # markers sit at) and ``item_indent`` (the content column of the current
        # item, where continuation paragraphs and nested lists must align).
        self._lists: list[dict[str, object]] = []
        # Parallel stack for <span>: records whether each open span was bold, so
        # the matching </span> knows whether to close a ``**`` run.
        self._span_bold: list[bool] = []
        # Set right after a list marker is emitted so the first block child of an
        # <li> (a wrapping <p>/<h4>) hugs the marker instead of starting a blank
        # line, which would leave an empty bullet.
        self._suppress_para = False

    def _cur_indent(self) -> str:
        """Continuation indent for the innermost open list item (``""`` at top level)."""
        return str(self._lists[-1]["item_indent"]) if self._lists else ""

    def _emit_see(self, tag: str, attrs: list, self_closing: bool) -> None:
        attrs_str = "".join(f' {name}="{value}"' for name, value in attrs)
        if self_closing:
            self.parts.append(f"<{tag}{attrs_str} />")
        else:
            self.parts.append(f"<{tag}{attrs_str}>")

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "see":
            self._emit_see(tag, attrs, self_closing=False)
            return
        if tag == "br":
            self.parts.append("\n" + self._cur_indent())
            return
        if tag in _PARAGRAPH_TAGS:
            if not self._suppress_para:
                self.parts.append("\n\n" + self._cur_indent())
            self._suppress_para = False
            return
        if tag in ("ul", "ol"):
            # A nested list's markers align under the content column of the
            # enclosing item; a top-level list sits at column 0.
            base = self._cur_indent()
            self._lists.append({"type": tag, "count": 0, "base_indent": base, "item_indent": base})
            self.parts.append("\n")
            return
        if tag == "li":
            frame = self._lists[-1] if self._lists else None
            base = str(frame["base_indent"]) if frame else ""
            if frame and frame["type"] == "ol":
                frame["count"] = int(frame["count"]) + 1
                marker = f"{frame['count']}. "
            else:
                marker = "- "
            if frame:
                # Continuation lines / nested lists align under the item's text,
                # i.e. past the marker (4 cols for "10. ", 3 for "1. ", 2 for "- ").
                frame["item_indent"] = base + " " * len(marker)
            self.parts.append(f"\n{base}{marker}")
            self._suppress_para = True
            return
        if re.fullmatch(r"h[1-6]", tag):
            prefix = "" if self._suppress_para else "\n\n" + self._cur_indent()
            self._suppress_para = False
            self.parts.append(prefix + "#" * int(tag[1]) + " ")
            return
        if tag in ("strong", "b"):
            self.parts.append(_B_OPEN)
            return
        if tag in ("em", "i"):
            self.parts.append(_I_OPEN)
            return
        if tag == "span":
            bold = _is_bold_span(dict(attrs))
            self._span_bold.append(bold)
            if bold:
                self.parts.append(_B_OPEN)
            return
        # tr introduces a new table row; any other tag (td, th, table, font, …)
        # is dropped but its text content is kept.
        if tag == "tr":
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        if tag == "see":
            self._emit_see(tag, attrs, self_closing=True)
            return
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "see":
            self.parts.append("</see>")
            return
        if tag in _PARAGRAPH_TAGS:
            self.parts.append("\n\n" + self._cur_indent())
            return
        if tag in ("ul", "ol"):
            if self._lists:
                self._lists.pop()
            self.parts.append("\n")
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n\n" + self._cur_indent())
            return
        if tag in ("strong", "b"):
            self.parts.append(_B_CLOSE)
            return
        if tag in ("em", "i"):
            self.parts.append(_I_CLOSE)
            return
        if tag == "span":
            if self._span_bold.pop() if self._span_bold else False:
                self.parts.append(_B_CLOSE)

    def handle_data(self, data: str) -> None:
        if not data.strip():
            # Drop inter-tag whitespace (e.g. the newline between <li> and its
            # wrapping <p>) while a marker is hugging its first child, so the
            # marker doesn't end up on a line of its own.
            if self._suppress_para:
                return
            self.parts.append(data)
            return
        self._suppress_para = False
        self.parts.append(data)

    def get_markdown(self) -> str:
        return "".join(self.parts)


def html_to_markdown(html: str) -> str:
    """Convert an HTML fragment (with ``<see>`` tags already inlined) to markdown.

    Preserves paragraphs, ordered/unordered lists, headings and bold/italic
    emphasis, and passes ``<see cref>``/``<see href>`` tags through untouched.
    Trailing per-line whitespace and runs of blank lines are normalised.
    """
    parser = _HtmlToMarkdown()
    parser.feed(html)
    parser.close()
    text = parser.get_markdown()

    # Non-breaking spaces decoded from &nbsp; -> regular spaces.
    text = text.replace("\xa0", " ")

    # Resolve emphasis sentinels. CommonMark forbids whitespace directly inside
    # the markers (``** foo **`` renders literally), and the source often wraps a
    # trailing space inside <strong>, so relocate any inner whitespace outside
    # the span and drop spans left empty.
    text = re.sub(rf"{_B_OPEN}([ \t]+)", r"\1" + _B_OPEN, text)
    text = re.sub(rf"([ \t]+){_B_CLOSE}", _B_CLOSE + r"\1", text)
    text = re.sub(rf"{_I_OPEN}([ \t]+)", r"\1" + _I_OPEN, text)
    text = re.sub(rf"([ \t]+){_I_CLOSE}", _I_CLOSE + r"\1", text)
    text = text.replace(_B_OPEN + _B_CLOSE, "").replace(_I_OPEN + _I_CLOSE, "")
    text = text.replace(_B_OPEN, "**").replace(_B_CLOSE, "**")
    text = text.replace(_I_OPEN, "*").replace(_I_CLOSE, "*")

    # Strip trailing whitespace on each line (the source riddles list items with
    # a trailing space before the newline).
    text = re.sub(r"[ \t]+\n", "\n", text)
    # Collapse 3+ newlines to a single blank line.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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

    def replace_link(match: re.Match[str]) -> str:
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

    # Convert the remaining HTML structure (paragraphs, lists, headings, bold,
    # …) to markdown, keeping the <see cref>/<see href> tags intact. This also
    # decodes HTML entities and normalises whitespace.
    return html_to_markdown(result)


def href_to_see_ref(href: str) -> tuple[str, str]:
    """
    Resolve a "See Also" link href to an XML reference attribute.

    Returns a (attr, value) tuple where ``attr`` is either ``"cref"`` (for API
    type/member references) or ``"href"`` (for guide pages / external URLs).

    Examples:
    - "SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2~GetCorresponding.html"
      -> ("cref", "SolidWorks.Interop.sldworks.IComponent2.GetCorresponding")
    - "../sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm"
      -> ("href", "https://help.solidworks.com/2026/english/api/sldworksapiprogguide//Overview/SOLIDWORKS_Connected.htm")
    """
    cref = parse_href_to_cref(href)
    if cref:
        return ("cref", cref)
    return ("href", convert_to_full_url(href))


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
    filename = href
    if "/" in href or "\\" in href:
        filename = href.split("/")[-1].split("\\")[-1]

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
