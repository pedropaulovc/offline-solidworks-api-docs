"""Rewrite URLs in Markdown files to work with new hierarchical structure."""

import re
from pathlib import Path
from typing import Dict
from urllib.parse import urljoin, urlparse


class UrlRewriter:
    """Rewrite URLs in Markdown files."""

    def __init__(self, url_to_markdown_map: Dict[str, Path]) -> None:
        """Initialize the URL rewriter.

        Args:
            url_to_markdown_map: Mapping of original URLs to new Markdown file paths
        """
        self.url_to_markdown_map = url_to_markdown_map

        # Pre-process URLs to handle different formats
        self._build_url_index()

    def _build_url_index(self) -> None:
        """Build an index of URLs for efficient lookup."""
        self.url_index: Dict[str, Path] = {}

        for url, md_path in self.url_to_markdown_map.items():
            # Store by full URL
            self.url_index[url] = md_path

            # Also store by path component (without query params)
            parsed = urlparse(url)
            path_only = parsed.path
            if path_only:
                self.url_index[path_only] = md_path

            # Store without domain
            if url.startswith("http"):
                without_domain = parsed.path
                if parsed.query:
                    without_domain += "?" + parsed.query
                if without_domain:
                    self.url_index[without_domain] = md_path

    def rewrite_markdown_file(self, md_file: Path, base_url: str) -> int:
        """Rewrite URLs in a Markdown file.

        Args:
            md_file: Path to Markdown file
            base_url: Base URL of the original HTML page

        Returns:
            Number of URLs rewritten
        """
        content = md_file.read_text(encoding="utf-8")
        new_content, count = self.rewrite_urls(content, base_url, md_file)

        if count > 0:
            md_file.write_text(new_content, encoding="utf-8")

        return count

    def rewrite_urls(self, content: str, base_url: str, source_file: Path) -> tuple[str, int]:
        """Rewrite URLs in content.

        Args:
            content: Markdown content
            base_url: Base URL of the original page
            source_file: Path to the source Markdown file

        Returns:
            Tuple of (rewritten content, number of rewrites)
        """
        rewrite_count = 0

        # Pattern to match markdown links: [text](url)
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"

        def replace_link(match: re.Match) -> str:
            nonlocal rewrite_count

            link_text = match.group(1)
            link_url = match.group(2)

            # Skip certain URLs
            if self._should_skip_url(link_url):
                return match.group(0)  # Return original

            # Resolve relative URL to absolute
            absolute_url = urljoin(base_url, link_url)

            # Find corresponding markdown file
            target_md = self._find_markdown_file(absolute_url)

            if target_md:
                # Calculate relative path from source to target
                relative_path = self._calculate_relative_path(source_file, target_md)

                # Replace .html with .md if present
                relative_path = re.sub(r"\.html?$", ".md", relative_path, flags=re.IGNORECASE)

                rewrite_count += 1
                return f"[{link_text}]({relative_path})"

            # URL not found in our index, return original
            return match.group(0)

        new_content = re.sub(link_pattern, replace_link, content)

        return new_content, rewrite_count

    def _should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped.

        Args:
            url: URL to check

        Returns:
            True if URL should be skipped
        """
        # Skip external URLs (starting with http:// or https://)
        if url.startswith("http://") or url.startswith("https://"):
            # But don't skip help.solidworks.com URLs
            if "help.solidworks.com" not in url:
                return True

        # Skip /sldworksapi/ URLs (API reference links)
        if "/sldworksapi/" in url:
            return True

        # Skip anchors only
        if url.startswith("#"):
            return True

        # Skip mailto links
        if url.startswith("mailto:"):
            return True

        return False

    def _find_markdown_file(self, url: str) -> Path | None:
        """Find the Markdown file corresponding to a URL.

        Args:
            url: URL to look up

        Returns:
            Path to Markdown file or None if not found
        """
        # Try exact match first
        if url in self.url_index:
            return self.url_index[url]

        # Try without query parameters
        parsed = urlparse(url)
        path_only = parsed.path

        if path_only in self.url_index:
            return self.url_index[path_only]

        # Try without domain
        if url.startswith("http"):
            without_domain = parsed.path
            if parsed.query:
                without_domain += "?" + parsed.query

            if without_domain in self.url_index:
                return self.url_index[without_domain]

        # Try with .htm extension replaced by .html
        if path_only.endswith(".htm"):
            html_path = path_only + "l"  # .html
            if html_path in self.url_index:
                return self.url_index[html_path]

        return None

    def _calculate_relative_path(self, source: Path, target: Path) -> str:
        """Calculate relative path from source to target.

        Args:
            source: Source file path
            target: Target file path

        Returns:
            Relative path as string
        """
        # Get the parent directories
        source_dir = source.parent
        target_path = target

        # Calculate relative path
        try:
            relative = target_path.relative_to(source_dir)
            return str(relative).replace("\\", "/")
        except ValueError:
            # Not a direct relative path, need to go up
            pass

        # Find common ancestor
        source_parts = list(source_dir.parts)
        target_parts = list(target_path.parts)

        # Find common prefix length
        common_length = 0
        for i, (s, t) in enumerate(zip(source_parts, target_parts)):
            if s == t:
                common_length = i + 1
            else:
                break

        # Calculate ups needed
        ups_needed = len(source_parts) - common_length

        # Build relative path
        relative_parts = [".."] * ups_needed + list(target_parts[common_length:])
        return "/".join(relative_parts)


def main() -> None:
    """Test URL rewriter."""
    import json

    # Build URL to Markdown map from metadata
    import jsonlines

    metadata_file = Path("110_extract_docs_md/metadata/files_created.jsonl")
    url_to_md: Dict[str, Path] = {}

    with jsonlines.open(metadata_file) as reader:
        for entry in reader:
            original_url = entry.get("original_url", "")
            markdown_path = entry.get("markdown_path", "")

            if original_url and markdown_path:
                full_url = f"https://help.solidworks.com{original_url}"
                url_to_md[full_url] = Path(markdown_path)
                url_to_md[original_url] = Path(markdown_path)

    print(f"Loaded {len(url_to_md)} URL mappings")

    # Create rewriter
    rewriter = UrlRewriter(url_to_md)

    # Find all markdown files and rewrite
    md_dir = Path("110_extract_docs_md/output/markdown")
    total_rewrites = 0

    for md_file in md_dir.rglob("*.md"):
        # Get original URL for this file from metadata
        with jsonlines.open(metadata_file) as reader:
            for entry in reader:
                if entry.get("markdown_path") == str(md_file):
                    original_url = entry.get("original_url", "")
                    base_url = f"https://help.solidworks.com{original_url}"

                    count = rewriter.rewrite_markdown_file(md_file, base_url)
                    if count > 0:
                        print(f"  Rewrote {count} URLs in {md_file.relative_to(md_dir)}")
                        total_rewrites += count
                    break

    print(f"\nTotal URL rewrites: {total_rewrites}")


if __name__ == "__main__":
    main()
