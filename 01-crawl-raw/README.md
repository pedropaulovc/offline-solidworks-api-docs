# Phase 1: Raw HTML Crawler

This directory contains the Scrapy-based crawler for downloading the SolidWorks API documentation. The start page (Welcome.htm) is downloaded in full format to capture the complete table of contents, while all subsequent pages are saved in print preview format for cleaner, more compact HTML.

## 📁 Directory Structure

```
01-crawl-raw/
├── solidworks_scraper/       # Scrapy project
│   ├── settings.py          # Crawler configuration
│   ├── pipelines.py         # Data processing pipelines
│   └── spiders/
│       └── api_docs_spider.py  # Main spider implementation
├── tests/                   # Test suite
│   ├── test_spider.py      # Spider tests
│   ├── test_pipelines.py   # Pipeline tests
│   └── fixtures/           # Test HTML samples
├── output/                  # Crawl output (gitignored)
│   ├── html/               # Downloaded HTML files
│   └── metadata/           # Crawl metadata
│       ├── urls_crawled.jsonl    # List of crawled URLs
│       ├── crawl_stats.json      # Crawl statistics
│       ├── errors.jsonl          # Error log
│       └── manifest.json         # Crawl configuration
├── run_crawler.py          # Main entry point
└── validate_crawl.py       # Validation script
```

## 🚀 Usage

### Quick Test Run

Test the crawler with a small subset of pages:

```bash
# From project root
uv run python 01-crawl-raw/run_crawler.py --test

# Or from this directory
cd 01-crawl-raw
uv run python run_crawler.py --test
```

### Full Crawl

Run a complete crawl of the API documentation:

```bash
uv run python 01-crawl-raw/run_crawler.py
```

**Note**: A full crawl will:
- Take 3-4 hours to complete
- Download ~100-150 MB of HTML
- Respect a 2-second delay between requests
- Capture 458+ documentation pages

### Resume Interrupted Crawl

If the crawl is interrupted, resume from where it left off:

```bash
uv run python 01-crawl-raw/run_crawler.py --resume
```

### Validate Results

Check the completeness and integrity of the crawl:

```bash
# Basic validation
uv run python 01-crawl-raw/validate_crawl.py

# Detailed validation with verbose output
uv run python 01-crawl-raw/validate_crawl.py --verbose
```

## 🔧 Configuration

### Key Settings (solidworks_scraper/settings.py)

```python
# User agent - identifies as Chrome browser
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Polite crawling settings
CONCURRENT_REQUESTS = 1          # Single-threaded
DOWNLOAD_DELAY = 2               # 2 seconds between requests
ROBOTSTXT_OBEY = True           # Respect robots.txt

# URL boundaries
ALLOWED_DOMAINS = ["help.solidworks.com"]
BASE_URL_PATH = "/2026/english/api/"

# Only download HTML
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
}
```

### Customizing the Crawl

To modify crawl behavior, edit:

1. **Starting URL**: In `api_docs_spider.py`, modify `start_urls`
2. **URL Boundaries**: In `api_docs_spider.py`, adjust `base_path`
3. **Crawl Delay**: In `settings.py`, change `DOWNLOAD_DELAY`
4. **Concurrent Requests**: In `settings.py`, modify `CONCURRENT_REQUESTS`

## 🕷️ Spider Implementation

The main spider (`api_docs_spider.py`) implements:

### URL Processing
- **Start URL** (Welcome.htm): Downloaded in full format to capture complete table of contents
- **Subsequent URLs**: Converted to print preview format (`&format=p&value=1`) for cleaner HTML
- Enforces boundary checking (stays within `/2026/english/api/`)
- Filters out non-HTML resources (CSS, JS, images)

### Data Extraction
- Captures page content and metadata
- Calculates content hashes for integrity
- Extracts page titles for organization

### Error Handling
- Retries failed requests (up to 3 times)
- Logs errors to `errors.jsonl`
- Continues crawling despite individual failures

## 📦 Pipelines

The crawler uses multiple pipelines for data processing:

### HtmlSavePipeline
- Saves HTML content to organized file structure
- Converts URLs to safe file paths
- Handles query parameters in filenames

### MetadataLogPipeline
- Records comprehensive metadata for each page
- Creates manifest file with crawl configuration
- Logs errors separately

### DuplicateCheckPipeline
- Prevents reprocessing of already-crawled URLs
- Loads existing metadata on startup for resume capability

### ValidationPipeline
- Validates content meets minimum requirements
- Checks for HTML validity
- Warns about suspicious content

## 📊 Output Structure

### HTML Files (`output/html/`)

Files are organized by URL path:
```
output/html/
├── sldworksapiprogguide/
│   └── Welcome_16777215.htm
├── sldworksapi/
│   ├── SolidWorks.Interop.sldworks~IAdvancedHoleFeatureData_12345.html
│   └── ...
└── ...
```

### Metadata Files (`output/metadata/`)

#### urls_crawled.jsonl
One JSON object per line, containing:
```json
{
  "original_url": "https://help.solidworks.com/2026/english/api/...",
  "print_url": "https://help.solidworks.com/...&format=p&value=1",
  "timestamp": "2025-11-14T10:30:00Z",
  "file_path": "output/html/sldworksapi/...",
  "content_hash": "sha256:...",
  "content_length": 12345,
  "status_code": 200,
  "title": "IAdvancedHoleFeatureData Interface",
  "session_id": "2025-11-14-103000"
}
```

#### crawl_stats.json
Summary statistics:
```json
{
  "start_time": "2025-11-14T10:00:00Z",
  "end_time": "2025-11-14T12:00:00Z",
  "total_pages": 460,
  "successful_pages": 458,
  "failed_pages": 2,
  "skipped_pages": 0
}
```

#### errors.jsonl
Error records:
```json
{
  "url": "https://help.solidworks.com/...",
  "error": "Connection timeout",
  "timestamp": "2025-11-14T10:35:00Z",
  "session_id": "2025-11-14-103000"
}
```

## 🧪 Testing

### Run All Tests
```bash
uv run pytest 01-crawl-raw/tests/ -v
```

### Run Specific Tests
```bash
# Test spider only
uv run pytest 01-crawl-raw/tests/test_spider.py -v

# Test pipelines only
uv run pytest 01-crawl-raw/tests/test_pipelines.py -v
```

### Coverage Report
```bash
uv run pytest 01-crawl-raw/tests/ --cov=solidworks_scraper --cov-report=html
```

## ✅ Validation Criteria

The validation script checks:

1. **Page Count**: Minimum 435 pages (95% of expected 458)
2. **Success Rate**: >95% of attempted pages successfully crawled
3. **Metadata Integrity**: All required metadata files present
4. **File Matching**: HTML files correspond to metadata records
5. **Content Validation**: HTML files contain valid content
6. **No Excessive Duplicates**: Checks for duplicate content hashes

## 🐛 Troubleshooting

### Issue: Spider not finding any links

**Solution**: Check that the starting URL is accessible and returns HTML content with links.

### Issue: 403 Forbidden errors

**Solutions**:
- Verify user agent is set correctly
- Increase DOWNLOAD_DELAY
- Check if site requires cookies/session

### Issue: Crawl stops unexpectedly

**Solutions**:
- Check `errors.jsonl` for error patterns
- Use `--resume` to continue
- Verify network connectivity

### Issue: Validation fails with low page count

**Solutions**:
- Check URL boundary settings
- Verify print preview URLs work
- Look for patterns in skipped pages

## 🔍 Monitoring Progress

During crawl, monitor:

1. **Console output**: Shows real-time progress
2. **metadata/urls_crawled.jsonl**: Growing list of crawled pages
3. **metadata/errors.jsonl**: Any errors encountered
4. **output/html/**: HTML files being saved

## 📈 Performance Optimization

If you need faster crawling (use with caution):

1. Reduce `DOWNLOAD_DELAY` (minimum 1 second recommended)
2. Increase `CONCURRENT_REQUESTS` (max 2 recommended)
3. Enable HTTP caching in development:
   ```python
   HTTPCACHE_ENABLED = True
   HTTPCACHE_DIR = "httpcache"
   ```

## 🔄 Updating for New SolidWorks Versions

When a new SolidWorks version is released:

1. Update the year in URL paths (e.g., 2026 → 2027)
2. Modify `BASE_URL_PATH` in settings.py
3. Update `start_urls` in api_docs_spider.py
4. Clear previous crawl data
5. Run fresh crawl and validate

## 📝 Notes

- Print preview format (`&format=p&value=1`) provides cleaner HTML
- The crawler respects robots.txt by default
- Duplicate detection allows resuming interrupted crawls
- All timestamps are in ISO 8601 format (UTC)
- Content hashes use SHA-256 for integrity verification

---

For issues or improvements, please refer to the main project README or create an issue in the repository.