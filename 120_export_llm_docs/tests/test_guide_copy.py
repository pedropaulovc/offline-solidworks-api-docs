"""Tests for how Phase 120 ships the guide Markdown under ``docs/``."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from export_pipeline import ExportPipeline

from shared.constants import SOLIDWORKS_API_BASE_PATH


def _guide_root(phase_dir: Path, pages: dict[str, str]) -> Path:
    """A guide phase whose manifest lists ``pages`` (path under the root -> help page)."""
    root = phase_dir / "output" / "markdown"
    entries = []
    for rel, page in pages.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(f"# {rel}\n", encoding="utf-8")
        entries.append({
            "original_url": f"{SOLIDWORKS_API_BASE_PATH}/{page}",
            "markdown_path": f"{phase_dir.name}/output/markdown/{rel}",
        })
    (phase_dir / "metadata").mkdir(parents=True)
    (phase_dir / "metadata" / "files_created.jsonl").write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8"
    )
    return root


def test_only_manifest_listed_pages_ship(tmp_path):
    """A stale file an earlier run left in a guide tree is not copied into the bundle."""
    root = _guide_root(tmp_path / "115", {"swconst/DP_Units.md": "swconst/DP_Units.htm"})
    (root / "swcommands").mkdir()
    (root / "swcommands" / "SolidWorks.Interop.swcommands.md").write_text("old\n", encoding="utf-8")
    pipeline = ExportPipeline(str(tmp_path / "out"))

    guide_pages = pipeline._load_guide_pages([str(root)])
    page_urls = pipeline._copy_guide_pages(guide_pages)

    shipped = sorted(p.relative_to(tmp_path / "out").as_posix() for p in (tmp_path / "out").rglob("*.md"))
    assert shipped == ["docs/swconst/DP_Units.md"]
    assert page_urls == {"docs/swconst/DP_Units.md": f"{SOLIDWORKS_API_BASE_PATH}/swconst/DP_Units.htm"}
    assert pipeline._build_guide_links(guide_pages) == {"dp_units.htm": "docs/swconst/DP_Units.md"}
    assert pipeline.stats.programming_guide_files == 1


def test_two_pages_at_one_bundle_path_fail(tmp_path):
    """Two guide phases writing the same ``docs/`` path would silently overwrite one."""
    first = _guide_root(tmp_path / "110", {"swconst/A.md": "sldworksapiprogguide/A.htm"})
    second = _guide_root(tmp_path / "115", {"swconst/A.md": "swconst/A.htm"})
    pipeline = ExportPipeline(str(tmp_path / "out"))

    with pytest.raises(ValueError, match="docs/swconst/A.md"):
        pipeline._copy_guide_pages(pipeline._load_guide_pages([str(first), str(second)]))


def test_paths_differing_only_in_case_fail(tmp_path):
    """Unpacked on Windows or macOS, one of the two files would replace the other."""
    root = _guide_root(tmp_path / "115", {
        "swcommands/SOLIDWORKS.Interop.swcommands.md": "swcommands/SOLIDWORKS.Interop.swcommands.htm",
        "swcommands/SolidWorks.Interop.swcommands.md": "swcommands/SolidWorks.Interop.swcommands.htm",
    })
    pipeline = ExportPipeline(str(tmp_path / "out"))
    pipeline._copy_guide_pages(pipeline._load_guide_pages([str(root)]))

    with pytest.raises(ValueError, match="differ only in case"):
        pipeline._check_case_collisions()


def test_manifest_without_its_tree_is_skipped(tmp_path, capsys):
    """After a fresh clone the committed manifest lists pages output/ does not have: the
    root is skipped with a warning (as Phase 90 does), not a crash halfway through."""
    root = _guide_root(tmp_path / "115", {"swconst/DP_Units.md": "swconst/DP_Units.htm"})
    (root / "swconst" / "DP_Units.md").unlink()
    pipeline = ExportPipeline(str(tmp_path / "out"))

    guide_pages = pipeline._load_guide_pages([str(root)])

    assert guide_pages == []
    assert pipeline._build_guide_links(guide_pages) == {}
    assert "swconst/DP_Units.md" in capsys.readouterr().out
