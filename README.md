# Offline SolidWorks API Documentation

A comprehensive crawler and transformation pipeline for creating offline, searchable versions of the SolidWorks API documentation.

## ⚠️ Legal Notice

**IMPORTANT**: This tool is designed for personal, educational, and fair use only. The crawled documentation content is copyrighted by Dassault Systèmes SolidWorks Corporation.

- DO NOT redistribute crawled content
- DO NOT use for commercial purposes
- Each user must crawl the documentation themselves
- Crawled HTML content is gitignored and not included in this repository

## 📋 Overview

This project provides a reproducible pipeline for:
1. **Crawling** the SolidWorks API documentation using the expandToc API
2. **Extracting** member information (properties and methods) from HTML
3. **Extracting** type-level documentation (descriptions, examples, remarks)
4. **Extracting** enumeration members and values
5. **Generating** XMLDoc for Visual Studio IntelliSense (future phase)
6. **Creating** searchable indexes for offline use (future phase)

## 🏗️ Project Structure

```
offline-solidworks-api-docs/
├── 01-crawl-toc-pages/          # Phase 1: Crawl API docs via expandToc API
│   ├── solidworks_scraper/      # Scrapy project
│   ├── tests/                   # Test suite
│   ├── output/                  # Crawled data (gitignored)
│   │   ├── html/                # HTML files and JSON TOC structure
│   │   └── metadata/            # Crawl metadata (tracked)
│   ├── run_crawler.py           # Main entry point
│   └── validate_crawl.py        # Validation script
├── 02-extract-members/          # Phase 2: Extract properties & methods
│   ├── extract_members.py       # Main extraction script
│   ├── validate_extraction.py   # Validation script
│   ├── metadata/                # Output (api_members.xml)
│   └── tests/                   # Test suite
├── 03-extract-type-info/        # Phase 3: Extract type descriptions & examples
│   ├── extract_type_info.py     # Main extraction script
│   ├── validate_extraction.py   # Validation script
│   ├── metadata/                # Output (api_types.xml)
│   └── tests/                   # Test suite
├── 04-extract-enum-members/     # Phase 4: Extract enumeration members
│   ├── extract_enum_members.py  # Main extraction script
│   ├── metadata/                # Output (api_enums.xml)
│   └── tests/                   # Test suite
├── shared/                      # Shared utilities and helpers
├── CLAUDE.md                    # Project context for AI assistants
├── pyproject.toml               # Python project configuration
└── README.md                    # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- uv package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/offline-solidworks-api-docs.git
cd offline-solidworks-api-docs

# Install dependencies with uv
uv sync
```

### Running the Pipeline

#### Phase 1: Crawl Documentation

```bash
# Run a test crawl (limited pages)
uv run python 01-crawl-toc-pages/run_crawler.py --test

# Run full crawl (will take several hours)
uv run python 01-crawl-toc-pages/run_crawler.py

# Resume interrupted crawl
uv run python 01-crawl-toc-pages/run_crawler.py --resume

# Validate crawl results
uv run python 01-crawl-toc-pages/validate_crawl.py
```

#### Phase 2: Extract Members

```bash
# Extract properties and methods from crawled HTML
uv run python 02-extract-members/extract_members.py

# Validate extraction results
uv run python 02-extract-members/validate_extraction.py
```

#### Phase 3: Extract Type Information

```bash
# Extract type descriptions, examples, and remarks
uv run python 03-extract-type-info/extract_type_info.py

# Validate extraction results
uv run python 03-extract-type-info/validate_extraction.py
```

#### Phase 4: Extract Enum Members

```bash
# Extract enumeration members and values
uv run python 04-extract-enum-members/extract_enum_members.py
```

## 📊 Expected Results

### Phase 1: Crawling
- **460+ pages** from the SolidWorks API documentation
- Clean HTML content extracted from `__NEXT_DATA__` JSON
- JSON TOC structure from expandToc API
- Complete metadata for reproducibility
- **>95% success rate** for validation to pass

### Phase 2: Member Extraction
- **458+ types** with member information
- Properties and methods extracted from `*_members_*` HTML files
- Output: `api_members.xml` (~5 MB)

### Phase 3: Type Information Extraction
- **1674+ type files** processed
- **~1568 types** with descriptions (93%)
- **~561 types** with code examples (33%)
- **~3708 total examples** (VBA, VB.NET, C#, C++)
- **~455 types** with remarks (27%)
- Output: `api_types.xml` (~5 MB)

### Phase 4: Enum Extraction
- Enumeration members and values extracted
- Output: `api_enums.xml`

## 🧪 Testing

```bash
# Run all tests
uv run pytest -v

# Run tests for specific phase
uv run pytest 01-crawl-toc-pages/tests/ -v
uv run pytest 02-extract-members/tests/ -v
uv run pytest 03-extract-type-info/tests/ -v
uv run pytest 04-extract-enum-members/tests/ -v

# Run with coverage
uv run pytest --cov=01-crawl-toc-pages --cov=02-extract-members --cov=03-extract-type-info --cov-report=html
```

## 📝 Output Formats

### Phase 1: Crawl Metadata (JSON)

**urls_crawled.jsonl** - One record per crawled page:
```json
{
  "url": "https://help.solidworks.com/2026/english/api/sldworksapi/...",
  "timestamp": "2025-11-14T10:30:00Z",
  "file_path": "output/html/sldworksapi/...",
  "content_hash": "sha256:abc123...",
  "content_length": 12345,
  "status_code": 200,
  "title": "IAdvancedHoleFeatureData Interface",
  "session_id": "2025-11-14-103000"
}
```

**crawl_stats.json** - Summary statistics:
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

### Phase 2-4: Extracted Data (XML)

All extraction phases produce structured XML files:
- **api_members.xml** - Properties and methods for each type
- **api_types.xml** - Type descriptions, examples, and remarks
- **api_enums.xml** - Enumeration members and values

Each extraction also produces a summary JSON file with statistics.

## 🔧 Configuration

### Crawler Settings

Key settings in `01-crawl-toc-pages/solidworks_scraper/settings.py`:

- **User Agent**: Chrome browser to ensure proper access
- **Crawl Delay**: 2 seconds (respectful crawling)
- **Concurrent Requests**: 1 (polite single-threaded)
- **URL Boundary**: `/2026/english/api/` (stays within API docs)
- **Robots.txt**: Respected by default

### Python Project

Configuration in `pyproject.toml`:

- **Python Version**: 3.12+
- **Dependencies**: Scrapy, pytest, mypy, ruff, jsonlines
- **Code Quality**: Type checking with mypy, linting with ruff
- **Testing**: pytest with coverage support

## 🚦 Validation

Each phase includes validation scripts that check:

### Phase 1: Crawl Validation
- ✅ Minimum page count (95% of expected 460)
- ✅ All metadata files present and valid
- ✅ HTML files match metadata records
- ✅ No excessive duplicates
- ✅ Success rate >95%

### Phase 2-4: Extraction Validation
- ✅ XML files are well-formed
- ✅ All required fields present
- ✅ Type/member counts match expectations
- ✅ Summary statistics are accurate

## 🛠️ Development

### Project Principles

1. **Modularity**: Each phase reads from previous, writes to next
2. **Reproducibility**: All outputs are deterministic
3. **Metadata-Driven**: Comprehensive tracking for validation
4. **Copyright Compliance**: HTML content gitignored, users crawl themselves

### Code Quality

```bash
# Type checking with mypy
uv run mypy 01-crawl-toc-pages/
uv run mypy 02-extract-members/
uv run mypy 03-extract-type-info/

# Linting with ruff
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Run pre-commit hooks
uv run pre-commit run --all-files
```

## 📄 License

The crawler code is provided for educational purposes. The SolidWorks API documentation content is copyrighted by Dassault Systèmes SolidWorks Corporation.

## 🤝 Contributing

Contributions are welcome for:
- Improving crawler reliability
- Adding transformation pipelines
- Enhancing validation
- Documentation improvements

Please ensure all contributions maintain reproducibility and respect copyright.

## ⚡ Performance

### Phase 1: Crawling
- **Time**: ~15 minutes for complete crawl
- **Size**: ~100-150 MB of HTML content
- **Pages**: 460+ documentation pages
- **Network**: ~2 requests per second (2s delay)
- **Memory**: ~200-500 MB during crawl

### Phase 2-4: Extraction
- **Time**: ~30 seconds per phase (1674 files)
- **Memory**: <100 MB per phase
- **Output**: ~5 MB XML per phase

## 🐛 Troubleshooting

### Phase 1: Crawling Issues

1. **"scrapy: command not found"**
   - Use `uv run` prefix: `uv run python 01-crawl-toc-pages/run_crawler.py`

2. **Rate limiting or 403 errors**
   - Increase DOWNLOAD_DELAY in settings.py
   - Check robots.txt compliance

3. **Incomplete crawl**
   - Use `--resume` flag to continue
   - Check errors.jsonl for failed URLs

4. **No pages discovered**
   - Check expandToc API is accessible
   - Verify starting URL returns valid JSON

### Phase 2-4: Extraction Issues

1. **"No HTML files found"**
   - Ensure Phase 1 crawl has completed successfully
   - Check input directory path is correct

2. **Validation failures**
   - Run with `--verbose` for details
   - Check extraction_summary.json for error patterns

3. **Missing type information**
   - Normal - not all types have examples/remarks
   - Check validation percentages for expected coverage

## 📚 Documentation Structure

Each phase has detailed documentation:

- **README.md** (this file) - Project overview
- **01-crawl-toc-pages/README.md** - Crawler implementation details
- **02-extract-members/README.md** - Member extraction details
- **03-extract-type-info/README.md** - Type info extraction details
- **CLAUDE.md** - Project context for AI assistants

## 🔮 Future Phases (Planned)

- **Phase 5**: Merge all XML outputs into unified structure
- **Phase 6**: Generate XMLDoc for Visual Studio IntelliSense
- **Phase 7**: Create searchable offline documentation browser
- **Phase 8**: Export to additional formats (JSON, Markdown, PDF)

---

**Remember**: Always respect copyright and use this tool responsibly for personal/educational purposes only.
