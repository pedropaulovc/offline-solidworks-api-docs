#!/usr/bin/env python
"""Convert the referenced pages crawled in Phase 115 to Markdown.

Mirrors Phase 110's output contract so Phase 120 can consume it unchanged: each
page becomes ``output/markdown/<path-under-api>.md`` and is recorded in
``metadata/files_created.jsonl`` with its ``original_url`` -> ``markdown_path``.
Unlike Phase 110 there is no TOC; files are laid out by their URL path, which is
inherently collision-free and greppable.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import jsonlines

REPO_ROOT = Path(__file__).parent.parent.resolve()
PHASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(REPO_ROOT / "110_extract_docs_md"))
from html_to_markdown import HtmlToMarkdownConverter  # noqa: E402

API_PREFIX = "2026/english/api/"


def markdown_relpath(url: str) -> str:
    """``.../api/swconst/DP_Dimensions.htm`` -> ``swconst/DP_Dimensions.md``."""
    path = urlparse(url).path.lstrip("/")
    rel = path[len(API_PREFIX):] if path.startswith(API_PREFIX) else path
    for suffix in (".html", ".htm"):
        if rel.endswith(suffix):
            rel = rel[: -len(suffix)]
            break
    return rel + ".md"


def main() -> int:
    input_meta = PHASE_DIR / "metadata" / "urls_crawled.jsonl"
    output_dir = PHASE_DIR / "output" / "markdown"
    files_created_path = PHASE_DIR / "metadata" / "files_created.jsonl"

    if not input_meta.exists():
        print(f"No crawl metadata at {input_meta}; run run_crawler.py first")
        return 1

    converter = HtmlToMarkdownConverter(
        html_dir=PHASE_DIR / "output" / "html",
        metadata_file=input_meta,
        output_dir=output_dir,
    )
    converter.load_metadata()

    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[dict] = []
    converted = failed = 0

    with jsonlines.open(input_meta) as reader:
        for entry in reader:
            url = entry.get("url")
            file_path = entry.get("file_path")
            if not url or not file_path:
                continue
            html_file = PHASE_DIR / file_path
            if not html_file.exists():
                print(f"  [SKIP] {url} (HTML missing)")
                failed += 1
                continue
            try:
                markdown = converter.convert_html_to_markdown(html_file)
                out_path = output_dir / markdown_relpath(url)
                meta = converter.save_markdown(markdown, out_path)
                created.append({
                    "original_url": urlparse(url).path,  # path form, matches Phase 110
                    "original_html": file_path,
                    "markdown_path": str(out_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                    "content_hash": meta["content_hash"],
                    "content_length": meta["content_length"],
                    "title": entry.get("title", ""),
                })
                converted += 1
                print(f"  [OK] {markdown_relpath(url)}")
            except Exception as e:  # noqa: BLE001
                print(f"  [FAIL] {url} - {e}")
                failed += 1

    with jsonlines.open(files_created_path, mode="w") as writer:
        writer.write_all(created)

    summary = {
        "phase": "115_crawl_referenced_pages",
        "converted_files": converted,
        "failed_files": failed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(PHASE_DIR / "metadata" / "extraction_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nConverted {converted} referenced pages ({failed} failed) -> {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
