"""Base spider for help.solidworks.com crawls: retry transient faults, never drop a page silently.

The help server occasionally answers with a corrupt body or an incomplete page. The
2027 full run lost one page to each while every phase still exited 0:

- Phase 10 lost ``IDraftFeatureData2.html?id=4.1.114`` to "Error -3 while decompressing
  data: invalid stored block lengths". HttpCompressionMiddleware raises from
  ``process_response``, which bypasses RetryMiddleware and lands straight in the errback.
- Phase 30 lost ``ISurface~GetIntersectCurveCount2.html``: its ``__NEXT_DATA__`` came back
  with ``helpContentData: null`` (a refetch returns the full page) and the callback crashed.

``HelpPageSpider`` retries both through Scrapy's ``get_retry_request``, so ``RETRY_TIMES``
bounds them like any download retry. Only once a page's retries are exhausted is it
counted in ``failed_pages`` and logged to ``errors.jsonl``; each phase's ``run_crawler.py``
then exits non-zero via ``crawl_exit_code`` so ``run_pipeline.sh`` stops before the hole
reaches downstream phases.
"""

import json
from collections.abc import Generator, Iterable
from typing import Any

import scrapy
from scrapy.crawler import Crawler
from scrapy.downloadermiddlewares.retry import get_retry_request
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Request, Response
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.python.failure import Failure


class MissingHelpTextError(Exception):
    """A help page response that carries no ``helpText`` HTML.

    ``not_found`` marks the server's own "This page cannot be found." error page, which
    it serves (with HTTP 200) both for dead links and for momentary backend failures.
    """

    def __init__(self, reason: str, *, not_found: bool = False) -> None:
        super().__init__(reason)
        self.not_found = not_found


def read_help_text(response: Response) -> str:
    """The ``helpText`` HTML embedded in a help page's ``__NEXT_DATA__`` JSON.

    Raises MissingHelpTextError (with a short, fixed reason, used as the retry stats key)
    when the JSON is missing or unparseable or holds no help text.
    """
    json_text = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
    if not json_text:
        raise MissingHelpTextError("no __NEXT_DATA__ JSON")
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise MissingHelpTextError("unparseable __NEXT_DATA__ JSON") from e

    content: Any = data
    for key in ("props", "pageProps", "helpContentData"):
        content = content.get(key) if isinstance(content, dict) else None
    if not isinstance(content, dict):
        raise MissingHelpTextError("helpContentData is null" if content is None else "helpContentData is not an object")

    help_text = content.get("helpText")
    if isinstance(help_text, str) and help_text:
        return help_text
    if content.get("ErrorTitle"):
        raise MissingHelpTextError(f"server error page: {content['ErrorTitle']}", not_found=True)
    raise MissingHelpTextError("empty helpText")


class HelpPageSpider(scrapy.Spider):
    """Spider base that retries transient faults and counts every lost page.

    Subclasses keep a ``self.stats`` dict with at least ``total_pages``,
    ``successful_pages``, ``failed_pages`` and ``skipped_pages``.
    """

    stats: dict[str, Any]

    # Link-derived crawls (examples, referenced pages) follow cross-reference links,
    # dozens of which the server answers with "This page cannot be found." on every
    # fetch (stale ms-its:*.chm:: links, help_list.htm, empty stubs). When set, such a
    # page is skipped once its retries confirm it. TOC and member-list crawls fetch
    # pages the docs themselves list, so there it is a lost page like any other.
    dead_links_expected = False

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
            retry = get_retry_request(response.request, spider=self, reason=str(missing))
            if retry is not None:
                self.logger.warning(f"Retrying {response.url}: {missing}")
                yield retry
                return None
            self.stats["total_pages"] += 1
            if missing.not_found and self.dead_links_expected:
                self.logger.warning(f"Skipping dead link {response.url}: {missing}")
                self.stats["skipped_pages"] += 1
            else:
                yield self.page_failed(response.url, str(missing))
            return None
        self.stats["total_pages"] += 1
        return help_text

    def retry_or_fail(self, request: Request, reason: str | Exception) -> Generator[Any, None, None]:
        """Yield a retry of ``request``, or its error item once retries are exhausted."""
        retry = get_retry_request(request, spider=self, reason=reason)
        if retry is not None:
            self.logger.warning(f"Retrying {request.url}: {reason}")
            yield retry
        else:
            yield self.page_failed(request.url, str(reason))

    def handle_error(self, failure: Failure) -> Generator[Any, None, None]:
        """Errback: retry faults RetryMiddleware never saw; count the rest as failed.

        Errors raised while processing a response (decompression and the like) skip
        RetryMiddleware, so they are retried here. Download errors RetryMiddleware
        already retried carry its ``retry_times`` and are not retried again. HTTP error
        statuses (RETRY_HTTP_CODES are retried upstream) and ignored requests are final.
        """
        request: Request = failure.request  # type: ignore[attr-defined]
        if failure.check(HttpError, IgnoreRequest):
            yield self.page_failed(request.url, str(failure.value))
        else:
            yield from self.retry_or_fail(request, failure.value)

    def page_failed(self, url: str, error: str) -> dict[str, Any]:
        """Count a lost page and return the error item MetadataLogPipeline writes to errors.jsonl."""
        self.stats["failed_pages"] += 1
        self.logger.error(f"Failed to crawl {url}: {error}")
        return {"type": "error", "url": url, "error": error}

    def crawl_failures(self) -> dict[str, int]:
        """Nonzero counts of events that left holes in the corpus, by kind.

        Each kind is counted once at its source (not via log counters, which depend on
        LOG_LEVEL and count unrelated errors): pages that failed after their retries,
        and callback exceptions, which never reach the errback (the crawler's stats
        record them).
        """
        counts = {"failed pages": self.stats["failed_pages"]}
        crawler = getattr(self, "crawler", None)  # absent on spiders built outside a crawler
        if crawler is not None:
            counts["callback exceptions"] = crawler.stats.get_value("spider_exceptions/count", 0)
        return {kind: count for kind, count in counts.items() if count}


def crawl_exit_code(crawler: Crawler) -> int:
    """Process exit code for a finished crawl: 0 when no page was lost, else 1 (with a summary)."""
    spider = crawler.spider
    if not isinstance(spider, HelpPageSpider):
        print("\n[ERROR] Crawl never started; no pages were fetched.")
        return 1
    failures = spider.crawl_failures()
    if not failures:
        return 0
    summary = ", ".join(f"{count} {kind}" for kind, count in failures.items())
    print(f"\n[ERROR] Crawl lost pages ({summary}); see metadata/errors.jsonl and the crawl log.")
    return 1
