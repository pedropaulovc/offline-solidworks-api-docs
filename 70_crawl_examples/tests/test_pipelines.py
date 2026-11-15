"""Tests for the pipelines"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from scrapy.http import HtmlResponse, Request, Response

from solidworks_scraper import pipelines
from solidworks_scraper.pipelines import HtmlSavePipeline, ValidationPipeline
from solidworks_scraper.spiders.examples_spider import ExamplesSpider

from shared.constants import SOLIDWORKS_API_FULL_BASE_URL, SOLIDWORKS_API_VERSION


@pytest.fixture
def marker_pipeline(tmp_path, monkeypatch):
    """HtmlSavePipeline writing its corpus and version marker under tmp_path."""
    marker = tmp_path / "crawl_version.txt"
    monkeypatch.setattr(pipelines, "CRAWL_VERSION_FILE", marker)
    pipeline = HtmlSavePipeline()
    pipeline.output_dir = tmp_path / "html"
    pipeline.output_dir.mkdir()
    return pipeline, marker


def test_version_marker_written_only_after_clean_finish(marker_pipeline, spider):
    pipeline, marker = marker_pipeline

    pipeline.open_spider(spider)
    (pipeline.output_dir / "page.htm").write_text("x")
    assert marker.read_text().strip() != SOLIDWORKS_API_VERSION  # partial corpus while crawling

    pipeline.spider_closed(spider, "finished")
    assert marker.read_text().strip() == SOLIDWORKS_API_VERSION


def test_version_marker_not_current_after_interrupted_crawl(marker_pipeline, spider):
    pipeline, marker = marker_pipeline
    marker.write_text(f"{SOLIDWORKS_API_VERSION}\n")

    pipeline.open_spider(spider)
    pipeline.spider_closed(spider, "shutdown")

    assert marker.read_text().strip() != SOLIDWORKS_API_VERSION


def test_resume_after_interrupt_restores_version_marker(marker_pipeline, spider):
    """An interrupted crawl leaves this year's pages; a --resume run that finishes marks them current."""
    pipeline, marker = marker_pipeline
    pipeline.open_spider(spider)
    (pipeline.output_dir / "page.htm").write_text("x")
    pipeline.spider_closed(spider, "shutdown")

    resumed = HtmlSavePipeline()
    resumed.output_dir = pipeline.output_dir
    resumed.open_spider(spider)
    resumed.spider_closed(spider, "finished")

    assert marker.read_text().strip() == SOLIDWORKS_API_VERSION


def test_version_marker_not_current_when_pages_failed(marker_pipeline, spider):
    pipeline, marker = marker_pipeline
    pipeline.open_spider(spider)
    spider.stats["failed_pages"] = 3

    pipeline.spider_closed(spider, "finished")

    assert marker.read_text().strip() != SOLIDWORKS_API_VERSION


def test_version_marker_not_current_after_callback_exception(marker_pipeline, spider):
    """Exceptions in parse_page never reach the errback; the crawler's stats still record them."""
    pipeline, marker = marker_pipeline
    spider.crawler = Mock()
    spider.crawler.stats.get_value.side_effect = lambda key, default=None: 2 if key == "spider_exceptions/count" else 0
    pipeline.open_spider(spider)

    pipeline.spider_closed(spider, "finished")

    assert marker.read_text().strip() != SOLIDWORKS_API_VERSION


def test_version_marker_not_current_after_save_failure(marker_pipeline, spider):
    """A page whose write raises leaves a hole, whatever LOG_LEVEL hides from the log counters."""
    pipeline, marker = marker_pipeline
    pipeline.open_spider(spider)
    url = f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/Some_Example.htm"
    pipeline.url_to_file_path(url).mkdir(parents=True)  # a directory where the page file should go

    item = pipeline.process_item({"url": url, "content": "<html>example</html>"}, spider)
    pipeline.spider_closed(spider, "finished")

    assert "save_error" in item
    assert spider.stats["save_failures"] == 1
    assert marker.read_text().strip() != SOLIDWORKS_API_VERSION


@pytest.mark.parametrize("source_state", ["malformed", "missing"])
def test_version_marker_not_current_after_url_source_failure(marker_pipeline, spider, tmp_path, source_state):
    """A malformed or missing example-URL source drops whole URL families; that corpus is not complete."""
    pipeline, marker = marker_pipeline
    xml = tmp_path / "api_member_details.xml"
    if source_state == "malformed":
        xml.write_text("<Types><Type>")
    spider._load_urls_from_file(xml, "member details")
    pipeline.open_spider(spider)

    pipeline.spider_closed(spider, "finished")

    assert spider.stats["url_source_failures"] == 1
    assert marker.read_text().strip() != SOLIDWORKS_API_VERSION


def test_version_marker_not_current_after_next_data_parse_failure(marker_pipeline, spider):
    """A page whose __NEXT_DATA__ is not JSON is never saved; that corpus is not complete."""
    pipeline, marker = marker_pipeline
    url = f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/test.htm"
    body = b'<html><script id="__NEXT_DATA__" type="application/json">{not json</script></html>'
    response = HtmlResponse(
        url=url, request=Request(url), body=body, encoding="utf-8", headers={"Content-Type": "text/html"}
    )
    pipeline.open_spider(spider)

    assert list(spider.parse_page(response)) == []
    pipeline.spider_closed(spider, "finished")

    assert spider.stats["parse_failures"] == 1
    assert marker.read_text().strip() != SOLIDWORKS_API_VERSION


def test_older_corpus_marker_is_dropped(marker_pipeline, spider):
    """A --resume run on last year's pages mixes years; no year may claim the corpus afterwards."""
    pipeline, marker = marker_pipeline
    marker.write_text("1999\n")
    (pipeline.output_dir / "old.htm").write_text("x")

    pipeline.open_spider(spider)
    pipeline.spider_closed(spider, "finished")

    assert not marker.exists()


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
    url = f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/test.htm"
    path = pipeline.url_to_file_path(url)
    assert "sldworksapi" in str(path)
    assert str(path).endswith("test.htm")

    # URL with query parameters: a deterministic hash is appended for uniqueness
    # and the filename is normalized to .html.
    url_with_query = f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/test.htm?id=123"
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
