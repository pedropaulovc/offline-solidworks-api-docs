"""
Tests for the SolidWorks API documentation spider.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from scrapy.http import Response, Request, HtmlResponse
from pathlib import Path
import sys

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

    def test_convert_to_print_preview(self):
        """Test URL conversion to print preview format"""
        # Test URL without query parameters
        url1 = "https://help.solidworks.com/2026/english/api/test.html"
        result1 = self.spider.convert_to_print_preview(url1)
        assert "format=p" in result1
        assert "value=1" in result1

        # Test URL with existing query parameters
        url2 = "https://help.solidworks.com/2026/english/api/test.html?id=123"
        result2 = self.spider.convert_to_print_preview(url2)
        assert "format=p" in result2
        assert "value=1" in result2
        assert "id=123" in result2

        # Test URL with multiple existing parameters
        url3 = "https://help.solidworks.com/2026/english/api/test.html?id=123&lang=en"
        result3 = self.spider.convert_to_print_preview(url3)
        assert "format=p" in result3
        assert "value=1" in result3
        assert "id=123" in result3
        assert "lang=en" in result3

    def test_url_boundary_checking(self):
        """Test that spider respects URL boundaries"""
        # Create mock links
        good_link = Mock()
        good_link.url = "https://help.solidworks.com/2026/english/api/sldworks/test.html"

        bad_link1 = Mock()
        bad_link1.url = "https://help.solidworks.com/2025/english/api/test.html"  # Wrong year

        bad_link2 = Mock()
        bad_link2.url = "https://help.solidworks.com/2026/french/api/test.html"  # Wrong language

        bad_link3 = Mock()
        bad_link3.url = "https://help.solidworks.com/2026/english/docs/test.html"  # Not API

        # Process links
        processed = self.spider.process_links([good_link, bad_link1, bad_link2, bad_link3])

        # Check only good link is included
        assert len(processed) == 1
        assert "format=p" in processed[0].url
        assert "value=1" in processed[0].url
        assert "/2026/english/api/" in processed[0].url

    def test_parse_page_with_valid_html(self):
        """Test parsing a valid HTML page"""
        # Create mock response
        mock_response = Mock(spec=HtmlResponse)
        mock_response.url = "https://help.solidworks.com/2026/english/api/test.html?format=p&value=1"
        mock_response.status = 200
        mock_response.headers = {'Content-Type': b'text/html; charset=utf-8'}
        mock_response.text = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Test Content</h1>
            <p>This is a test page with content.</p>
        </body>
        </html>
        """
        mock_response.body = mock_response.text.encode('utf-8')
        mock_response.xpath = Mock()
        mock_response.xpath.return_value.get = Mock(return_value="Test Page")
        mock_response.meta = {'original_url': 'https://help.solidworks.com/2026/english/api/test.html'}

        # Parse the page
        items = list(self.spider.parse_page(mock_response))

        # Check item was created correctly
        assert len(items) == 1
        item = items[0]
        assert item['url'] == mock_response.url
        assert item['status_code'] == 200
        assert item['content'] == mock_response.text
        assert item['title'] == 'Test Page'
        assert 'content_hash' in item
        assert 'timestamp' in item
        assert 'session_id' in item

    def test_parse_page_skips_non_html(self):
        """Test that non-HTML content is skipped"""
        # Create mock response with non-HTML content type
        mock_response = Mock(spec=Response)
        mock_response.url = "https://help.solidworks.com/2026/english/api/test.pdf"
        mock_response.headers = {'Content-Type': b'application/pdf'}

        # Parse the page
        items = list(self.spider.parse_page(mock_response))

        # Check no items were created
        assert len(items) == 0
        assert self.spider.stats['skipped_pages'] == 1

    def test_parse_page_skips_outside_boundary(self):
        """Test that pages outside boundary are skipped"""
        # Create mock response outside boundary
        mock_response = Mock(spec=Response)
        mock_response.url = "https://help.solidworks.com/2026/english/docs/test.html"
        mock_response.headers = {'Content-Type': b'text/html'}

        # Parse the page
        items = list(self.spider.parse_page(mock_response))

        # Check no items were created
        assert len(items) == 0
        assert self.spider.stats['skipped_pages'] == 1  # First skip in this test

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
        assert error_item['type'] == 'error'
        assert error_item['url'] == mock_failure.request.url
        assert 'Connection timeout' in error_item['error']
        assert 'timestamp' in error_item
        assert self.spider.stats['failed_pages'] == 1

    def test_start_requests(self):
        """Test that start requests are generated correctly"""
        requests = list(self.spider.start_requests())

        assert len(requests) == 1
        request = requests[0]
        assert isinstance(request, Request)
        # Start URL should NOT be converted to print preview (to preserve full TOC)
        assert "format=p" not in request.url or "value=1" not in request.url
        assert request.meta['original_url'] == self.spider.start_urls[0]
        assert request.meta['is_start_page'] == True

    def test_spider_statistics_tracking(self):
        """Test that spider tracks statistics correctly"""
        # Initial state
        assert self.spider.stats['total_pages'] == 0
        assert self.spider.stats['successful_pages'] == 0
        assert self.spider.stats['failed_pages'] == 0

        # Create mock response
        mock_response = Mock(spec=HtmlResponse)
        mock_response.url = "https://help.solidworks.com/2026/english/api/test.html?format=p&value=1"
        mock_response.status = 200
        mock_response.headers = {'Content-Type': b'text/html'}
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.body = mock_response.text.encode('utf-8')
        mock_response.xpath = Mock()
        mock_response.xpath.return_value.get = Mock(return_value="Test")
        mock_response.meta = {}

        # Parse a successful page
        list(self.spider.parse_page(mock_response))

        # Check statistics updated
        assert self.spider.stats['total_pages'] == 1
        assert self.spider.stats['successful_pages'] == 1

    def test_duplicate_url_handling(self):
        """Test that duplicate URLs are not processed twice"""
        # Create mock response
        mock_response = Mock(spec=HtmlResponse)
        mock_response.url = "https://help.solidworks.com/2026/english/api/duplicate.html"
        mock_response.status = 200
        mock_response.headers = {'Content-Type': b'text/html'}
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.body = mock_response.text.encode('utf-8')
        mock_response.xpath = Mock()
        mock_response.xpath.return_value.get = Mock(return_value="Test")
        mock_response.meta = {}

        # Parse the same URL twice
        items1 = list(self.spider.parse_page(mock_response))
        items2 = list(self.spider.parse_page(mock_response))

        # Check only first parse created items
        assert len(items1) == 1
        assert len(items2) == 0  # Second parse should skip

    def test_extract_links_from_json(self):
        """Test extracting links from __NEXT_DATA__ JSON blob"""
        import scrapy

        # Create mock response with JSON data
        json_content = '''
        {
            "props": {
                "pageProps": {
                    "allGuidesSectionData": [
                        {"name": "Welcome", "url": "/2026/english/api/sldworksapiprogguide/Welcome.htm?id=0"},
                        {"name": "Getting Started", "url": "/2026/english/api/help_list.htm?id=1"},
                        {"name": "API Help", "url": "/2026/english/api/help_list.htm?id=2"},
                        {"name": "Outside Boundary", "url": "/2025/english/docs/test.html"}
                    ]
                }
            }
        }
        '''

        mock_response = Mock(spec=HtmlResponse)
        mock_response.url = "https://help.solidworks.com/2026/english/api/sldworksapiprogguide/Welcome.htm?id=0"
        mock_response.xpath = Mock()
        mock_response.xpath.return_value.get = Mock(return_value=json_content)
        mock_response.urljoin = lambda url: f"https://help.solidworks.com{url}"

        # Extract links
        requests = list(self.spider.extract_links_from_json(mock_response))

        # Should yield 3 requests (4th is outside boundary)
        assert len(requests) == 3

        # Check that all requests are scrapy.Request objects
        for req in requests:
            assert isinstance(req, scrapy.Request)
            # Check print preview format was applied
            assert "format=p" in req.url
            assert "value=1" in req.url
            # Check within boundary
            assert "/2026/english/api/" in req.url

    def test_extract_links_from_json_no_data(self):
        """Test extract_links_from_json handles missing JSON gracefully"""
        mock_response = Mock(spec=HtmlResponse)
        mock_response.url = "https://help.solidworks.com/2026/english/api/test.html"
        mock_response.xpath = Mock()
        mock_response.xpath.return_value.get = Mock(return_value=None)  # No JSON found

        # Should return empty list without errors
        requests = list(self.spider.extract_links_from_json(mock_response))
        assert len(requests) == 0