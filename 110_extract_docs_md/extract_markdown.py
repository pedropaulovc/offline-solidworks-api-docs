"""Main script to extract HTML to Markdown with hierarchical file organization."""

import json
import jsonlines
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from html_to_markdown import HtmlToMarkdownConverter
from toc_builder import TocNode, TocTreeBuilder
from url_rewriter import UrlRewriter


class MarkdownExtractor:
    """Extract and reorganize documentation as Markdown files."""

    def __init__(
        self,
        input_dir: Path = Path("100_crawl_programming_guide/output/html"),
        metadata_file: Path = Path("100_crawl_programming_guide/metadata/urls_crawled.jsonl"),
        output_dir: Path = Path("110_extract_docs_md/output/markdown"),
        metadata_dir: Path = Path("110_extract_docs_md/metadata"),
    ) -> None:
        """Initialize the Markdown extractor.

        Args:
            input_dir: Directory containing HTML files and expandToc JSONs
            metadata_file: Path to urls_crawled.jsonl metadata file
            output_dir: Output directory for Markdown files
            metadata_dir: Directory for metadata files
        """
        self.input_dir = input_dir
        self.metadata_file = metadata_file
        self.output_dir = output_dir
        self.metadata_dir = metadata_dir

        # Initialize components
        self.toc_builder = TocTreeBuilder(input_dir)
        self.converter = HtmlToMarkdownConverter(
            html_dir=input_dir,
            metadata_file=metadata_file,
            output_dir=output_dir,
        )

        # Statistics
        self.stats = {
            "total_nodes": 0,
            "converted_files": 0,
            "skipped_files": 0,
            "failed_files": 0,
            "start_time": datetime.now(timezone.utc).isoformat(),
        }

        # Metadata tracking
        self.files_created: list[dict[str, Any]] = []

    def run(self) -> None:
        """Run the extraction process."""
        print("Phase 11: Extract Documentation to Markdown")
        print("=" * 60)

        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        # Load metadata
        print("\n1. Loading metadata...")
        self.converter.load_metadata()
        print(f"   Loaded {len(self.converter.url_to_file_map)} URL mappings")

        # Build TOC tree
        print("\n2. Building TOC tree...")
        root = self.toc_builder.build_tree()
        self.stats["total_nodes"] = len(self.toc_builder.nodes)
        print(f"   Built tree with {self.stats['total_nodes']} nodes")

        # Process all nodes
        print("\n3. Converting HTML to Markdown and reorganizing...")
        self._process_node(root, root, [])

        # Save metadata
        print("\n4. Saving metadata...")
        self._save_metadata()

        # Rewrite URLs
        print("\n5. Rewriting relative URLs...")
        self._rewrite_urls()

        # Print statistics
        print("\n" + "=" * 60)
        print("Extraction Complete!")
        print(f"  Total nodes: {self.stats['total_nodes']}")
        print(f"  Converted: {self.stats['converted_files']}")
        print(f"  Skipped: {self.stats['skipped_files']}")
        print(f"  Failed: {self.stats['failed_files']}")
        print(f"  URLs rewritten: {self.stats.get('urls_rewritten', 0)}")
        print(f"  Output: {self.output_dir}")

    def _process_node(
        self,
        node: TocNode,
        root: TocNode,
        path_segments: list[str],
    ) -> None:
        """Process a single TOC node and its children.

        Args:
            node: Current node to process
            root: Root node of the tree
            path_segments: Current path segments (for recursion)
        """
        # Process current node if it's a leaf (content page)
        if node.is_leaf and node.url:
            # Leaf nodes: create file in current directory (don't add to path)
            self._convert_node(node, path_segments)
        else:
            # Non-leaf nodes: add to path for children
            if node.id != root.id:
                # Get sanitized directory name from node name
                dir_name = self.converter.sanitize_filename(node.name)
                current_path = path_segments + [dir_name]
            else:
                current_path = path_segments

            # Recursively process children
            for child in node.children:
                self._process_node(child, root, current_path)

    def _convert_node(
        self,
        node: TocNode,
        path_segments: list[str],
    ) -> None:
        """Convert a single node's HTML to Markdown.

        Args:
            node: Node to convert
            path_segments: Directory path segments
        """
        # Get HTML file for this node's URL
        full_url = f"https://help.solidworks.com{node.url}"
        html_file = self.converter.get_html_file_for_url(full_url)

        if not html_file or not html_file.exists():
            print(f"   [SKIP] {node.name} (HTML not found)")
            self.stats["skipped_files"] += 1
            return

        try:
            # Convert HTML to Markdown
            markdown_content = self.converter.convert_html_to_markdown(html_file)

            # Determine output path
            # Use sanitized node name as filename
            filename = self.converter.sanitize_filename(node.name) + ".md"
            output_path = self.output_dir / Path(*path_segments) / filename

            # Save Markdown file
            metadata = self.converter.save_markdown(markdown_content, output_path)

            # Track file creation
            self.files_created.append(
                {
                    "node_id": node.id,
                    "node_name": node.name,
                    "original_url": node.url,
                    "original_html": str(html_file.relative_to(self.input_dir.parent.parent)),
                    "markdown_path": metadata["file_path"],
                    "content_hash": metadata["content_hash"],
                    "content_length": metadata["content_length"],
                    "path_segments": path_segments,
                }
            )

            print(f"   [OK] {'/'.join(path_segments)}/{filename}")
            self.stats["converted_files"] += 1

        except Exception as e:
            print(f"   [FAIL] {node.name} - {e!s}")
            self.stats["failed_files"] += 1

    def _save_metadata(self) -> None:
        """Save metadata files."""
        # Save files_created.jsonl
        files_created_path = self.metadata_dir / "files_created.jsonl"
        with jsonlines.open(files_created_path, mode="w") as writer:
            writer.write_all(self.files_created)

        print(f"   Saved: {files_created_path}")

        # Save extraction_stats.json
        self.stats["end_time"] = datetime.now(timezone.utc).isoformat()
        stats_path = self.metadata_dir / "extraction_stats.json"
        with stats_path.open("w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2)

        print(f"   Saved: {stats_path}")

        # Save manifest.json
        manifest = {
            "phase": "110_extract_docs_md",
            "description": "Convert HTML documentation to Markdown with hierarchical organization",
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": self.stats,
        }

        manifest_path = self.metadata_dir / "manifest.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        print(f"   Saved: {manifest_path}")

    def _rewrite_urls(self) -> None:
        """Rewrite URLs in all Markdown files."""
        # Build URL to Markdown path mapping
        url_to_md: dict[str, Path] = {}

        for entry in self.files_created:
            original_url = entry.get("original_url", "")
            markdown_path = entry.get("markdown_path", "")

            if original_url and markdown_path:
                # Full URL
                full_url = f"https://help.solidworks.com{original_url}"
                url_to_md[full_url] = Path(markdown_path)
                # Also store without domain
                url_to_md[original_url] = Path(markdown_path)

        print(f"   Built mapping with {len(url_to_md)} URLs")

        # Create URL rewriter
        rewriter = UrlRewriter(url_to_md)

        # Rewrite URLs in all files
        total_rewrites = 0

        for entry in self.files_created:
            markdown_path = Path(entry.get("markdown_path", ""))
            original_url = entry.get("original_url", "")

            if not markdown_path.exists():
                continue

            base_url = f"https://help.solidworks.com{original_url}"
            count = rewriter.rewrite_markdown_file(markdown_path, base_url)
            total_rewrites += count

        self.stats["urls_rewritten"] = total_rewrites
        print(f"   Rewrote {total_rewrites} URLs across {len(self.files_created)} files")


def main() -> None:
    """Main entry point."""
    extractor = MarkdownExtractor()
    extractor.run()


if __name__ == "__main__":
    main()
