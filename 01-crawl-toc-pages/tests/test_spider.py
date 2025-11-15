"""
Tests for the SolidWorks API documentation spider.
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock

from scrapy.http import HtmlResponse, Response

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from solidworks_scraper.spiders.api_docs_spider import ApiDocsSpider


class TestApiDocsSpider:
    """Test suite for ApiDocsSpider"""

    def setup_method(self):
        """Set up test fixtures"""
        self.spider = ApiDocsSpider()

    def test_spider_name(self):
        """Test spider has correct name"""
        assert self.spider.name == "api_docs"

    def test_allowed_domains(self):
        """Test spider has correct allowed domains"""
        assert "help.solidworks.com" in self.spider.allowed_domains

    def test_url_boundary_checking(self):
        """Test that spider respects URL boundaries"""
        # Test that spider only processes URLs within the boundary
        from urllib.parse import urlparse

        good_url = "https://help.solidworks.com/2026/english/api/sldworks/test.html"
        bad_url1 = "https://help.solidworks.com/2025/english/api/test.html"  # Wrong year
        bad_url2 = "https://help.solidworks.com/2026/french/api/test.html"  # Wrong language
        bad_url3 = "https://help.solidworks.com/2026/english/docs/test.html"  # Not API

        # Check boundary logic
        assert urlparse(good_url).path.startswith(self.spider.base_path)
        assert not urlparse(bad_url1).path.startswith(self.spider.base_path)
        assert not urlparse(bad_url2).path.startswith(self.spider.base_path)
        assert not urlparse(bad_url3).path.startswith(self.spider.base_path)

    def test_parse_page_with_valid_html(self):
        """Test parsing a valid HTML page"""
        # Create mock response with __NEXT_DATA__ JSON
        help_text_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <h1>Test Content</h1>
            <p>This is a test page with content.</p>
        </body>
        </html>
        """

        next_data_json = {"props": {"pageProps": {"helpContentData": {"helpText": help_text_content}}}}

        mock_response = Mock(spec=HtmlResponse)
        mock_response.url = "https://help.solidworks.com/2026/english/api/test.html?id=123"
        mock_response.status = 200
        mock_response.headers = {"Content-Type": b"text/html; charset=utf-8"}
        mock_response.body = b"<html><body>Test</body></html>"

        # Mock xpath to return the JSON and title
        def xpath_side_effect(query):
            result = Mock()
            if "__NEXT_DATA__" in query:
                result.get = Mock(return_value=json.dumps(next_data_json))
            elif "title" in query:
                result.get = Mock(return_value="Test Page")
            else:
                result.get = Mock(return_value=None)
            return result

        mock_response.xpath = xpath_side_effect
        mock_response.meta = {}

        # Parse the page
        items = list(self.spider.parse_page(mock_response))

        # Check item was created correctly
        assert len(items) == 1
        item = items[0]
        assert item["url"] == mock_response.url
        assert item["status_code"] == 200
        assert item["content"] == help_text_content
        assert item["title"] == "Test Page"
        assert "content_hash" in item
        assert "timestamp" in item
        assert "session_id" in item

    def test_parse_page_skips_non_html(self):
        """Test that non-HTML content is skipped"""
        # Create mock response with non-HTML content type
        mock_response = Mock(spec=Response)
        mock_response.url = "https://help.solidworks.com/2026/english/api/test.pdf"
        mock_response.headers = {"Content-Type": b"application/pdf"}

        # Parse the page
        items = list(self.spider.parse_page(mock_response))

        # Check no items were created
        assert len(items) == 0
        assert self.spider.stats["skipped_pages"] == 1

    def test_parse_page_skips_outside_boundary(self):
        """Test that pages outside boundary are skipped"""
        # Create mock response outside boundary
        mock_response = Mock(spec=Response)
        mock_response.url = "https://help.solidworks.com/2026/english/docs/test.html"
        mock_response.headers = {"Content-Type": b"text/html"}

        # Parse the page
        items = list(self.spider.parse_page(mock_response))

        # Check no items were created
        assert len(items) == 0
        assert self.spider.stats["skipped_pages"] == 1  # First skip in this test

    def test_handle_error(self):
        """Test error handling"""
        # Create mock failure
        mock_failure = Mock()
        mock_failure.request = Mock()
        mock_failure.request.url = "https://help.solidworks.com/2026/english/api/error.html"
        mock_failure.value = Exception("Connection timeout")

        # Handle the error
        items = list(self.spider.handle_error(mock_failure))

        # Check error item was created
        assert len(items) == 1
        error_item = items[0]
        assert error_item["type"] == "error"
        assert error_item["url"] == mock_failure.request.url
        assert "Connection timeout" in error_item["error"]
        assert "timestamp" in error_item
        assert self.spider.stats["failed_pages"] == 1

    def test_start_requests(self):
        """Test that start URLs are correctly configured"""
        # Check that spider has the correct start URL for expandToc
        assert len(self.spider.start_urls) == 1
        start_url = self.spider.start_urls[0]
        assert "expandToc" in start_url
        assert "version=2026" in start_url
        assert "language=english" in start_url
        assert "product=api" in start_url

    def test_spider_statistics_tracking(self):
        """Test that spider tracks statistics correctly"""
        # Initial state
        assert self.spider.stats["total_pages"] == 0
        assert self.spider.stats["successful_pages"] == 0
        assert self.spider.stats["failed_pages"] == 0

        # Create mock response with __NEXT_DATA__
        help_text = "<html><body>Test</body></html>"
        next_data = {"props": {"pageProps": {"helpContentData": {"helpText": help_text}}}}

        mock_response = Mock(spec=HtmlResponse)
        mock_response.url = "https://help.solidworks.com/2026/english/api/test.html?id=1"
        mock_response.status = 200
        mock_response.headers = {"Content-Type": b"text/html"}
        mock_response.body = b"<html><body>Test</body></html>"

        def xpath_side_effect(query):
            result = Mock()
            if "__NEXT_DATA__" in query:
                result.get = Mock(return_value=json.dumps(next_data))
            elif "title" in query:
                result.get = Mock(return_value="Test")
            else:
                result.get = Mock(return_value=None)
            return result

        mock_response.xpath = xpath_side_effect
        mock_response.meta = {}

        # Parse a successful page
        list(self.spider.parse_page(mock_response))

        # Check statistics updated
        assert self.spider.stats["total_pages"] == 1
        assert self.spider.stats["successful_pages"] == 1

    def test_duplicate_url_handling(self):
        """Test that duplicate URLs are not processed twice"""
        # Create mock response with __NEXT_DATA__
        help_text = "<html><body>Test</body></html>"
        next_data = {"props": {"pageProps": {"helpContentData": {"helpText": help_text}}}}

        mock_response = Mock(spec=HtmlResponse)
        mock_response.url = "https://help.solidworks.com/2026/english/api/duplicate.html"
        mock_response.status = 200
        mock_response.headers = {"Content-Type": b"text/html"}
        mock_response.body = b"<html><body>Test</body></html>"

        def xpath_side_effect(query):
            result = Mock()
            if "__NEXT_DATA__" in query:
                result.get = Mock(return_value=json.dumps(next_data))
            elif "title" in query:
                result.get = Mock(return_value="Test")
            else:
                result.get = Mock(return_value=None)
            return result

        mock_response.xpath = xpath_side_effect
        mock_response.meta = {}

        # Parse the same URL twice
        items1 = list(self.spider.parse_page(mock_response))
        items2 = list(self.spider.parse_page(mock_response))

        # Check only first parse created items
        assert len(items1) == 1
        assert len(items2) == 0  # Second parse should skip

    def test_extract_urls_from_json(self):
        """Test extracting URLs from JSON structure"""
        # Test with nested structure
        json_data = {
            "children": [
                {"url": "/2026/english/api/page1.htm"},
                {
                    "url": "/2026/english/api/page2.htm",
                    "children": [{"url": "/2026/english/api/page3.htm"}, {"url": "/2026/english/api/page4.htm"}],
                },
            ]
        }

        # Extract URLs
        urls = self.spider.extract_urls_from_json(json_data)

        # Should get all 4 URLs
        assert len(urls) == 4
        assert "/2026/english/api/page1.htm" in urls
        assert "/2026/english/api/page2.htm" in urls
        assert "/2026/english/api/page3.htm" in urls
        assert "/2026/english/api/page4.htm" in urls

    def test_extract_urls_from_json_no_data(self):
        """Test extract_urls_from_json handles empty data gracefully"""
        # Test with empty dict
        assert self.spider.extract_urls_from_json({}) == []

        # Test with empty list
        assert self.spider.extract_urls_from_json([]) == []

        # Test with dict without url or children
        assert self.spider.extract_urls_from_json({"name": "test"}) == []
