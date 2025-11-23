# Phase 5: Extract Type Member Details

This phase extracts detailed information about type members (properties and methods) from crawled SolidWorks API documentation HTML files.

## Overview

**Input**: HTML files from Phase 3 (30_crawl_type_members/output/html)
**Output**: XML file containing member details (metadata/api_member_details.xml)
**Status**: Complete and tested

## What This Phase Does

This phase processes **member files** (format: `Assembly~Namespace.Type~Member.html`) and extracts:

1. **Member Name**: Property or method name (e.g., `AccessSelections`)
2. **Type**: Full type path (e.g., `SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData`)
3. **Assembly**: The .NET assembly containing the type
4. **Signature**: C# method/property signature without return type (e.g., `AccessSelections(System.object TopDoc, System.object Component)`)
5. **Description**: Brief description of what the member does
6. **Parameters**: List of parameters with descriptions (for methods)
7. **Returns**: Description of the return value (from "Return Value" or "Property Value" sections)
8. **Remarks**: Additional notes and cross-references

## Output Format

The extracted information is saved as XML in this format:

```xml
<Members>
    <Member>
        <Assembly>SolidWorks.Interop.sldworks</Assembly>
        <Type>SolidWorks.Interop.sldworks.IAdvancedHoleFeatureData</Type>
        <Name>AccessSelections</Name>
        <Signature>AccessSelections(System.object TopDoc, System.object Component)</Signature>
        <Description><![CDATA[Gains access to the selections used to define the Advanced Hole feature.]]></Description>
        <Parameters>
            <Parameter>
                <Name>TopDoc</Name>
                <Description><![CDATA[<see cref="SolidWorks.Interop.sldworks.IModelDoc2">IModelDoc2</see> for the part]]></Description>
            </Parameter>
            <Parameter>
                <Name>Component</Name>
                <Description><![CDATA[Null or Nothing]]></Description>
            </Parameter>
        </Parameters>
        <Returns><![CDATA[True if the selections are successfully accessed, false if not]]></Returns>
        <Remarks><![CDATA[This method puts the model into a rollback state...]]></Remarks>
    </Member>
    <!-- More members... -->
</Members>
```

## Usage

### Run Extraction

```bash
# Extract all member details
uv run python 50_extract_type_member_details/extract_member_details.py

# Extract with verbose output
uv run python 50_extract_type_member_details/extract_member_details.py --verbose

# Specify custom input/output directories
uv run python 50_extract_type_member_details/extract_member_details.py \
  --input-dir path/to/html \
  --output-dir path/to/output
```

### Validate Results

```bash
# Run validation checks
uv run python 50_extract_type_member_details/validate_extraction.py

# Validate with verbose output
uv run python 50_extract_type_member_details/validate_extraction.py --verbose
```

### Run Tests

```bash
# Run all tests
uv run pytest 50_extract_type_member_details/tests/ -v

# Run with coverage
uv run pytest 50_extract_type_member_details/tests/ --cov=50_extract_type_member_details
```

## Architecture

### Key Components

1. **MemberDetailsExtractor** (`extract_member_details.py`)
   - HTML parser that extracts member information
   - Handles signatures, parameters, return values, and remarks
   - Converts HTML links to XMLDoc format

2. **File Filtering** (`is_member_file()` in `shared/extraction_utils.py`)
   - Identifies member files (two `~` separators)
   - Excludes special files and member list pages

3. **Filename Extraction**
   - `extract_namespace_from_filename()`: Parses assembly and type from filename
   - `extract_member_name_from_filename()`: Extracts member name
   - Example: `Assembly~Namespace.Type~Member.html`

4. **XML Generation** (`create_xml_output()`)
   - Creates well-formed XML with proper CDATA escaping
   - Pretty-prints for readability
   - Uses shared utilities from `shared/extraction_utils.py`

### HTML Parsing Strategy

The parser uses Python's `HTMLParser` to:

1. **Detect page title** to extract member name and type
2. **Extract description** from text between title and first `<h1>`
3. **Parse C# signature** from the `.NET Syntax` section
4. **Collect parameters** from the `Parameters` section (dl/dt/dd structure)
5. **Extract return value** from the `Return Value` or `Property Value` section
6. **Parse remarks** while preserving HTML structure and cross-references

## Expected Results

From a full crawl of SolidWorks 2026 API documentation:

- **Total member files processed**: ~5,000-10,000
- **Members extracted**: ~5,000-10,000
- **Members with descriptions**: ~90%+
- **Members with signatures**: ~80%+
- **Members with parameters**: ~60%+
- **Members with return values**: ~50%+
- **Members with remarks**: ~30%+

## File Structure

```
50_extract_type_member_details/
├── extract_member_details.py      # Main extraction script
├── validate_extraction.py         # Validation script
├── README.md                       # This file
├── metadata/                       # Output directory
│   ├── api_member_details.xml     # Extracted member information
│   └── extraction_summary.json    # Extraction statistics
└── tests/                          # Unit tests
    ├── __init__.py
    └── test_extract_member_details.py
```

## Error Handling

The extraction process is designed to be robust:

- **Missing fields**: Members without certain fields are still included
- **HTML parsing errors**: Logged and counted in the summary
- **Invalid filenames**: Skipped with warning messages
- **Malformed HTML**: Parser continues with best effort

## Validation Checks

The validation script checks:

- XML is well-formed and parseable
- All required fields are present (Assembly, Type, Name)
- Member count matches summary metadata
- No duplicate members (warning only)
- Reasonable percentage of members have descriptions/parameters/returns

## Shared Code Refactoring

This phase leverages shared utilities from `shared/extraction_utils.py`:

- `extract_namespace_from_filename()`: Parse assembly/namespace/type from filename
- `extract_member_name_from_filename()`: Extract member name
- `is_member_file()`: Identify member files
- `prettify_xml()`: Format XML with CDATA sections
- `wrap_cdata_sections()`: Wrap content in CDATA

These utilities are also used by Phase 04 (Extract Type Details).

## Known Limitations

1. **Signature extraction**: Only C# signatures are extracted (VB.NET/C++ ignored), and return type is excluded
2. **Parameter types**: Included in signature with parameter names (full C# syntax)
3. **Empty parameter descriptions**: Some parameters have no description in source docs
4. **Link conversion**: Basic conversion to XMLDoc format, may miss some patterns

## Next Steps

This phase provides the foundation for:

- **Phase 09**: Merging member details with type info and generating XMLDoc files
- **Future phases**: Creating searchable offline documentation

## Troubleshooting

### No members extracted

Check that:
- Input directory contains HTML files from Phase 3
- Files follow the naming pattern: `Assembly~Namespace.Type~Member.html`
- Files have two `~` separators (not one like type files)

### Missing descriptions or parameters

This is normal - not all members have complete documentation. Run validation to see percentage coverage.

### Validation fails

Check the validation output for specific issues. Most common:
- XML file doesn't exist (run extraction first)
- Member count mismatch (indicates parsing errors)

## Dependencies

- Python 3.12+
- Standard library only (no external dependencies)
  - `html.parser`: HTML parsing
  - `xml.etree.ElementTree`: XML generation
  - `xml.dom.minidom`: XML pretty-printing
- Shared modules:
  - `shared/extraction_utils.py`: Common extraction utilities
  - `shared/xmldoc_links.py`: Link conversion utilities

## Performance

- **Processing time**: ~1-2 minutes for 5,000-10,000 files
- **Memory usage**: <200 MB
- **Output size**: ~10-20 MB XML file

---

**Remember**: This phase focuses on **member-level** documentation. For type-level information, see Phase 04 (Extract Type Details).
