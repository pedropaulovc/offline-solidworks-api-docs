# Shared Utilities

This directory contains shared utility modules used across multiple phases of the SolidWorks API documentation pipeline.

## Modules

### `xmldoc_links.py`

Utilities for converting HTML anchor tags to XMLDoc format for IntelliSense documentation.

**Functions:**

- `convert_links_to_see_refs(html: str) -> str`
  Converts HTML `<a>` tags to XMLDoc `<see cref>` or `<see href>` tags
  - Type references → `<see cref="Namespace.Type.Member">text</see>`
  - Guide pages → `<see href="url">text</see>`

- `parse_href_to_cref(href: str) -> Optional[str]`
  Extracts cref value from type reference URLs
  - Returns `None` for non-type references (guide pages)

- `convert_to_full_url(href: str) -> str`
  Converts relative URLs to full SolidWorks API documentation URLs

**Usage:**

```python
from shared.xmldoc_links import convert_links_to_see_refs

html = '<a href="SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature.html">IFeature</a>'
result = convert_links_to_see_refs(html)
# Returns: '<see cref="SolidWorks.Interop.sldworks.IFeature">IFeature</see>'
```

**Testing:**

```bash
uv run pytest shared/tests/ -v
```

## Design Principles

- **Stateless**: All functions are pure and don't rely on global state
- **Reusable**: Can be imported by any phase of the pipeline
- **Well-tested**: Comprehensive unit tests for all functionality
- **Documented**: Clear docstrings and examples

## Adding New Shared Modules

When adding new shared utilities:

1. Create the module in `shared/`
2. Add comprehensive unit tests in `shared/tests/`
3. Update this README with documentation
4. Ensure all tests pass before committing
