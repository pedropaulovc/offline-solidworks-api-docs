"""The guide pages a Markdown phase (110, 115) wrote, as its manifest lists them.

Phases 90 and 120 ship guide Markdown. They take the page list from the phase's
``metadata/files_created.jsonl``, not from the files on disk, so a file the
current run did not write (left by an earlier run, or put there by hand) never
ships.
"""

import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GuidePage:
    """One page of a guide Markdown tree."""

    original_url: str  # help path of the source page: /2027/english/api/swconst/X.htm
    rel_path: str  # path under the Markdown root: swconst/X.md
    file: Path


def manifest_path(markdown_root: Path) -> Path:
    """``<phase>/metadata/files_created.jsonl`` for ``<phase>/output/markdown``."""
    return markdown_root.parent.parent / "metadata" / "files_created.jsonl"


class GuidePagesUnavailable(Exception):
    """A guide root whose pages cannot be shipped: the Markdown tree or its manifest is
    missing, or the manifest lists a page that is not in the tree (a manifest
    committed while ``output/`` is gitignored, after a fresh clone)."""


def read_guide_pages(markdown_root: Path) -> list[GuidePage]:
    """The pages the manifest beside ``markdown_root`` lists, sorted by ``rel_path``.

    Raises GuidePagesUnavailable unless the manifest and every page it lists exist.
    """
    manifest = manifest_path(markdown_root)
    if not manifest.exists():
        raise GuidePagesUnavailable(f"no manifest at {manifest}")
    pages = []
    with open(manifest, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            # markdown_path is repo-relative and always under ".../output/markdown/".
            rel = entry["markdown_path"].replace("\\", "/").split("output/markdown/", 1)[-1]
            pages.append(GuidePage(entry["original_url"], rel, markdown_root / rel))
    missing = [page.rel_path for page in pages if not page.file.exists()]
    if missing:
        raise GuidePagesUnavailable(
            f"{manifest} lists {len(missing)} page(s) not in {markdown_root} "
            f"(e.g. {missing[0]}); rerun that phase"
        )
    return sorted(pages, key=lambda page: page.rel_path)


def case_collisions(paths: Iterable[str]) -> list[list[str]]:
    """Groups of paths that differ only in case, each sorted.

    On Windows and macOS, the default file systems are case-insensitive: unpacking
    a bundle that holds two such paths keeps only one of them.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        groups[path.casefold()].append(path)
    return sorted(sorted(group) for group in groups.values() if len(group) > 1)
