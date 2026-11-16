"""Tests for shared.guide_pages."""

import json
from pathlib import Path

import pytest

from shared.guide_pages import GuidePage, GuidePagesUnavailable, case_collisions, read_guide_pages


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
    for name in ("A.md", "B.md", "Stale.md"):
        (root / "swconst" / name).write_text(f"# {name}\n", encoding="utf-8")

    assert read_guide_pages(root) == [
        GuidePage("/2027/english/api/swconst/A.htm", "swconst/A.md", root / "swconst" / "A.md"),
        GuidePage("/2027/english/api/swconst/B.htm", "swconst/B.md", root / "swconst" / "B.md"),
    ]


def test_missing_manifest_raises(tmp_path):
    root = tmp_path / "110" / "output" / "markdown"
    root.mkdir(parents=True)

    with pytest.raises(GuidePagesUnavailable, match="no manifest"):
        read_guide_pages(root)


def test_manifest_without_its_tree_raises(tmp_path):
    """The manifests are committed and output/ is gitignored: after a fresh clone there
    is a manifest but no tree. Callers skip such a root."""
    root = _write_manifest(tmp_path / "115", [
        {"original_url": "/2027/english/api/swconst/A.htm", "markdown_path": "115/output/markdown/swconst/A.md"},
    ])

    with pytest.raises(GuidePagesUnavailable, match="no Markdown tree"):
        read_guide_pages(root)


def test_tree_missing_a_listed_page_fails(tmp_path):
    """A tree that is there but lacks a listed page is damaged or partly regenerated;
    skipping the whole root would quietly ship a bundle without that phase."""
    root = _write_manifest(tmp_path / "115", [
        {"original_url": "/2027/english/api/swconst/A.htm", "markdown_path": "115/output/markdown/swconst/A.md"},
        {"original_url": "/2027/english/api/swconst/B.htm", "markdown_path": "115/output/markdown/swconst/B.md"},
    ])
    (root / "swconst").mkdir(parents=True)
    (root / "swconst" / "A.md").write_text("# A\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="swconst/B.md"):
        read_guide_pages(root)


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
