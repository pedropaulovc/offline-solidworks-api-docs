# Developer Guide

This guide is for developers who want to run the documentation generation pipeline, contribute to the project, or understand how it works.

**For end users**: See [README.md](README.md) for how to use the pre-generated documentation packages.

## 📋 Pipeline Overview

This project provides a reproducible 13-phase pipeline for generating offline documentation for the SolidWorks API:

### Pipeline Phases

1. **Crawl TOC Pages** (Phase 10) - Crawl API documentation via expandToc API ✅
2. **Extract Types** (Phase 20) - Extract type information from table of contents ✅
3. **Crawl Type Members** (Phase 30) - Crawl member pages (properties and methods) ✅
4. **Extract Type Details** (Phase 40) - Extract type-level documentation ✅
5. **Extract Member Details** (Phase 50) - Extract member parameters and return values ✅
6. **Extract Enum Members** (Phase 60) - Extract enumeration members and values ✅
7. **Crawl Examples** (Phase 70) - Crawl example pages ✅
8. **Parse Examples** (Phase 80) - Parse example content into structured format ✅
9. **Export XMLDoc** (Phase 90) - Generate XMLDoc for Visual Studio IntelliSense ✅
10. **Crawl Programming Guide** (Phase 100) - Crawl programming guide pages ✅
11. **Extract Docs to Markdown** (Phase 110) - Convert HTML to Markdown ✅
12. **Export LLM Docs** (Phase 120) - Export LLM-friendly documentation ✅
13. **Create Release Packages** (Phase 200) - Create versioned release packages ✅

### Architecture Principles

1. **Modular Pipeline**: Each phase reads from previous, writes to next
2. **Reproducibility**: All outputs are deterministic
3. **Metadata-Driven**: Comprehensive tracking for validation
4. **Copyright Compliance**: HTML content gitignored, users crawl themselves

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
├── 90_export_xmldoc/            # Phase 9: Export XMLDoc files
│   ├── generate_xmldoc.py       # Main generation script
│   ├── data_merger.py           # Data merging utilities
│   ├── xmldoc_id.py             # XMLDoc ID generation
│   ├── output/                  # XMLDoc files
│   └── tests/                   # Test suite
├── 100_crawl_programming_guide/ # Phase 10: Crawl programming guide
│   ├── solidworks_scraper/      # Scrapy project
│   ├── output/                  # Crawled HTML (gitignored)
│   └── run_crawler.py           # Main entry point
├── 110_extract_docs_md/         # Phase 11: Extract docs to Markdown
│   ├── extract_docs_md.py       # Main extraction script
│   ├── validate_extraction.py   # Validation script
│   ├── output/                  # Markdown files
│   └── tests/                   # Test suite
├── 120_export_llm_docs/         # Phase 12: Export LLM-friendly docs
│   ├── export_llm_docs.py       # Main export script
│   ├── validate_export.py       # Validation script
│   ├── output/                  # LLM-optimized markdown
│   └── tests/                   # Test suite
├── 200_export_full_release/     # Phase 13: Create release packages
│   ├── export_release.py        # Main export script
│   ├── validate_release.py      # Validation script
│   ├── output/                  # Release packages
│   └── tests/                   # Test suite
├── shared/                      # Shared utilities and helpers
├── CLAUDE.md                    # Project context for AI assistants
├── DEVELOPING.md                # This file
├── pyproject.toml               # Python project configuration
└── README.md                    # User documentation
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **uv** package manager (https://github.com/astral-sh/uv)
- **Git**

### Installation

```bash
# Clone the repository
git clone https://github.com/pedropaulovc/offline-solidworks-api-docs.git
cd offline-solidworks-api-docs

# Install dependencies with uv
uv sync
```

## 🔧 Running the Pipeline

### Complete Pipeline

To run all phases sequentially:

```bash
# Phase 1: Crawl Table of Contents
uv run python 10_crawl_toc_pages/run_crawler.py
uv run python 10_crawl_toc_pages/validate_crawl.py

# Phase 2: Extract Types
uv run python 20_extract_types/extract_types.py
uv run python 20_extract_types/validate_extraction.py

# Phase 3: Crawl Type Members
uv run python 30_crawl_type_members/run_crawler.py

# Phase 4: Extract Type Details
uv run python 40_extract_type_details/extract_type_info.py
uv run python 40_extract_type_details/validate_extraction.py

# Phase 5: Extract Member Details
uv run python 50_extract_type_member_details/extract_member_details.py
uv run python 50_extract_type_member_details/validate_extraction.py

# Phase 6: Extract Enum Members
uv run python 60_extract_enum_members/extract_enum_members.py

# Phase 7: Crawl Examples
uv run python 70_crawl_examples/run_crawler.py

# Phase 8: Parse Examples
uv run python 80_parse_examples/parse_examples.py
uv run python 80_parse_examples/validate_parse.py

# Phase 9: Generate XMLDoc
uv run python 90_export_xmldoc/generate_xmldoc.py
uv run python 90_export_xmldoc/validate_generation.py

# Phase 10: Crawl Programming Guide
uv run python 100_crawl_programming_guide/run_crawler.py
uv run python 100_crawl_programming_guide/validate_crawl.py

# Phase 11: Extract Docs to Markdown
uv run python 110_extract_docs_md/extract_docs_md.py
uv run python 110_extract_docs_md/validate_extraction.py

# Phase 12: Export LLM Documentation
uv run python 120_export_llm_docs/export_llm_docs.py
uv run python 120_export_llm_docs/validate_export.py

# Phase 13: Create Release Packages
uv run python 200_export_full_release/export_release.py
uv run python 200_export_full_release/validate_release.py
```

### Quick Testing

Run a test crawl with limited pages:

```bash
# Test Phase 1 with limited pages
uv run python 10_crawl_toc_pages/run_crawler.py --test

# Resume interrupted crawl
uv run python 10_crawl_toc_pages/run_crawler.py --resume
```

## 📊 Expected Results

### Phase 1: Crawl TOC Pages
- **460+ pages** from the SolidWorks API documentation
- Clean HTML content extracted from `__NEXT_DATA__` JSON
- JSON TOC structure from expandToc API
- Complete metadata for reproducibility
- **>95% success rate** for validation to pass

### Phase 2: Extract Types
- **458+ types** with member information
- Properties and methods extracted from table of contents
- Output: `api_types.xml`

### Phase 3: Crawl Type Members
- **~11,500+ member pages** crawled (properties and methods)
- HTML content for each type member
- Complete metadata for reproducibility

### Phase 4: Extract Type Details
- **1,674+ type files** processed
- **~1,568 types** with descriptions (93%)
- **~561 types** with code examples (33%)
- **~3,708 total examples** (VBA, VB.NET, C#, C++)
- **~455 types** with remarks (27%)
- Output: `api_types.xml` (~5 MB)

### Phase 5: Extract Member Details
- **~11,523 members** extracted
- Parameter details, return values, and remarks
- Output: `member_details.xml`

### Phase 6: Extract Enum Members
- Enumeration members and values extracted
- Output: `enum_members.xml`

### Phase 7: Crawl Examples
- Example pages crawled from documentation
- HTML content for code examples

### Phase 8: Parse Examples
- Code examples extracted and parsed
- Indentation preserved with CDATA wrapping
- Output: `examples.xml`

### Phase 9: Generate XMLDoc
- **10 XMLDoc files** generated (one per assembly)
- Complete IntelliSense documentation
- Output: `90_export_xmldoc/output/*.xml`

### Phase 10: Crawl Programming Guide
- **145 programming guide pages** crawled
- Hierarchical TOC structure preserved
- HTML content extracted from `__NEXT_DATA__` JSON

### Phase 11: Extract Docs to Markdown
- **125 content pages** converted to Markdown
- Hierarchical file organization matching TOC
- **134 URLs rewritten** for relative links
- 100% success rate

### Phase 12: Export LLM Documentation
- **26,902 markdown files** generated (file-per-member)
- Grep-optimized structure for AI tools
- Functional categories integration
- Output: `120_export_llm_docs/output/`

### Phase 13: Create Release Packages
- **XMLDoc package** for Visual Studio IntelliSense
- **LLM docs package** for AI-assisted development
- Git tag-based versioning
- Output: `200_export_full_release/output/`

## 🧪 Testing

### Run All Tests

```bash
# Run complete test suite
uv run pytest -v

# Run with coverage
uv run pytest --cov --cov-report=html
```

### Run Tests by Phase

```bash
# Phase-specific tests
uv run pytest 10_crawl_toc_pages/tests/ -v
uv run pytest 20_extract_types/tests/ -v
uv run pytest 40_extract_type_details/tests/ -v
uv run pytest 50_extract_type_member_details/tests/ -v
uv run pytest 60_extract_enum_members/tests/ -v
uv run pytest 80_parse_examples/tests/ -v
uv run pytest 90_export_xmldoc/tests/ -v
uv run pytest 100_crawl_programming_guide/tests/ -v
uv run pytest 110_extract_docs_md/tests/ -v
uv run pytest 120_export_llm_docs/tests/ -v
uv run pytest 200_export_full_release/tests/ -v
```

## 🔍 Code Quality

### Type Checking

```bash
# Type check with mypy
uv run mypy 10_crawl_toc_pages/
uv run mypy 20_extract_types/
uv run mypy 40_extract_type_details/
uv run mypy 50_extract_type_member_details/
uv run mypy 60_extract_enum_members/
uv run mypy 80_parse_examples/
uv run mypy 90_export_xmldoc/
```

### Linting

```bash
# Lint with ruff
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .
```

### Pre-commit Hooks

```bash
# Run all pre-commit hooks
uv run pre-commit run --all-files
```

## 📝 Output Formats

### Crawl Metadata (JSON Lines)

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

### Extracted Data (XML)

All extraction phases produce structured XML files:
- **Phase 2**: `api_types.xml` - Type definitions
- **Phase 4**: `api_types.xml` - Type descriptions, examples, remarks
- **Phase 5**: `member_details.xml` - Member parameters, return values, remarks
- **Phase 6**: `enum_members.xml` - Enumeration members and values
- **Phase 8**: `examples.xml` - Code examples in structured format
- **Phase 9**: `SolidWorks.Interop.*.xml` - XMLDoc files for IntelliSense (10 files)

### LLM Documentation (Markdown)

- **Phase 11**: Hierarchical markdown files matching TOC structure
- **Phase 12**: Flat grep-optimized markdown files with YAML frontmatter

### Release Packages (ZIP)

- **Phase 13**: Versioned ZIP files ready for distribution

## ⚡ Performance

### Complete Pipeline
- **Total Time**: ~4-5 hours for complete pipeline
- **Storage**: ~800 MB (HTML + intermediate files + LLM docs)
- **Final Output**: 2 release packages (XMLDoc + LLM docs, ~60 MB compressed)

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
- **Phase 10** (Crawl Programming Guide): ~5 minutes
- **Phase 11** (Extract Docs to Markdown): ~30 seconds
- **Phase 12** (Export LLM Docs): ~60 seconds
- **Phase 13** (Create Release Packages): ~10 seconds

## 🔧 Configuration

### Crawler Settings

Key settings in crawler `settings.py` files:

- **User Agent**: Chrome browser to ensure proper access
- **Crawl Delay**: 2 seconds (respectful crawling)
- **Concurrent Requests**: 1 (polite single-threaded)
- **URL Boundary**: `/2026/english/api/` (stays within API docs)
- **Robots.txt**: Respected by default

### Python Project

Configuration in `pyproject.toml`:

- **Python Version**: 3.12+
- **Dependencies**: Scrapy, pytest, mypy, ruff, jsonlines, BeautifulSoup4
- **Code Quality**: Type checking with mypy, linting with ruff
- **Testing**: pytest with coverage support

## 🚦 Validation

Each phase includes validation scripts that check:

### Crawl Validation (Phases 1, 3, 7, 10)
- ✅ Minimum page count (95% of expected)
- ✅ All metadata files present and valid
- ✅ HTML files match metadata records
- ✅ No excessive duplicates
- ✅ Success rate >95%

### Extraction Validation (Phases 2, 4, 5, 6, 8, 9)
- ✅ XML files are well-formed
- ✅ All required fields present
- ✅ Type/member counts match expectations
- ✅ Summary statistics are accurate

### Export Validation (Phases 11, 12, 13)
- ✅ All expected files generated
- ✅ Markdown files have proper frontmatter
- ✅ Cross-references are valid
- ✅ Package integrity verified

## 🐛 Troubleshooting

### Crawling Issues

**"scrapy: command not found"**
- Use `uv run` prefix: `uv run python 10_crawl_toc_pages/run_crawler.py`

**Rate limiting or 403 errors**
- Increase DOWNLOAD_DELAY in settings.py
- Check robots.txt compliance

**Incomplete crawl**
- Use `--resume` flag to continue
- Check errors.jsonl for failed URLs

**No pages discovered**
- Check expandToc API is accessible
- Verify starting URL returns valid JSON

### Extraction Issues

**"No HTML files found"**
- Ensure previous crawl phase has completed successfully
- Check input directory path is correct

**Validation failures**
- Run with `--verbose` flag for details
- Check extraction_summary.json for error patterns

**Missing type information**
- Normal - not all types have examples/remarks
- Check validation percentages for expected coverage

## 🤝 Contributing

### Development Workflow

1. **Fork** the repository
2. **Create** a feature branch
3. **Make** your changes
4. **Add** tests for new functionality
5. **Run** validation: `uv run pytest -v`
6. **Check** code quality: `uv run ruff check .`
7. **Submit** a pull request

### Code Guidelines

- Use type hints where possible
- Follow PEP 8 conventions
- Document complex logic with comments
- Write comprehensive docstrings
- Maintain >80% test coverage
- Ensure reproducibility

### Testing Philosophy

- Unit tests for individual components
- Integration tests for pipelines
- Regression tests for crawl completeness
- Mock external dependencies in tests

## 📚 Documentation

Each phase has detailed documentation:

- **10_crawl_toc_pages/README.md** - Crawler implementation details
- **20_extract_types/README.md** - Type extraction details
- **30_crawl_type_members/README.md** - Member crawling details
- **40_extract_type_details/README.md** - Type detail extraction
- **50_extract_type_member_details/README.md** - Member detail extraction
- **60_extract_enum_members/README.md** - Enum extraction details
- **70_crawl_examples/README.md** - Example crawling details
- **80_parse_examples/README.md** - Example parsing details
- **90_export_xmldoc/README.md** - XMLDoc export details
- **100_crawl_programming_guide/README.md** - Programming guide crawling
- **110_extract_docs_md/README.md** - Markdown extraction details
- **120_export_llm_docs/README.md** - LLM documentation export
- **200_export_full_release/README.md** - Release package creation
- **CLAUDE.md** - Project context for AI assistants

## 🔮 Future Enhancements

Planned features for future development:

- **Phase 130**: Build searchable offline index
- **Phase 140**: Export to additional formats (HTML, PDF, etc.)
- **Enhanced search**: Full-text search across all documentation
- **IDE plugins**: Direct integration with Visual Studio, VS Code, etc.
- **Incremental updates**: Support for updating documentation without full re-crawl
- **Multi-version support**: Track documentation across SolidWorks versions

## ⚖️ Legal & Ethical Considerations

### Copyright Compliance

- ⚠️ Crawled content is copyrighted by Dassault Systèmes SolidWorks Corporation
- 📚 For personal/educational use only
- 🚫 No redistribution of crawled HTML content
- ⏱️ Respectful crawling (2-second delays)
- ✅ Generated packages (XMLDoc, LLM docs) can be shared under fair use

### Technical Boundaries

- Must stay within `/2026/english/api/` URL boundary
- Content extracted from `__NEXT_DATA__` JSON (helpText field)
- Minimum 95% success rate for validation
- Expected ~460 TOC pages, ~11,500 member pages

## 📞 Support

- **Issues**: https://github.com/pedropaulovc/offline-solidworks-api-docs/issues
- **Discussions**: GitHub Discussions (for questions and ideas)
- **Documentation**: See README.md and phase-specific docs

## 🙏 Acknowledgments

Built with:
- **Scrapy** - Best-in-class web crawling framework
- **BeautifulSoup4** - HTML parsing and content extraction
- **pytest** - Comprehensive testing framework
- **uv** - Fast, modern Python package management
- **mypy & ruff** - Code quality and type checking

---

**Happy Developing!** 🚀

For user documentation, see [README.md](README.md)
