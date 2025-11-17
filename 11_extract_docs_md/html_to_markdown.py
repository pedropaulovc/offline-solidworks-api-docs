"""Convert HTML documentation to Markdown format."""

import hashlib
import html2text
import json
import jsonlines
from pathlib import Path
from typing import Any


class HtmlToMarkdownConverter:
    """Convert HTML files to Markdown format."""

    def __init__(
        self,
        html_dir: Path,
        metadata_file: Path,
        output_dir: Path,
    ) -> None:
        """Initialize the HTML to Markdown converter.

        Args:
            html_dir: Directory containing HTML files
            metadata_file: Path to urls_crawled.jsonl metadata file
            output_dir: Output directory for Markdown files
        """
        self.html_dir = html_dir
        self.metadata_file = metadata_file
        self.output_dir = output_dir
        self.url_to_file_map: dict[str, Path] = {}

        # Configure html2text
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.ignore_emphasis = False
        self.h2t.body_width = 0  # Don't wrap text
        self.h2t.unicode_snob = True  # Use unicode chars instead of ASCII
        self.h2t.skip_internal_links = False

    def load_metadata(self) -> None:
        """Load URL to file path mappings from metadata."""
        with jsonlines.open(self.metadata_file) as reader:
            for entry in reader:
                url = entry.get("url", "")
                file_path = entry.get("file_path", "")

                if file_path and url:
                    # Convert to absolute path
                    full_path = self.html_dir.parent.parent / file_path
                    self.url_to_file_map[url] = full_path

    def get_html_file_for_url(self, url: str) -> Path | None:
        """Get HTML file path for a given URL.

        Args:
            url: URL to look up

        Returns:
            Path to HTML file or None if not found
        """
        # Normalize URL to full format
        if not url.startswith("http"):
            url = f"https://help.solidworks.com{url}"

        return self.url_to_file_map.get(url)

    def convert_html_to_markdown(self, html_path: Path) -> str:
        """Convert HTML file to Markdown.

        Args:
            html_path: Path to HTML file

        Returns:
            Markdown content
        """
        with html_path.open(encoding="utf-8") as f:
            html_content = f.read()

        # Convert to Markdown
        markdown = self.h2t.handle(html_content)

        return markdown

    def sanitize_filename(self, name: str) -> str:
        """Sanitize filename by removing invalid characters.

        Args:
            name: Original name

        Returns:
            Sanitized name safe for filesystem
        """
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")

        # Remove leading/trailing spaces and dots
        name = name.strip(". ")

        # Limit length to avoid filesystem issues
        if len(name) > 200:
            name = name[:200]

        return name

    def save_markdown(
        self,
        markdown_content: str,
        output_path: Path,
    ) -> dict[str, Any]:
        """Save Markdown content to file.

        Args:
            markdown_content: Markdown content to save
            output_path: Output file path

        Returns:
            Metadata about the saved file
        """
        # Create parent directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save file
        with output_path.open("w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Calculate hash
        content_hash = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()

        # Get path relative to current working directory (project root)
        try:
            relative_path = output_path.relative_to(Path.cwd())
        except ValueError:
            # Fallback if path is not under cwd
            relative_path = output_path

        return {
            "file_path": str(relative_path).replace("\\", "/"),
            "content_hash": content_hash,
            "content_length": len(markdown_content),
        }


def main() -> None:
    """Test the HTML to Markdown converter."""
    import sys

    if len(sys.argv) > 1:
        html_file = Path(sys.argv[1])
    else:
        print("Usage: python html_to_markdown.py <html_file>")
        sys.exit(1)

    if not html_file.exists():
        print(f"Error: File not found: {html_file}")
        sys.exit(1)

    # Create converter
    converter = HtmlToMarkdownConverter(
        html_dir=html_file.parent,
        metadata_file=Path("10_crawl_programming_guide/metadata/urls_crawled.jsonl"),
        output_dir=Path("11_extract_docs_md/output/markdown"),
    )

    # Convert file
    markdown = converter.convert_html_to_markdown(html_file)

    # Print result
    print(markdown)


if __name__ == "__main__":
    main()
