"""Tests for CRLF normalisation of shipped bundles."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from shared.line_endings import TEXT_SUFFIXES, normalize_file, normalize_tree, to_crlf  # noqa: E402


@pytest.mark.parametrize(
    "raw, expected",
    [
        (b"a\nb", b"a\r\nb"),                    # LF -> CRLF
        (b"a\r\nb", b"a\r\nb"),                  # already CRLF, unchanged
        (b"a\rb", b"a\r\nb"),                    # lone CR (classic Mac)
        (b"a\r\nb\nc\rd", b"a\r\nb\r\nc\r\nd"),  # mixed in one file
        (b"", b""),
        (b"no newline at all", b"no newline at all"),
        (b"trailing\n", b"trailing\r\n"),
    ],
)
def test_to_crlf(raw, expected):
    assert to_crlf(raw) == expected


def test_to_crlf_is_idempotent():
    """Re-running the export must not produce CRCRLF and must not churn the diff."""
    once = to_crlf(b"line one\nline two\n")
    assert to_crlf(once) == once


def test_normalize_file_reports_whether_bytes_changed(tmp_path):
    lf = tmp_path / "a.md"
    lf.write_bytes(b"x\ny\n")
    assert normalize_file(lf) is True
    assert lf.read_bytes() == b"x\r\ny\r\n"
    # Second pass is a no-op, so a rebuild does not rewrite every file.
    assert normalize_file(lf) is False


def test_normalize_tree_covers_nested_text_and_skips_other_formats(tmp_path):
    (tmp_path / "types" / "IFoo").mkdir(parents=True)
    (tmp_path / "types" / "IFoo" / "_overview.md").write_bytes(b"# Foo\nbar\n")
    (tmp_path / "manifest.json").write_bytes(b'{\n  "a": 1\n}')
    (tmp_path / "doc.xml").write_bytes(b"<a>\n</a>")
    # Not a shipped text format: rewriting it would corrupt the file.
    png = tmp_path / "logo.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n\x00raw\nbytes")
    original_png = png.read_bytes()

    changed, scanned = normalize_tree(tmp_path)

    assert scanned == 3
    assert changed == 3
    assert (tmp_path / "types" / "IFoo" / "_overview.md").read_bytes() == b"# Foo\r\nbar\r\n"
    assert (tmp_path / "manifest.json").read_bytes() == b'{\r\n  "a": 1\r\n}'
    assert png.read_bytes() == original_png


def test_normalize_tree_second_run_changes_nothing(tmp_path):
    (tmp_path / "a.md").write_bytes(b"one\ntwo\n")
    normalize_tree(tmp_path)
    changed, scanned = normalize_tree(tmp_path)
    assert (changed, scanned) == (0, 1)


def test_normalize_tree_tolerates_missing_root(tmp_path):
    """A phase may legitimately produce no output; that is not an error."""
    assert normalize_tree(tmp_path / "never-created") == (0, 0)


def test_normalize_tree_handles_non_utf8_bytes(tmp_path):
    """Transformation is defined on line-ending bytes, so undecodable content is
    passed through rather than crashing the export."""
    f = tmp_path / "odd.md"
    f.write_bytes(b"caf\xe9\nnext\n")  # latin-1, invalid UTF-8
    normalize_tree(tmp_path)
    assert f.read_bytes() == b"caf\xe9\r\nnext\r\n"


def test_text_suffixes_cover_what_the_bundle_ships():
    assert {".md", ".xml", ".json"} <= TEXT_SUFFIXES


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
