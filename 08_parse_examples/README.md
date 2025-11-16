# Phase 8: Parse Examples

Parses HTML example files from Phase 7 and generates XML with CDATA-wrapped example content.

## Overview

Phase 8 takes the HTML example files crawled in Phase 7 and extracts the example content (descriptions, code snippets, etc.) into a structured XML format. The XML contains `<Example>` elements with URLs and CDATA-wrapped content including code blocks.

## Prerequisites

- **Phase 7** must be completed (HTML files in `07_crawl_examples/output/html/`)
- Python 3.12+
- BeautifulSoup4 library

## Project Structure

```
06_parse_examples/
├── parse_examples.py      # Main parsing script
├── validate_parse.py      # Validation script
├── tests/
│   └── test_parser.py    # Test suite
├── output/
│   └── examples.xml      # Generated XML (gitignored)
├── metadata/
│   ├── parse_stats.json  # Parsing statistics
│   ├── manifest.json     # Parse configuration
│   └── parse_errors.json # Error log (if any)
└── README.md             # This file
```

## Installation

Install dependencies:

```bash
uv pip install beautifulsoup4
```

## Usage

### Run the Parser

```bash
uv run python 08_parse_examples/parse_examples.py
```

This will:
1. Read all HTML files from `07_crawl_examples/output/html/`
2. Extract example content (text and code blocks)
3. Generate `output/examples.xml` with CDATA-wrapped content
4. Save metadata to `metadata/` directory

### Validate Results

```bash
uv run python 08_parse_examples/validate_parse.py
```

Add `--verbose` to see all warnings:

```bash
uv run python 08_parse_examples/validate_parse.py --verbose
```

### Run Tests

```bash
uv run pytest 08_parse_examples/tests/ -v
```

## Output Format

### XML Structure

```xml
<Examples>
    <Example>
        <Url>sldworksapi/Example_Name.htm</Url>
        <Content><![CDATA[
Example Title
Description text here.

<code>
' VBA code here
Sub Main()
    ' Code content
End Sub
</code>
        ]]></Content>
    </Example>
    ...
</Examples>
```

### Key Features

- **Relative URLs**: Preserved from Phase 7 directory structure
- **CDATA Wrapping**: All content wrapped in CDATA to preserve special characters
- **Code Blocks**: Code wrapped in `<code>` tags
- **Clean Formatting**: HTML tags stripped, whitespace normalized
- **Line Breaks**: Preserved from `<br>` tags and `<pre>` blocks

## Metadata Files

### parse_stats.json

```json
{
  "total_files": 1198,
  "successful": 1198,
  "failed": 0,
  "empty_content": 0
}
```

### manifest.json

```json
{
  "parser_version": "1.0.0",
  "input_directory": "07_crawl_examples/output/html",
  "output_file": "08_parse_examples/output/examples.xml",
  "total_examples": 1198
}
```

## Implementation Details

### HTML Parsing

The parser handles different HTML structures:

1. **`<p class="APICODE">`**: VBA-style code paragraphs
2. **`<pre>`**: Preformatted code blocks (preserves newlines)
3. **`<div>` with Monospace**: Container divs with code paragraphs

### Whitespace Normalization

- **Regular paragraphs**: Newlines collapsed to spaces
- **`<pre>` blocks**: Newlines preserved
- **`<br>` tags**: Converted to actual newlines
- **Multiple spaces**: Collapsed to single space
- **Trailing spaces**: Removed from each line

### Code Block Merging

- Multiple consecutive `<pre>` tags are merged into a single `<code>` block
- `<p class="APICODE">` paragraphs in the same `<div>` are merged
- Ensures continuous code examples stay together

## Validation

The validation script checks:

- ✅ XML file exists and is well-formed
- ✅ All examples have URLs and content
- ✅ No duplicate URLs
- ✅ Content is not empty or suspiciously short
- ✅ 100% coverage against Phase 7 HTML files
- ✅ Metadata files are present and valid

### Expected Results

```
Statistics:
  File size (bytes): 6,647,572
  Total examples: 1,198
  Empty content: 0
  Missing URLs: 0
  Missing content: 0
  Duplicate URLs: 0
  Short content: 0
  Source HTML files: 1,198
  Coverage (%): 100

[PASS] No issues found!
```

## Test Suite

Tests cover:

- Parser initialization
- HTML parsing (simple, complex, with `<br>` tags, with spans)
- Relative path extraction
- XML structure generation
- CDATA wrapping
- Whitespace normalization
- Error handling
- Metadata saving

Run tests with:

```bash
uv run pytest 08_parse_examples/tests/ -v
```

## Known Limitations

1. **HTML Entities**: Some special characters might not be perfectly preserved
2. **Complex Formatting**: Advanced HTML formatting is stripped
3. **Syntax Highlighting**: Color/style information is lost (intentional)
4. **Tables**: Not specially handled, extracted as plain text

## Performance

- **Processing Time**: ~10-20 seconds for 1,198 files
- **Memory Usage**: ~100-200 MB during parsing
- **Output Size**: ~6.6 MB XML file

## Troubleshooting

### Parser Issues

**Problem**: Double spaces in output
- **Cause**: HTML source has multiple space characters
- **Solution**: Already handled by regex cleanup

**Problem**: Missing line breaks in code
- **Cause**: File uses `<pre>` tags without explicit `<br>`
- **Solution**: Already handled by `preserve_newlines` parameter

**Problem**: Multiple code blocks for one example
- **Cause**: Multiple `<pre>` tags in HTML
- **Solution**: Already handled by pre-block merging logic

### Validation Errors

**Problem**: Coverage < 100%
- Check if Phase 7 completed successfully
- Verify HTML directory path is correct

**Problem**: Empty content warnings
- Some example pages may legitimately have minimal content
- Check specific files manually to verify

## Future Enhancements

Potential improvements for future phases:

1. **Language Detection**: Automatically detect code language (VB, C#, VBA, etc.)
2. **Code Syntax Validation**: Check if code is syntactically valid
3. **Cross-References**: Link examples to their API types from Phase 03
4. **Example Categorization**: Group examples by functionality or API area
5. **Search Index**: Build searchable index of example content

## Dependencies

- **BeautifulSoup4**: HTML parsing and tag extraction
- **xml.etree.ElementTree**: XML generation
- **pathlib**: File path handling
- **hashlib**: Content hashing for integrity checks

## Integration with Other Phases

### Inputs from Phase 7

- HTML files: `07_crawl_examples/output/html/**/*.htm`
- Used for: Example content source

### Outputs for Future Phases

- `output/examples.xml`: Structured example data for:
  - Phase 9+: Building searchable documentation
  - Phase 10+: Generating IntelliSense XML
  - Future: Example browser/search interface

## Copyright Notice

⚠️ **Important**: The example code content is copyrighted by Dassault Systèmes SolidWorks Corporation. This tool is for personal/educational use only. Do not redistribute the parsed content.

## License

This parsing tool (code only) is part of the offline-solidworks-api-docs project.
