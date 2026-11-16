"""
Tests for the TypeMembersSpider
"""

import json
import xml.etree.ElementTree as ET

import pytest
from scrapy.http import HtmlResponse, Request
from twisted.python.failure import Failure

from shared.constants import SOLIDWORKS_API_FULL_BASE_URL
from solidworks_scraper.spiders import type_members_spider
from solidworks_scraper.spiders.type_members_spider import TypeMembersSpider


@pytest.fixture
def spider(crawler_spider):
    """Create a spider instance for testing, bound to a crawler so it can retry"""
    return crawler_spider(TypeMembersSpider)


@pytest.fixture
def members_xml(tmp_path, monkeypatch):
    """Phase 2 api_members.xml path that load_urls reads, redirected under tmp_path.

    load_urls resolves the file relative to the spider module's ``__file__``.
    """
    fake_module_file = tmp_path / "30_crawl_type_members" / "solidworks_scraper" / "spiders" / "type_members_spider.py"
    monkeypatch.setattr(type_members_spider, "__file__", str(fake_module_file))
    xml_file = tmp_path / "20_extract_types" / "metadata" / "api_members.xml"
    xml_file.parent.mkdir(parents=True)
    return xml_file


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
        headers={"Content-Type": "text/html; charset=utf-8"},
    )


class TestTypeMembersSpider:
    """Test suite for TypeMembersSpider"""

    def test_spider_name(self, spider):
        """Test spider has correct name"""
        assert spider.name == "type_members"

    def test_allowed_domains(self, spider):
        """Test allowed domains configuration"""
        assert "help.solidworks.com" in spider.allowed_domains

    def test_load_urls_from_xml(self, spider, members_xml, sample_xml_content):
        """Test loading URLs from XML file"""
        members_xml.write_text(sample_xml_content)

        urls = spider.load_urls()

        # Should extract 3 unique URLs
        assert len(urls) == 3
        assert "/sldworksapi/Test~TestProperty.html" in urls
        assert "/sldworksapi/Test~TestMethod.html" in urls
        assert "/sldworksapi/Test~TestProperty2.html" in urls

    def test_load_urls_deduplication(self, spider, members_xml):
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

        members_xml.write_text(xml_content)

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
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

        items = list(spider.parse_page(response))

        # A page without __NEXT_DATA__ is retried, not skipped
        assert len(items) == 1
        assert isinstance(items[0], Request)
        assert spider.stats["skipped_pages"] == 0

    def test_start_requests_generates_requests(self, spider, members_xml, sample_xml_content):
        """Test that start_requests generates correct requests"""
        members_xml.write_text(sample_xml_content)

        spider.urls_to_crawl = spider.load_urls()

        requests = list(spider.start_requests())

        # Should generate 3 requests
        assert len(requests) == 3

        # Pages are fetched as plain absolute URLs (content comes from __NEXT_DATA__,
        # so no print-format query is needed)
        assert sorted(req.url for req in requests) == [
            f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/Test~TestMethod.html",
            f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/Test~TestProperty.html",
            f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/Test~TestProperty2.html",
        ]

    def test_handle_error_retries_then_fails(self, spider):
        """A download error reaching the errback is retried; once retries are exhausted it is a failed page"""
        failure = Failure(Exception("Test error"))
        failure.request = Request(url="https://help.solidworks.com/test")

        [retry] = list(spider.handle_error(failure))
        assert isinstance(retry, Request)
        assert spider.stats["failed_pages"] == 0

        failure.request = retry.replace(meta={"retry_times": spider.crawler.settings.getint("RETRY_TIMES")})
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


# The 2027 full run lost this page: it came back once with helpContentData null in
# __NEXT_DATA__, and parse_page crashed on it.
INTERSECT_URL = (
    f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/"
    "SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISurface~GetIntersectCurveCount2.html"
)


def member_page(help_content_data, meta=None) -> HtmlResponse:
    next_data = json.dumps({"props": {"pageProps": {"helpContentData": help_content_data}}})
    body = (
        "<html><head><title>GetIntersectCurveCount2 Method (ISurface)</title></head><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{next_data}</script></body></html>'
    )
    return HtmlResponse(
        url=INTERSECT_URL,
        request=Request(INTERSECT_URL, meta=meta or {}),
        body=body.encode("utf-8"),
        headers={"Content-Type": "text/html; charset=utf-8"},
    )


def test_null_help_content_data_is_retried_and_the_retry_is_saved(spider):
    [retry] = list(spider.parse_page(member_page(None)))

    assert isinstance(retry, Request)
    assert retry.url == INTERSECT_URL
    assert retry.dont_filter

    # The refetched page is not mistaken for an already-crawled duplicate
    [item] = list(spider.parse_page(member_page({"helpText": "<p>GetIntersectCurveCount2</p>"}, retry.meta)))

    assert item["url"] == INTERSECT_URL
    assert item["content"] == "<p>GetIntersectCurveCount2</p>"
    assert spider.stats["successful_pages"] == 1
    assert spider.stats["total_pages"] == 1
    assert spider.crawl_failures() == {}


def test_null_help_content_data_fails_the_crawl_once_retries_are_exhausted(spider):
    meta = {"retry_times": spider.crawler.settings.getint("RETRY_TIMES")}

    [error] = list(spider.parse_page(member_page(None, meta)))

    assert error == {"type": "error", "url": INTERSECT_URL, "error": "helpContentData is null"}
    assert spider.stats["failed_pages"] == 1
    assert spider.stats["skipped_pages"] == 0
    assert spider.crawl_failures() == {"failed pages": 1}
