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
  Converts relative URLs to full SolidWorks API documentation URLs, resolving CHM
  aliases first (see `chm_aliases.py`)

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

### `chm_aliases.py`

`resolve_chm_alias(link)` rewrites a compiled-help alias link to the absolute URL of the
web page it names; `chm_alias_page(link)` returns that page as a path under the API root.
Many cross-file links still carry the CHM form, `ms-its:swconst.chm::/DP_Dimensions.htm`
or `sldworksAPIProgGuide.chm::/OVERVIEW/Type_Libraries.htm`; the web help serves each
CHM's pages from the folder under `/api` named after it, lowercased (`swconst/`,
`sldworksapiprogguide/`). Joined onto the linking page's folder as written, the alias is
a URL the server answers with its not-found page. An alias names the same page wherever
it is written, so whatever precedes the CHM name (the linking folder, `../`, `ms-its:`,
`mk:@MSITStore:`) is dropped and the page is placed under the API root; the result does
not depend on how deep the linking page sits. The path inside the CHM keeps its case: the
server matches paths case-insensitively, as do Phase 115's and Phase 120's in-bundle
lookups.

`relative_chm_alias(link, page_url)` gives the same page as a link relative to the page
the alias is written on (`../swconst/DP_Dimensions.htm`), the form of that page's other
relative links.

Used where links leave the help HTML: `convert_to_full_url` (`<see href>` in phases
40/50/60), the example URLs phases 40/50 record (as API-root paths, `/sldworksapi/X.htm`),
Phase 70's legacy example harvester, Phase 115's link targets, and the Phase 110/115
HTML-to-Markdown conversion (`relative_chm_alias`), so neither the guide Markdown nor the
Phase 90 guides catalog built from it carries an alias.

### `guide_pages.py`

`read_guide_pages(markdown_root)` returns the pages a guide phase (110, 115) lists in its
`metadata/files_created.jsonl`, with each page's help path and path under the root.
Phases 90 and 120 ship guide Markdown from this list, not from the files on disk, so a
page an earlier run left in the tree never ships. A missing tree or manifest (a fresh
clone: manifests are committed, `output/` is not) raises `GuidePagesUnavailable`, which
both phases warn about and skip; a tree missing a listed page raises
`FileNotFoundError`. `case_collisions(paths)` finds paths that differ only in case;
Phase 120 fails the export on any, since unpacking the bundle on Windows or macOS would
keep only one of each.

### `markdown_links.py`

`markdown_destination(path, fragment="")` builds the Markdown link destination for a
bundle file path. Guide pages are named after TOC titles, so a `#` in the name is
percent-encoded (it would start the fragment) and a path with a space or parenthesis is
angle-wrapped. Phase 110's URL rewriter and Phase 120's guide-link rewrite, See Also and
`<see href>` rendering all use it.

### `help_page_spider.py`

`HelpPageSpider`, the base class of all five crawl spiders (phases 10, 30, 70, 100,
115). help.solidworks.com occasionally answers with a corrupt body or an incomplete page;
the base class retries those instead of dropping the page:

- `handle_error` (the errback) retries download errors (timeouts, lost connections),
  `RETRY_HTTP_CODES` statuses, and errors raised while processing a response, such as
  "Error -3 while decompressing data". Other HTTP statuses and ignored requests are final.
  Scrapy's RetryMiddleware is disabled, so every retry takes this one path.
- `help_text_or_retry` (use as `help_text = yield from self.help_text_or_retry(response)`)
  retries pages whose `__NEXT_DATA__` is missing or unparseable, or whose
  `helpContentData`/`helpText` is null or empty.

Retries go through `get_retry_request`, so `RETRY_TIMES` bounds them, and retry *n* is
held back `RETRY_BACKOFF_SECONDS * n` seconds (5, 10, 15) so a short backend hiccup does
not use up every attempt. The wait happens outside the downloader (`schedule_later`: a
reactor timer, then `engine.crawl`, with the spider kept open while requests wait), so a
waiting retry holds no `CONCURRENT_REQUESTS` slot. The retry stats key is a fixed reason
(exception class, `HelpTextProblem` value, HTTP status); details such as the server's
error title go to the log and `errors.jsonl`.

Once a page's retries are exhausted it counts in `failed_pages` and is logged to
`errors.jsonl`. Pages `HtmlSavePipeline` cannot write count in `save_failures`
(`save_failed()`), and callback exceptions count too. `crawl_exit_code(crawler, mode)`
makes `run_crawler.py` exit 1 when any of those happened or the crawl did not finish (it
closed for any reason but `finished`; `--test` runs also accept `closespider_pagecount`),
so `run_pipeline.sh` stops.

Only the server's "This page cannot be found." page counts as a dead link, and only where
`dead_link_policy = DeadLinkPolicy.SKIP_CONFIRMED` (phases 70 and 115, which follow
cross-reference links). The server shows the same page during outages, so such a page is
refetched once a minute later (counted apart from the retry budget, so a page whose
earlier attempts timed out still gets it) and only then skipped. Skipped dead links are
listed, sorted, under `dead_links` in the phase's `crawl_stats.json` and counted in the
exit summary, so a page that newly turns up there shows in the committed metadata's
diff. Everywhere else, and for any other error page, a not-found page is a failure like
any page without help text.

Each crawl phase's `MetadataLogPipeline` appends to `urls_crawled.jsonl` as downloads
finish, so it calls `sort_url_log` when the spider closes: the committed log is ordered
by URL, and a recrawl's diff shows only pages that changed.

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
