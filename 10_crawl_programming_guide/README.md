# Phase 10: Programming Guide Crawler

This directory contains the Scrapy-based crawler for downloading the SolidWorks Programming Guide documentation. The crawler uses the SolidWorks expandToc JSON API to discover all documentation pages (starting from id=1), then extracts clean HTML content from the `__NEXT_DATA__` JSON embedded in each page.

**Key Difference from Phase 01**: This phase crawls the Programming Guide (id=1) instead of the API Reference (id=2).

## 📁 Directory Structure

```
10_crawl_programming_guide/
├── solidworks_scraper/       # Scrapy project
│   ├── settings.py          # Crawler configuration
│   ├── pipelines.py         # Data processing pipelines
│   ├── items.py             # Scrapy item definitions
│   └── spiders/
│       └── api_docs_spider.py  # Main spider implementation
├── tests/                   # Test suite
│   ├── test_spider.py      # Spider tests
│   ├── test_pipelines.py   # Pipeline tests
│   └── fixtures/           # Test HTML samples
├── output/                  # Crawl output (gitignored)
│   └── html/               # Downloaded HTML files
├── metadata/                # Crawl metadata
│   ├── urls_crawled.jsonl    # List of crawled URLs
│   ├── crawl_stats.json      # Crawl statistics
│   ├── errors.jsonl          # Error log
│   └── manifest.json         # Crawl configuration
├── run_crawler.py          # Main entry point
├── validate_crawl.py       # Validation script
└── README.md               # This file
```

## 🚀 Usage

### Quick Test Run

Test the crawler with a small subset of pages:

```bash
# From project root
uv run python 10_crawl_programming_guide/run_crawler.py --test

# Or from this directory
cd 10_crawl_programming_guide
uv run python run_crawler.py --test
```

### Full Crawl

Run a complete crawl of the Programming Guide documentation:

```bash
uv run python 10_crawl_programming_guide/run_crawler.py
```

**Note**: A full crawl will:
- Take approximately 30-40 seconds to complete
- Download ~6 MB of compressed HTML
- Respect a 0.1-second delay between requests
- Capture 145 Programming Guide pages (starting from id=1)

### Resume Interrupted Crawl

If the crawl is interrupted, resume from where it left off:

```bash
uv run python 10_crawl_programming_guide/run_crawler.py --resume
```

### Validate Results

Check the completeness and integrity of the crawl:

```bash
# Basic validation
uv run python 10_crawl_programming_guide/validate_crawl.py

# Detailed validation with verbose output
uv run python 10_crawl_programming_guide/validate_crawl.py --verbose
```

**Note**: Validation threshold is set to 138 pages minimum (95% of expected 145 pages).

## 🔧 Configuration

### Key Settings (solidworks_scraper/settings.py)

- **CONCURRENT_REQUESTS**: 5 (parallel downloads)
- **DOWNLOAD_DELAY**: 0.1 seconds (polite crawling)
- **ROBOTSTXT_OBEY**: False (with justification)
- **Pipelines**: HtmlSavePipeline and MetadataLogPipeline

### Spider Configuration (api_docs_spider.py)

```python
class ApiDocsSpider(scrapy.Spider):
    name = "api_docs"
    # Starting URL for Programming Guide (id=1)
    start_urls = ["https://help.solidworks.com/expandToc?version=2026&language=english&product=api&queryParam=?id=1"]
```

## 🧪 Testing

Run the test suite:

```bash
# All tests
uv run pytest 10_crawl_programming_guide/tests/ -v

# Specific test file
uv run pytest 10_crawl_programming_guide/tests/test_spider.py -v
```

## 📊 Output Format

### HTML Files

HTML content is extracted from the `helpText` field in the `__NEXT_DATA__` JSON and saved with the following naming convention:

```
output/html/
├── expandToc_id_1.json              # Main TOC JSON (id=1)
├── expandToc_id_1.0.json            # Child TOC sections
├── expandToc_id_1.1.json
├── help_*.html                      # Documentation pages with hashed names
└── [namespace]/                     # Subdirectories for different namespaces
    └── *.html
```

### Metadata Files

#### urls_crawled.jsonl

Each line contains metadata about a crawled page:

```json
{
  "url": "https://help.solidworks.com/2026/english/api/...",
  "file_path": "output/html/...",
  "content_hash": "sha256_hash",
  "content_length": 12345,
  "status_code": 200,
  "title": "Page Title"
}
```

#### crawl_stats.json

Overall crawl statistics:

```json
{
  "total_pages": 150,
  "successful_pages": 145,
  "failed_pages": 2,
  "skipped_pages": 3,
  "reason": "finished"
}
```

## 🎯 How It Works

### Stage 1: TOC Discovery

1. Fetch initial TOC from: `https://help.solidworks.com/expandToc?version=2026&language=english&product=api&queryParam=?id=1`
2. Recursively extract all URLs from the `children` array in the JSON response
3. For each URL with an `id` parameter, create additional expandToc requests
4. Build complete page list via recursive discovery

### Stage 2: Page Crawling

1. For each discovered URL, fetch the HTML page
2. Extract `__NEXT_DATA__` JSON from the page
3. Extract `helpText` field from `props.pageProps.helpContentData`
4. Save clean HTML content and metadata

### Stage 3: Validation

1. Verify all expected files exist
2. Check metadata integrity
3. Validate success rate >95%
4. Ensure minimum page count threshold met
5. Check for duplicates and errors

## 🔍 URL Boundaries

All crawled URLs must be within the boundary:

```
/2026/english/api/
```

URLs outside this path are automatically skipped.

## 📝 Validation Criteria

A successful crawl must meet:

- ✅ Success rate ≥ 95%
- ✅ Page count ≥ 138 (95% of expected 145)
- ✅ All metadata files present and valid
- ✅ No duplicate URLs
- ✅ All URLs within boundary

## 🔄 Differences from Phase 01

| Aspect | Phase 01 (API Reference) | Phase 10 (Programming Guide) |
|--------|--------------------------|------------------------------|
| Start ID | 2 | 1 |
| Spider Name | api_docs | api_docs |
| Expected Pages | ~458 | 145 |
| Validation Threshold | 435 minimum | 138 minimum |
| Implementation | Standalone | Standalone |
| Pipelines | HtmlSavePipeline, MetadataLogPipeline | HtmlSavePipeline, MetadataLogPipeline |

## 🛠️ Troubleshooting

### No pages being crawled

- Check network connectivity
- Verify start URL is accessible
- Check scrapy logs for errors

### Validation fails

- Run with `--verbose` to see detailed issues
- Check `metadata/errors.jsonl` for error patterns
- Verify page count threshold is appropriate

### Memory issues

- Reduce `CONCURRENT_REQUESTS` in settings
- Enable autothrottle in settings
- Clear output directory between runs

## 📚 Next Steps

To verify the crawl or integrate with subsequent phases:

1. **Validate results**: Run `uv run python validate_crawl.py --verbose`
2. **Explore output**: Check `output/html/` for downloaded pages
3. **Review metadata**: Check `metadata/` for crawl statistics
4. **Integrate with Phase 02**: Use the extracted type data for further processing

## 🔗 Related Phases

- **Phase 01**: Crawls API Reference documentation (id=2)
- **Phase 02-09**: Extract and process crawled content

## 🆚 Relationship to Phase 01

This phase is a direct adaptation of Phase 01 with only the start URL changed from `id=2` to `id=1`. All other functionality remains the same:
- Same spider implementation
- Same pipelines
- Same validation logic
- Same output format

The main difference is the content being crawled: Programming Guide vs API Reference.

## 📄 License & Legal

⚠️ **Important**: The crawled content is copyrighted by Dassault Systèmes SolidWorks Corporation.

- For personal/educational use only
- Do not redistribute crawled content
- Respect crawl delays and robots.txt (where reasonable)
- This is a research/documentation tool for personal use
