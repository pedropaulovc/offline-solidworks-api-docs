# Phase 1: Raw HTML Crawler

This directory contains the Scrapy-based crawler for downloading the SolidWorks API documentation. The crawler uses the SolidWorks expandToc JSON API to discover all documentation pages, then extracts clean HTML content from the `__NEXT_DATA__` JSON embedded in each page.

## 📁 Directory Structure

```
01_crawl_toc_pages/
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
uv run python 01_crawl_toc_pages/run_crawler.py --test

# Or from this directory
cd 01_crawl_toc_pages
uv run python run_crawler.py --test
```

### Full Crawl

Run a complete crawl of the API documentation:

```bash
uv run python 01_crawl_toc_pages/run_crawler.py
```

**Note**: A full crawl will:
- Take 3-4 hours to complete
- Download ~100-150 MB of HTML
- Respect a 2-second delay between requests
- Capture 458+ documentation pages

### Resume Interrupted Crawl

If the crawl is interrupted, resume from where it left off:

```bash
uv run python 01_crawl_toc_pages/run_crawler.py --resume
```

### Validate Results

Check the completeness and integrity of the crawl:

```bash
# Basic validation
uv run python 01_crawl_toc_pages/validate_crawl.py

# Detailed validation with verbose output
uv run python 01_crawl_toc_pages/validate_crawl.py --verbose
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
   - Current: `https://help.solidworks.com/expandToc?version=2026&language=english&product=api&queryParam=?id=2`
   - Change version, language, or starting id as needed
2. **URL Boundaries**: In `api_docs_spider.py`, adjust `base_path`
   - Current: `/2026/english/api/`
3. **Crawl Delay**: In `settings.py`, change `DOWNLOAD_DELAY`
4. **Concurrent Requests**: In `settings.py`, modify `CONCURRENT_REQUESTS`

## 🔬 How It Works: The expandToc API

The SolidWorks documentation site uses a JSON API called `expandToc` to serve its table of contents. Understanding this is key to understanding how the crawler works:

### expandToc API Structure

**Request Format:**
```
https://help.solidworks.com/expandToc?version=2026&language=english&product=api&queryParam=?id=<N>
```

**Response Structure:**
```json
{
  "children": [
    {
      "name": "Page Title",
      "url": "/2026/english/api/sldworksapi/SomeClass.htm?id=123",
      "children": [
        // Nested pages...
      ]
    }
  ]
}
```

The crawler:
1. Starts with `id=2` (root API documentation node)
2. Extracts all URLs from the `children` array
3. For each URL with an `id` parameter, makes another expandToc request
4. Recursively discovers all pages in the documentation tree

### Page Content Extraction

Each documentation page contains a `<script id="__NEXT_DATA__">` tag with JSON data:
```json
{
  "props": {
    "pageProps": {
      "helpContentData": {
        "helpText": "<html>...actual documentation HTML...</html>"
      }
    }
  }
}
```

The crawler extracts only the `helpText` field, which contains clean HTML without navigation, headers, or other page chrome.

## 🕷️ Spider Implementation

The main spider (`api_docs_spider.py`) implements a two-stage crawling approach:

### Stage 1: Table of Contents Discovery
- **Start URL**: `https://help.solidworks.com/expandToc?version=2026&language=english&product=api&queryParam=?id=2`
- Fetches JSON structure containing all documentation page URLs
- Recursively extracts URLs from nested `children` arrays
- Creates expandToc requests for each page's `id` parameter to discover nested pages

### Stage 2: Content Extraction
- Visits each documentation page URL
- Extracts `__NEXT_DATA__` JSON blob embedded in the HTML
- Parses `props.pageProps.helpContentData.helpText` to get clean HTML content
- Saves only the helpText HTML (no navigation, headers, or other page chrome)

### URL Processing
- Enforces boundary checking (stays within `/2026/english/api/`)
- Filters out non-HTML resources (CSS, JS, images)
- Tracks visited URLs to prevent duplicates

### Data Extraction
- Captures clean HTML content from helpText field
- Calculates content hashes (SHA-256) for integrity
- Extracts page titles for organization
- Stores complete metadata for reproducibility

### Error Handling
- Retries failed requests (up to 3 times)
- Logs errors to `errors.jsonl`
- Continues crawling despite individual failures
- Gracefully handles missing JSON data

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

Files are organized by URL path and include both HTML content and JSON TOC data:
```
output/html/
├── expandToc_id_2.json           # Main TOC structure
├── expandToc_id_0.json           # Sub-TOC for id=0
├── expandToc_id_1.json           # Sub-TOC for id=1
├── sldworksapiprogguide/
│   └── Welcome_<hash>.html       # helpText HTML content
├── sldworksapi/
│   ├── SolidWorks.Interop.sldworks~IAdvancedHoleFeatureData_<hash>.html
│   └── ...
└── ...
```

**File naming:**
- **expandToc files**: Named by ID parameter (e.g., `expandToc_id_2.json`)
- **HTML files**: Original path with query parameter hash appended (deterministic)
- Query parameter hash ensures unique filenames for pages with different parameters

### Metadata Files (`output/metadata/`)

#### urls_crawled.jsonl
One JSON object per line, containing:
```json
{
  "url": "https://help.solidworks.com/2026/english/api/sldworksapi/...",
  "timestamp": "2025-11-14T10:30:00Z",
  "file_path": "output/html/sldworksapi/...",
  "content_hash": "sha256:...",
  "content_length": 12345,
  "status_code": 200,
  "title": "IAdvancedHoleFeatureData Interface",
  "session_id": "2025-11-14-103000"
}
```

**Note**: For expandToc JSON files, the content is the full JSON response. For HTML pages, the content is the extracted helpText HTML.

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
uv run pytest 01_crawl_toc_pages/tests/ -v
```

### Run Specific Tests
```bash
# Test spider only
uv run pytest 01_crawl_toc_pages/tests/test_spider.py -v

# Test pipelines only
uv run pytest 01_crawl_toc_pages/tests/test_pipelines.py -v
```

### Coverage Report
```bash
uv run pytest 01_crawl_toc_pages/tests/ --cov=solidworks_scraper --cov-report=html
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
- Verify expandToc API is returning data
- Check for pages missing `__NEXT_DATA__` JSON
- Look for patterns in skipped pages in metadata/errors.jsonl

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

1. **Update expandToc URL** in `api_docs_spider.py`:
   - Change `version=2026` to `version=2027` in `start_urls`
2. **Update base path** in `api_docs_spider.py`:
   - Change `self.base_path = "/2026/english/api/"` to `"/2027/english/api/"`
3. **Update manifest** in `pipelines.py`:
   - Update `start_url` and `boundary` in `MetadataLogPipeline.init_manifest()`
4. **Clear previous crawl data**:
   - Delete or archive `output/` and `metadata/` directories
5. **Run fresh crawl and validate**

## 📝 Notes

- **Clean HTML**: Content is extracted from `__NEXT_DATA__` JSON, providing pure documentation HTML without navigation or page chrome
- **JSON TOC Structure**: The expandToc API provides the complete table of contents in JSON format
- **Duplicate Detection**: Tracks visited URLs to prevent reprocessing and allow resuming interrupted crawls
- **Deterministic Filenames**: Query parameters are hashed (MD5) to create unique, deterministic filenames
- **Timestamps**: All timestamps are in ISO 8601 format (UTC)
- **Content Hashes**: SHA-256 hashes ensure integrity verification
- **Robots.txt**: The crawler respects robots.txt by default

---

For issues or improvements, please refer to the main project README or create an issue in the repository.
