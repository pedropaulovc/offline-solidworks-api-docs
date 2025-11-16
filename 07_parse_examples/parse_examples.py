"""
Phase 06: Parse Examples
Extracts example content from HTML files (Phase 05 output) and generates XML format.

This script:
1. Reads HTML files from 05_crawl_examples/output/html/
2. Extracts text content and code blocks
3. Generates XML with <Example> elements containing URLs and CDATA-wrapped content
4. Outputs to metadata/examples.xml
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from xml.dom import minidom


class ExampleParser:
    """Parses HTML example files and extracts structured content."""

    def __init__(self, html_dir: Path, output_file: Path):
        """
        Initialize the parser.

        Args:
            html_dir: Directory containing HTML files from Phase 05
            output_file: Output XML file path
        """
        self.html_dir = Path(html_dir)
        self.output_file = Path(output_file)
        self.stats = {
            'total_files': 0,
            'successful': 0,
            'failed': 0,
            'empty_content': 0,
        }
        self.errors: List[Dict[str, str]] = []

    def parse_html_file(self, file_path: Path) -> Optional[str]:
        """
        Parse a single HTML file and extract formatted content.

        Args:
            file_path: Path to HTML file

        Returns:
            Formatted content string with code blocks, or None if parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract all content elements
            content_parts = []
            in_code_block = False
            in_pre_block = False

            # Process all top-level elements (including divs which may contain code)
            for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'pre', 'div'], recursive=False):
                # Check if this is a code block
                if element.name == 'p' and element.get('class') == ['APICODE']:
                    # Close pre block if we were in one
                    if in_pre_block:
                        in_pre_block = False
                        # Don't close code block - continue in same block

                    # Start a code block if not already in one
                    if not in_code_block:
                        content_parts.append('<code>')
                        in_code_block = True

                    # Get the text content (preserve newlines to keep indentation via <br> tags)
                    text = self._get_inner_html(element, preserve_newlines=True)
                    if text:
                        content_parts.append(text)

                elif element.name == 'div' and (
                    'Monospace' in str(element.get('style', '')) or
                    element.find('p', class_='APICODE')
                ):
                    # This is a code container div
                    if in_pre_block:
                        in_pre_block = False

                    if not in_code_block:
                        content_parts.append('<code>')
                        in_code_block = True

                    # Process all APICODE paragraphs within the div (preserve indentation)
                    for p in element.find_all('p', class_='APICODE'):
                        text = self._get_inner_html(p, preserve_newlines=True)
                        if text:
                            content_parts.append(text)

                elif element.name == 'pre':
                    # Pre-formatted code block (preserve newlines from source)
                    # Multiple consecutive <pre> tags should be in the same code block
                    if not in_code_block:
                        content_parts.append('<code>')
                        in_code_block = True
                        in_pre_block = True
                    elif not in_pre_block:
                        # Was in a different type of code block, add separator
                        in_pre_block = True

                    text = self._get_inner_html(element, is_pre=True)
                    if text:
                        content_parts.append(text)

                else:
                    # Regular text element (h1, h2, h3, p without APICODE class)
                    # Close any open code block first
                    if in_code_block:
                        content_parts.append('</code>')
                        in_code_block = False
                        in_pre_block = False

                    # Add the text content
                    text = element.get_text().strip()
                    if text:
                        # Check if this looks like a file name (ends with file extension)
                        if any(text.endswith(ext) for ext in ['.vb', '.cs', '.cpp', '.h', '.js', '.py', '.java']):
                            content_parts.append(f'\n{text}')
                        else:
                            content_parts.append(text)

            # Close any remaining open code block
            if in_code_block:
                content_parts.append('</code>')

            # Join all parts
            formatted_content = '\n'.join(content_parts)

            # Clean up excessive blank lines (more than 2 consecutive)
            while '\n\n\n' in formatted_content:
                formatted_content = formatted_content.replace('\n\n\n', '\n\n')

            # Remove trailing spaces on each line
            lines = formatted_content.split('\n')
            lines = [line.rstrip() for line in lines]
            formatted_content = '\n'.join(lines)

            return formatted_content.strip() if formatted_content.strip() else None

        except Exception as e:
            self.errors.append({
                'file': str(file_path),
                'error': str(e)
            })
            return None

    def _get_inner_html(self, element, preserve_newlines: bool = False, is_pre: bool = False) -> str:
        """
        Get text content of an element, stripping all HTML tags.

        Args:
            element: BeautifulSoup element
            preserve_newlines: If True, preserve newlines from <br> tags
            is_pre: If True, this is a <pre> block - preserve actual newlines from source

        Returns:
            Text content as string
        """
        import re

        # Use a placeholder for br tags to preserve intentional line breaks
        LINEBREAK_MARKER = '<<<LINEBREAK>>>'

        # Replace <br> tags with a marker
        for br in element.find_all('br'):
            br.replace_with(LINEBREAK_MARKER)

        # Get text content (automatically strips all HTML tags and decodes entities)
        text = element.get_text()

        if is_pre:
            # For <pre> blocks: preserve actual newlines from HTML source
            # Just normalize horizontal whitespace on each line
            lines = text.split('\n')
            processed_lines = []
            for line in lines:
                # Collapse multiple spaces/tabs but preserve leading whitespace
                match = re.match(r'^([ \t]*)(.*)', line)
                if match:
                    leading = match.group(1)
                    rest = match.group(2)
                    # Collapse multiple spaces in the rest
                    rest = re.sub(r'[ \t]+', ' ', rest)
                    processed_lines.append(leading + rest.rstrip())
                else:
                    processed_lines.append(line.rstrip())
            text = '\n'.join(processed_lines)

        elif preserve_newlines:
            # For code blocks with <br> tags: preserve line breaks from <br>
            # Split by linebreak marker to get actual code lines
            segments = text.split(LINEBREAK_MARKER)
            processed_segments = []

            for segment in segments:
                # First, collapse ALL whitespace (including HTML source newlines) to spaces
                # This handles HTML formatting while preserving the space characters from &nbsp;
                collapsed = re.sub(r'[\r\n\t]+', ' ', segment)  # Convert newlines/tabs to spaces
                collapsed = re.sub(r' +', ' ', collapsed)  # Collapse multiple spaces to one

                # Now strip ONLY leading/trailing spaces that came from HTML formatting
                # But we need to preserve leading spaces from &nbsp; (indentation)
                # The trick: strip first, then we know any remaining content is meaningful
                collapsed = collapsed.strip()

                # Now restore proper indentation by counting leading spaces in original segment
                # Extract leading spaces from the ORIGINAL segment (before collapsing)
                # Include both regular spaces and non-breaking spaces (\xa0 from &nbsp;)
                original_leading = ''
                for char in segment:
                    if char in ' \t\xa0':
                        original_leading += char
                    elif char in '\r\n':
                        # Skip HTML source newlines
                        continue
                    else:
                        # Hit first non-whitespace, stop
                        break

                # Combine original leading spaces with collapsed content
                if collapsed:
                    processed_segments.append(original_leading + collapsed)
                elif original_leading:
                    # Blank line with just spaces
                    processed_segments.append(original_leading.rstrip())
                else:
                    # Completely empty line
                    processed_segments.append('')

            # Join segments with actual newlines (where <br> tags were)
            text = '\n'.join(processed_segments)
        else:
            # For other tags: normalize all whitespace
            text = re.sub(r'[ \t]+', ' ', text)  # Collapse horizontal whitespace
            text = re.sub(r'\n[ \t]*', ' ', text)  # Replace newlines with space

        # Clean up: remove only TRAILING spaces before newlines
        # Don't remove leading spaces after newlines (that's indentation!)
        text = re.sub(r' +\n', '\n', text)

        # Remove double spaces (but not at line beginnings - that's indentation)
        # Only collapse multiple spaces in the middle of lines
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Match leading whitespace separately
            match = re.match(r'^([ \t]*)(.*)', line)
            if match:
                leading = match.group(1)
                rest = match.group(2)
                # Collapse multiple spaces in the content part only
                rest = re.sub(r' {2,}', ' ', rest)
                cleaned_lines.append(leading + rest)
            else:
                cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)

        # Normalize non-breaking spaces to regular spaces for code output
        # This makes the output more standard and easier to work with
        text = text.replace('\xa0', ' ')

        # Replace any remaining LINEBREAK markers with actual newlines
        # This ensures markers are removed even if they weren't processed by the preserve_newlines branch
        text = text.replace(LINEBREAK_MARKER, '\n')

        # Only strip trailing whitespace - preserve leading indentation
        text = text.rstrip()
        # But also strip leading newlines (not spaces - that's indentation!)
        while text.startswith('\n'):
            text = text[1:]

        return text

    def get_relative_path(self, file_path: Path) -> str:
        """
        Get the relative path from the html directory.

        Args:
            file_path: Absolute path to HTML file

        Returns:
            Relative path (e.g., 'sldworksapi/Example.htm')
        """
        return str(file_path.relative_to(self.html_dir)).replace('\\', '/')

    def parse_all_examples(self) -> ET.Element:
        """
        Parse all HTML files and create XML structure.

        Returns:
            Root XML element with all examples
        """
        # Create root element
        root = ET.Element('Examples')

        # Find all HTML files
        html_files = sorted(self.html_dir.rglob('*.htm'))
        self.stats['total_files'] = len(html_files)

        print(f"Found {len(html_files)} HTML files to parse...")

        for html_file in html_files:
            # Parse the file
            content = self.parse_html_file(html_file)

            if content is None:
                self.stats['failed'] += 1
                continue

            if not content:
                self.stats['empty_content'] += 1
                continue

            # Get relative path for URL
            relative_path = self.get_relative_path(html_file)

            # Create Example element
            example_elem = ET.SubElement(root, 'Example')

            # Add URL
            url_elem = ET.SubElement(example_elem, 'Url')
            url_elem.text = relative_path

            # Add Content with CDATA
            content_elem = ET.SubElement(example_elem, 'Content')
            # CDATA is handled during serialization
            content_elem.text = content

            self.stats['successful'] += 1

            # Progress indicator
            if self.stats['successful'] % 100 == 0:
                print(f"Processed {self.stats['successful']}/{len(html_files)} files...")

        print(f"\nParsing complete!")
        print(f"  Successful: {self.stats['successful']}")
        print(f"  Failed: {self.stats['failed']}")
        print(f"  Empty content: {self.stats['empty_content']}")

        return root

    def _prettify_xml(self, elem: ET.Element) -> str:
        """
        Return a pretty-printed XML string with CDATA sections.

        Args:
            elem: Root XML element

        Returns:
            Formatted XML string
        """
        # Convert to string
        rough_string = ET.tostring(elem, encoding='unicode')

        # Parse with minidom for pretty printing
        reparsed = minidom.parseString(rough_string)

        # Get pretty XML
        pretty_xml = reparsed.toprettyxml(indent='    ', encoding='utf-8').decode('utf-8')

        # Wrap Content text in CDATA
        # Replace <Content>...</Content> with <Content><![CDATA[...]]></Content>
        import re

        def wrap_cdata(match):
            content = match.group(1)
            # Unescape XML entities since we're putting in CDATA
            content = (content
                       .replace('&lt;', '<')
                       .replace('&gt;', '>')
                       .replace('&quot;', '"')
                       .replace('&apos;', "'")
                       .replace('&amp;', '&'))  # Must be last
            return f'<Content><![CDATA[\n{content}\n        ]]></Content>'

        # Match Content elements and wrap their text in CDATA
        pretty_xml = re.sub(
            r'<Content>(.*?)</Content>',
            wrap_cdata,
            pretty_xml,
            flags=re.DOTALL
        )

        # Remove extra blank lines
        lines = pretty_xml.split('\n')
        lines = [line for line in lines if line.strip() or line.startswith('<?xml')]
        pretty_xml = '\n'.join(lines)

        return pretty_xml

    def save_xml(self, root: ET.Element) -> None:
        """
        Save XML to output file.

        Args:
            root: Root XML element
        """
        # Create output directory if needed
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # Get pretty XML with CDATA
        xml_string = self._prettify_xml(root)

        # Save to file
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(xml_string)

        print(f"\nXML saved to: {self.output_file}")

        # Calculate file size and hash
        file_size = os.path.getsize(self.output_file)
        with open(self.output_file, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        print(f"File size: {file_size:,} bytes")
        print(f"SHA-256: {file_hash}")

    def save_metadata(self, metadata_dir: Path) -> None:
        """
        Save parsing metadata.

        Args:
            metadata_dir: Directory to save metadata files
        """
        metadata_dir.mkdir(parents=True, exist_ok=True)

        # Save statistics
        stats_file = metadata_dir / 'parse_stats.json'
        with open(stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        print(f"Statistics saved to: {stats_file}")

        # Save errors if any
        if self.errors:
            errors_file = metadata_dir / 'parse_errors.json'
            with open(errors_file, 'w') as f:
                json.dump(self.errors, f, indent=2)
            print(f"Errors saved to: {errors_file}")

        # Save manifest
        manifest = {
            'parser_version': '1.0.0',
            'input_directory': str(self.html_dir),
            'output_file': str(self.output_file),
            'total_examples': self.stats['successful'],
        }
        manifest_file = metadata_dir / 'manifest.json'
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        print(f"Manifest saved to: {manifest_file}")

    def run(self) -> None:
        """Run the complete parsing pipeline."""
        print("=" * 60)
        print("Phase 06: Parse Examples")
        print("=" * 60)
        print()

        # Check input directory exists
        if not self.html_dir.exists():
            print(f"ERROR: Input directory not found: {self.html_dir}")
            print("Please run Phase 05 first to crawl example pages.")
            sys.exit(1)

        # Parse all examples
        root = self.parse_all_examples()

        # Save XML output
        self.save_xml(root)

        # Save metadata
        metadata_dir = self.output_file.parent.parent / 'metadata'
        self.save_metadata(metadata_dir)

        print()
        print("=" * 60)
        print("Parsing complete!")
        print("=" * 60)


def main():
    """Main entry point."""
    # Get project root
    project_root = Path(__file__).parent.parent

    # Define paths
    html_dir = project_root / '05_crawl_examples' / 'output' / 'html'
    output_file = project_root / '06_parse_examples' / 'output' / 'examples.xml'

    # Create parser and run
    parser = ExampleParser(html_dir, output_file)
    parser.run()


if __name__ == '__main__':
    main()
