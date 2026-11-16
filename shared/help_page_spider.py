"""Base spider for help.solidworks.com crawls: retry transient faults, never drop a page silently.

The help server occasionally answers with a corrupt body or an incomplete page. The
2027 full run lost one page to each while every phase still exited 0:

- Phase 10 lost ``IDraftFeatureData2.html?id=4.1.114`` to "Error -3 while decompressing
  data: invalid stored block lengths". HttpCompressionMiddleware raises from
  ``process_response``, which bypasses RetryMiddleware and lands straight in the errback.
- Phase 30 lost ``ISurface~GetIntersectCurveCount2.html``: its ``__NEXT_DATA__`` came back
  with ``helpContentData: null`` (a refetch returns the full page) and the callback crashed.

``HelpPageSpider`` issues every retry itself, through Scrapy's ``get_retry_request``, so
``RETRY_TIMES`` bounds them: response-processing errors like those above, pages without
help text, and the HTTP statuses (``RETRY_HTTP_CODES``) and download errors Scrapy's
RetryMiddleware used to retry back to back (the spider disables it). Retry n is held back
``RETRY_BACKOFF_SECONDS * n`` seconds outside the downloader, so a backend hiccup of a few
seconds does not use up every attempt and a waiting retry does not occupy a
CONCURRENT_REQUESTS slot. Only once a page's retries are exhausted is it counted in
``failed_pages`` and logged to ``errors.jsonl``; each phase's ``run_crawler.py`` then exits
non-zero via ``crawl_exit_code`` so ``run_pipeline.sh`` stops before the hole reaches
downstream phases.
"""

import bisect
import json
from collections.abc import Generator, Iterable
from enum import Enum
from pathlib import Path
from typing import Any, Self

import jsonlines
import scrapy
from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.downloadermiddlewares.retry import get_retry_request
from scrapy.exceptions import DontCloseSpider, IgnoreRequest
from scrapy.http import Request, Response
from scrapy.settings import BaseSettings
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy.utils.response import response_status_message
from twisted.internet.interfaces import IDelayedCall, IReactorTime
from twisted.python.failure import Failure

# Retry n of a page waits RETRY_BACKOFF_SECONDS * n before it is fetched (5 s, 10 s,
# 15 s with RETRY_TIMES = 3), so the attempts span half a minute rather than a moment.
RETRY_BACKOFF_SECONDS = 5

# The title of the server's error page for a page it does not have. It is also served
# for pages it does have during outages ("The page might not exist or is temporarily
# unavailable"), so even where dead links are expected a not-found page is refetched
# once, a minute later (well past a passing hiccup; the wait holds no download slot),
# before it is skipped. Skipped dead links are listed in crawl_stats.json, so a page
# that newly turns up there shows in the committed metadata's diff.
NOT_FOUND_TITLE = "This page cannot be found."
DEAD_LINK_CONFIRMATIONS = 1
DEAD_LINK_CONFIRMATION_DELAY_SECONDS = 60
# Counted apart from retry_times, which other faults (a timeout, a null page) also use up.
NOT_FOUND_CONFIRMATIONS_META = "not_found_confirmations"


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

    ``problem.value`` is the fixed reason (it names retry stats keys); ``str()`` adds the
    detail (a key name, the server's error title) for the log and errors.jsonl.
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
    # still not found when refetched a minute later is skipped as a dead link.
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


class HelpPageSpider(scrapy.Spider):
    """Spider base that retries transient faults and counts every lost page."""

    dead_link_policy = DeadLinkPolicy.FAIL
    clock: IReactorTime | None = None  # the running reactor unless a test sets one

    @classmethod
    def update_settings(cls, settings: BaseSettings) -> None:
        super().update_settings(settings)
        # Every retry is issued by this class (see handle_error) and held back outside the
        # downloader; RetryMiddleware would retry the same faults back to back. Disabled by
        # the dotted path DOWNLOADER_MIDDLEWARES_BASE uses (a class key would not match it).
        middlewares = settings.getdict("DOWNLOADER_MIDDLEWARES")
        retry_middleware = "scrapy.downloadermiddlewares.retry.RetryMiddleware"
        settings.set("DOWNLOADER_MIDDLEWARES", {**middlewares, retry_middleware: None}, priority="spider")

    @classmethod
    def from_crawler(cls, crawler: Crawler, *args: Any, **kwargs: Any) -> Self:
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider._stay_open_for_waiting_requests, signal=signals.spider_idle)
        crawler.signals.connect(spider._cancel_waiting_requests, signal=signals.spider_closed)
        return spider

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._waiting: set[IDelayedCall] = set()
        # Subclasses add their own counters with self.stats.update(...).
        self.stats: dict[str, Any] = {
            "total_pages": 0,
            "successful_pages": 0,
            "failed_pages": 0,
            "skipped_pages": 0,
            "save_failures": 0,
            "dead_links": [],  # sorted, so crawl_stats.json is deterministic
        }

    def start_requests(self) -> Iterable[Request]:
        """Seed ``start_urls`` with the errback, so a failed seed is retried and counted too."""
        for url in self.start_urls:
            yield Request(url, callback=self.parse, errback=self.handle_error, dont_filter=True)

    def schedule_later(self, request: Request, delay: float) -> None:
        """Hand ``request`` to the engine after ``delay`` seconds.

        The wait happens outside the downloader, so it holds no CONCURRENT_REQUESTS slot;
        the spider stays open until every waiting request has been handed over.
        """
        clock = self.clock
        if clock is None:
            from twisted.internet import reactor as clock  # imported late: Scrapy installs it

        def release() -> None:
            self._waiting.discard(call)
            self.crawler.engine.crawl(request)

        call = clock.callLater(delay, release)
        self._waiting.add(call)

    def _stay_open_for_waiting_requests(self) -> None:
        if self._waiting:
            raise DontCloseSpider

    def _cancel_waiting_requests(self) -> None:
        for call in self._waiting:
            call.cancel()
        self._waiting.clear()

    def help_text_or_retry(self, response: Response) -> Generator[Any, None, str | None]:
        """Return the page's help text, or schedule a retry / yield an error item and return None.

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
        if missing.problem is HelpTextProblem.NOT_FOUND_PAGE and self.dead_link_policy is DeadLinkPolicy.SKIP_CONFIRMED:
            self._confirm_dead_link(response)
            return
        if self.retry_later(response.request, missing.problem.value, str(missing)) is not None:
            return
        self.stats["total_pages"] += 1
        yield self.page_failed(response.url, str(missing))

    def _confirm_dead_link(self, response: Response) -> None:
        confirmations = response.meta.get(NOT_FOUND_CONFIRMATIONS_META, 0)
        if confirmations < DEAD_LINK_CONFIRMATIONS:
            delay = DEAD_LINK_CONFIRMATION_DELAY_SECONDS
            self.logger.info(f"Not found; refetching in {delay}s to confirm a dead link: {response.url}")
            meta = {**response.meta, NOT_FOUND_CONFIRMATIONS_META: confirmations + 1}
            self.schedule_later(response.request.replace(meta=meta, dont_filter=True), delay)
            return
        self.logger.warning(f"Skipping dead link {response.url}: still not found after {confirmations} refetch(es)")
        self.stats["total_pages"] += 1
        self.stats["skipped_pages"] += 1
        bisect.insort(self.stats["dead_links"], response.url)

    def retry_later(self, request: Request, reason: str | Exception, detail: str = "") -> Request | None:
        """Schedule a delayed retry of ``request`` and return it, or None once its retries are used up.

        ``reason`` names the retry stats key, so it comes from a fixed set (an exception
        class, a HelpTextProblem value, an HTTP status); ``detail`` only goes to the log.
        """
        max_retry_times = request.meta.get("max_retry_times", self.crawler.settings.getint("RETRY_TIMES"))
        # The one exhaustion check: page_failed logs the give-up, so get_retry_request
        # never reaches its own "Gave up retrying" ERROR line.
        if request.meta.get("retry_times", 0) >= max_retry_times:
            return None
        retry = get_retry_request(request, spider=self, reason=reason, max_retry_times=max_retry_times)
        assert retry is not None  # budget left, checked above
        delay = RETRY_BACKOFF_SECONDS * retry.meta["retry_times"]
        self.logger.warning(f"Retrying {request.url} in {delay}s: {detail or reason}")
        self.schedule_later(retry, delay)
        return retry

    def retry_or_fail(self, request: Request, reason: str | Exception, detail: str = "") -> Generator[Any, None, None]:
        """Schedule a retry of ``request``, or yield its error item once retries are exhausted."""
        if self.retry_later(request, reason, detail) is not None:
            return
        yield self.page_failed(request.url, detail or str(reason))

    def handle_error(self, failure: Failure) -> Generator[Any, None, None]:
        """Errback: retry transient faults, count the rest as failed.

        Retried: download errors (timeouts, lost connections), errors raised while
        processing a response (decompression and the like) and RETRY_HTTP_CODES statuses.
        Final: any other HTTP status, and ignored requests.
        """
        request: Request = failure.request  # type: ignore[attr-defined]
        if failure.check(HttpError):  # before IgnoreRequest, its base class
            status = failure.value.response.status
            reason = response_status_message(status)
            if status not in {int(code) for code in self.crawler.settings.getlist("RETRY_HTTP_CODES")}:
                yield self.page_failed(request.url, reason)
                return
            yield from self.retry_or_fail(request, reason)
            return
        if failure.check(IgnoreRequest):
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
    if dead_links := spider.stats["dead_links"]:
        print(
            f"\nSkipped {len(dead_links)} dead links (still not found when refetched); "
            "they are listed under dead_links in metadata/crawl_stats.json."
        )
    if spider.crawl_failures():
        print(f"\n[ERROR] Crawl lost pages ({spider.failure_summary()}); see metadata/errors.jsonl and the crawl log.")
        return 1
    return 0


def sort_url_log(urls_file: Path) -> None:
    """Rewrite a crawl's ``urls_crawled.jsonl`` with its records sorted by URL.

    MetadataLogPipeline appends a record as each concurrent download finishes, so the
    line order differs on every crawl. Called when the spider closes, so the committed
    log changes only where a page did (a new hash, a lost or added URL), not wholesale.
    """
    if not urls_file.exists():
        return
    with jsonlines.open(urls_file) as reader:
        records = list(reader)
    records.sort(key=lambda record: record.get("url") or "")
    staged = urls_file.with_suffix(".jsonl.sorting")
    with jsonlines.open(staged, mode="w") as writer:  # the format the pipeline appends in
        writer.write_all(records)
    staged.replace(urls_file)
