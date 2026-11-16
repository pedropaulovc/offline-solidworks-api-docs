"""Tests for the examples spider"""

import json
import tempfile
from pathlib import Path

import pytest
from scrapy.http import HtmlResponse, Request

from solidworks_scraper.spiders.examples_spider import ExamplesSpider

from shared.constants import SOLIDWORKS_API_FULL_BASE_URL
from shared.help_page_spider import DEAD_LINK_CONFIRMATION_DELAY_SECONDS


@pytest.fixture
def spider(crawler_spider):
    """Create a spider instance for testing, bound to a crawler so it can retry"""
    return crawler_spider(ExamplesSpider)


@pytest.fixture
def sample_urls_file():
    """Create a temporary URLs file"""
    urls_content = """/sldworksapi/test1.htm
/sldworksapi/test2.htm
/swmotionstudyapi/example1.htm
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(urls_content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink()


def test_spider_initialization(spider):
    """Test that spider initializes correctly"""
    assert spider.name == "examples"
    assert "help.solidworks.com" in spider.allowed_domains
    assert spider.base_url == SOLIDWORKS_API_FULL_BASE_URL


def test_load_urls_converts_relative_to_absolute():
    """Test that relative URLs are converted to absolute"""
    xml_content = """<?xml version="1.0" ?>
<Types>
    <Type>
        <Name>TestType</Name>
        <Examples>
            <Example>
                <Url>/sldworksapi/test.htm</Url>
            </Example>
        </Examples>
    </Type>
</Types>
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml", encoding="utf-8") as f:
        f.write(xml_content)
        temp_path = Path(f.name)

    try:
        spider = ExamplesSpider()
        spider.type_xml_file = temp_path
        spider.member_xml_file = Path("nonexistent.xml")  # Won't exist
        spider.legacy_urls_file = Path("nonexistent.txt")  # Skip the tracked orphan-recovery list
        urls = spider._load_urls()

        assert len(urls) == 1
        assert urls[0] == f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/test.htm"

    finally:
        temp_path.unlink()


def test_load_urls_removes_duplicates():
    """Test that duplicate URLs are removed within a single file"""
    xml_content = """<?xml version="1.0" ?>
<Types>
    <Type>
        <Name>TestType1</Name>
        <Examples>
            <Example>
                <Url>/sldworksapi/test1.htm</Url>
            </Example>
            <Example>
                <Url>/sldworksapi/test1.htm</Url>
            </Example>
        </Examples>
    </Type>
    <Type>
        <Name>TestType2</Name>
        <Examples>
            <Example>
                <Url>/sldworksapi/test2.htm</Url>
            </Example>
        </Examples>
    </Type>
</Types>
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml", encoding="utf-8") as f:
        f.write(xml_content)
        temp_path = Path(f.name)

    try:
        spider = ExamplesSpider()
        spider.type_xml_file = temp_path
        spider.member_xml_file = Path("nonexistent.xml")  # Won't exist
        spider.legacy_urls_file = Path("nonexistent.txt")  # Skip the tracked orphan-recovery list
        urls = spider._load_urls()

        assert len(urls) == 2
        assert all("test" in url for url in urls)

    finally:
        temp_path.unlink()


def test_load_urls_from_both_files():
    """Test that URLs are loaded from both type and member XML files and deduplicated"""
    type_xml_content = """<?xml version="1.0" ?>
<Types>
    <Type>
        <Name>TestType</Name>
        <Examples>
            <Example>
                <Url>/sldworksapi/test1.htm</Url>
            </Example>
            <Example>
                <Url>/sldworksapi/test2.htm</Url>
            </Example>
        </Examples>
    </Type>
</Types>
"""

    member_xml_content = """<?xml version="1.0" ?>
<Members>
    <Member>
        <Name>TestMember</Name>
        <Examples>
            <Example>
                <Url>/sldworksapi/test2.htm</Url>
            </Example>
            <Example>
                <Url>/sldworksapi/test3.htm</Url>
            </Example>
        </Examples>
    </Member>
</Members>
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml", encoding="utf-8") as f:
        f.write(type_xml_content)
        type_path = Path(f.name)

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml", encoding="utf-8") as f:
        f.write(member_xml_content)
        member_path = Path(f.name)

    try:
        spider = ExamplesSpider()
        spider.type_xml_file = type_path
        spider.member_xml_file = member_path
        spider.legacy_urls_file = Path("nonexistent.txt")  # Skip the tracked orphan-recovery list
        urls = spider._load_urls()

        # Should have 3 unique URLs (test1, test2, test3)
        # test2 appears in both files but should be deduplicated
        assert len(urls) == 3
        assert spider.stats["urls_from_types"] == 2
        assert spider.stats["urls_from_members"] == 2
        assert all("test" in url for url in urls)

    finally:
        type_path.unlink()
        member_path.unlink()


def test_parse_page_extracts_title(spider):
    """Test that page title is extracted correctly"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Example Code - VBA</title>
    </head>
    <body>
        <script id="__NEXT_DATA__" type="application/json">
        {
            "props": {
                "pageProps": {
                    "helpContentData": {
                        "helpText": "<html><body>Example code here</body></html>"
                    }
                }
            }
        }
        </script>
    </body>
    </html>
    """

    url = f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/test.htm"
    request = Request(url)
    response = HtmlResponse(
        url=url,
        request=request,
        body=html_content.encode("utf-8"),
        encoding="utf-8",
        headers={"Content-Type": b"text/html; charset=utf-8"},
    )

    items = list(spider.parse_page(response))
    assert len(items) == 1
    assert items[0]["title"] == "Example Code - VBA"


def test_parse_page_handles_missing_next_data(spider):
    """Test that pages without __NEXT_DATA__ are retried, not skipped"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
    </head>
    <body>
        <p>No NEXT_DATA here</p>
    </body>
    </html>
    """

    url = f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/test.htm"
    request = Request(url)
    response = HtmlResponse(
        url=url,
        request=request,
        body=html_content.encode("utf-8"),
        encoding="utf-8",
        headers={"Content-Type": "text/html; charset=utf-8"},
    )

    items = list(spider.parse_page(response))
    assert items == []
    assert spider.stats["skipped_pages"] == 0
    assert spider.stats["failed_pages"] == 0


def test_confirmed_dead_example_link_is_skipped_not_failed(spider, release_waiting):
    """Some example links are dead (the server's "cannot be found" page on every fetch); once
    a refetch confirms one, it is skipped and listed rather than failing the crawl."""
    url = f"{SOLIDWORKS_API_FULL_BASE_URL}/swconst/ms-its:sldworksapi.chm::/Add_Component_and_Mate_Example_VB.htm"
    next_data = json.dumps(
        {"props": {"pageProps": {"helpContentData": {"ErrorTitle": "This page cannot be found."}}}}
    )
    body = f'<html><body><script id="__NEXT_DATA__" type="application/json">{next_data}</script></body></html>'

    def page(meta):
        return HtmlResponse(
            url=url,
            request=Request(url, meta=meta),
            body=body.encode("utf-8"),
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    assert list(spider.parse_page(page({}))) == []
    [confirmation] = release_waiting(spider, DEAD_LINK_CONFIRMATION_DELAY_SECONDS)

    assert list(spider.parse_page(page(confirmation.meta))) == []
    assert spider.stats["skipped_pages"] == 1
    assert spider.stats["dead_links"] == [url]
    assert spider.stats["failed_pages"] == 0
