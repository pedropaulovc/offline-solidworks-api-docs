"""
Markdown Generator for Phase 120: Export LLM-Friendly Documentation

This module generates markdown documentation files for API types.
Supports both monolithic (one file per type) and grep-optimized (file-per-member) formats.
"""

import re
from pathlib import Path
from typing import Dict, Optional, List
import html

from models import TypeInfo, ExampleContent, Member, Property, Method, EnumMember

# ``../`` sequence from a generated file to the bundle root, used to build
# relative links into ``docs/``. Type files live at ``types/{Name}/*.md`` (two
# levels deep); enum and index files are one level deep.
DOCS_PREFIX_TYPE = "../../"
DOCS_PREFIX_FLAT = "../"


def _block(lines: List[str]) -> str:
    """Join already-formatted markdown lines into one tight block (no blank lines between).

    Used for list items and table rows, which must render adjacent. The block is
    appended as a single element so the surrounding ``"\\n".join(md)`` only ever
    inserts one blank line before and after it.
    """
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _indent_continuation(text: str, indent: str = "  ") -> str:
    """Indent every line after the first so a multi-line value renders as the
    continuation of a ``- `` list item (nested paragraphs/sublists stay under
    the bullet instead of escaping it). Blank lines are left empty."""
    lines = text.split("\n")
    return "\n".join(lines[:1] + [f"{indent}{line}" if line else line for line in lines[1:]])


# A converted value that opens with a list bullet or heading is block markdown:
# it must not be pasted inline after a label (``- **Param**: - A``), or the first
# element is swallowed as literal text instead of starting a list/heading.
_STARTS_WITH_BLOCK = re.compile(r"\s*(?:[-*] |\d+\. |#{1,6} )")


def _indent_all(text: str, indent: str = "  ") -> str:
    """Indent every non-empty line by ``indent`` (blank lines stay empty)."""
    return "\n".join(f"{indent}{line}" if line else line for line in text.split("\n"))


def _labeled_bullet(prefix: str, content: str) -> str:
    """Render ``{prefix}{content}`` as a ``- `` list item. If ``content`` starts
    with block markdown, drop it onto indented continuation lines under the label
    (``- **Param**:\\n  - A``) instead of inlining it (``- **Param**: - A``)."""
    if _STARTS_WITH_BLOCK.match(content):
        return f"{prefix.rstrip()}\n{_indent_all(content)}"
    return _indent_continuation(f"{prefix}{content}")


def _labeled_field(label: str, value: str) -> str:
    """Render a top-level ``{label} {value}`` field. If ``value`` starts with
    block markdown, break it onto its own block after the label so the first
    list item / heading isn't consumed as inline text."""
    if _STARTS_WITH_BLOCK.match(value):
        return f"{label}\n\n{value}"
    return f"{label} {value}"


def clean_text(text: str) -> str:
    """Clean raw XML text: unescape HTML entities, drop CDATA markers, and
    collapse runs of blank lines so paragraphs are separated by at most one."""
    if not text:
        return ""

    text = html.unescape(text)
    text = text.replace('<![CDATA[', '').replace(']]>', '')
    # Collapse runs of blank lines (matches the rest of the document).
    text = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', text)
    return text.strip()


def guide_link_key(url: str) -> str:
    """Normalize a ``<see href>`` URL to the key used in the guide-link map:
    the lowercased ``.htm``/``.html`` basename (host, path, and query stripped)."""
    return url.split('?')[0].rstrip('/').split('/')[-1].lower()


def parse_api_ref_url(url: str) -> "Optional[tuple[str, str, Optional[str]]]":
    """Parse a SolidWorks API-reference URL into ``(assembly, type, member)``.

    Reference pages are named ``{Namespace}~{Namespace}.{Type}[~{Member}].html``
    and live under an assembly folder (``sldworksapi``, ``swconst``, …). Returns
    ``None`` when the basename has no ``~`` — the reliable marker that separates
    reference pages from example/programming-guide pages in those same folders.

    Example::

        .../sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IFeature~ModifyDefinition.html
        -> ("sldworksapi", "IFeature", "ModifyDefinition")
        .../sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IMacroFeatureData.html
        -> ("sldworksapi", "IMacroFeatureData", None)
    """
    path = url.split('?')[0].split('#')[0]
    segments = [s for s in path.split('/') if s]
    if not segments:
        return None
    basename = re.sub(r'\.html?$', '', segments[-1], flags=re.IGNORECASE)
    if '~' not in basename:
        return None
    parts = basename.split('~')
    if len(parts) < 2:
        return None
    assembly = segments[-2] if len(segments) >= 2 else ''
    type_name = parts[1].rsplit('.', 1)[-1]
    member_name = parts[2] if len(parts) > 2 else None
    if not type_name:
        return None
    return assembly, type_name, member_name


def simplify_cross_references(text: str, guide_links: Optional[Dict[str, str]] = None,
                             rel_prefix: str = "") -> str:
    """Convert inline XML-style cross-references to markdown/wiki links.

    - ``<see cref="FQN">Label</see>`` and self-closing ``<see cref="FQN" />``
      become ``[[Label]]`` wiki-links (greppable API references).
    - ``<see href="URL">Label</see>`` becomes a relative markdown link to the
      programming-guide file when that page ships in the bundle
      (``[Label](<rel_prefix + docs/…>)``), otherwise a plain external link
      ``[Label](URL)``.

    Args:
        text: Raw text containing ``<see …>`` tags.
        guide_links: Map of :func:`guide_link_key` -> bundle-relative docs path
            (e.g. ``docs/Programming with the SOLIDWORKS API/In-process Methods.md``).
        rel_prefix: ``../`` sequence to reach the bundle root from the file being
            rendered (``../../`` for ``types/X/…`` files, ``../`` for ``enums/`` and
            ``index/`` files).
    """
    if not text:
        return ""

    links = guide_links or {}

    # <see cref="...">LinkText</see> -> [[LinkText]]
    text = re.sub(r'<see cref="[^"]+">([^<]+)</see>', r'[[\1]]', text)

    # Self-closing <see cref="FQN" /> -> [[last segment of FQN]]
    text = re.sub(r'<see cref="([^"]+)"\s*/>',
                  lambda m: f'[[{m.group(1).split(".")[-1]}]]', text)

    # <see href="URL">LinkText</see> -> relative file link (in-bundle) or external link
    def replace_href(match: "re.Match[str]") -> str:
        url, label = match.group(1), match.group(2)
        target = links.get(guide_link_key(url))
        if target:
            return f'[{label}](<{rel_prefix}{target}>)'
        return f'[{label}]({url})'

    text = re.sub(r'<see href="([^"]*)">([^<]+)</see>', replace_href, text)
    return text


def strip_cross_references(text: str) -> str:
    """Reduce ``<see …>`` cross-references to their plain label text.

    Used for short preview strings (e.g. truncated index descriptions) where a
    ``[[…]]`` wiki-link or ``[label](<…>)`` file link would only add noise and,
    worse, be cut mid-link by a length cap. ``<see cref="FQN" />`` self-closing
    tags collapse to the last FQN segment.
    """
    if not text:
        return ""

    text = re.sub(r'<see (?:cref|href)="[^"]*">([^<]+)</see>', r'\1', text)
    text = re.sub(r'<see cref="([^"]+)"\s*/>',
                  lambda m: m.group(1).split(".")[-1], text)
    return text


class MarkdownGenerator:
    """Generates markdown documentation for API types."""

    def __init__(self, output_base_path: str, examples_loader_func=None, grep_optimized=False,
                 example_categories=None, guide_links=None):
        """
        Initialize the markdown generator.

        Args:
            output_base_path: Base path for output markdown files
            examples_loader_func: Function to load example content by URL
            grep_optimized: If True, generate file-per-member structure for greppability
            example_categories: Dict mapping example URLs to category names (for grep_optimized mode)
            guide_links: Dict mapping guide_link_key(url) -> bundle-relative docs path,
                used to turn ``<see href>`` guide references into relative file links
        """
        self.output_base_path = Path(output_base_path)
        self.examples_loader_func = examples_loader_func
        self.grep_optimized = grep_optimized
        self.example_categories = example_categories or {}
        self.guide_links = guide_links or {}

    def generate_type_documentation(self, type_info: TypeInfo, category: Optional[str] = None) -> str:
        """
        Generate markdown documentation for a type.

        Args:
            type_info: The TypeInfo object to document
            category: Optional functional category for the type

        Returns:
            Generated markdown content as a string
        """
        md = []

        # Title
        md.append(f"# {type_info.name}\n")

        # Metadata
        md.append(f"**Assembly**: {type_info.assembly}  ")
        md.append(f"**Namespace**: {type_info.namespace}\n")

        if category:
            md.append(f"**Category**: {category}\n")

        # Description
        if type_info.description:
            md.append("## Description\n")
            md.append(f"{self._clean_text(type_info.description)}\n")

        # Remarks
        if type_info.remarks:
            md.append("## Remarks\n")
            md.append(f"{self._clean_text(type_info.remarks)}\n")

        # Enum Members, as a Member | Value table
        if type_info.enum_members:
            md.append("## Enumeration Members\n")
            md.append(self._enum_members_table(type_info.enum_members, self._clean_text))

        # Properties
        if type_info.properties:
            md.append("## Properties\n")
            for prop in type_info.properties:
                md.append(f"### {prop.name}\n")

                if prop.description:
                    md.append(f"{self._clean_text(prop.description)}\n")

                if prop.signature:
                    md.append(f"**Signature**: `{prop.signature}`\n")

                if prop.parameters:
                    md.append("**Parameters**:\n")
                    md.append(_block([
                        _labeled_bullet(
                            f"- `{param.name}` - ",
                            self._clean_text(param.description) if param.description else 'No description'
                        )
                        for param in prop.parameters
                    ]))

                if prop.returns:
                    md.append(f"{_labeled_field('**Returns**:', self._clean_text(prop.returns))}\n")

                if prop.remarks:
                    md.append(f"{_labeled_field('**Remarks**:', self._clean_text(prop.remarks))}\n")

        # Methods
        if type_info.methods:
            md.append("## Methods\n")
            for method in type_info.methods:
                md.append(f"### {method.name}\n")

                if method.description:
                    md.append(f"{self._clean_text(method.description)}\n")

                if method.signature:
                    md.append(f"**Signature**: `{method.signature}`\n")

                if method.parameters:
                    md.append("**Parameters**:\n")
                    md.append(_block([
                        _labeled_bullet(
                            f"- `{param.name}` - ",
                            self._clean_text(param.description) if param.description else 'No description'
                        )
                        for param in method.parameters
                    ]))

                if method.returns:
                    md.append(f"{_labeled_field('**Returns**:', self._clean_text(method.returns))}\n")

                if method.remarks:
                    md.append(f"{_labeled_field('**Remarks**:', self._clean_text(method.remarks))}\n")

        # Examples
        if type_info.examples:
            md.append("## Examples\n")

            # Group examples by language
            examples_by_lang = {}
            for example_ref in type_info.examples:
                lang = example_ref.language
                if lang not in examples_by_lang:
                    examples_by_lang[lang] = []
                examples_by_lang[lang].append(example_ref)

            for lang, examples in sorted(examples_by_lang.items()):
                for example_ref in examples:
                    md.append(f"### {example_ref.name} ({lang})\n")

                    # Try to load the full example content
                    if self.examples_loader_func:
                        example_content = self.examples_loader_func(example_ref.url)
                        if example_content:
                            # Extract code from example content
                            code = self._extract_code_from_example(example_content.content, lang)
                            if code:
                                lang_tag = self._get_language_tag(lang)
                                md.append(f"```{lang_tag}\n{code}\n```\n")

                    # Link to full example
                    example_file = self._get_example_file_path(example_ref.url, category)
                    if example_file:
                        md.append(f"[View full example]({example_file})\n")

        return "\n".join(md)

    def _clean_text(self, text: str) -> str:
        """Instance delegator for the module-level :func:`clean_text`."""
        return clean_text(text)

    def _extract_code_from_example(self, content: str, language: str) -> str:
        """
        Extract code from example content.

        Args:
            content: Full example content
            language: Programming language

        Returns:
            Extracted code or empty string
        """
        # Look for code between <code> tags
        code_match = re.search(r'<code>(.*?)</code>', content, re.DOTALL | re.IGNORECASE)
        if code_match:
            code = code_match.group(1)
            # Clean up the code
            code = html.unescape(code)
            code = code.strip()
            return code

        return ""

    def _get_language_tag(self, language: str) -> str:
        """
        Get the markdown language tag for syntax highlighting.

        Args:
            language: Language name from API docs

        Returns:
            Markdown language tag
        """
        lang_map = {
            'C#': 'csharp',
            'VBA': 'vba',
            'VB.NET': 'vbnet',
            'C++': 'cpp',
            'Python': 'python',
        }
        return lang_map.get(language, 'text')

    def _get_example_file_path(self, url: str, category: Optional[str]) -> str:
        """
        Get the relative path to the example markdown file.

        Args:
            url: Example URL
            category: Functional category (unused with flat folder structure, kept for API compatibility)

        Returns:
            Relative path from API doc to example file
        """
        # Convert URL to filename
        # e.g., "sldworksapi/Create_Advanced_Hole_Example_CSharp.htm" -> "Create_Advanced_Hole_Example_CSharp.md"
        filename = url.split('/')[-1].replace('.htm', '.md').replace('.html', '.md')

        # Relative path from API doc to docs/examples/Example.md (flat folder structure)
        # Assuming API doc is at api/assembly/Type.md, need to go up 2 levels
        return f"../../docs/examples/{filename}"

    def _get_example_path_for_overview(self, url: str, type_info: TypeInfo) -> str:
        """
        Get the relative path to the example markdown file from a type overview file.

        Args:
            url: Example URL
            type_info: The TypeInfo object (to determine if type or enum)

        Returns:
            Relative path from _overview.md to example file
        """
        # Convert URL to filename
        # e.g., "sldworksapi/Traverse_Bodies_Example_CPlusPlusCLI.htm" -> "Traverse_Bodies_Example_CPlusPlusCLI.md"
        filename = url.split('/')[-1].replace('.htm', '.md').replace('.html', '.md')

        # Relative path from types/TypeName/_overview.md or enums/EnumName/_overview.md
        # to examples/Example.md (flat folder structure)
        return f"../../examples/{filename}"

    def _get_example_path_for_member(self, url: str, type_info: TypeInfo) -> str:
        """
        Get the relative path to the example markdown file from a member file.

        Args:
            url: Example URL
            type_info: The TypeInfo object (to determine category)

        Returns:
            Relative path from member.md to example file
        """
        # Member files are at the same level as _overview.md, so use the same logic
        return self._get_example_path_for_overview(url, type_info)

    def generate_type_overview(self, type_info: TypeInfo, rel_prefix: str = DOCS_PREFIX_TYPE) -> str:
        """
        Generate type overview markdown (description, remarks, metadata) without members.
        Used for grep-optimized _overview.md files.

        Args:
            type_info: The TypeInfo object to document
            rel_prefix: ``../`` sequence to the bundle root (see DOCS_PREFIX_TYPE)

        Returns:
            Generated markdown content as a string
        """
        md = []

        # YAML frontmatter
        md.append("---")
        md.append(f"name: {type_info.name}")
        md.append(f"assembly: {type_info.assembly}")
        md.append(f"namespace: {type_info.namespace}")
        if type_info.functional_category:
            md.append(f"category: {type_info.functional_category}")
        md.append(f"is_enum: {type_info.is_enum}")
        md.append(f"property_count: {len(type_info.properties)}")
        md.append(f"method_count: {len(type_info.methods)}")
        md.append(f"enum_member_count: {len(type_info.enum_members)}")
        md.append("---\n")

        # Title
        md.append(f"# {type_info.name}\n")

        # Metadata (one tight block; lines joined with markdown hard breaks)
        md.append(self._metadata_block(type_info))

        # Description
        if type_info.description:
            md.append("## Description\n")
            md.append(f"{self._simplify_cross_references(self._clean_text(type_info.description), rel_prefix)}\n")

        # Remarks
        if type_info.remarks:
            md.append("## Remarks\n")
            md.append(f"{self._simplify_cross_references(self._clean_text(type_info.remarks), rel_prefix)}\n")

        # Member counts (omit the section entirely when there are none)
        members = []
        if type_info.properties:
            members.append(f"- **Properties**: {len(type_info.properties)}")
        if type_info.methods:
            members.append(f"- **Methods**: {len(type_info.methods)}")
        if type_info.enum_members:
            members.append(f"- **Enumeration Members**: {len(type_info.enum_members)}")
        if members:
            md.append("## Members\n")
            md.append(_block(members))

        # Examples section
        if type_info.examples:
            md.append("## Examples\n")
            md.append(_block([
                f"- [{ex.name} ({ex.language})]"
                f"({self._get_example_path_for_overview(ex.url, type_info)})"
                for ex in type_info.examples
            ]))

        # See Also cross-references
        if type_info.see_also:
            md.extend(self._render_see_also(type_info.see_also, rel_prefix))

        return "\n".join(md)

    def generate_member_documentation(self, type_info: TypeInfo, member: Member, member_kind: str,
                                      rel_prefix: str = DOCS_PREFIX_TYPE) -> str:
        """
        Generate markdown documentation for a single member (property or method).

        Args:
            type_info: The parent TypeInfo object
            member: The member (Property or Method) to document
            member_kind: "property" or "method"
            rel_prefix: ``../`` sequence to the bundle root (see DOCS_PREFIX_TYPE)

        Returns:
            Generated markdown content as a string
        """
        md = []

        # YAML frontmatter
        md.append("---")
        md.append(f"type: {type_info.name}")
        md.append(f"member: {member.name}")
        md.append(f"kind: {member_kind}")
        md.append(f"assembly: {type_info.assembly}")
        md.append(f"namespace: {type_info.namespace}")
        if type_info.functional_category:
            md.append(f"category: {type_info.functional_category}")
        md.append("---\n")

        # Title
        md.append(f"# {type_info.name}.{member.name}\n")

        # Description
        if member.description:
            md.append(f"{self._simplify_cross_references(self._clean_text(member.description), rel_prefix)}\n")

        # Signature (prefixed with the return type when known)
        if member.signature:
            full_signature = f"{member.return_type} {member.signature}".strip() if member.return_type else member.signature
            md.append(f"**Signature**: `{full_signature}`\n")

        # Return type (called out separately for greppability)
        if member.return_type:
            md.append(f"**Return type**: `{member.return_type}`\n")

        # Parameters
        if member.parameters:
            md.append("## Parameters\n")
            md.append(_block([
                _labeled_bullet(
                    f"- **{param.name}**: ",
                    self._simplify_cross_references(self._clean_text(param.description), rel_prefix) if param.description else 'No description'
                )
                for param in member.parameters
            ]))

        # Returns
        if member.returns:
            md.append(f"## Returns\n")
            md.append(f"{self._simplify_cross_references(self._clean_text(member.returns), rel_prefix)}\n")

        # Remarks
        if member.remarks:
            md.append(f"## Remarks\n")
            md.append(f"{self._simplify_cross_references(self._clean_text(member.remarks), rel_prefix)}\n")

        # Examples section
        if member.examples:
            md.append("## Examples\n")
            md.append(_block([
                f"- [{ex.name} ({ex.language})]"
                f"({self._get_example_path_for_member(ex.url, type_info)})"
                for ex in member.examples
            ]))

        # See Also cross-references
        if member.see_also:
            md.extend(self._render_see_also(member.see_also, rel_prefix))

        return "\n".join(md)

    def _get_example_path_for_enum_file(self, url: str) -> str:
        """Relative path to an example file from a flat ``enums/{Enum}.md`` file (up one level)."""
        filename = url.split('/')[-1].replace('.htm', '.md').replace('.html', '.md')
        return f"../examples/{filename}"

    def _enum_members_table(self, enum_members: List[EnumMember], transform) -> str:
        """Render enumeration members as a two-column ``Member | Value`` markdown table.

        The source ``description`` is a merged ``value = meaning`` blob (or a bare
        value), so it maps to a single ``Value`` cell. ``transform`` is applied to
        each description (e.g. clean-up + cross-reference resolution). Cell content
        is flattened: embedded pipes are escaped and newlines become ``<br>`` so
        multi-line descriptions (lists, notes) don't break the table.
        """
        lines = ["| Member | Value |", "| --- | --- |"]
        for enum_member in enum_members:
            value = transform(enum_member.description) if enum_member.description else ""
            value = value.strip().replace("|", "\\|")
            value = re.sub(r"\n+", "<br>", value)
            lines.append(f"| {enum_member.name} | {value} |")
        return "\n".join(lines) + "\n"

    def generate_enum_documentation(self, type_info: TypeInfo, rel_prefix: str = DOCS_PREFIX_FLAT) -> str:
        """
        Generate a single self-contained markdown file for an enumeration, with all
        members inline (replaces the per-member file-per-enum-member layout).

        Args:
            type_info: The enum TypeInfo object to document
            rel_prefix: ``../`` sequence to the bundle root (see DOCS_PREFIX_FLAT)

        Returns:
            Generated markdown content as a string
        """
        md = []

        # YAML frontmatter
        md.append("---")
        md.append(f"name: {type_info.name}")
        md.append("kind: enum")
        md.append(f"assembly: {type_info.assembly}")
        md.append(f"namespace: {type_info.namespace}")
        if type_info.functional_category:
            md.append(f"category: {type_info.functional_category}")
        md.append("is_enum: True")
        md.append(f"enum_member_count: {len(type_info.enum_members)}")
        md.append("---\n")

        # Title and metadata
        md.append(f"# {type_info.name}\n")
        md.append(self._metadata_block(type_info))

        # Description
        if type_info.description:
            md.append("## Description\n")
            md.append(f"{self._simplify_cross_references(self._clean_text(type_info.description), rel_prefix)}\n")

        # Remarks
        if type_info.remarks:
            md.append("## Remarks\n")
            md.append(f"{self._simplify_cross_references(self._clean_text(type_info.remarks), rel_prefix)}\n")

        # All enumeration members inline, as a Member | Value table
        md.append("## Enumeration Members\n")
        md.append(self._enum_members_table(
            type_info.enum_members,
            lambda text: self._simplify_cross_references(self._clean_text(text), rel_prefix),
        ))

        # Examples (enum-level, if any)
        if type_info.examples:
            md.append("## Examples\n")
            md.append(_block([
                f"- [{ex.name} ({ex.language})]"
                f"({self._get_example_path_for_enum_file(ex.url)})"
                for ex in type_info.examples
            ]))

        # See Also cross-references
        if type_info.see_also:
            md.extend(self._render_see_also(type_info.see_also, rel_prefix))

        return "\n".join(md)

    def save_enum_documentation(self, type_info: TypeInfo, output_path: Path) -> int:
        """Write a single flat ``enums/{Enum}.md`` file. Returns number of files written (1)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_enum_documentation(type_info))
        return 1

    def _metadata_block(self, type_info: TypeInfo) -> str:
        """Render the Assembly/Namespace/Category metadata as one block.

        Lines are joined with markdown hard breaks (two trailing spaces) so they
        render on consecutive lines, and the block ends with a newline so the
        join only adds a single blank line before the next section.
        """
        lines = [
            f"**Assembly**: {type_info.assembly}",
            f"**Namespace**: {type_info.namespace}",
        ]
        if type_info.functional_category:
            lines.append(f"**Category**: {type_info.functional_category}")
        return "  \n".join(lines) + "\n"

    def _render_see_also(self, see_also: List, rel_prefix: str = "") -> List[str]:
        """
        Render a ``## See Also`` markdown block from a list of CrossRef objects.

        API references (cref) become ``[[Label]]`` wiki-links so they stay
        greppable and consistent with inline cross-references; guide references
        (href) become relative file links when the page ships in the bundle,
        otherwise plain external links. ``rel_prefix`` is the ``../`` sequence
        that reaches the bundle root from the file being rendered.

        Returns an empty list when there are no cross-references. The heading and
        the (tight) list of links are returned as two elements so the caller's
        ``"\\n".join(md)`` puts one blank line before the heading and none
        between the links.
        """
        if not see_also:
            return []

        def render(ref) -> str:
            if ref.attr == "cref":
                return f"- [[{ref.label}]]"
            target = self.guide_links.get(guide_link_key(ref.value))
            if target:
                return f"- [{ref.label}](<{rel_prefix}{target}>)"
            return f"- [{ref.label}]({ref.value})"

        return ["## See Also\n", _block([render(ref) for ref in see_also])]

    def _simplify_cross_references(self, text: str, rel_prefix: str = "") -> str:
        """Instance delegator for the module-level :func:`simplify_cross_references`."""
        return simplify_cross_references(text, self.guide_links, rel_prefix)

    def save_grep_optimized_documentation(self, type_info: TypeInfo, output_dir: Path) -> int:
        """
        Generate and save grep-optimized documentation for a type.
        Creates a directory structure: types/TypeName/ with separate files for each member.

        Args:
            type_info: The TypeInfo object to document
            output_dir: Base directory (e.g., output/api/types/TypeName/)

        Returns:
            Number of files generated
        """
        files_generated = 0

        # Create type directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate type overview
        overview_md = self.generate_type_overview(type_info)
        overview_path = output_dir / "_overview.md"
        with open(overview_path, 'w', encoding='utf-8') as f:
            f.write(overview_md)
        files_generated += 1

        # Generate property files
        for prop in type_info.properties:
            member_md = self.generate_member_documentation(type_info, prop, "property")
            member_path = output_dir / f"{sanitize_filename(prop.name)}.md"
            with open(member_path, 'w', encoding='utf-8') as f:
                f.write(member_md)
            files_generated += 1

        # Generate method files
        for method in type_info.methods:
            member_md = self.generate_member_documentation(type_info, method, "method")
            member_path = output_dir / f"{sanitize_filename(method.name)}.md"
            with open(member_path, 'w', encoding='utf-8') as f:
                f.write(member_md)
            files_generated += 1

        # NOTE: Enums are not exported here. They are written as a single flat
        # enums/{Enum}.md file via save_enum_documentation() (see export_pipeline).

        return files_generated

    def save_type_documentation(self, type_info: TypeInfo, output_path: Path):
        """
        Generate and save documentation for a type to a file.

        Args:
            type_info: The TypeInfo object to document
            output_path: Path where the markdown file should be saved
        """
        # Determine category if we have one
        category = type_info.functional_category

        # Generate markdown
        markdown = self.generate_type_documentation(type_info, category)

        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string to be used as a filename.

    Args:
        name: The string to sanitize

    Returns:
        Sanitized string safe for use as a filename
    """
    # Replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')

    # Keep spaces as-is to match directory structure created by example_generator.py
    return name


def main():
    """Main function for testing the markdown generator."""
    import argparse
    from data_loader import DataLoader

    parser = argparse.ArgumentParser(description='Generate markdown documentation')
    parser.add_argument('--phase20', default='20_extract_types/metadata/api_members.xml')
    parser.add_argument('--phase40', default='40_extract_type_details/metadata/api_types.xml')
    parser.add_argument('--phase50', default='50_extract_type_member_details/metadata/api_member_details.xml')
    parser.add_argument('--phase60', default='60_extract_enum_members/metadata/enum_members.xml')
    parser.add_argument('--phase80', default='80_parse_examples/output/examples.xml')
    parser.add_argument('--output', default='120_export_llm_docs/output/api')
    parser.add_argument('--type', help='Generate docs for a specific type (fully qualified name)')

    args = parser.parse_args()

    # Load data
    loader = DataLoader()
    types = loader.load_all(
        args.phase20,
        args.phase40,
        args.phase50,
        args.phase60,
        args.phase80
    )

    # Create markdown generator
    generator = MarkdownGenerator(
        output_base_path=args.output,
        examples_loader_func=loader.get_example_content
    )

    if args.type:
        # Generate for specific type
        if args.type in types:
            type_info = types[args.type]
            output_path = Path(args.output) / f"{type_info.name}.md"
            generator.save_type_documentation(type_info, output_path)
            print(f"Generated documentation for {args.type}")
            print(f"Saved to: {output_path}")
        else:
            print(f"Type not found: {args.type}")
    else:
        # Generate for first type as a test
        sample_type = next(iter(types.values()))
        output_path = Path(args.output) / f"{sample_type.name}.md"
        generator.save_type_documentation(sample_type, output_path)
        print(f"Generated sample documentation for {sample_type.fully_qualified_name}")
        print(f"Saved to: {output_path}")


if __name__ == '__main__':
    main()
