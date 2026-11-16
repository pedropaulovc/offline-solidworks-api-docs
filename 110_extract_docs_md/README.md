# Phase 11: Extract Documentation to Markdown

This phase converts the HTML documentation pages from Phase 10 into Markdown format and reorganizes them according to the hierarchical Table of Contents structure.

## Overview

Phase 11 takes the crawled Programming Guide HTML pages and:
1. Converts HTML to clean, readable Markdown using `html2text`
2. Reorganizes files into a hierarchical directory structure matching the TOC
3. Generates metadata for tracking conversions and validation

## Input

- **HTML Files**: `100_crawl_programming_guide/output/html/**/*.html` (145 files)
- **expandToc JSON Files**: `100_crawl_programming_guide/output/html/expandToc_id_*.json` (145 files)
- **Metadata**: `100_crawl_programming_guide/metadata/urls_crawled.jsonl`

## Output

- **Markdown Files**: `110_extract_docs_md/output/markdown/**/*.md` (~125 content files)
- **Metadata Files**: `110_extract_docs_md/metadata/`
  - `files_created.jsonl`: Detailed conversion tracking
  - `extraction_stats.json`: Statistics and metrics
  - `manifest.json`: Phase configuration and metadata

## Directory Structure

```
110_extract_docs_md/
├── extract_markdown.py         # Main extraction script
├── toc_builder.py              # TOC tree builder
├── html_to_markdown.py         # HTML to Markdown converter
├── validate_extraction.py      # Validation script
├── tests/                      # Test suite
│   └── test_extraction.py
├── output/
│   └── markdown/               # Hierarchical markdown files (gitignored)
│       ├── Overview/
│       ├── SOLIDWORKS Partner Program/
│       ├── Types of SOLIDWORKS API Applications/
│       ├── SOLIDWORKS API Object Model and Class Hierarchy/
│       └── Programming with the SOLIDWORKS API/
└── metadata/                   # Tracking metadata (tracked in git)
    ├── files_created.jsonl
    ├── extraction_stats.json
    └── manifest.json
```

## Usage

### Extract Documentation

Convert all HTML files to Markdown:

```bash
uv run python 110_extract_docs_md/extract_markdown.py
```

Expected output:
- 125 Markdown files created
- Hierarchical directory structure matching TOC
- Metadata files for tracking

### Validate Results

Run validation checks:

```bash
uv run python 110_extract_docs_md/validate_extraction.py --verbose
```

Validation checks:
- All expected directories exist
- All Markdown files created successfully
- No empty files
- Metadata is complete and accurate
- File structure matches expectations

### Run Tests

Execute the test suite:

```bash
uv run pytest 110_extract_docs_md/tests/ -v
```

## Components

### 1. TOC Tree Builder (`toc_builder.py`)

Builds a hierarchical tree structure from expandToc JSON files:
- Loads all expandToc files
- Constructs parent-child relationships
- Provides tree traversal methods

**Example Usage:**
```python
from toc_builder import TocTreeBuilder

builder = TocTreeBuilder(Path("100_crawl_programming_guide/output/html"))
root = builder.build_tree()
builder.print_tree(root)  # Display tree structure
```

### 2. HTML to Markdown Converter (`html_to_markdown.py`)

Converts HTML content to Markdown format:
- Uses `html2text` library for conversion
- Preserves formatting, links, and structure
- Sanitizes filenames for filesystem compatibility

**Features:**
- Body width: unlimited (no text wrapping)
- Unicode support enabled
- Preserves links and images
- Clean, readable output

### 3. Markdown Extractor (`extract_markdown.py`)

Main orchestrator that:
- Builds TOC tree structure
- Converts each HTML file to Markdown
- Organizes files hierarchically
- Tracks metadata and statistics

**Process:**
1. Clear `output/markdown/`, so a page that left the TOC does not keep its old file
   (Phases 90 and 120 ship only `files_created.jsonl`'s pages, but the tree should match too)
2. Load metadata from Phase 10
3. Build TOC tree from expandToc files
4. Traverse tree and convert each leaf node; a page with no text, only images, is
   skipped (the bundle ships no images, so it would be one dangling `![](x.gif)`;
   links to it stay on the help page, which shows the image). This is decided on the
   HTML: in the Markdown a linked thumbnail or a layout table leaves text-like residue
5. Save Markdown files in hierarchical structure
6. Generate metadata and statistics

### 4. Validation Script (`validate_extraction.py`)

Comprehensive validation including:
- Directory existence checks
- Metadata file validation
- Markdown file completeness
- File structure verification
- Success rate calculation

**Validation Criteria:**
- Minimum 120 files converted (95% of 125 expected)
- Success rate ≥ 95%
- No missing files
- Proper hierarchical structure

## File Organization

The output Markdown files are organized to mirror the TOC hierarchy:

```
output/markdown/
├── Overview/
│   └── Overview.md
├── Types of SOLIDWORKS API Applications/
│   ├── Overview/
│   │   └── Overview.md
│   ├── SOLIDWORKS Macros/
│   │   ├── Overview/
│   │   │   └── Overview.md
│   │   ├── Record SOLIDWORKS Macro/
│   │   │   └── Record SOLIDWORKS Macro.md
│   │   └── ...
│   └── Standalone and Add-in Applications/
│       ├── Overview/
│       │   └── Overview.md
│       ├── Old Style MFC Extension Add-ins/
│       │   ├── Old Style MFC Extension Add-ins and Resources/
│       │   │   └── Old Style MFC Extension Add-ins and Resources.md
│       │   └── ...
│       └── ...
└── Programming with the SOLIDWORKS API/
    ├── Add-ins/
    │   ├── Callbacks/
    │   │   └── Callbacks.md
    │   └── ...
    └── ...
```

Each file path corresponds to its position in the documentation hierarchy as defined by the expandToc structure.

## Metadata

### files_created.jsonl

Each line contains information about a converted file:

```json
{
  "node_id": "1.2.1.6",
  "node_name": "Context-Sensitive SOLIDWORKS API Help",
  "original_url": "/2027/english/api/sldworksapiprogguide/GettingStarted/ContextSensitiveHelp.htm?id=1.2.1.6",
  "original_html": "output/html/sldworksapiprogguide/GettingStarted/ContextSensitiveHelp_abc123_abc123.html",
  "markdown_path": "110_extract_docs_md/output/markdown/Types of SOLIDWORKS API Applications/SOLIDWORKS Macros/Context-Sensitive SOLIDWORKS API Help/Context-Sensitive SOLIDWORKS API Help.md",
  "content_hash": "sha256_hash_here",
  "content_length": 5432,
  "path_segments": ["Types of SOLIDWORKS API Applications", "SOLIDWORKS Macros", "Context-Sensitive SOLIDWORKS API Help"]
}
```

### extraction_stats.json

Overall statistics (no run timestamps, so a rerun on the same input leaves the committed
file unchanged). `skipped_files` counts TOC nodes with no crawled HTML;
`image_only_pages` lists pages deliberately not written:

```json
{
  "total_nodes": 145,
  "converted_files": 125,
  "skipped_files": 0,
  "failed_files": 0,
  "image_only_pages": []
}
```

## Implementation Details

### HTML to Markdown Conversion

The converter uses a fresh `html2text` instance per page (`new_html2text()`): the parser
keeps state between calls, so a shared instance let an unclosed `<table>` on one page
reshape the next page's markdown. Settings:
- `body_width=0`: No line wrapping
- `unicode_snob=True`: Use Unicode characters
- `ignore_links=False`: Preserve links
- `ignore_images=False`: Preserve images
- `ignore_emphasis=False`: Preserve formatting

Before conversion, CHM-alias `href`s (`sldworksapi.chm::/SOLIDWORKS.Interop.sldworks~X.html`,
`ms-its:swconst.chm::/DP_Units.htm`) are rewritten as links relative to the page, to the
page the alias names (`../../sldworksapi/SOLIDWORKS.Interop.sldworks~X.html`), via
`shared/chm_aliases.py`. As written they are dead links, and Phase 90 copies the
Markdown into `SolidWorks.Interop.guides.xml` verbatim.

### Filename Sanitization

Invalid characters are replaced with underscores:
- `<>:"/\|?*` → `_`
- Leading/trailing spaces and dots removed
- Maximum length: 200 characters

### Path Construction

The hierarchical path for each file is built by:
1. Starting from the root node
2. Traversing parent-child relationships
3. Using sanitized node names as directory names
4. Placing the Markdown file in the deepest directory

## Testing

The test suite covers:
- TOC tree building
- HTML to Markdown conversion
- File organization
- Metadata generation
- Validation logic

Run tests with:
```bash
uv run pytest 110_extract_docs_md/tests/ -v --cov
```

## Dependencies

- **html2text**: HTML to Markdown conversion
- **jsonlines**: Metadata storage
- **pathlib**: File system operations

All dependencies are managed via `pyproject.toml`.

## Performance

- **Processing Time**: ~2-3 minutes for 125 files
- **Memory Usage**: ~100-200 MB
- **Output Size**: ~2-5 MB for all Markdown files

## Known Limitations

1. **TOC Pages**: Non-leaf nodes (TOC/index pages) are not converted, only content pages
2. **Character Encoding**: Uses UTF-8 throughout, may need adjustment for other encodings
3. **Link Preservation**: Links to other guide pages become relative `.md` paths,
   matched case-insensitively, as the help server matches paths. The destination is
   built by `shared/markdown_links.py` (as Phase 120's are), so it is not always the
   literal file name: a `#` in the name is percent-encoded (`Visual C%23.md` for
   `Visual C#.md`), and a path with a space or parenthesis is angle-wrapped
   (`[x](<Add-ins/Add-in Toolbars.md>)`). The rest keep their help-site form, relative
   to the page's original URL; Phase 120 resolves those against the files it ships or
   the online help.
4. **Image Handling**: Image references preserved but images themselves not downloaded.
   A page with no text, only images, is not written (see above).

## Troubleshooting

### Issue: Missing HTML files

**Symptom**: Skipped files during extraction

**Solution**: Ensure Phase 10 crawl completed successfully

```bash
uv run python 100_crawl_programming_guide/validate_crawl.py
```

### Issue: Invalid filenames

**Symptom**: Files not created or path errors

**Solution**: Check for special characters in node names. The sanitizer should handle most cases, but extremely long names may be truncated.

### Issue: Validation fails

**Symptom**: Validation script reports errors

**Solution**: Check the validation report for details:

```bash
uv run python 110_extract_docs_md/validate_extraction.py --verbose --save-report
```

Review the generated `validation_report_*.json` file for specific errors.

## Future Enhancements

Potential improvements for Phase 11:

1. **Link Rewriting**: Convert absolute URLs to relative paths for offline use
2. **Image Download**: Optionally download and embed images
3. **Table of Contents**: Generate a master TOC file linking all pages
4. **Search Index**: Create a searchable index of all content
5. **Format Options**: Support additional output formats (AsciiDoc, reStructuredText, etc.)

## Related Phases

- **Phase 10** (`100_crawl_programming_guide`): Crawls Programming Guide HTML pages
- **Phase 12** (future): Build searchable offline documentation

## Version History

- **v1.0.0** (2025-01-17): Initial implementation
  - HTML to Markdown conversion
  - Hierarchical file organization
  - Metadata tracking
  - Validation script
  - Test suite

## License & Copyright

See main project README for copyright and usage guidelines. All crawled content remains property of Dassault Systèmes and is for personal/educational use only.
