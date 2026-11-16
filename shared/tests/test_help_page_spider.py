"""Tests for HelpPageSpider: transient faults are retried, and lost pages are counted, never dropped."""

import gzip
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from scrapy.downloadermiddlewares.httpcompression import HttpCompressionMiddleware
from scrapy.http import HtmlResponse, Request, Response
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.python.failure import Failure

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from shared.constants import SOLIDWORKS_API_FULL_BASE_URL  # noqa: E402
from shared.help_page_spider import HelpPageSpider, MissingHelpTextError, crawl_exit_code, read_help_text  # noqa: E402

URL = f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/Example.html"
NOT_FOUND = {
    "ErrorTitle": "This page cannot be found.",
    "ErrorMessage": "The page might not exist or is temporarily unavailable.",
}


class PagesSpider(HelpPageSpider):
    name = "help_pages"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.stats = {"total_pages": 0, "successful_pages": 0, "failed_pages": 0, "skipped_pages": 0}

    def parse_page(self, response: Response) -> Any:
        help_text = yield from self.help_text_or_retry(response)
        if help_text is not None:
            yield {"url": response.url, "content": help_text}

    parse = parse_page


class DeadLinksSpider(PagesSpider):
    name = "help_pages_dead_links"
    dead_links_expected = True


@pytest.fixture
def spider(crawler_spider):
    return crawler_spider(PagesSpider)


def exhausted(spider: HelpPageSpider) -> dict[str, int]:
    """Request meta of an attempt that already used every retry RETRY_TIMES allows."""
    return {"retry_times": spider.crawler.settings.getint("RETRY_TIMES")}


def next_data_page(next_data: str | None, meta: dict | None = None) -> HtmlResponse:
    script = f'<script id="__NEXT_DATA__" type="application/json">{next_data}</script>' if next_data else ""
    body = f"<html><head><title>Example</title></head><body>{script}</body></html>"
    return HtmlResponse(
        url=URL,
        request=Request(URL, meta=meta or {}),
        body=body.encode("utf-8"),
        encoding="utf-8",
        headers={"Content-Type": "text/html; charset=utf-8"},
    )


def help_page(help_content_data: Any, meta: dict | None = None) -> HtmlResponse:
    return next_data_page(json.dumps({"props": {"pageProps": {"helpContentData": help_content_data}}}), meta)


def decompression_failure(spider: HelpPageSpider, meta: dict | None = None) -> Failure:
    """The failure a corrupt gzip body produces: HttpCompressionMiddleware raises it from
    process_response, which skips RetryMiddleware, so it reaches the errback unretried."""
    body = bytearray(gzip.compress(b"<html>" + bytes(range(256)) * 50 + b"</html>"))
    body[10:16] = b"\x07" * 6
    request = Request(URL, meta=meta or {})
    response = Response(URL, body=bytes(body), headers={"Content-Encoding": "gzip"}, request=request)
    try:
        HttpCompressionMiddleware.from_crawler(spider.crawler).process_response(request, response, spider)
    except Exception:
        failure = Failure()
    else:
        pytest.fail("corrupt gzip body decompressed")
    failure.request = request  # set by Scrapy's scraper before calling the errback
    return failure


# --- read_help_text ---------------------------------------------------------


def test_read_help_text_returns_help_html():
    assert read_help_text(help_page({"helpText": "<p>doc</p>"})) == "<p>doc</p>"


@pytest.mark.parametrize(
    "response, reason",
    [
        (help_page(None), "helpContentData is null"),
        (help_page({"helpText": ""}), "empty helpText"),
        (next_data_page(None), "no __NEXT_DATA__ JSON"),
        (next_data_page("{not json"), "unparseable __NEXT_DATA__ JSON"),
        (next_data_page(json.dumps({"props": None})), "helpContentData is null"),
    ],
)
def test_read_help_text_reports_why_help_text_is_missing(response, reason):
    with pytest.raises(MissingHelpTextError, match=reason) as missing:
        read_help_text(response)
    assert not missing.value.not_found


def test_read_help_text_flags_the_server_not_found_page():
    with pytest.raises(MissingHelpTextError) as missing:
        read_help_text(help_page(NOT_FOUND))
    assert missing.value.not_found


# --- response without help text ---------------------------------------------


def test_null_help_content_data_is_retried(spider):
    """Phase 30 lost ISurface~GetIntersectCurveCount2.html to helpContentData: null (and crashed)."""
    [retry] = list(spider.parse_page(help_page(None)))

    assert isinstance(retry, Request)
    assert retry.url == URL
    assert retry.dont_filter
    assert retry.meta["retry_times"] == 1
    assert spider.stats == {"total_pages": 0, "successful_pages": 0, "failed_pages": 0, "skipped_pages": 0}


def test_page_without_help_text_fails_once_retries_are_exhausted(spider):
    [error] = list(spider.parse_page(help_page(None, meta=exhausted(spider))))

    assert error == {"type": "error", "url": URL, "error": "helpContentData is null"}
    assert spider.stats["failed_pages"] == 1
    assert spider.stats["total_pages"] == 1
    assert spider.crawl_failures() == {"failed pages": 1}


def test_not_found_page_fails_a_crawl_of_listed_pages(spider):
    """TOC and member-list crawls fetch pages the docs list, so even a confirmed not-found page is lost."""
    assert isinstance(next(spider.parse_page(help_page(NOT_FOUND))), Request)

    [error] = list(spider.parse_page(help_page(NOT_FOUND, meta=exhausted(spider))))

    assert error["type"] == "error"
    assert spider.stats["failed_pages"] == 1


def test_confirmed_dead_link_is_skipped_where_dead_links_are_expected(crawler_spider):
    spider = crawler_spider(DeadLinksSpider)
    assert isinstance(next(spider.parse_page(help_page(NOT_FOUND))), Request)  # may be a transient error page

    assert list(spider.parse_page(help_page(NOT_FOUND, meta=exhausted(spider)))) == []
    assert spider.stats["skipped_pages"] == 1
    assert spider.crawl_failures() == {}


def test_dead_link_tolerance_does_not_cover_transient_faults(crawler_spider):
    spider = crawler_spider(DeadLinksSpider)

    [error] = list(spider.parse_page(help_page(None, meta=exhausted(spider))))

    assert error["type"] == "error"
    assert spider.stats["failed_pages"] == 1


def test_page_with_help_text_counts_once(spider):
    assert list(spider.parse_page(help_page({"helpText": "<p>doc</p>"}))) == [{"url": URL, "content": "<p>doc</p>"}]
    assert spider.stats["total_pages"] == 1
    assert spider.crawl_failures() == {}


# --- errback ----------------------------------------------------------------


def test_decompression_error_is_retried(spider):
    """Phase 10 lost IDraftFeatureData2.html?id=4.1.114 to 'Error -3 while decompressing data'."""
    failure = decompression_failure(spider)
    assert "decompressing data" in str(failure.value)

    [retry] = list(spider.handle_error(failure))

    assert isinstance(retry, Request)
    assert retry.url == URL
    assert retry.meta["retry_times"] == 1
    assert spider.stats["failed_pages"] == 0
    assert spider.crawler.stats.get_value("retry/count") == 1


def test_decompression_error_fails_once_retries_are_exhausted(spider):
    failure = decompression_failure(spider, meta=exhausted(spider))

    [error] = list(spider.handle_error(failure))

    assert error["type"] == "error"
    assert error["url"] == URL
    assert "decompressing data" in error["error"]
    assert spider.stats["failed_pages"] == 1
    assert spider.crawl_failures() == {"failed pages": 1}


def test_http_error_status_is_not_retried_again(spider):
    """RetryMiddleware already retried RETRY_HTTP_CODES; any status reaching the errback is final."""
    request = Request(URL)
    failure = Failure(HttpError(Response(URL, status=404, request=request), "Ignoring non-200 response"))
    failure.request = request

    [error] = list(spider.handle_error(failure))

    assert error["type"] == "error"
    assert spider.stats["failed_pages"] == 1


def test_start_urls_get_the_errback(spider):
    spider.start_urls = [URL]
    [request] = list(spider.start_requests())
    assert request.errback == spider.handle_error
    assert request.callback == spider.parse


# --- crawl outcome ----------------------------------------------------------


def test_callback_exceptions_count_as_lost_pages(spider):
    spider.crawler.stats.set_value("spider_exceptions/count", 2)
    assert spider.crawl_failures() == {"callback exceptions": 2}


def test_crawl_exit_code(spider):
    spider.crawler.spider = spider  # as Crawler.crawl() does
    assert crawl_exit_code(spider.crawler) == 0

    spider.stats["failed_pages"] = 1
    assert crawl_exit_code(spider.crawler) == 1


def test_crawl_exit_code_when_the_spider_never_started(spider):
    assert spider.crawler.spider is None
    assert crawl_exit_code(spider.crawler) == 1
