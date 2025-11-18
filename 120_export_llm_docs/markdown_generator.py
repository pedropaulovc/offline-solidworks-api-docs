"""
Markdown Generator for Phase 120: Export LLM-Friendly Documentation

This module generates markdown documentation files for API types.
"""

import re
from pathlib import Path
from typing import Dict, Optional
import html

from models import TypeInfo, ExampleContent


class MarkdownGenerator:
    """Generates markdown documentation for API types."""

    def __init__(self, output_base_path: str, examples_loader_func=None):
        """
        Initialize the markdown generator.

        Args:
            output_base_path: Base path for output markdown files
            examples_loader_func: Function to load example content by URL
        """
        self.output_base_path = Path(output_base_path)
        self.examples_loader_func = examples_loader_func

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

        # Enum Members
        if type_info.enum_members:
            md.append("## Enumeration Members\n")
            for enum_member in type_info.enum_members:
                md.append(f"### {enum_member.name}\n")
                if enum_member.description:
                    md.append(f"{self._clean_text(enum_member.description)}\n")

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
                    for param in prop.parameters:
                        param_desc = self._clean_text(param.description) if param.description else "No description"
                        md.append(f"- `{param.name}` - {param_desc}\n")
                    md.append("")

                if prop.returns:
                    md.append(f"**Returns**: {self._clean_text(prop.returns)}\n")

                if prop.remarks:
                    md.append(f"**Remarks**: {self._clean_text(prop.remarks)}\n")

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
                    for param in method.parameters:
                        param_desc = self._clean_text(param.description) if param.description else "No description"
                        md.append(f"- `{param.name}` - {param_desc}\n")
                    md.append("")

                if method.returns:
                    md.append(f"**Returns**: {self._clean_text(method.returns)}\n")

                if method.remarks:
                    md.append(f"**Remarks**: {self._clean_text(method.remarks)}\n")

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
        """
        Clean text by unescaping HTML entities and removing CDATA markers.

        Args:
            text: Raw text from XML

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Unescape HTML entities
        text = html.unescape(text)

        # Remove CDATA markers if present
        text = text.replace('<![CDATA[', '').replace(']]>', '')

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

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
            category: Functional category

        Returns:
            Relative path from API doc to example file
        """
        # Convert URL to filename
        # e.g., "sldworksapi/Create_Advanced_Hole_Example_CSharp.htm" -> "Create_Advanced_Hole_Example_CSharp.md"
        filename = url.split('/')[-1].replace('.htm', '.md').replace('.html', '.md')

        if category:
            # Relative path from api/Assembly/Category/Type.md to docs/examples/Category/Example.md
            return f"../../../docs/examples/{category}/{filename}"
        else:
            # If no category, just link to docs/examples
            return f"../../docs/examples/{filename}"

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

    # Replace spaces with underscores
    name = name.replace(' ', '_')

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
