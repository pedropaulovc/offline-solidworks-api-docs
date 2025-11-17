# Phase 3: Crawl Type Members

**Status**: ✅ Complete

## Overview

Phase 3 crawls the detailed documentation pages for all type members (properties and methods) extracted in Phase 2. This phase reads URLs directly from Phase 2's `api_members.xml` and downloads the HTML content for each property and method.

## Purpose

- **Input**: Phase 2's `api_members.xml` containing URLs for all properties and methods
- **Process**: Download and save the HTML documentation for each member
- **Output**: HTML files containing member details (signatures, descriptions, examples, remarks)

## Prerequisites

- ✅ Phase 1 complete (10_crawl_toc_pages)
- ✅ Phase 2 complete (20_extract_types)

## Usage

### Running the Crawler

```bash
# Full crawl (all type members)
uv run python 30_crawl_type_members/run_crawler.py

# Test crawl (first 100 pages)
uv run python 30_crawl_type_members/run_crawler.py --test

# Resume from previous crawl
uv run python 30_crawl_type_members/run_crawler.py --resume

# Crawl with validation
uv run python 30_crawl_type_members/run_crawler.py --validate
```

### Validation

```bash
# Basic validation
uv run python 30_crawl_type_members/validate_crawl.py

# Verbose validation with error analysis
uv run python 30_crawl_type_members/validate_crawl.py --verbose
```

### Running Tests

```bash
# Run all tests
uv run pytest 30_crawl_type_members/tests/ -v

# Run with coverage
uv run pytest 30_crawl_type_members/tests/ --cov=30_crawl_type_members --cov-report=html
```

## How It Works

### 1. URL Extraction

The spider reads Phase 2's `api_members.xml` directly and extracts all property and method URLs:

```python
def load_urls(self):
    """Load URLs directly from Phase 2's api_members.xml"""
    xml_file = Path(...) / "20_extract_types" / "metadata" / "api_members.xml"

    # Parse XML and extract <Property><Url> and <Method><Url> elements
    # Returns deduplicated, sorted list of URLs
```

### 2. Crawling

The Scrapy spider:
- Converts relative URLs to absolute URLs
- Adds print preview format parameters (`?format=p&value=1`)
- Downloads each page
- Extracts `helpText` from `__NEXT_DATA__` JSON
- Saves HTML content to organized file structure

### 3. Storage

HTML files are organized by their namespace/assembly:
```
output/html/
├── sldworksapi/
│   ├── SolidWorks.Interop.sldworks~IModelDoc2~GetTitle.html
│   ├── SolidWorks.Interop.sldworks~IModelDoc2~Visible.html
│   └── ...
├── swmotionstudyapi/
│   └── ...
└── ...
```

### 4. Metadata Tracking

The crawler generates comprehensive metadata:
- `urls_crawled.jsonl`: One entry per crawled page
- `errors.jsonl`: Failed requests and errors
- `crawl_stats.json`: Summary statistics
- `manifest.json`: Configuration snapshot

## Output Files

### Metadata Files

| File | Description |
|------|-------------|
| `metadata/urls_crawled.jsonl` | JSONL file with one entry per crawled URL |
| `metadata/errors.jsonl` | Errors encountered during crawling |
| `metadata/crawl_stats.json` | Summary statistics (counts, success rate, etc.) |
| `metadata/manifest.json` | Configuration snapshot for reproducibility |

### HTML Files

| Directory | Contents |
|-----------|----------|
| `output/html/` | Crawled HTML files organized by namespace |

**Note**: HTML files are gitignored as they contain copyrighted content from Dassault Systèmes.

## Expected Results

### Full Crawl

- **Pages**: ~5,000-10,000 type members (varies by SolidWorks version)
- **Success Rate**: ≥95%
- **Duration**: ~2-4 hours (with 0.1s delay between requests)
- **Storage**: ~200-400 MB

### Test Crawl

- **Pages**: 100
- **Success Rate**: ≥95%
- **Duration**: ~1-2 minutes

## Configuration

### Scrapy Settings

Key settings in `solidworks_scraper/settings.py`:

```python
CONCURRENT_REQUESTS = 5              # Parallel requests
DOWNLOAD_DELAY = 0.1                 # 0.1 second delay (respectful)
ROBOTSTXT_OBEY = False              # Documentation is public
DOWNLOAD_TIMEOUT = 30                # 30 second timeout
RETRY_TIMES = 3                      # Retry failed requests
```

### Pipelines

1. **HtmlSavePipeline** (priority 300): Saves HTML content to files
2. **MetadataLogPipeline** (priority 400): Logs metadata to JSONL

## Troubleshooting

### No URLs loaded from XML

**Error**: `Loaded 0 unique URLs from api_members.xml`

**Solution**: Run Phase 2 first:
```bash
uv run python 20_extract_types/extract_members.py
```

### Low success rate

**Symptoms**: Success rate below 95%

**Possible causes**:
- Network issues
- Server rate limiting
- Invalid URLs from Phase 2

**Solutions**:
1. Check `metadata/errors.jsonl` for error patterns
2. Increase `DOWNLOAD_DELAY` in settings.py
3. Use `--resume` to continue from where it stopped
4. Validate Phase 2 output

### Missing HTML files

**Symptoms**: Crawled URLs count doesn't match HTML file count

**Possible causes**:
- Pipeline errors
- Disk space issues
- Permission errors

**Solutions**:
1. Check logs for pipeline errors
2. Verify disk space
3. Check directory permissions

## Performance Optimization

### Speed vs. Courtesy Trade-offs

```python
# Faster (use responsibly)
CONCURRENT_REQUESTS = 10
DOWNLOAD_DELAY = 0.05

# More respectful (default)
CONCURRENT_REQUESTS = 5
DOWNLOAD_DELAY = 0.1

# Very respectful
CONCURRENT_REQUESTS = 2
DOWNLOAD_DELAY = 0.5
```

### Resume After Interruption

The crawler supports resuming:
```bash
# Start crawl
uv run python 30_crawl_type_members/run_crawler.py

# Interrupted? Resume with:
uv run python 30_crawl_type_members/run_crawler.py --resume
```

## Data Flow

```
Phase 2 Output                    Phase 3 Processing              Phase 3 Output
┌─────────────────┐              ┌──────────────────┐           ┌──────────────┐
│ api_members.xml │──────────────▶│ TypeMembersSpider│───────────▶│ HTML files   │
│                 │              │                  │           │ (5000+ pages)│
│ - Properties    │              │ 1. Load URLs     │           ├──────────────┤
│ - Methods       │              │ 2. Download HTML │           │ Metadata:    │
│ - Namespaces    │              │ 3. Extract data  │           │ - crawl stats│
└─────────────────┘              │ 4. Save files    │           │ - errors.jsonl
                                 └──────────────────┘           │ - urls.jsonl │
                                                                └──────────────┘
```

## Next Steps

After completing Phase 3, you can:

1. **Phase 4**: Extract detailed member information from HTML
2. **Phase 5**: Parse examples and code samples
3. **Phase 6**: Generate XMLDoc files for IntelliSense

## Architecture Notes

### Why Direct XML Reading?

Previous design had an intermediate `extract_member_urls.py` step, but we simplified:
- ✅ Fewer files to manage
- ✅ Single source of truth (XML)
- ✅ Automatic updates when XML changes
- ✅ Less manual steps for users

### URL Deduplication

The spider automatically deduplicates URLs because:
- Some members may appear in multiple types (inheritance)
- Interface and implementation may share URLs
- Using a `set()` ensures each URL is crawled only once

## Copyright Notice

⚠️ **Important**: The HTML content crawled by this phase is copyrighted by Dassault Systèmes. This tool is for personal/educational use only. Do not redistribute the crawled content.

## Contributing

When modifying this phase:
1. Maintain reproducibility (deterministic outputs)
2. Update tests for new features
3. Keep validation thresholds realistic
4. Document configuration changes
5. Test with `--test` flag first

## Support

For issues or questions:
1. Check this README
2. Review logs in console output
3. Examine `metadata/errors.jsonl`
4. Validate Phase 2 output first
5. Open an issue with error details
