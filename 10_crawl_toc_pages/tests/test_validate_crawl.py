"""Regression tests for the crawl validator (validate_crawl.py).

These pin down the record schema the validator reads. The crawler writes a
``url`` field (not ``print_url``) and stores expandToc API responses as ``.json``
files; an earlier validator expected ``print_url`` and treated every record as a
duplicate / out-of-boundary / missing-HTML, producing thousands of false-positive
warnings. These tests guard against that drift recurring.
"""

import importlib.util
import json
from pathlib import Path

import jsonlines

# validate_crawl.py lives in a numerically-prefixed dir that isn't importable by
# name, so load it directly from its path.
_VALIDATOR_PATH = Path(__file__).parent.parent / "validate_crawl.py"
_spec = importlib.util.spec_from_file_location("validate_crawl", _VALIDATOR_PATH)
validate_crawl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_crawl)
CrawlValidator = validate_crawl.CrawlValidator


def _write_records(tmp_path: Path, records: list[dict]) -> Path:
    """Lay out an output/ + metadata/ tree and return the output dir."""
    output_dir = tmp_path / "output"
    (output_dir / "html").mkdir(parents=True)
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    with jsonlines.open(metadata_dir / "urls_crawled.jsonl", "w") as writer:
        writer.write_all(records)
    return output_dir


def _content_record(name: str, suffix: str = ".html") -> dict:
    """A normal content-page record as the crawler writes it (note: ``url``)."""
    return {
        "url": f"https://help.solidworks.com/2026/english/api/sldworksapi/{name}{suffix}",
        "file_path": f"output\\html\\sldworksapi\\{name}{suffix}",
        "content_hash": f"hash_{name}",
        "content_length": 5000,
        "status_code": 200,
        "title": name,
    }


def _expandtoc_record(node_id: str) -> dict:
    """An expandToc API record — saved as .json, query-param boundary form."""
    return {
        "url": (
            "https://help.solidworks.com/expandToc?version=2026&language=english"
            f"&product=api&queryParam=?id={node_id}"
        ),
        "file_path": f"output\\html\\expandToc_id_{node_id}.json",
        "content_hash": f"toc_{node_id}",
        "content_length": 1000,
        "status_code": 200,
        "title": "expandToc JSON",
    }


def test_url_field_is_recognized(tmp_path):
    """The canonical ``url`` field must not be reported as a missing field."""
    output_dir = _write_records(tmp_path, [_content_record("A"), _content_record("B")])
    validator = CrawlValidator(output_dir)
    validator._validate_urls_crawled(verbose=False)

    assert not any("Missing field 'url'" in w for w in validator.warnings)
    assert not any("Missing field 'print_url'" in w for w in validator.warnings)


def test_unique_urls_are_not_flagged_as_duplicates(tmp_path):
    """Distinct URLs must not collide (the old None-key bug flagged every record)."""
    records = [_content_record(n) for n in ("A", "B", "C")] + [_expandtoc_record("2.1")]
    output_dir = _write_records(tmp_path, records)
    validator = CrawlValidator(output_dir)
    validator._validate_urls_crawled(verbose=False)

    assert not any("Duplicate URL" in w for w in validator.warnings)


def test_genuine_duplicate_url_is_flagged(tmp_path):
    """A real repeated URL should still be reported."""
    output_dir = _write_records(tmp_path, [_content_record("A"), _content_record("A")])
    validator = CrawlValidator(output_dir)
    validator._validate_urls_crawled(verbose=False)

    assert any("Duplicate URL" in w for w in validator.warnings)


def test_expandtoc_url_is_within_boundary(tmp_path):
    """expandToc API URLs use the query-param form and are in-boundary."""
    output_dir = _write_records(tmp_path, [_expandtoc_record("2"), _content_record("A")])
    validator = CrawlValidator(output_dir)
    validator._validate_urls_crawled(verbose=False)

    assert not any("outside boundary" in w for w in validator.warnings)


def test_truly_out_of_boundary_url_is_flagged(tmp_path):
    """A URL for a different year/product is still caught."""
    stray = {
        "url": "https://help.solidworks.com/2017/english/api/sldworksapi/Old.html",
        "file_path": "output\\html\\Old.html",
        "content_hash": "stray",
        "content_length": 100,
    }
    output_dir = _write_records(tmp_path, [stray])
    validator = CrawlValidator(output_dir)
    validator._validate_urls_crawled(verbose=False)

    assert any("outside boundary" in w for w in validator.warnings)


def test_json_expandtoc_records_not_reported_as_missing_html(tmp_path):
    """expandToc .json responses have no HTML file and must not be 'missing HTML'."""
    records = [_content_record("A"), _expandtoc_record("2"), _expandtoc_record("2.1")]
    output_dir = _write_records(tmp_path, records)
    # Create only the HTML file on disk; the .json responses intentionally absent.
    html_file = output_dir / "html" / "sldworksapi" / "A.html"
    html_file.parent.mkdir(parents=True, exist_ok=True)
    html_file.write_text("<html><body>content</body></html>", encoding="utf-8")

    validator = CrawlValidator(output_dir)
    validator._validate_html_files(verbose=False)

    assert not any("without HTML files" in w for w in validator.warnings)
