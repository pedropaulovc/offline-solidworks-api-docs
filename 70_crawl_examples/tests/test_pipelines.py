"""Tests for the pipelines"""

import tempfile
from pathlib import Path

import pytest
from scrapy.http import Request, Response

from solidworks_scraper.pipelines import HtmlSavePipeline, ValidationPipeline
from solidworks_scraper.spiders.examples_spider import ExamplesSpider


@pytest.fixture
def spider():
    """Create a spider instance for testing"""
    return ExamplesSpider()


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir)


def test_html_save_pipeline_url_to_file_path():
    """Test URL to file path conversion"""
    pipeline = HtmlSavePipeline()

    # Simple URL (no query params): the original .htm extension is preserved.
    # This is required by phase 80 (parse_examples.py), which reads example files
    # via rglob('*.htm'); rewriting to .html would make it find zero examples.
    url = "https://help.solidworks.com/2026/english/api/sldworksapi/test.htm"
    path = pipeline.url_to_file_path(url)
    assert "sldworksapi" in str(path)
    assert str(path).endswith("test.htm")

    # URL with query parameters: a deterministic hash is appended for uniqueness
    # and the filename is normalized to .html.
    url_with_query = "https://help.solidworks.com/2026/english/api/sldworksapi/test.htm?id=123"
    path_with_query = pipeline.url_to_file_path(url_with_query)
    path_str = str(path_with_query)
    assert "sldworksapi" in path_str
    assert "test_" in path_str  # Should have hash appended
    assert path_str.endswith(".html")


def test_validation_pipeline_checks_required_fields(spider):
    """Test that validation pipeline checks for required fields"""
    pipeline = ValidationPipeline()

    # Complete item
    complete_item = {
        "url": "https://example.com/test.htm",
        "content": "<html><body>Test content with enough text to pass validation</body></html>",
        "content_hash": "abc123",
    }

    result = pipeline.process_item(complete_item, spider)
    assert result == complete_item  # Should pass through unchanged

    # Incomplete item (missing content_hash)
    incomplete_item = {
        "url": "https://example.com/test.htm",
        "content": "<html><body>Test content</body></html>",
    }

    # Should still process but log warning (check via spider logger)
    result = pipeline.process_item(incomplete_item, spider)
    assert result == incomplete_item


def test_validation_pipeline_warns_on_short_content(spider):
    """Test that validation pipeline warns about suspiciously short content"""
    pipeline = ValidationPipeline()

    short_item = {
        "url": "https://example.com/test.htm",
        "content": "<html></html>",  # Too short
        "content_hash": "abc123",
    }

    # Should process but log warning
    result = pipeline.process_item(short_item, spider)
    assert result == short_item


def test_pipeline_skips_error_items(spider):
    """Test that pipelines skip error items"""
    pipeline = ValidationPipeline()

    error_item = {
        "type": "error",
        "url": "https://example.com/failed.htm",
        "error": "Connection timeout",
    }

    result = pipeline.process_item(error_item, spider)
    assert result == error_item  # Should pass through unchanged
