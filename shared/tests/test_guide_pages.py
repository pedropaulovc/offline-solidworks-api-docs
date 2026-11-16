"""Tests for shared.guide_pages."""

import json
from pathlib import Path

import pytest

from shared.guide_pages import GuidePage, case_collisions, read_guide_pages


def _write_manifest(phase_dir: Path, entries: list[dict]) -> Path:
    metadata_dir = phase_dir / "metadata"
    metadata_dir.mkdir(parents=True)
    (metadata_dir / "files_created.jsonl").write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8"
    )
    return phase_dir / "output" / "markdown"


def test_guide_pages_come_from_the_manifest_only(tmp_path):
    """A file on disk the manifest does not list is not a page; listed pages come back
    sorted by their path under the Markdown root."""
    root = _write_manifest(tmp_path / "115", [
        {"original_url": "/2027/english/api/swconst/B.htm", "markdown_path": "115/output/markdown/swconst/B.md"},
        {"original_url": "/2027/english/api/swconst/A.htm", "markdown_path": "115\\output\\markdown\\swconst\\A.md"},
    ])
    (root / "swconst").mkdir(parents=True)
    (root / "swconst" / "Stale.md").write_text("old\n", encoding="utf-8")

    assert read_guide_pages(root) == [
        GuidePage("/2027/english/api/swconst/A.htm", "swconst/A.md", root / "swconst" / "A.md"),
        GuidePage("/2027/english/api/swconst/B.htm", "swconst/B.md", root / "swconst" / "B.md"),
    ]


def test_missing_manifest_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_guide_pages(tmp_path / "110" / "output" / "markdown")


def test_case_collisions():
    paths = [
        "docs/swcommands/SolidWorks.Interop.swcommands.md",
        "docs/swcommands/SOLIDWORKS.Interop.swcommands.md",
        "docs/swconst/A.md",
        "types/IFoo/_overview.md",
    ]
    assert case_collisions(paths) == [[
        "docs/swcommands/SOLIDWORKS.Interop.swcommands.md",
        "docs/swcommands/SolidWorks.Interop.swcommands.md",
    ]]
    assert case_collisions(paths[1:]) == []
