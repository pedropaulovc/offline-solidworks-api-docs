# Offline SolidWorks API Documentation

A comprehensive crawler and transformation pipeline for creating offline, searchable versions of the SolidWorks API documentation with XMLDoc files for Visual Studio IntelliSense.

## 🚀 Quick Start: Using Pre-Generated XMLDoc Files

**Want IntelliSense for SolidWorks API?** Just follow these steps:

1. **Download** `SolidWorks.Interop.xmldoc.v1.0.0.zip` from the [latest release](https://github.com/pedropaulovc/offline-solidworks-api-docs/releases/latest)
2. **Extract** the XML files from the archive
3. **Copy** them to the same folder where the SolidWorks SDK DLLs are located:
   - **SOLIDWORKS 3DEXPERIENCE**: `C:\Program Files\Dassault Systemes\SOLIDWORKS 3DEXPERIENCE\SOLIDWORKS\api\redist`
   - **Standard SOLIDWORKS**: `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist`
4. **Restart** Visual Studio or your IDE
5. **Enjoy** full IntelliSense documentation with tooltips, parameter info, and examples!

The XML files should be placed alongside their corresponding DLL files (e.g., `SolidWorks.Interop.sldworks.xml` next to `SolidWorks.Interop.sldworks.dll`).

## 📋 Overview

This project provides a reproducible pipeline for generating XMLDoc files that enable IntelliSense support for the SolidWorks API in Visual Studio and other IDEs.

### Pipeline Phases

The complete pipeline consists of 9 phases:

1. **Crawling** the SolidWorks API documentation using the expandToc API ✅
2. **Extracting** type information from the table of contents ✅
3. **Crawling** type member pages (properties and methods) ✅
4. **Extracting** type-level documentation (descriptions, examples, remarks) ✅
5. **Extracting** type member details (parameters, return values, remarks) ✅
6. **Extracting** enumeration members and values ✅
7. **Crawling** example pages ✅
8. **Parsing** example content into structured format ✅
9. **Generating** XMLDoc for Visual Studio IntelliSense ✅

## 🏗️ Project Structure

```
offline-solidworks-api-docs/
├── 10_crawl_toc_pages/          # Phase 1: Crawl API docs via expandToc API
│   ├── solidworks_scraper/      # Scrapy project
│   ├── tests/                   # Test suite
│   ├── output/                  # Crawled data (gitignored)
│   │   ├── html/                # HTML files and JSON TOC structure
│   │   └── metadata/            # Crawl metadata (tracked)
│   ├── run_crawler.py           # Main entry point
│   └── validate_crawl.py        # Validation script
├── 20_extract_types/            # Phase 2: Extract types from TOC
│   ├── extract_types.py         # Main extraction script
│   ├── validate_extraction.py   # Validation script
│   ├── metadata/                # Output (api_types.xml)
│   └── tests/                   # Test suite
├── 30_crawl_type_members/       # Phase 3: Crawl member pages
│   ├── solidworks_scraper/      # Scrapy project
│   ├── tests/                   # Test suite
│   ├── output/                  # Crawled HTML (gitignored)
│   └── run_crawler.py           # Main entry point
├── 40_extract_type_details/     # Phase 4: Extract type details
│   ├── extract_type_info.py     # Main extraction script
│   ├── validate_extraction.py   # Validation script
│   ├── metadata/                # Output (api_types.xml)
│   └── tests/                   # Test suite
├── 50_extract_type_member_details/ # Phase 5: Extract member details
│   ├── extract_member_details.py # Main extraction script
│   ├── validate_extraction.py   # Validation script
│   ├── output/                  # Output (member_details.xml)
│   └── tests/                   # Test suite
├── 60_extract_enum_members/     # Phase 6: Extract enumeration members
│   ├── extract_enum_members.py  # Main extraction script
│   ├── metadata/                # Output (enum_members.xml)
│   └── tests/                   # Test suite
├── 70_crawl_examples/           # Phase 7: Crawl example pages
│   ├── solidworks_scraper/      # Scrapy project
│   ├── output/                  # Crawled HTML (gitignored)
│   └── run_crawler.py           # Main entry point
├── 80_parse_examples/           # Phase 8: Parse example content
│   ├── parse_examples.py        # Main parsing script
│   ├── validate_parse.py        # Validation script
│   ├── output/                  # Output (examples.xml)
│   └── tests/                   # Test suite
├── 90_generate_xmldoc/          # Phase 9: Generate XMLDoc files
│   ├── generate_xmldoc.py       # Main generation script
│   ├── data_merger.py           # Data merging utilities
│   ├── xmldoc_id.py             # XMLDoc ID generation
│   ├── output/                  # XMLDoc files
│   └── tests/                   # Test suite
├── 100_crawl_programming_guide/ # Phase 10: Crawl programming guide
├── 110_extract_docs_md/         # Phase 11: Extract docs to Markdown
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
git clone https://github.com/pedropaulovc/offline-solidworks-api-docs.git
cd offline-solidworks-api-docs

# Install dependencies with uv
uv sync
```

### Running the Complete Pipeline

To generate the XMLDoc files yourself (instead of using the pre-generated ones):

#### Phase 1: Crawl Documentation

```bash
# Run a test crawl (limited pages)
uv run python 10_crawl_toc_pages/run_crawler.py --test

# Run full crawl (will take several hours)
uv run python 10_crawl_toc_pages/run_crawler.py

# Resume interrupted crawl
uv run python 10_crawl_toc_pages/run_crawler.py --resume

# Validate crawl results
uv run python 10_crawl_toc_pages/validate_crawl.py
```

#### Phase 2: Extract Types

```bash
# Extract types from table of contents
uv run python 20_extract_types/extract_types.py

# Validate extraction results
uv run python 20_extract_types/validate_extraction.py
```

#### Phase 3: Crawl Type Members

```bash
# Crawl member pages (properties and methods)
uv run python 30_crawl_type_members/run_crawler.py
```

#### Phase 4: Extract Type Details

```bash
# Extract type descriptions, examples, and remarks
uv run python 40_extract_type_details/extract_type_info.py

# Validate extraction results
uv run python 40_extract_type_details/validate_extraction.py
```

#### Phase 5: Extract Member Details

```bash
# Extract member parameters, return values, and remarks
uv run python 50_extract_type_member_details/extract_member_details.py

# Validate extraction results
uv run python 50_extract_type_member_details/validate_extraction.py
```

#### Phase 6: Extract Enum Members

```bash
# Extract enumeration members and values
uv run python 60_extract_enum_members/extract_enum_members.py
```

#### Phase 7: Crawl Examples

```bash
# Crawl example pages
uv run python 70_crawl_examples/run_crawler.py
```

#### Phase 8: Parse Examples

```bash
# Parse example content into structured format
uv run python 80_parse_examples/parse_examples.py

# Validate parsing results
uv run python 80_parse_examples/validate_parse.py
```

#### Phase 9: Generate XMLDoc

```bash
# Generate XMLDoc files for IntelliSense
uv run python 90_generate_xmldoc/generate_xmldoc.py

# Validate XMLDoc generation
uv run python 90_generate_xmldoc/validate_generation.py
```

## 📊 Expected Results

### Phase 1: Crawling
- **460+ pages** from the SolidWorks API documentation
- Clean HTML content extracted from `__NEXT_DATA__` JSON
- JSON TOC structure from expandToc API
- Complete metadata for reproducibility
- **>95% success rate** for validation to pass

### Phase 2: Type Extraction
- **458+ types** with member information
- Properties and methods extracted from table of contents
- Output: `api_types.xml`

### Phase 3: Member Crawling
- **~11,500+ member pages** crawled (properties and methods)
- HTML content for each type member
- Complete metadata for reproducibility

### Phase 4: Type Details Extraction
- **1674+ type files** processed
- **~1568 types** with descriptions (93%)
- **~561 types** with code examples (33%)
- **~3708 total examples** (VBA, VB.NET, C#, C++)
- **~455 types** with remarks (27%)
- Output: `api_types.xml` (~5 MB)

### Phase 5: Member Details Extraction
- **~11,523 members** extracted
- Parameter details, return values, and remarks
- Output: `member_details.xml`

### Phase 6: Enum Extraction
- Enumeration members and values extracted
- Output: `enum_members.xml`

### Phase 7: Example Crawling
- Example pages crawled from documentation
- HTML content for code examples

### Phase 8: Example Parsing
- Code examples extracted and parsed
- Indentation preserved with CDATA wrapping
- Output: `examples.xml`

### Phase 9: XMLDoc Generation
- **10 XMLDoc files** generated (one per assembly)
- Complete IntelliSense documentation
- Output: `90_generate_xmldoc/output/*.xml`

## 🧪 Testing

```bash
# Run all tests
uv run pytest -v

# Run tests for specific phase
uv run pytest 10_crawl_toc_pages/tests/ -v
uv run pytest 20_extract_types/tests/ -v
uv run pytest 40_extract_type_details/tests/ -v
uv run pytest 50_extract_type_member_details/tests/ -v
uv run pytest 60_extract_enum_members/tests/ -v
uv run pytest 80_parse_examples/tests/ -v
uv run pytest 90_generate_xmldoc/tests/ -v

# Run with coverage
uv run pytest --cov --cov-report=html
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

### Phases 2-9: Extracted Data (XML)

All extraction phases produce structured XML files:
- **Phase 2**: `api_types.xml` - Type definitions
- **Phase 4**: `api_types.xml` - Type descriptions, examples, and remarks
- **Phase 5**: `member_details.xml` - Member parameters, return values, and remarks
- **Phase 6**: `enum_members.xml` - Enumeration members and values
- **Phase 8**: `examples.xml` - Code examples in structured format
- **Phase 9**: `SolidWorks.Interop.*.xml` - XMLDoc files for IntelliSense (10 files)

Each extraction also produces a summary JSON file with statistics.

## 🔧 Configuration

### Crawler Settings

Key settings in `10_crawl_toc_pages/solidworks_scraper/settings.py`:

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

### Phases 2-9: Extraction Validation
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
uv run mypy 10_crawl_toc_pages/
uv run mypy 20_extract_types/
uv run mypy 40_extract_type_details/

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

### Complete Pipeline
- **Total Time**: ~4-5 hours for complete pipeline
- **Storage**: ~500-600 MB (HTML + intermediate files)
- **Final Output**: 10 XMLDoc files (~2 MB compressed)

### Phase-by-Phase Breakdown
- **Phase 1** (Crawl TOC): ~15 minutes, ~150 MB HTML
- **Phase 2** (Extract Types): ~10 seconds
- **Phase 3** (Crawl Members): ~3-4 hours, ~400 MB HTML
- **Phase 4** (Extract Type Details): ~30 seconds
- **Phase 5** (Extract Member Details): ~60 seconds
- **Phase 6** (Extract Enums): ~10 seconds
- **Phase 7** (Crawl Examples): ~10 minutes
- **Phase 8** (Parse Examples): ~20 seconds
- **Phase 9** (Generate XMLDoc): ~30 seconds

## 🐛 Troubleshooting

### Phase 1: Crawling Issues

1. **"scrapy: command not found"**
   - Use `uv run` prefix: `uv run python 10_crawl_toc_pages/run_crawler.py`

2. **Rate limiting or 403 errors**
   - Increase DOWNLOAD_DELAY in settings.py
   - Check robots.txt compliance

3. **Incomplete crawl**
   - Use `--resume` flag to continue
   - Check errors.jsonl for failed URLs

4. **No pages discovered**
   - Check expandToc API is accessible
   - Verify starting URL returns valid JSON

### Phases 2-9: Extraction Issues

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

- **README.md** (this file) - Project overview and quick start
- **10_crawl_toc_pages/README.md** - Crawler implementation details
- **20_extract_types/README.md** - Type extraction details
- **30_crawl_type_members/README.md** - Member crawling details
- **40_extract_type_details/README.md** - Type detail extraction
- **50_extract_type_member_details/README.md** - Member detail extraction
- **60_extract_enum_members/README.md** - Enum extraction details
- **70_crawl_examples/README.md** - Example crawling details
- **80_parse_examples/README.md** - Example parsing details
- **90_generate_xmldoc/README.md** - XMLDoc generation details
- **100_crawl_programming_guide/README.md** - Programming guide crawling
- **110_extract_docs_md/README.md** - Markdown extraction details
- **CLAUDE.md** - Project context for AI assistants

## 🔮 Future Enhancements (Planned)

- **Phase 120**: Create searchable offline documentation browser
- **Phase 130**: Export to additional formats (JSON, PDF)
- **Enhanced search**: Full-text search across all documentation
- **IDE plugins**: Direct integration with Visual Studio, VS Code, etc.

## ⚠️ Legal Notice

**IMPORTANT**: This tool is designed for personal, educational, and fair use only. The crawled documentation content is copyrighted by Dassault Systèmes SolidWorks Corporation.

- ❌ DO NOT redistribute crawled content
- ❌ DO NOT use for commercial purposes
- ✅ Each user must crawl the documentation themselves
- ✅ Pre-generated XMLDoc files can be shared (fair use)
- 📁 Crawled HTML content is gitignored and not included in this repository

**Remember**: Always respect copyright and use this tool responsibly for personal/educational purposes only.
