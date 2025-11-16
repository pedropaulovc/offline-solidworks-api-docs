"""
Tests for the TypeMembersSpider
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from scrapy.http import HtmlResponse, Request

from solidworks_scraper.spiders.type_members_spider import TypeMembersSpider


@pytest.fixture
def spider():
    """Create a spider instance for testing"""
    return TypeMembersSpider()


@pytest.fixture
def sample_xml_content():
    """Sample XML content for testing"""
    return """<?xml version="1.0" ?>
<Types>
    <Type>
        <Name>TestType1</Name>
        <Assembly>SolidWorks.Interop.sldworks</Assembly>
        <Namespace>SolidWorks.Interop.sldworks</Namespace>
        <PublicProperties>
            <Property>
                <Name>TestProperty</Name>
                <Url>/sldworksapi/Test~TestProperty.html</Url>
            </Property>
        </PublicProperties>
        <PublicMethods>
            <Method>
                <Name>TestMethod</Name>
                <Url>/sldworksapi/Test~TestMethod.html</Url>
            </Method>
        </PublicMethods>
    </Type>
    <Type>
        <Name>TestType2</Name>
        <Assembly>SolidWorks.Interop.sldworks</Assembly>
        <Namespace>SolidWorks.Interop.sldworks</Namespace>
        <PublicProperties>
            <Property>
                <Name>TestProperty2</Name>
                <Url>/sldworksapi/Test~TestProperty2.html</Url>
            </Property>
        </PublicProperties>
    </Type>
</Types>"""


@pytest.fixture
def sample_html_response():
    """Sample HTML response with __NEXT_DATA__ JSON"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Property - SolidWorks API</title>
    </head>
    <body>
        <script id="__NEXT_DATA__" type="application/json">
        {
            "props": {
                "pageProps": {
                    "helpContentData": {
                        "helpText": "<div class='member-doc'><h1>TestProperty</h1><p>Test description</p></div>"
                    }
                }
            }
        }
        </script>
    </body>
    </html>
    """
    request = Request(url="https://help.solidworks.com/test")
    return HtmlResponse(
        url="https://help.solidworks.com/test",
        body=html_content.encode("utf-8"),
        request=request,
    )


class TestTypeMembers Spider:
    """Test suite for TypeMembersSpider"""

    def test_spider_name(self, spider):
        """Test spider has correct name"""
        assert spider.name == "type_members"

    def test_allowed_domains(self, spider):
        """Test allowed domains configuration"""
        assert "help.solidworks.com" in spider.allowed_domains

    def test_load_urls_from_xml(self, spider, tmp_path, sample_xml_content):
        """Test loading URLs from XML file"""
        # Create temporary XML file
        xml_file = tmp_path / "api_members.xml"
        xml_file.write_text(sample_xml_content)

        # Mock the path to point to our temp file
        with patch.object(
            Path,
            "__truediv__",
            side_effect=lambda self, other: xml_file if str(other).endswith("api_members.xml") else Path(self) / other,
        ):
            urls = spider.load_urls()

        # Should extract 3 unique URLs
        assert len(urls) == 3
        assert "/sldworksapi/Test~TestProperty.html" in urls
        assert "/sldworksapi/Test~TestMethod.html" in urls
        assert "/sldworksapi/Test~TestProperty2.html" in urls

    def test_load_urls_deduplication(self, spider, tmp_path):
        """Test that duplicate URLs are removed"""
        xml_content = """<?xml version="1.0" ?>
<Types>
    <Type>
        <Name>Type1</Name>
        <Assembly>Test</Assembly>
        <Namespace>Test</Namespace>
        <PublicProperties>
            <Property>
                <Name>Prop1</Name>
                <Url>/test/Prop1.html</Url>
            </Property>
        </PublicProperties>
    </Type>
    <Type>
        <Name>Type2</Name>
        <Assembly>Test</Assembly>
        <Namespace>Test</Namespace>
        <PublicProperties>
            <Property>
                <Name>Prop1</Name>
                <Url>/test/Prop1.html</Url>
            </Property>
        </PublicProperties>
    </Type>
</Types>"""

        xml_file = tmp_path / "api_members.xml"
        xml_file.write_text(xml_content)

        with patch.object(
            Path,
            "__truediv__",
            side_effect=lambda self, other: xml_file if str(other).endswith("api_members.xml") else Path(self) / other,
        ):
            urls = spider.load_urls()

        # Should have only 1 URL (duplicates removed)
        assert len(urls) == 1
        assert "/test/Prop1.html" in urls

    def test_parse_page_extracts_content(self, spider, sample_html_response):
        """Test that parse_page correctly extracts helpText"""
        items = list(spider.parse_page(sample_html_response))

        assert len(items) == 1
        item = items[0]

        assert "url" in item
        assert "content" in item
        assert "content_hash" in item
        assert "title" in item

        # Check that helpText was extracted
        assert "TestProperty" in item["content"]
        assert "Test description" in item["content"]

    def test_parse_page_skips_non_html(self, spider):
        """Test that non-HTML content is skipped"""
        request = Request(url="https://help.solidworks.com/test.json")
        response = HtmlResponse(
            url="https://help.solidworks.com/test.json",
            body=b'{"test": "data"}',
            request=request,
            headers={"Content-Type": "application/json"},
        )

        items = list(spider.parse_page(response))

        # Should skip and return empty
        assert len(items) == 0
        assert spider.stats["skipped_pages"] == 1

    def test_parse_page_handles_missing_next_data(self, spider):
        """Test handling of pages without __NEXT_DATA__"""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body><p>No __NEXT_DATA__ here</p></body>
        </html>
        """
        request = Request(url="https://help.solidworks.com/test")
        response = HtmlResponse(
            url="https://help.solidworks.com/test",
            body=html_content.encode("utf-8"),
            request=request,
        )

        items = list(spider.parse_page(response))

        # Should skip
        assert len(items) == 0
        assert spider.stats["skipped_pages"] == 1

    def test_start_requests_generates_requests(self, spider, tmp_path, sample_xml_content):
        """Test that start_requests generates correct requests"""
        xml_file = tmp_path / "api_members.xml"
        xml_file.write_text(sample_xml_content)

        with patch.object(
            Path,
            "__truediv__",
            side_effect=lambda self, other: xml_file if str(other).endswith("api_members.xml") else Path(self) / other,
        ):
            spider.urls_to_crawl = spider.load_urls()

        requests = list(spider.start_requests())

        # Should generate 3 requests
        assert len(requests) == 3

        # Check that URLs are absolute and have format parameter
        for req in requests:
            assert req.url.startswith("https://help.solidworks.com")
            assert "format=p&value=1" in req.url

    def test_handle_error_logs_failure(self, spider):
        """Test that handle_error logs failures correctly"""
        from twisted.python.failure import Failure

        # Create a mock failure
        request = Request(url="https://help.solidworks.com/test")
        error = Exception("Test error")
        failure = Failure(error)
        failure.request = request

        error_items = list(spider.handle_error(failure))

        assert len(error_items) == 1
        error_item = error_items[0]

        assert error_item["type"] == "error"
        assert error_item["url"] == "https://help.solidworks.com/test"
        assert "Test error" in error_item["error"]
        assert spider.stats["failed_pages"] == 1

    def test_statistics_tracking(self, spider, sample_html_response):
        """Test that spider tracks statistics correctly"""
        # Initial state
        assert spider.stats["total_pages"] == 0
        assert spider.stats["successful_pages"] == 0

        # Process a page
        list(spider.parse_page(sample_html_response))

        # Check stats updated
        assert spider.stats["total_pages"] == 1
        assert spider.stats["successful_pages"] == 1

    def test_duplicate_url_handling(self, spider, sample_html_response):
        """Test that duplicate URLs are not processed twice"""
        # Process same URL twice
        list(spider.parse_page(sample_html_response))
        items = list(spider.parse_page(sample_html_response))

        # Second time should return empty (already crawled)
        assert len(items) == 0
        assert spider.stats["total_pages"] == 1  # Only counted once
