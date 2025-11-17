# Phase 7: Crawl Example Pages

This directory contains the Scrapy-based crawler for downloading SolidWorks API example pages referenced in the `api_types.xml` file from Phase 4. The crawler extracts clean HTML content from the `__NEXT_DATA__` JSON embedded in each page.

## 📁 Directory Structure

```
70_crawl_examples/
├── solidworks_scraper/       # Scrapy project
│   ├── settings.py          # Crawler configuration
│   ├── pipelines.py         # Data processing pipelines
│   └── spiders/
│       └── examples_spider.py  # Main spider implementation
├── tests/                   # Test suite
│   ├── test_spider.py      # Spider tests
│   ├── test_pipelines.py   # Pipeline tests
│   └── test_url_extractor.py  # URL extractor tests
├── output/                  # Crawl output (gitignored)
│   └── html/               # Downloaded HTML files
├── metadata/               # Metadata
│   ├── urls_crawled.jsonl  # List of crawled URLs
│   ├── crawl_stats.json    # Crawl statistics
│   ├── errors.jsonl        # Error log
│   └── manifest.json       # Crawl configuration
├── extract_example_urls.py # URL extraction script
├── run_crawler.py          # Main entry point
└── validate_crawl.py       # Validation script
```

## 🚀 Usage

### Prerequisites

Make sure you have completed **Phase 3** (extract_type_info) first, as this phase reads directly from:
- `03_extract_type_info/metadata/api_types.xml`

### Step 1: Test Crawl

Test the crawler with a small subset of pages:

```bash
# From project root
uv run python 05_crawl_examples/run_crawler.py --test

# Or from this directory
cd 05_crawl_examples
uv run python run_crawler.py --test
```

This will crawl only the first 20 example pages to verify everything works.

### Step 2: Full Crawl

Run a complete crawl of all example pages:

```bash
uv run python 05_crawl_examples/run_crawler.py
```

**Note**: A full crawl will:
- Take 20-30 minutes to complete
- Download ~50-100 MB of HTML
- Respect a 0.1-second delay between requests
- Capture ~1,198 example pages

### Step 3: Validate Results

Check the completeness and integrity of the crawl:

```bash
# Basic validation
uv run python 05_crawl_examples/validate_crawl.py

# Detailed validation with verbose output
uv run python 05_crawl_examples/validate_crawl.py --verbose

# Generate detailed JSON report
uv run python 05_crawl_examples/validate_crawl.py --report validation_report.json
```

### Resume Interrupted Crawl

If the crawl is interrupted, resume from where it left off:

```bash
uv run python 05_crawl_examples/run_crawler.py --resume
```

## 🔧 Configuration

### Key Settings (solidworks_scraper/settings.py)

- **CONCURRENT_REQUESTS**: 5 (parallel requests)
- **DOWNLOAD_DELAY**: 0.1 seconds (polite crawling)
- **ROBOTSTXT_OBEY**: False (necessary for accessing documentation)
- **RETRY_TIMES**: 3 (retry failed requests)
- **DOWNLOAD_TIMEOUT**: 30 seconds

### Adjusting Crawl Speed

To crawl faster (use responsibly):

```python
# In settings.py
CONCURRENT_REQUESTS = 10
DOWNLOAD_DELAY = 0.05
```

To crawl slower (more polite):

```python
# In settings.py
CONCURRENT_REQUESTS = 2
DOWNLOAD_DELAY = 0.5
```

## 📊 Output Format

### HTML Files

Stored in `output/html/` with organized directory structure:

```
output/html/
├── sldworksapi/
│   ├── Create_Advanced_Hole_Example_VB.html
│   ├── Create_Advanced_Hole_Example_CSharp.html
│   └── ...
├── swmotionstudyapi/
│   ├── Create_Motion_Studies_Example_VB.html
│   └── ...
└── dsgnchkapi/
    └── ...
```

### Metadata Files

#### urls_crawled.jsonl

One JSON object per line:

```json
{
  "url": "https://help.solidworks.com/2026/english/api/sldworksapi/example.htm",
  "timestamp": "2024-11-15T10:30:00",
  "file_path": "05_crawl_examples/output/html/sldworksapi/example.html",
  "content_hash": "abc123...",
  "content_length": 12345,
  "status_code": 200,
  "title": "Example - VBA",
  "session_id": "2024-11-15-103000"
}
```

#### crawl_stats.json

Summary statistics:

```json
{
  "start_time": "2024-11-15T10:00:00",
  "end_time": "2024-11-15T10:30:00",
  "total_pages": 1198,
  "successful_pages": 1195,
  "failed_pages": 2,
  "skipped_pages": 1,
  "reason": "finished"
}
```

## 🧪 Testing

Run the test suite:

```bash
# From project root
uv run pytest 05_crawl_examples/tests/ -v

# With coverage
uv run pytest 05_crawl_examples/tests/ --cov=05_crawl_examples --cov-report=term-missing
```

### Test Coverage

- **test_url_extractor.py**: URL extraction logic
- **test_spider.py**: Spider initialization and parsing
- **test_pipelines.py**: Pipeline processing

## 🔍 How It Works

### 1. URL Loading

The `examples_spider.py`:
1. Reads directly from `03_extract_type_info/metadata/api_types.xml`
2. Finds all `<Example><Url>` elements
3. Extracts and deduplicates URLs
4. Converts relative URLs to absolute
5. Makes HTTP requests to each URL
6. Extracts `__NEXT_DATA__` JSON from page
7. Extracts `helpText` HTML content
8. Yields items to pipelines

### 2. Pipeline Processing

The pipelines process each item:

1. **HtmlSavePipeline**: Saves HTML to organized file structure
2. **MetadataLogPipeline**: Logs metadata to JSONL files
3. **DuplicateCheckPipeline**: Skips already-crawled URLs (for resume)
4. **ValidationPipeline**: Validates content integrity

### 3. Validation

The `validate_crawl.py` script checks:
- File existence and completeness
- URL coverage vs. source XML
- HTML file validity
- Metadata consistency
- Success rate (>90%)
- Content integrity (hash verification)

## 📈 Expected Results

For a complete crawl:

- **Example URLs**: ~1,198 unique URLs
- **Success Rate**: >95%
- **Total Size**: 50-100 MB
- **Duration**: 20-30 minutes
- **Error Rate**: <5%

## 🐛 Troubleshooting

### No URLs Found

If the spider can't find URLs:

```bash
# Check that Phase 3 XML exists
ls 03_extract_type_info/metadata/api_types.xml

# Verify XML has Example/Url elements
grep -c "<Url>" 03_extract_type_info/metadata/api_types.xml
```

### High Error Rate

If many pages fail to crawl:

1. Check internet connection
2. Verify SolidWorks documentation site is accessible
3. Increase `DOWNLOAD_TIMEOUT` in settings.py
4. Reduce `CONCURRENT_REQUESTS` to avoid rate limiting

### Missing __NEXT_DATA__

If pages are missing the `__NEXT_DATA__` JSON:

- The page structure may have changed
- Check a sample URL in a browser
- Update the XPath selector in `examples_spider.py`

### Hash Mismatches

If content integrity checks fail:

- File may have been modified after crawl
- Re-run the crawl for affected URLs
- Check disk integrity

## 🔗 Integration with Pipeline

### Input

- `03_extract_type_info/metadata/api_types.xml` - Source of example URLs

### Output

- `05_crawl_examples/output/html/` - Example page HTML
- `05_crawl_examples/metadata/urls_crawled.jsonl` - Metadata

### Next Phase

The downloaded examples will be used in future phases for:
- Extracting code snippets
- Organizing examples by language (VB, C#, VBA, C++)
- Building example documentation
- Creating searchable example index

## 📝 Notes

### Example Languages

The examples come in multiple languages:
- **VB** (Visual Basic 6)
- **VBNET** (VB.NET)
- **CSharp** (C#)
- **VBA** (VBA for Microsoft Office/SolidWorks macros)
- **CPlusPlus** (C++ COM)

### URL Patterns

Example URLs follow these patterns:
- `/sldworksapi/Example_Name_Language.htm`
- `/swmotionstudyapi/Example_Name_Language.htm`
- `/dsgnchkapi/Example_Name_Language.htm`

### Content Structure

Each example page typically contains:
- Code snippet
- Description/explanation
- Prerequisites
- Remarks section

## 🎯 Success Criteria

A successful crawl should meet these criteria:

- ✅ All example URLs extracted (1,198)
- ✅ >95% crawl success rate
- ✅ All HTML files saved with correct structure
- ✅ Metadata complete and consistent
- ✅ Content hashes match file contents
- ✅ No duplicate URLs in metadata
- ✅ Validation passes all checks

## 🚦 Performance Tips

### Optimize for Speed

```python
# settings.py
CONCURRENT_REQUESTS = 10
DOWNLOAD_DELAY = 0.05
REACTOR_THREADPOOL_MAXSIZE = 20
```

### Optimize for Reliability

```python
# settings.py
CONCURRENT_REQUESTS = 2
DOWNLOAD_DELAY = 0.5
RETRY_TIMES = 5
```

### Memory Usage

The crawler typically uses:
- **Memory**: 100-300 MB
- **Disk I/O**: Moderate (writing HTML files)
- **Network**: ~5-10 req/sec (depending on settings)

## 📚 See Also

- [Phase 1 README](../10_crawl_toc_pages/README.md) - TOC crawler
- [Phase 3 README](../03_extract_type_info/README.md) - Type info extraction
- [Scrapy Documentation](https://docs.scrapy.org/) - Scrapy framework
- [SolidWorks API Help](https://help.solidworks.com/2026/english/api/) - Source documentation

---

**Status**: ✅ Implemented and tested
**Last Updated**: 2024-11-15
