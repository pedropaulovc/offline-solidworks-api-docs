# Shared Utilities

This directory contains shared utility modules used across multiple phases of the SolidWorks API documentation pipeline.

## Modules

### `xmldoc_links.py`

Utilities for converting HTML anchor tags to XMLDoc format for IntelliSense documentation.

**Functions:**

- `convert_links_to_see_refs(html: str) -> str`
  Converts HTML `<a>` tags to XMLDoc `<see cref>` or `<see href>` tags
  - Type references → `<see cref="Namespace.Type.Member">text</see>`
  - Guide pages → `<see href="url">text</see>`

- `parse_href_to_cref(href: str) -> Optional[str]`
  Extracts cref value from type reference URLs
  - Returns `None` for non-type references (guide pages)

- `convert_to_full_url(href: str) -> str`
  Converts relative URLs to full SolidWorks API documentation URLs

**Usage:**

```python
from shared.xmldoc_links import convert_links_to_see_refs

html = '<a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html">IFeature</a>'
result = convert_links_to_see_refs(html)
# Returns: '<see cref="SolidWorks.Interop.sldworks.IFeature">IFeature</see>'
```

**Testing:**

```bash
uv run pytest shared/tests/ -v
```

### `help_page_spider.py`

`HelpPageSpider`, the base class of all five crawl spiders (phases 10, 30, 70, 100,
115). help.solidworks.com occasionally answers with a corrupt body or an incomplete page;
the base class retries those instead of dropping the page:

- `handle_error` (the errback) retries errors raised while processing a response, such as
  "Error -3 while decompressing data", which bypass Scrapy's RetryMiddleware. HTTP error
  statuses and ignored requests are final; download errors RetryMiddleware already retried
  are not retried again.
- `help_text_or_retry` (use as `help_text = yield from self.help_text_or_retry(response)`)
  retries pages whose `__NEXT_DATA__` is missing or unparseable, or whose
  `helpContentData`/`helpText` is null or empty.

Retries go through `get_retry_request`, so `RETRY_TIMES` bounds them, and
`RetryDelayMiddleware` (registered by the spider) holds retry *n* back for
`RETRY_BACKOFF_SECONDS * n` seconds (5, 10, 15) so a short backend hiccup does not use
up every attempt. Once a page's retries are exhausted it counts in `failed_pages` and is
logged to `errors.jsonl`. Pages `HtmlSavePipeline` cannot write count in `save_failures`
(`save_failed()`), and callback exceptions count too. `crawl_exit_code(crawler, mode)`
makes `run_crawler.py` exit 1 when any of those happened or the crawl did not finish (it
closed for any reason but `finished`; `--test` runs also accept `closespider_pagecount`),
so `run_pipeline.sh` stops.

Only the server's "This page cannot be found." page counts as a dead link, and only where
`dead_link_policy = DeadLinkPolicy.SKIP_CONFIRMED` (phases 70 and 115, which follow
cross-reference links): such a page is refetched once, after a delay, then skipped with a
warning. Everywhere else, and for any other error page, it is a failure like any page
without help text.

## Design Principles

- **Stateless**: All functions are pure and don't rely on global state
- **Reusable**: Can be imported by any phase of the pipeline
- **Well-tested**: Comprehensive unit tests for all functionality
- **Documented**: Clear docstrings and examples

## Adding New Shared Modules

When adding new shared utilities:

1. Create the module in `shared/`
2. Add comprehensive unit tests in `shared/tests/`
3. Update this README with documentation
4. Ensure all tests pass before committing
