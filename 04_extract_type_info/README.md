# Phase 3: Extract Type Information

This phase extracts type-level information (descriptions, examples, and remarks) from crawled SolidWorks API documentation HTML files.

## Overview

**Input**: HTML files from Phase 1 (01_crawl_toc_pages/output/html)
**Output**: XML file containing type information (metadata/api_types.xml)
**Status**: Complete and tested

## What This Phase Does

This phase processes **type files** (excluding `*_members_*` and `*_namespace_*` files) and extracts:

1. **Type Name**: Interface or class name (e.g., `IAdvancedHoleFeatureData`)
2. **Assembly**: The .NET assembly containing the type
3. **Namespace**: The .NET namespace containing the type
4. **Description**: Brief description of what the type does
5. **Examples**: Code examples with language and URL references
6. **Remarks**: Additional notes and cross-references

## Output Format

The extracted information is saved as XML in this format:

```xml
<Types>
    <Type>
        <Name>IAdvancedHoleFeatureData</Name>
        <Assembly>SolidWorks.Interop.sldworks</Assembly>
        <Namespace>SolidWorks.Interop.sldworks</Namespace>
        <Description>Allows access to the Advanced Hole feature data.</Description>
        <Examples>
            <Example>
                <Name>Create Advanced Hole Feature</Name>
                <Language>VBA</Language>
                <Url>/sldworksapi/Create_Advanced_Hole_Example_VB.htm</Url>
            </Example>
            <Example>
                <Name>Create Advanced Hole Feature</Name>
                <Language>VB.NET</Language>
                <Url>/sldworksapi/Create_Advanced_Hole_Example_VBNET.htm</Url>
            </Example>
            <Example>
                <Name>Create Advanced Hole Feature</Name>
                <Language>C#</Language>
                <Url>/sldworksapi/Create_Advanced_Hole_Example_CSharp.htm</Url>
            </Example>
        </Examples>
        <Remarks>To create an Advanced Hole feature, see the IFeatureManager.AdvancedHole Remarks.</Remarks>
    </Type>
    <!-- More types... -->
</Types>
```

## Usage

### Run Extraction

```bash
# Extract all type information
uv run python 03_extract_type_info/extract_type_info.py

# Extract with verbose output
uv run python 03_extract_type_info/extract_type_info.py --verbose

# Specify custom input/output directories
uv run python 03_extract_type_info/extract_type_info.py \
  --input-dir path/to/html \
  --output-dir path/to/output
```

### Validate Results

```bash
# Run validation checks
uv run python 03_extract_type_info/validate_extraction.py

# Validate with verbose output
uv run python 03_extract_type_info/validate_extraction.py --verbose
```

### Run Tests

```bash
# Run all tests
uv run pytest 03_extract_type_info/tests/ -v

# Run with coverage
uv run pytest 03_extract_type_info/tests/ --cov=03-extract-type-info
```

## Architecture

### Key Components

1. **TypeInfoExtractor** (`extract_type_info.py`)
   - HTML parser that extracts type information
   - Handles description, examples, and remarks sections
   - Converts HTML links to cleaned text

2. **File Filtering** (`is_type_file()`)
   - Identifies type files vs. members/namespace files
   - Excludes special files (help_list, FunctionalCategories, etc.)

3. **Namespace Extraction** (`extract_namespace_from_filename()`)
   - Parses assembly and namespace from filename pattern
   - Example: `SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITypeName_hash.html`

4. **XML Generation** (`create_xml_output()`)
   - Creates well-formed XML with proper escaping
   - Pretty-prints for readability

### HTML Parsing Strategy

The parser uses Python's `HTMLParser` to:

1. **Detect sections** by looking for `<h1>` tags (Example, Remarks, etc.)
2. **Collect content** within each section until the next section
3. **Extract links** in the Examples section with language detection
4. **Clean remarks** by removing excess HTML while preserving cross-references

## Expected Results

From a full crawl of SolidWorks 2026 API documentation:

- **Total type files processed**: ~1674
- **Types extracted**: ~1674
- **Types with descriptions**: ~1568 (93%)
- **Types with examples**: ~561 (33%)
- **Total examples**: ~3708
- **Types with remarks**: ~455 (27%)

## File Structure

```
03_extract_type_info/
├── extract_type_info.py      # Main extraction script
├── validate_extraction.py    # Validation script
├── README.md                  # This file
├── metadata/                  # Output directory
│   ├── api_types.xml          # Extracted type information
│   └── extraction_summary.json # Extraction statistics
└── tests/                     # Unit tests
    ├── __init__.py
    └── test_extract_type_info.py
```

## Error Handling

The extraction process is designed to be robust:

- **Missing fields**: Types without certain fields are still included
- **HTML parsing errors**: Logged and counted in the summary
- **Invalid filenames**: Skipped with warning messages
- **Malformed HTML**: Parser continues with best effort

## Validation Checks

The validation script checks:

- XML is well-formed and parseable
- All required fields are present (Name, Assembly, Namespace)
- Type count matches summary metadata
- No duplicate type names (warning only)
- Reasonable percentage of types have descriptions/examples

## Known Limitations

1. **Remarks formatting**: Currently simplified - HTML is mostly stripped
2. **Cross-references**: Link conversion is basic, may miss some patterns
3. **Language detection**: Inferred from filename, may not be 100% accurate
4. **No deduplication**: Some types may have multiple HTML files (different versions)

## Next Steps

This phase provides the foundation for:

- **Phase 4**: Merging type info with member info from Phase 2
- **Phase 5**: Generating XMLDoc/IntelliSense files
- **Phase 6**: Creating searchable offline documentation

## Troubleshooting

### No types extracted

Check that:
- Input directory contains HTML files from Phase 1
- Files follow the naming pattern: `Assembly~Namespace.Type_hash.html`
- Files don't contain `_members_` or `_namespace_` in the name

### Missing descriptions or examples

This is normal - not all types have examples or detailed remarks. Run validation to see percentage coverage.

### Validation fails

Check the validation output for specific issues. Most common:
- XML file doesn't exist (run extraction first)
- Type count mismatch (indicates parsing errors)

## Dependencies

- Python 3.12+
- Standard library only (no external dependencies)
  - `html.parser`: HTML parsing
  - `xml.etree.ElementTree`: XML generation
  - `xml.dom.minidom`: XML pretty-printing

## Performance

- **Processing time**: ~30 seconds for 1674 files
- **Memory usage**: <100 MB
- **Output size**: ~5 MB XML file

---

**Remember**: This phase focuses on **type-level** documentation. For member-level information (properties and methods), see Phase 2 (02_extract_members).
