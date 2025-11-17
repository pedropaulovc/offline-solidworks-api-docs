# Phase 2: Extract Members

This phase extracts API member information (properties and methods) from the crawled HTML files and compiles them into an XML format.

## Overview

The extraction script scans all `*_members_*.html` files from the crawl phase and parses them to extract:
- Type/Interface names
- Public properties with their URLs
- Public methods with their URLs

## Usage

### Basic Extraction

```bash
uv run python 02_extract_members/extract_members.py
```

### With Custom Paths

```bash
uv run python 02_extract_members/extract_members.py \
  --input-dir 10_crawl_toc_pages/output/html \
  --output-dir 02_extract_members/metadata
```

### Verbose Mode

```bash
uv run python 02_extract_members/extract_members.py --verbose
```

## Output

The script generates two files in `02_extract_members/metadata/`:

### 1. api_members.xml

XML file containing all extracted type information:

```xml
<Types>
    <Type>
        <Name>IAnnotationView</Name>
        <Assembly>SolidWorks.Interop.sldworks</Assembly>
        <Namespace>SolidWorks.Interop.sldworks</Namespace>
        <PublicProperties>
            <Property>
                <Name>Always2D</Name>
                <Url>/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotationView~Always2D.html</Url>
            </Property>
            <!-- More properties -->
        </PublicProperties>
        <PublicMethods>
            <Method>
                <Name>Activate</Name>
                <Url>/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotationView~Activate.html</Url>
            </Method>
            <!-- More methods -->
        </PublicMethods>
    </Type>
</Types>
```

### 2. extraction_summary.json

Summary metadata about the extraction:

```json
{
  "total_files_processed": 458,
  "types_extracted": 456,
  "errors": 2,
  "output_file": "02_extract_members/metadata/api_members.xml",
  "error_files": [...]
}
```

## Architecture

### MemberExtractor Class

HTML parser that:
1. Extracts type name from page title
2. Identifies "Public Properties" and "Public Methods" sections
3. Parses table rows to extract member names and URLs
4. Builds structured data for each type

### Key Functions

- `extract_members_from_file()`: Process a single HTML file
- `create_xml_output()`: Generate formatted XML from extracted data
- `main()`: Orchestrate the extraction pipeline

## Dependencies

Uses only Python standard library:
- `html.parser`: HTML parsing
- `xml.etree.ElementTree`: XML generation
- `xml.dom.minidom`: Pretty-printing XML
- `pathlib`: File system operations
- `json`: Metadata storage

## Error Handling

- Skips files that can't be parsed
- Reports errors in summary JSON
- Continues processing remaining files
- Verbose mode shows detailed error information

## Testing

Run tests with:

```bash
uv run pytest 02_extract_members/tests/ -v
```

## Next Steps

This phase prepares data for:
- **Phase 3**: Generate XMLDoc for IntelliSense
- **Phase 4**: Build searchable offline index
- **Phase 5**: Export to various formats
