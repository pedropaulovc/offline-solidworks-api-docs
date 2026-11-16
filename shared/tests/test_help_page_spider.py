"""Tests for HelpPageSpider: transient faults are retried, and lost pages are counted, never dropped."""

import gzip
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pytest
from scrapy.downloadermiddlewares.httpcompression import HttpCompressionMiddleware
from scrapy.http import HtmlResponse, Request, Response
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.task import Clock
from twisted.python.failure import Failure

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from shared.constants import SOLIDWORKS_API_FULL_BASE_URL  # noqa: E402
from shared.help_page_spider import (  # noqa: E402
    NOT_FOUND_TITLE,
    RETRY_BACKOFF_SECONDS,
    RETRY_DELAY_META,
    CrawlMode,
    DeadLinkPolicy,
    HelpPageSpider,
    HelpTextProblem,
    MissingHelpTextError,
    RetryDelayMiddleware,
    crawl_exit_code,
    read_help_text,
)

URL = f"{SOLIDWORKS_API_FULL_BASE_URL}/sldworksapi/Example.html"
# What the live server returns for every page the 2027 run found without helpText
# (68 pages in phases 70 and 115, re-fetched 2026-11-16, DP_ImageQuality.htm included).
NOT_FOUND = {
    "ErrorTitle": NOT_FOUND_TITLE,
    "ErrorMessage": "The page might not exist or is temporarily unavailable. Try again or try searching for the topic.",
    "errorDetails": "on TreeExpand : HTML=help_list.htm?id= : V=2027 : L=english : P=api Error - ...",
}


class PagesSpider(HelpPageSpider):
    name = "help_pages"

    def parse_page(self, response: Response) -> Any:
        help_text = yield from self.help_text_or_retry(response)
        if help_text is not None:
            yield {"url": response.url, "content": help_text}

    parse = parse_page


class DeadLinksSpider(PagesSpider):
    name = "help_pages_dead_links"
    dead_link_policy = DeadLinkPolicy.SKIP_CONFIRMED


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
    "response, problem, reason",
    [
        (help_page(None), HelpTextProblem.NULL_HELP_CONTENT, "helpContentData is null"),
        (help_page({"helpText": ""}), HelpTextProblem.EMPTY_HELP_TEXT, "empty helpText"),
        (next_data_page(None), HelpTextProblem.NO_NEXT_DATA, "no __NEXT_DATA__ JSON"),
        (next_data_page("{not json"), HelpTextProblem.UNPARSEABLE_NEXT_DATA, "unparseable __NEXT_DATA__ JSON"),
        (
            next_data_page(json.dumps({"props": None})),
            HelpTextProblem.MISSING_OBJECT,
            "missing object in __NEXT_DATA__: props",
        ),
        (
            next_data_page(json.dumps({"props": {"pageProps": {}}})),
            HelpTextProblem.MISSING_OBJECT,
            "missing object in __NEXT_DATA__: helpContentData",
        ),
        (help_page(NOT_FOUND), HelpTextProblem.NOT_FOUND_PAGE, "server not-found page"),
        (
            help_page({"ErrorTitle": "Something went wrong."}),
            HelpTextProblem.SERVER_ERROR_PAGE,
            "server error page: Something went wrong.",
        ),
    ],
)
def test_read_help_text_reports_why_help_text_is_missing(response, problem, reason):
    with pytest.raises(MissingHelpTextError) as missing:
        read_help_text(response)
    assert missing.value.problem is problem
    assert str(missing.value) == reason


# --- response without help text ---------------------------------------------


def test_null_help_content_data_is_retried_after_a_delay(spider):
    """Phase 30 lost ISurface~GetIntersectCurveCount2.html to helpContentData: null (and crashed)."""
    [retry] = list(spider.parse_page(help_page(None)))

    assert isinstance(retry, Request)
    assert retry.url == URL
    assert retry.dont_filter
    assert retry.meta["retry_times"] == 1
    assert retry.meta[RETRY_DELAY_META] == RETRY_BACKOFF_SECONDS
    assert spider.stats["total_pages"] == spider.stats["failed_pages"] == 0

    [second] = list(spider.parse_page(help_page(None, meta=retry.meta)))
    assert second.meta[RETRY_DELAY_META] == 2 * RETRY_BACKOFF_SECONDS


def test_page_without_help_text_fails_once_retries_are_exhausted(spider):
    [error] = list(spider.parse_page(help_page(None, meta=exhausted(spider))))

    assert error == {"type": "error", "url": URL, "error": "helpContentData is null"}
    assert spider.stats["failed_pages"] == 1
    assert spider.stats["total_pages"] == 1
    assert spider.crawl_failures() == {"failed pages": 1}


def test_not_found_page_fails_a_crawl_of_listed_pages(spider):
    """TOC and member-list crawls fetch pages the docs list, so even a confirmed not-found page is lost."""
    assert isinstance(next(spider.parse_page(help_page(NOT_FOUND, meta={"retry_times": 1}))), Request)

    [error] = list(spider.parse_page(help_page(NOT_FOUND, meta=exhausted(spider))))

    assert error["type"] == "error"
    assert spider.stats["failed_pages"] == 1


def test_dead_link_is_refetched_once_then_skipped_quietly(crawler_spider, caplog):
    """The not-found page can be transient, so one delayed refetch confirms a dead link; no
    RETRY_TIMES refetches, and no ERROR log line for an expected skip."""
    spider = crawler_spider(DeadLinksSpider)
    [retry] = list(spider.parse_page(help_page(NOT_FOUND)))
    assert retry.meta["retry_times"] == 1
    assert retry.meta[RETRY_DELAY_META] == RETRY_BACKOFF_SECONDS

    with caplog.at_level(logging.WARNING):
        assert list(spider.parse_page(help_page(NOT_FOUND, meta=retry.meta))) == []

    assert spider.stats["skipped_pages"] == 1
    assert spider.crawl_failures() == {}
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert spider.crawler.stats.get_value("retry/max_reached") is None


def test_dead_link_tolerance_covers_only_the_not_found_page(crawler_spider):
    """Any other server error page, or no help text at all, is a transient fault even in link crawls."""
    spider = crawler_spider(DeadLinksSpider)

    assert isinstance(
        next(spider.parse_page(help_page({"ErrorTitle": "Something went wrong."}, {"retry_times": 1}))), Request
    )
    [error_page] = list(spider.parse_page(help_page({"ErrorTitle": "Something went wrong."}, exhausted(spider))))
    [null_page] = list(spider.parse_page(help_page(None, meta=exhausted(spider))))

    assert error_page["error"] == "server error page: Something went wrong."
    assert null_page["error"] == "helpContentData is null"
    assert spider.stats["failed_pages"] == 2
    assert spider.stats["skipped_pages"] == 0


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
    assert retry.meta[RETRY_DELAY_META] == RETRY_BACKOFF_SECONDS
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


def test_download_error_retry_middleware_exhausted_is_not_retried_again(spider):
    """RetryMiddleware already logged "Gave up retrying"; the errback must not retry or log it again."""
    failure = Failure(TimeoutError("timed out"))
    failure.request = Request(URL, meta=exhausted(spider))

    [error] = list(spider.handle_error(failure))

    assert error["type"] == "error"
    assert spider.crawler.stats.get_value("retry/max_reached") is None
    assert spider.crawler.stats.get_value("retry/count") is None


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


# --- retry delay ------------------------------------------------------------


def test_spider_registers_the_retry_delay_middleware(spider):
    assert RetryDelayMiddleware in spider.crawler.settings.getdict("DOWNLOADER_MIDDLEWARES")


def test_retry_delay_middleware_holds_a_retry_back():
    middleware = RetryDelayMiddleware()
    middleware.clock = Clock()

    assert middleware.process_request(Request(URL), spider=None) is None  # first attempts go straight out

    held = middleware.process_request(Request(URL, meta={RETRY_DELAY_META: 10}), spider=None)
    middleware.clock.advance(9.9)
    assert not held.called
    middleware.clock.advance(0.1)
    assert held.called
    assert held.result is None  # then the request continues down the middleware chain


# --- crawl outcome ----------------------------------------------------------


def finished(spider: HelpPageSpider, reason: str = "finished") -> HelpPageSpider:
    """Mark the crawl closed the way Crawler.crawl() and the engine do."""
    spider.crawler.spider = spider
    spider.crawler.stats.set_value("finish_reason", reason)
    return spider


def test_save_failures_count_as_lost_pages(spider):
    spider.save_failed(URL, OSError("disk full"))
    assert spider.crawl_failures() == {"save failures": 1}


def test_callback_exceptions_count_as_lost_pages(spider):
    spider.crawler.stats.set_value("spider_exceptions/count", 2)
    assert spider.crawl_failures() == {"callback exceptions": 2}


def test_failure_summary(spider):
    spider.stats["failed_pages"] = 1
    spider.save_failed(URL, OSError("disk full"))
    assert spider.failure_summary() == "1 failed pages, 1 save failures"


def test_crawl_exit_code(spider):
    finished(spider)
    assert crawl_exit_code(spider.crawler) == 0

    spider.stats["failed_pages"] = 1
    assert crawl_exit_code(spider.crawler) == 1


@pytest.mark.parametrize("reason", ["shutdown", "memusage_exceeded", "closespider_errorcount", None])
def test_crawl_that_stopped_early_fails(spider, reason):
    """Ctrl+C/SIGTERM, memory limits, and an engine that never opened drop queued pages without an errback."""
    finished(spider, reason)
    assert crawl_exit_code(spider.crawler) == 1


def test_page_count_cap_is_complete_only_for_test_runs(spider):
    finished(spider, "closespider_pagecount")
    assert crawl_exit_code(spider.crawler, CrawlMode.TEST) == 0
    assert crawl_exit_code(spider.crawler, CrawlMode.FULL) == 1


def test_crawl_exit_code_when_the_spider_never_started(spider):
    assert spider.crawler.spider is None
    assert crawl_exit_code(spider.crawler) == 1
