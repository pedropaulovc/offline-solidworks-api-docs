"""
Example Markdown Generator for Phase 120: Export LLM-Friendly Documentation

This module generates markdown files for code examples organized by functional category.
"""

import re
from pathlib import Path
from typing import Dict
import html

from models import ExampleContent


class ExampleGenerator:
    """Generates markdown documentation for code examples."""

    def __init__(self, output_base_path: str):
        """
        Initialize the example generator.

        Args:
            output_base_path: Base path for output markdown files (docs/examples/)
        """
        self.output_base_path = Path(output_base_path)

    def generate_example_documentation(self, example: ExampleContent) -> str:
        """
        Generate markdown documentation for a code example.

        Args:
            example: The ExampleContent object to document

        Returns:
            Generated markdown content as a string
        """
        md = []

        # Extract title and description from content
        title, description, code = self._parse_example_content(example.content)

        # Use extracted title or fallback to stored title
        if not title and example.title:
            title = example.title

        # Title
        if title:
            md.append(f"# {title}\n")
        else:
            md.append("# Code Example\n")

        # Source URL
        md.append(f"**Source**: `{example.url}`\n")

        # Description
        if description:
            md.append("## Description\n")
            md.append(f"{description}\n")

        # Code
        if code:
            md.append("## Code\n")

            # Detect language from code content
            language = self._detect_language(code, example.url)
            lang_tag = self._get_language_tag(language)

            md.append(f"```{lang_tag}\n{code}\n```\n")

        return "\n".join(md)

    def _parse_example_content(self, content: str) -> tuple:
        """
        Parse example content to extract title, description, and code.

        Args:
            content: Raw example content from Phase 80

        Returns:
            Tuple of (title, description, code)
        """
        if not content:
            return ("", "", "")

        # Unescape HTML
        content = html.unescape(content)

        # Extract title (usually the first line)
        lines = content.strip().split('\n')
        title = ""
        if lines:
            title = lines[0].strip()

        # Extract code from <code> tags
        code_match = re.search(r'<code>(.*?)</code>', content, re.DOTALL | re.IGNORECASE)
        code = ""
        if code_match:
            code = code_match.group(1).strip()
            code = html.unescape(code)

        # Extract description (text before <code> tag, excluding title)
        description = ""
        if code_match:
            before_code = content[:code_match.start()]
            # Remove title line and clean up
            desc_lines = [line.strip() for line in before_code.split('\n')[1:] if line.strip()]
            description = '\n'.join(desc_lines)
        else:
            # No code found, use all text after title
            desc_lines = [line.strip() for line in lines[1:] if line.strip()]
            description = '\n'.join(desc_lines)

        return (title, description, code)

    def _detect_language(self, code: str, url: str) -> str:
        """
        Detect the programming language from code content or URL.

        Args:
            code: Code content
            url: Example URL

        Returns:
            Detected language name
        """
        # Check URL for language indicators
        url_lower = url.lower()
        if 'csharp' in url_lower or '_cs.' in url_lower:
            return 'C#'
        elif 'vba' in url_lower or '_vba.' in url_lower:
            return 'VBA'
        elif 'vbnet' in url_lower or '_vb.' in url_lower:
            return 'VB.NET'
        elif 'cpp' in url_lower or '_cpp.' in url_lower:
            return 'C++'
        elif 'python' in url_lower or '_py.' in url_lower:
            return 'Python'

        # Check code content for language-specific keywords
        if 'using System' in code or 'namespace ' in code:
            return 'C#'
        elif 'Dim ' in code and 'As ' in code:
            return 'VBA'
        elif '#include' in code:
            return 'C++'

        return 'text'

    def _get_language_tag(self, language: str) -> str:
        """
        Get the markdown language tag for syntax highlighting.

        Args:
            language: Language name

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

    def save_example_documentation(self, example: ExampleContent, category: str):
        """
        Generate and save documentation for an example to a file.

        Args:
            example: The ExampleContent object to document
            category: Functional category for organization
        """
        # Generate filename from URL
        filename = self._url_to_filename(example.url)

        # Create category folder
        category_path = self.output_base_path / self._sanitize_path(category)
        category_path.mkdir(parents=True, exist_ok=True)

        # Generate markdown
        markdown = self.generate_example_documentation(example)

        # Write to file
        output_path = category_path / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

    def _url_to_filename(self, url: str) -> str:
        """
        Convert example URL to a markdown filename.

        Args:
            url: Example URL

        Returns:
            Markdown filename
        """
        # Get the last part of the URL
        filename = url.split('/')[-1]

        # Replace .htm/.html with .md
        filename = re.sub(r'\.(htm|html)$', '.md', filename, flags=re.IGNORECASE)

        # If no extension was replaced, add .md
        if not filename.endswith('.md'):
            filename += '.md'

        return filename

    def _sanitize_path(self, name: str) -> str:
        """
        Sanitize a string to be used as a directory/file name.

        Args:
            name: The string to sanitize

        Returns:
            Sanitized string
        """
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')

        return name


def main():
    """Main function for testing the example generator."""
    import argparse
    from data_loader import DataLoader

    parser = argparse.ArgumentParser(description='Generate example markdown documentation')
    parser.add_argument('--phase80', default='80_parse_examples/output/examples.xml')
    parser.add_argument('--output', default='120_export_llm_docs/output/docs/examples')
    parser.add_argument('--url', help='Generate docs for a specific example URL')

    args = parser.parse_args()

    # Load examples
    loader = DataLoader()
    loader._load_phase80(args.phase80)

    # Create example generator
    generator = ExampleGenerator(output_base_path=args.output)

    if args.url:
        # Generate for specific example
        if args.url in loader.examples:
            example = loader.examples[args.url]
            # Use a test category
            generator.save_example_documentation(example, "Test Category")
            print(f"Generated documentation for example: {args.url}")
        else:
            print(f"Example not found: {args.url}")
    else:
        # Generate for first example as a test
        if loader.examples:
            sample_url = next(iter(loader.examples.keys()))
            example = loader.examples[sample_url]
            generator.save_example_documentation(example, "Test Category")
            print(f"Generated sample documentation for example: {sample_url}")
            print(f"Total examples loaded: {len(loader.examples)}")
        else:
            print("No examples found")


if __name__ == '__main__':
    main()
