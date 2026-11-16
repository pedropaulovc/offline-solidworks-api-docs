"""Base spider for help.solidworks.com crawls: retry transient faults, never drop a page silently.

The help server occasionally answers with a corrupt body or an incomplete page. The
2027 full run lost one page to each while every phase still exited 0:

- Phase 10 lost ``IDraftFeatureData2.html?id=4.1.114`` to "Error -3 while decompressing
  data: invalid stored block lengths". HttpCompressionMiddleware raises from
  ``process_response``, which bypasses RetryMiddleware and lands straight in the errback.
- Phase 30 lost ``ISurface~GetIntersectCurveCount2.html``: its ``__NEXT_DATA__`` came back
  with ``helpContentData: null`` (a refetch returns the full page) and the callback crashed.

``HelpPageSpider`` retries both through Scrapy's ``get_retry_request``, so ``RETRY_TIMES``
bounds them like any download retry, and ``RetryDelayMiddleware`` spaces the attempts out
so a backend hiccup of a few seconds does not use them all up. Only once a page's retries
are exhausted is it counted in ``failed_pages`` and logged to ``errors.jsonl``; each
phase's ``run_crawler.py`` then exits non-zero via ``crawl_exit_code`` so
``run_pipeline.sh`` stops before the hole reaches downstream phases.
"""

import json
from collections.abc import Generator, Iterable
from enum import Enum
from typing import Any

import scrapy
from scrapy.crawler import Crawler
from scrapy.downloadermiddlewares.retry import get_retry_request
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Request, Response
from scrapy.settings import BaseSettings
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import IReactorTime
from twisted.internet.task import deferLater
from twisted.python.failure import Failure

# Retry n of a page waits RETRY_BACKOFF_SECONDS * n before it is fetched (5 s, 10 s,
# 15 s with RETRY_TIMES = 3), so the attempts span half a minute rather than a moment.
RETRY_BACKOFF_SECONDS = 5
RETRY_DELAY_META = "retry_delay"

# The title of the server's error page for a page it does not have. It is also served,
# briefly, for pages it does have ("The page might not exist or is temporarily
# unavailable"), so even where dead links are expected it is refetched once.
NOT_FOUND_TITLE = "This page cannot be found."
DEAD_LINK_CONFIRMATIONS = 1


class HelpTextProblem(Enum):
    """Why a help page response carries no ``helpText`` HTML."""

    NO_NEXT_DATA = "no __NEXT_DATA__ JSON"
    UNPARSEABLE_NEXT_DATA = "unparseable __NEXT_DATA__ JSON"
    MISSING_OBJECT = "missing object in __NEXT_DATA__"
    NULL_HELP_CONTENT = "helpContentData is null"
    EMPTY_HELP_TEXT = "empty helpText"
    NOT_FOUND_PAGE = "server not-found page"
    SERVER_ERROR_PAGE = "server error page"


class MissingHelpTextError(Exception):
    """A help page response that carries no ``helpText`` HTML, and why.

    ``str()`` is a short reason from a fixed set (it names retry stats keys).
    """

    def __init__(self, problem: HelpTextProblem, detail: str = "") -> None:
        super().__init__(f"{problem.value}: {detail}" if detail else problem.value)
        self.problem = problem


class DeadLinkPolicy(Enum):
    """What a page the server reports as not found means for a crawl."""

    # The docs' own TOC or member lists name the page: not finding it loses a page.
    FAIL = "fail"
    # Cross-reference links, dozens of which point at pages the server never had
    # (stale ms-its:*.chm:: links, help_list.htm, stubs like DP_ImageQuality.htm): a page
    # still not found after DEAD_LINK_CONFIRMATIONS refetches is skipped as a dead link.
    SKIP_CONFIRMED = "skip_confirmed"


class CrawlMode(Enum):
    """How a run_crawler.py invocation may end and still count as complete."""

    FULL = ("finished",)
    # --test caps the crawl with CLOSESPIDER_PAGECOUNT
    TEST = ("finished", "closespider_pagecount")


def read_help_text(response: Response) -> str:
    """The ``helpText`` HTML embedded in a help page's ``__NEXT_DATA__`` JSON.

    Raises MissingHelpTextError when the JSON is missing or unparseable or holds no help text.
    """
    json_text = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
    if not json_text:
        raise MissingHelpTextError(HelpTextProblem.NO_NEXT_DATA)
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise MissingHelpTextError(HelpTextProblem.UNPARSEABLE_NEXT_DATA) from e

    node: Any = data
    for key in ("props", "pageProps"):
        node = node.get(key) if isinstance(node, dict) else None
        if not isinstance(node, dict):
            raise MissingHelpTextError(HelpTextProblem.MISSING_OBJECT, key)
    if "helpContentData" not in node:
        raise MissingHelpTextError(HelpTextProblem.MISSING_OBJECT, "helpContentData")
    content = node["helpContentData"]
    if content is None:
        raise MissingHelpTextError(HelpTextProblem.NULL_HELP_CONTENT)
    if not isinstance(content, dict):
        raise MissingHelpTextError(HelpTextProblem.MISSING_OBJECT, "helpContentData")

    help_text = content.get("helpText")
    if isinstance(help_text, str) and help_text:
        return help_text
    error_title = content.get("ErrorTitle")
    if error_title == NOT_FOUND_TITLE:
        raise MissingHelpTextError(HelpTextProblem.NOT_FOUND_PAGE)
    if error_title:
        raise MissingHelpTextError(HelpTextProblem.SERVER_ERROR_PAGE, str(error_title))
    raise MissingHelpTextError(HelpTextProblem.EMPTY_HELP_TEXT)


class RetryDelayMiddleware:
    """Downloader middleware holding a retry back for its ``retry_delay`` meta (seconds).

    Registered by HelpPageSpider; the retries it issues set the delay.
    """

    clock: IReactorTime | None = None  # the running reactor unless a test sets one

    def process_request(self, request: Request, spider: scrapy.Spider) -> Deferred[None] | None:
        delay = request.meta.get(RETRY_DELAY_META)
        if not delay:
            return None
        clock = self.clock
        if clock is None:
            from twisted.internet import reactor as clock  # imported late: Scrapy installs it
        return deferLater(clock, delay, lambda: None)


class HelpPageSpider(scrapy.Spider):
    """Spider base that retries transient faults and counts every lost page."""

    dead_link_policy = DeadLinkPolicy.FAIL

    @classmethod
    def update_settings(cls, settings: BaseSettings) -> None:
        super().update_settings(settings)
        middlewares = settings.getdict("DOWNLOADER_MIDDLEWARES")
        settings.set("DOWNLOADER_MIDDLEWARES", {**middlewares, RetryDelayMiddleware: 100}, priority="spider")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Subclasses add their own counters with self.stats.update(...).
        self.stats: dict[str, Any] = {
            "total_pages": 0,
            "successful_pages": 0,
            "failed_pages": 0,
            "skipped_pages": 0,
            "save_failures": 0,
        }

    def start_requests(self) -> Iterable[Request]:
        """Seed ``start_urls`` with the errback, so a failed seed is retried and counted too."""
        for url in self.start_urls:
            yield Request(url, callback=self.parse, errback=self.handle_error, dont_filter=True)

    def help_text_or_retry(self, response: Response) -> Generator[Any, None, str | None]:
        """Return the page's help text, or yield a retry request / error item and return None.

        Use as ``help_text = yield from self.help_text_or_retry(response)``. Counts the
        page in ``total_pages`` once its outcome is final (not while it is being retried).
        """
        try:
            help_text = read_help_text(response)
        except MissingHelpTextError as missing:
            yield from self._missing_help_text(response, missing)
            return None
        self.stats["total_pages"] += 1
        return help_text

    def _missing_help_text(self, response: Response, missing: MissingHelpTextError) -> Generator[Any, None, None]:
        dead_link = (
            missing.problem is HelpTextProblem.NOT_FOUND_PAGE and self.dead_link_policy is DeadLinkPolicy.SKIP_CONFIRMED
        )
        retry = self.retry_request(
            response.request, str(missing), max_retry_times=DEAD_LINK_CONFIRMATIONS if dead_link else None
        )
        if retry is not None:
            yield retry
            return
        self.stats["total_pages"] += 1
        if dead_link:
            self.logger.warning(f"Skipping dead link {response.url}: {missing}")
            self.stats["skipped_pages"] += 1
            return
        yield self.page_failed(response.url, str(missing))

    def retry_request(
        self, request: Request, reason: str | Exception, max_retry_times: int | None = None
    ) -> Request | None:
        """A delayed retry of ``request``, or None once its retries are used up.

        Requests RetryMiddleware already retried to its limit carry its ``retry_times``
        and get no further retry (and no second "Gave up retrying" log line).
        """
        if max_retry_times is None:
            max_retry_times = request.meta.get("max_retry_times", self.crawler.settings.getint("RETRY_TIMES"))
        if request.meta.get("retry_times", 0) >= max_retry_times:
            return None
        retry = get_retry_request(request, spider=self, reason=reason, max_retry_times=max_retry_times)
        if retry is None:
            return None
        retry.meta[RETRY_DELAY_META] = RETRY_BACKOFF_SECONDS * retry.meta["retry_times"]
        self.logger.warning(f"Retrying {request.url} in {retry.meta[RETRY_DELAY_META]}s: {reason}")
        return retry

    def retry_or_fail(self, request: Request, reason: str | Exception) -> Generator[Any, None, None]:
        """Yield a retry of ``request``, or its error item once retries are exhausted."""
        retry = self.retry_request(request, reason)
        if retry is not None:
            yield retry
            return
        yield self.page_failed(request.url, str(reason))

    def handle_error(self, failure: Failure) -> Generator[Any, None, None]:
        """Errback: retry faults RetryMiddleware never saw; count the rest as failed.

        Errors raised while processing a response (decompression and the like) skip
        RetryMiddleware, so they are retried here. HTTP error statuses (RETRY_HTTP_CODES
        are retried upstream) and ignored requests are final.
        """
        request: Request = failure.request  # type: ignore[attr-defined]
        if failure.check(HttpError, IgnoreRequest):
            yield self.page_failed(request.url, str(failure.value))
            return
        yield from self.retry_or_fail(request, failure.value)

    def page_failed(self, url: str, error: str) -> dict[str, Any]:
        """Count a lost page and return the error item MetadataLogPipeline writes to errors.jsonl."""
        self.stats["failed_pages"] += 1
        self.logger.error(f"Failed to crawl {url}: {error}")
        return {"type": "error", "url": url, "error": error}

    def save_failed(self, url: str, error: Exception) -> None:
        """Count a page HtmlSavePipeline could not write: fetched, but still a hole."""
        self.stats["save_failures"] += 1
        self.logger.error(f"Failed to save HTML for {url}: {error}")

    def crawl_failures(self) -> dict[str, int]:
        """Nonzero counts of events that left holes in the corpus, by kind.

        Each kind is counted once at its source (not via log counters, which depend on
        LOG_LEVEL and count unrelated errors): pages that failed after their retries,
        pages that could not be saved, and callback exceptions, which never reach the
        errback (the crawler's stats record them).
        """
        counts = {
            "failed pages": self.stats["failed_pages"],
            "save failures": self.stats["save_failures"],
        }
        crawler = getattr(self, "crawler", None)  # absent on spiders built outside a crawler
        if crawler is not None:
            counts["callback exceptions"] = crawler.stats.get_value("spider_exceptions/count", 0)
        return {kind: count for kind, count in counts.items() if count}

    def failure_summary(self) -> str:
        """``crawl_failures()`` as one line, e.g. "1 failed pages, 2 save failures"."""
        return ", ".join(f"{count} {kind}" for kind, count in self.crawl_failures().items())


def crawl_exit_code(crawler: Crawler, mode: CrawlMode = CrawlMode.FULL) -> int:
    """Process exit code for a crawl: 0 when it ran to completion without losing a page, else 1.

    A crawl that stopped early (Ctrl+C or SIGTERM "shutdown", memusage_exceeded, an engine
    that never opened) dropped its queued requests without any errback, so it is
    incomplete however clean its counters look.
    """
    spider = crawler.spider
    if not isinstance(spider, HelpPageSpider):
        print("\n[ERROR] Crawl never started; no pages were fetched.")
        return 1
    finish_reason = crawler.stats.get_value("finish_reason")
    if finish_reason not in mode.value:
        print(
            f"\n[ERROR] Crawl did not run to completion (finish reason: {finish_reason}); queued pages were never fetched."
        )
        return 1
    if spider.crawl_failures():
        print(f"\n[ERROR] Crawl lost pages ({spider.failure_summary()}); see metadata/errors.jsonl and the crawl log.")
        return 1
    return 0
