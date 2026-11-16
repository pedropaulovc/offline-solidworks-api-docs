"""Tests for the Phase 115 HTML -> Markdown step (extract_markdown.py)."""

import importlib.util
import json
from pathlib import Path

from shared.constants import SOLIDWORKS_API_BASE_PATH, SOLIDWORKS_API_FULL_BASE_URL

PHASE_DIR = Path(__file__).resolve().parent.parent


def _load_extract_markdown():
    # Loaded by path: Phase 110 has a module of the same name on the test path.
    spec = importlib.util.spec_from_file_location("referenced_extract_markdown", PHASE_DIR / "extract_markdown.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_writes_only_this_runs_pages(tmp_path, monkeypatch):
    """A page an earlier run converted but this crawl no longer has is gone, an
    image-only page is skipped, and CHM aliases become page-relative links."""
    extract_markdown = _load_extract_markdown()
    phase_dir = tmp_path / "115_crawl_referenced_pages"
    monkeypatch.setattr(extract_markdown, "PHASE_DIR", phase_dir)
    monkeypatch.setattr(extract_markdown, "REPO_ROOT", tmp_path)

    html_dir = phase_dir / "output" / "html"
    html_dir.mkdir(parents=True)
    pages = {
        "swconst/DP_Units.htm": '<p>Units, see <a href="ms-its:sldworksapi.chm::/Units_Example.htm">example</a>.</p>',
        "sldworksapiprogguide/Miscellaneous/FreeFormCurves.htm": '<img src="FREEFORMCURVES.BMP">',
    }
    crawled = []
    for index, (path, html) in enumerate(pages.items()):
        (html_dir / f"{index}.html").write_text(html, encoding="utf-8")
        crawled.append({"url": f"{SOLIDWORKS_API_FULL_BASE_URL}/{path}", "file_path": f"output/html/{index}.html"})
    metadata_dir = phase_dir / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "urls_crawled.jsonl").write_text(
        "".join(json.dumps(entry) + "\n" for entry in crawled), encoding="utf-8"
    )
    markdown_dir = phase_dir / "output" / "markdown"
    (markdown_dir / "swcommands").mkdir(parents=True)
    (markdown_dir / "swcommands" / "SolidWorks.Interop.swcommands.md").write_text("old\n", encoding="utf-8")

    assert extract_markdown.main() == 0

    assert [p.relative_to(markdown_dir).as_posix() for p in markdown_dir.rglob("*.md")] == ["swconst/DP_Units.md"]
    units = (markdown_dir / "swconst" / "DP_Units.md").read_text(encoding="utf-8")
    assert "[example](../sldworksapi/Units_Example.htm)" in units
    with (metadata_dir / "files_created.jsonl").open(encoding="utf-8") as f:
        assert [json.loads(line)["markdown_path"] for line in f] == [
            "115_crawl_referenced_pages/output/markdown/swconst/DP_Units.md"
        ]
    summary = json.loads((metadata_dir / "extraction_summary.json").read_text(encoding="utf-8"))
    assert summary["image_only_pages"] == [f"{SOLIDWORKS_API_BASE_PATH}/sldworksapiprogguide/Miscellaneous/FreeFormCurves.htm"]
