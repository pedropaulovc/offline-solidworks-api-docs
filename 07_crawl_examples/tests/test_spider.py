"""Tests for the examples spider"""

import tempfile
from pathlib import Path

import pytest
from scrapy.http import HtmlResponse, Request

from solidworks_scraper.spiders.examples_spider import ExamplesSpider


@pytest.fixture
def spider():
    """Create a spider instance for testing"""
    return ExamplesSpider()


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
    assert spider.base_url == "https://help.solidworks.com/2026/english/api"


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
        spider.xml_file = temp_path
        urls = spider._load_urls()

        assert len(urls) == 1
        assert urls[0] == "https://help.solidworks.com/2026/english/api/sldworksapi/test.htm"

    finally:
        temp_path.unlink()


def test_load_urls_removes_duplicates():
    """Test that duplicate URLs are removed"""
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
        spider.xml_file = temp_path
        urls = spider._load_urls()

        assert len(urls) == 2
        assert all("test" in url for url in urls)

    finally:
        temp_path.unlink()


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

    url = "https://help.solidworks.com/2026/english/api/sldworksapi/test.htm"
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
    """Test that pages without __NEXT_DATA__ are skipped"""
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

    url = "https://help.solidworks.com/2026/english/api/sldworksapi/test.htm"
    request = Request(url)
    response = HtmlResponse(
        url=url,
        request=request,
        body=html_content.encode("utf-8"),
        encoding="utf-8",
    )

    items = list(spider.parse_page(response))
    assert len(items) == 0
    assert spider.stats["skipped_pages"] == 1
