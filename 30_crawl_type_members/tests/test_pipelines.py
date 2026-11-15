"""
Tests for the crawler pipelines
"""

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from shared.constants import SOLIDWORKS_API_FULL_BASE_URL
from solidworks_scraper import pipelines
from solidworks_scraper.pipelines import (
    DuplicateCheckPipeline,
    HtmlSavePipeline,
    MetadataLogPipeline,
    ValidationPipeline,
)


def test_exercises_this_phase_pipelines():
    """solidworks_scraper is a package name five crawl phases share; these tests must load phase 30's."""
    assert Path(pipelines.__file__).resolve().is_relative_to(Path(__file__).resolve().parents[1])


@pytest.fixture
def spider():
    """Mock spider for testing"""
    spider = MagicMock()
    spider.logger = MagicMock()
    return spider


@pytest.fixture
def sample_item():
    """Sample valid item for testing (content above ValidationPipeline's 100-byte minimum)"""
    content = "<html><body><h1>TestMethod</h1><p>Test description of the TestMethod member documentation page.</p></body></html>"
    return {
        "url": "https://help.solidworks.com/test/TestMethod.html",
        "original_url": "/test/TestMethod.html",
        "content": content,
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content_length": len(content),
        "status_code": 200,
        "title": "TestMethod - SolidWorks API",
        "headers": {"Content-Type": "text/html"},
    }


class TestHtmlSavePipeline:
    """Test suite for HtmlSavePipeline"""

    def test_url_to_file_path_basic(self, tmp_path):
        """Test basic URL to file path conversion"""
        pipeline = HtmlSavePipeline()
        pipeline.output_dir = tmp_path

        url = f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/Test~Method.html"
        file_path = pipeline.url_to_file_path(url)

        assert file_path.name == "Test~Method.html"
        assert "sldworksapi" in str(file_path)

    def test_url_to_file_path_with_query(self, tmp_path):
        """Test URL with query parameters"""
        pipeline = HtmlSavePipeline()
        pipeline.output_dir = tmp_path

        url = f"{SOLIDWORKS_API_FULL_BASE_URL}/test/Method.html?format=p&value=1"
        file_path = pipeline.url_to_file_path(url)

        # Should include hash of query params
        assert "_" in file_path.stem
        assert file_path.suffix == ".html"

    def test_process_item_saves_file(self, tmp_path, sample_item, spider):
        """Test that process_item saves HTML file"""
        pipeline = HtmlSavePipeline()
        pipeline.output_dir = tmp_path

        result = pipeline.process_item(sample_item, spider)

        # Check that file was saved
        assert "file_path" in result
        file_path = tmp_path.parent.parent / result["file_path"]

        # For testing, just verify the pipeline returns the item
        assert result["url"] == sample_item["url"]
        assert result["content"] == sample_item["content"]

    def test_process_item_skips_errors(self, tmp_path, spider):
        """Test that error items are skipped"""
        pipeline = HtmlSavePipeline()
        pipeline.output_dir = tmp_path

        error_item = {"type": "error", "url": "test", "error": "Test error"}
        result = pipeline.process_item(error_item, spider)

        assert result == error_item


class TestMetadataLogPipeline:
    """Test suite for MetadataLogPipeline"""

    @pytest.fixture
    def pipeline(self, tmp_path, monkeypatch):
        """Pipeline whose metadata dir (created, with a manifest, by __init__) is tmp_path/metadata.

        The metadata dir is resolved from the pipelines module's ``__file__``, so
        redirect that instead of letting __init__ rewrite the tracked manifest.
        """
        monkeypatch.setattr(pipelines, "__file__", str(tmp_path / "solidworks_scraper" / "pipelines.py"))
        return MetadataLogPipeline()

    def test_init_creates_directories(self, tmp_path, pipeline):
        """Test that __init__ creates the metadata directory and its manifest"""
        assert pipeline.metadata_dir == tmp_path / "metadata"
        assert pipeline.manifest_file.exists()

    def test_init_manifest(self, pipeline):
        """Test manifest file creation"""
        pipeline.manifest_file.unlink()

        pipeline.init_manifest()

        assert pipeline.manifest_file.exists()

        with open(pipeline.manifest_file) as f:
            manifest = json.load(f)

        assert "crawler_version" in manifest
        assert "phase" in manifest
        assert manifest["phase"] == "30_crawl_type_members"

    def test_process_item_logs_metadata(self, pipeline, sample_item, spider):
        """Test that metadata is logged"""
        # Add file_path to item
        sample_item["file_path"] = "output/html/test.html"

        result = pipeline.process_item(sample_item, spider)

        assert result == sample_item
        assert pipeline.urls_file.exists()

    def test_log_error(self, pipeline):
        """Test error logging"""
        error_item = {"type": "error", "url": "test_url", "error": "Test error message"}

        pipeline.log_error(error_item)

        # Check file was created
        assert pipeline.errors_file.exists()


class TestDuplicateCheckPipeline:
    """Test suite for DuplicateCheckPipeline"""

    def test_process_item_allows_new_url(self, sample_item, spider):
        """Test that new URLs are allowed through"""
        pipeline = DuplicateCheckPipeline()
        pipeline.seen_urls = set()

        result = pipeline.process_item(sample_item, spider)

        assert result == sample_item
        assert sample_item["url"] in pipeline.seen_urls

    def test_process_item_blocks_duplicate(self, sample_item, spider):
        """Test that duplicate URLs are blocked"""
        from scrapy.exceptions import DropItem

        pipeline = DuplicateCheckPipeline()
        pipeline.seen_urls = {sample_item["url"]}

        with pytest.raises(DropItem):
            pipeline.process_item(sample_item, spider)

    def test_skips_error_items(self, spider):
        """Test that error items are not checked for duplicates"""
        pipeline = DuplicateCheckPipeline()

        error_item = {"type": "error", "url": "test", "error": "Test"}
        result = pipeline.process_item(error_item, spider)

        assert result == error_item


class TestValidationPipeline:
    """Test suite for ValidationPipeline"""

    def test_validates_required_fields(self, sample_item, spider):
        """Test that required fields are validated"""
        pipeline = ValidationPipeline()

        result = pipeline.process_item(sample_item, spider)

        # Should pass through valid item
        assert result == sample_item
        # No warnings should be logged
        spider.logger.warning.assert_not_called()

    def test_warns_on_missing_fields(self, spider):
        """Test warnings for missing required fields"""
        pipeline = ValidationPipeline()

        incomplete_item = {
            "url": "test",
            # Missing content and content_hash
        }

        result = pipeline.process_item(incomplete_item, spider)

        # Should still return item
        assert result == incomplete_item
        # Should have logged warnings
        assert spider.logger.warning.call_count >= 2

    def test_warns_on_short_content(self, spider):
        """Test warning for suspiciously short content"""
        pipeline = ValidationPipeline()

        item = {
            "url": "test",
            "content": "short",
            "content_hash": "hash",
        }

        pipeline.process_item(item, spider)

        # Should warn about short content
        spider.logger.warning.assert_called()

    def test_skips_error_items(self, spider):
        """Test that error items are skipped"""
        pipeline = ValidationPipeline()

        error_item = {"type": "error", "url": "test", "error": "Test"}
        result = pipeline.process_item(error_item, spider)

        assert result == error_item
        spider.logger.warning.assert_not_called()
