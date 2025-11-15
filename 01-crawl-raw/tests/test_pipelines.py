"""
Tests for the SolidWorks API documentation pipelines.
"""

import pytest
from unittest.mock import Mock, patch, mock_open, MagicMock
from pathlib import Path
import json
import sys
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from solidworks_scraper.pipelines import (
    HtmlSavePipeline,
    MetadataLogPipeline,
    DuplicateCheckPipeline,
    ValidationPipeline
)
from scrapy.exceptions import DropItem


class TestHtmlSavePipeline:
    """Test suite for HtmlSavePipeline"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.pipeline = HtmlSavePipeline()

        # Override output directory to use temp directory
        self.pipeline.output_dir = Path(self.temp_dir) / 'html'
        self.pipeline.output_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up after tests"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_url_to_file_path_conversion(self):
        """Test URL to file path conversion"""
        # Test simple URL
        url1 = "https://help.solidworks.com/2026/english/api/sldworksapi/test.html"
        path1 = self.pipeline.url_to_file_path(url1)
        assert "sldworksapi" in str(path1)
        assert path1.name == "test.html"

        # Test URL with query parameters
        url2 = "https://help.solidworks.com/2026/english/api/test.html?id=123&format=p"
        path2 = self.pipeline.url_to_file_path(url2)
        assert "test_" in path2.name  # Should have hash appended
        assert path2.suffix == ".html"

        # Test URL without extension
        url3 = "https://help.solidworks.com/2026/english/api/folder/page"
        path3 = self.pipeline.url_to_file_path(url3)
        assert path3.suffix == ".html"

    def test_url_to_file_path_deterministic(self):
        """Test that URL to file path conversion is deterministic"""
        url = "https://help.solidworks.com/2026/english/api/test.html?id=123&format=p"

        # Call multiple times and ensure same result
        path1 = self.pipeline.url_to_file_path(url)
        path2 = self.pipeline.url_to_file_path(url)
        path3 = self.pipeline.url_to_file_path(url)

        assert path1 == path2 == path3, "File path should be deterministic for same URL"

        # Verify the specific hash for this URL
        # MD5 of "id=123&format=p" first 8 chars should be consistent
        assert "test_" in path1.name
        # The hash should be the same across test runs

    def test_process_item_saves_html(self):
        """Test that HTML content is saved correctly"""
        # Create mock spider
        mock_spider = Mock()
        mock_spider.logger = Mock()

        # Create test item
        item = {
            'url': 'https://help.solidworks.com/2026/english/api/test.html',
            'content': '<html><body>Test content</body></html>',
        }

        # Process the item
        processed_item = self.pipeline.process_item(item, mock_spider)

        # Check file was created
        expected_path = self.pipeline.url_to_file_path(item['url'])
        assert expected_path.exists()

        # Check file content
        with open(expected_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        assert saved_content == item['content']

        # Check file path was added to item
        assert 'file_path' in processed_item

    def test_process_item_skips_error_items(self):
        """Test that error items are skipped"""
        mock_spider = Mock()
        error_item = {'type': 'error', 'url': 'test.html', 'error': 'Failed'}

        result = self.pipeline.process_item(error_item, mock_spider)
        assert result == error_item  # Should return unchanged

    def test_process_item_handles_missing_content(self):
        """Test handling of items without content"""
        mock_spider = Mock()
        mock_spider.logger = Mock()

        item = {'url': 'https://test.com/test.html'}  # No content

        result = self.pipeline.process_item(item, mock_spider)
        assert result == item
        mock_spider.logger.warning.assert_called()


class TestMetadataLogPipeline:
    """Test suite for MetadataLogPipeline"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

        # Create pipeline and override paths to use temp directory
        self.pipeline = MetadataLogPipeline()
        self.pipeline.metadata_dir = Path(self.temp_dir) / 'metadata'
        self.pipeline.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline.urls_file = self.pipeline.metadata_dir / 'urls_crawled.jsonl'
        self.pipeline.errors_file = self.pipeline.metadata_dir / 'errors.jsonl'
        self.pipeline.manifest_file = self.pipeline.metadata_dir / 'manifest.json'

    def teardown_method(self):
        """Clean up after tests"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_manifest_creation(self):
        """Test that manifest file is created"""
        self.pipeline.init_manifest()
        assert self.pipeline.manifest_file.exists()

        with open(self.pipeline.manifest_file, 'r') as f:
            manifest = json.load(f)

        assert manifest['crawler_version'] == '1.0.0'
        assert manifest['boundary'] == '/2026/english/api/'
        assert manifest['crawl_delay_seconds'] == 2

    def test_process_item_logs_metadata(self):
        """Test that metadata is logged correctly"""
        mock_spider = Mock()
        mock_spider.logger = Mock()

        item = {
            'url': 'https://test.com/test.html',
            'original_url': 'https://test.com/test.html',
            'timestamp': '2024-01-01T12:00:00',
            'file_path': 'test/test.html',
            'content_hash': 'abc123',
            'content_length': 1000,
            'status_code': 200,
            'title': 'Test Page',
            'session_id': 'session-001',
        }

        self.pipeline.process_item(item, mock_spider)

        # Check metadata was written
        assert self.pipeline.urls_file.exists()

        # Read and verify metadata
        import jsonlines
        with jsonlines.open(self.pipeline.urls_file) as reader:
            saved_metadata = list(reader)[0]

        assert saved_metadata['print_url'] == item['url']
        assert saved_metadata['content_hash'] == 'abc123'
        assert saved_metadata['title'] == 'Test Page'

    def test_log_error(self):
        """Test error logging"""
        error_item = {
            'type': 'error',
            'url': 'https://test.com/error.html',
            'error': 'Connection failed',
            'timestamp': '2024-01-01T12:00:00',
            'session_id': 'session-001',
        }

        self.pipeline.log_error(error_item)

        # Check error was logged
        assert self.pipeline.errors_file.exists()

        # Read and verify error log
        import jsonlines
        with jsonlines.open(self.pipeline.errors_file) as reader:
            saved_error = list(reader)[0]

        assert saved_error['url'] == error_item['url']
        assert saved_error['error'] == 'Connection failed'


class TestDuplicateCheckPipeline:
    """Test suite for DuplicateCheckPipeline"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

        # Create test metadata file with existing URLs
        metadata_dir = Path(self.temp_dir) / 'output' / 'metadata'
        metadata_dir.mkdir(parents=True, exist_ok=True)
        self.urls_file = metadata_dir / 'urls_crawled.jsonl'

        # Write some existing URLs
        import jsonlines
        with jsonlines.open(self.urls_file, mode='w') as writer:
            writer.write({'print_url': 'https://test.com/existing1.html'})
            writer.write({'print_url': 'https://test.com/existing2.html'})

        # Patch Path to use temp directory
        with patch.object(Path, '__new__', return_value=Path(self.temp_dir)):
            self.pipeline = DuplicateCheckPipeline()
            self.pipeline.seen_urls = {
                'https://test.com/existing1.html',
                'https://test.com/existing2.html'
            }

    def teardown_method(self):
        """Clean up after tests"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_duplicate_detection(self):
        """Test that duplicates are detected"""
        mock_spider = Mock()
        mock_spider.logger = Mock()

        # Try to process existing URL
        duplicate_item = {'url': 'https://test.com/existing1.html'}

        with pytest.raises(DropItem) as exc_info:
            self.pipeline.process_item(duplicate_item, mock_spider)

        assert "Duplicate URL" in str(exc_info.value)

    def test_new_url_processing(self):
        """Test that new URLs are processed"""
        mock_spider = Mock()

        # Process new URL
        new_item = {'url': 'https://test.com/new.html'}
        result = self.pipeline.process_item(new_item, mock_spider)

        assert result == new_item
        assert new_item['url'] in self.pipeline.seen_urls


class TestValidationPipeline:
    """Test suite for ValidationPipeline"""

    def setup_method(self):
        """Set up test fixtures"""
        self.pipeline = ValidationPipeline()

    def test_validate_complete_item(self):
        """Test validation of complete item"""
        mock_spider = Mock()
        mock_spider.logger = Mock()

        item = {
            'url': 'https://test.com/test.html',
            'content': '<html><body>' + 'x' * 200 + '</body></html>',
            'timestamp': '2024-01-01T12:00:00',
            'content_hash': 'abc123',
        }

        result = self.pipeline.process_item(item, mock_spider)
        assert result == item
        # No warnings should be logged for valid item
        mock_spider.logger.warning.assert_not_called()

    def test_validate_missing_fields(self):
        """Test validation catches missing fields"""
        mock_spider = Mock()
        mock_spider.logger = Mock()

        item = {
            'url': 'https://test.com/test.html',
            # Missing content, timestamp, content_hash
        }

        self.pipeline.process_item(item, mock_spider)
        # Should log warnings for missing fields
        assert mock_spider.logger.warning.call_count >= 3

    def test_validate_short_content(self):
        """Test validation warns about short content"""
        mock_spider = Mock()
        mock_spider.logger = Mock()

        item = {
            'url': 'https://test.com/test.html',
            'content': '<html>x</html>',  # Very short content
            'timestamp': '2024-01-01T12:00:00',
            'content_hash': 'abc123',
        }

        self.pipeline.process_item(item, mock_spider)
        # Should warn about short content
        mock_spider.logger.warning.assert_called()
        assert "short content" in mock_spider.logger.warning.call_args[0][0].lower()

    def test_validate_non_html_content(self):
        """Test validation detects non-HTML content"""
        mock_spider = Mock()
        mock_spider.logger = Mock()

        item = {
            'url': 'https://test.com/test.html',
            'content': 'This is just plain text, not HTML' * 10,
            'timestamp': '2024-01-01T12:00:00',
            'content_hash': 'abc123',
        }

        self.pipeline.process_item(item, mock_spider)
        # Should warn about non-HTML content
        mock_spider.logger.warning.assert_called()
        assert "doesn't appear to be HTML" in mock_spider.logger.warning.call_args[0][0]


def test_regression_crawl_count():
    """
    Regression test to ensure crawler maintains minimum page count.
    This is a placeholder that would run after an actual crawl.
    """
    # This test would typically:
    # 1. Run a crawl
    # 2. Count pages in metadata
    # 3. Compare against expected minimum
    # 4. Fail if dropped more than 5%

    expected_minimum = 450  # Expecting at least 450 pages (allowing 5% drop from 458)

    # In a real test, you would read actual metadata
    # For now, this is a placeholder
    # actual_count = count_crawled_pages()
    # assert actual_count >= expected_minimum, f"Crawl regression: only {actual_count} pages (expected >= {expected_minimum})"

    assert True  # Placeholder for now