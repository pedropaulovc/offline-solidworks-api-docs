# CLAUDE.md - Project Context for AI Assistants

## Project Overview

This is a multi-phase pipeline project for creating offline, searchable versions of the SolidWorks API documentation. The project is designed with reproducibility, modularity, and copyright compliance as core principles.

## Current Status

✅ **Phase 1 (01-crawl-raw)**: Complete
- Scrapy-based crawler implemented
- Print preview URL conversion working
- Metadata tracking for reproducibility
- Validation scripts ready
- Test suite complete

⏳ **Future Phases**: Not yet implemented
- 02-extract-structure: Parse HTML to extract API structure
- 03-generate-xmldoc: Generate XMLDoc for IntelliSense
- 04-create-index: Build searchable offline index
- 05-export-formats: Export to various formats

## Key Technical Details

### Technology Stack
- **Python 3.12**: Primary language
- **uv**: Package management
- **Scrapy 2.13.3**: Web crawling framework
- **pytest**: Testing framework
- **jsonlines**: Metadata storage format

### Architecture Principles
1. **Modular Pipeline**: Each phase reads from previous, writes to next
2. **Reproducibility**: All transformations are deterministic
3. **Metadata-Driven**: Comprehensive tracking for validation
4. **Copyright Compliant**: HTML content gitignored, users crawl themselves

### Important URLs
- **Documentation Base**: `https://help.solidworks.com/2026/english/api/`
- **Starting Point**: `https://help.solidworks.com/2026/english/api/sldworksapiprogguide/Welcome.htm?id=0`
- **Print Preview Format**: Append `&format=p&value=1` to all URLs

## Development Guidelines

### When Adding New Features

1. **Maintain Reproducibility**: All outputs must be deterministic
2. **Test Coverage**: Aim for >80% test coverage
3. **Documentation**: Update relevant README files
4. **Validation**: Add validation checks for new functionality
5. **Copyright**: Never commit crawled HTML content

### Code Style
- Use type hints where possible
- Follow PEP 8 conventions
- Document complex logic with comments
- Write comprehensive docstrings

### Testing Philosophy
- Unit tests for individual components
- Integration tests for pipelines
- Regression tests for crawl completeness
- Mock external dependencies in tests

## Common Tasks

### Running a Test Crawl
```bash
uv run python 01-crawl-raw/run_crawler.py --test
```

### Validating Results
```bash
uv run python 01-crawl-raw/validate_crawl.py --verbose
```

### Running Tests
```bash
uv run pytest 01-crawl-raw/tests/ -v
```

## Project Constraints

### Legal/Ethical
- ⚠️ Crawled content is copyrighted by Dassault Systèmes
- 📚 For personal/educational use only
- 🚫 No redistribution of crawled content
- ⏱️ Respectful crawling (2-second delays)

### Technical
- Must stay within `/2026/english/api/` boundary
- Print preview format required for clean HTML
- Minimum 95% success rate for validation
- Expected ~458 pages from complete crawl

## Known Issues & Considerations

1. **Large HTML Files**: Some documentation pages are >500KB
2. **URL Parameters**: Print preview adds complexity to URL handling
3. **Session Management**: Currently stateless, may need cookies in future
4. **Version Updates**: URLs contain year (2026), needs updating annually

## Future Enhancement Ideas

### Phase 2: Extract Structure
- Parse HTML to extract classes, methods, properties
- Build hierarchical API model
- Extract code examples and remarks

### Phase 3: Generate XMLDoc
- Convert to Visual Studio IntelliSense format
- Maintain type information
- Include examples and documentation

### Phase 4: Search Index
- Build full-text search capability
- Create offline documentation browser
- Add cross-references and linking

### Phase 5: Export Formats
- Markdown for documentation sites
- JSON for programmatic access
- PDF for offline reading

## Debugging Tips

### If Crawl Fails
1. Check `output/metadata/errors.jsonl` for patterns
2. Verify user agent is set correctly
3. Test single URL with scrapy shell
4. Increase DOWNLOAD_DELAY if rate limited

### If Validation Fails
1. Run with `--verbose` flag
2. Check `validation_report_*.json` for details
3. Compare actual vs expected page counts
4. Verify URL boundaries are correct

## Environment Variables

Currently none required, but future phases might use:
- `SOLIDWORKS_API_VERSION`: Documentation version year
- `CRAWL_DELAY`: Override default delay
- `MAX_PAGES`: Limit for testing

## Dependencies to Note

### Why These Choices
- **Scrapy**: Best-in-class crawler with built-in features
- **jsonlines**: Append-only format perfect for streaming
- **uv**: Fast, modern Python package management
- **pytest**: Industry standard, great plugin ecosystem

## Performance Characteristics

- **Crawl Time**: ~3-4 hours for full documentation
- **Storage**: ~100-150 MB for HTML files
- **Memory**: ~200-500 MB during crawl
- **Network**: ~2 req/sec (limited by delay)

## File Naming Conventions

### Python Files
- Snake_case for modules: `api_docs_spider.py`
- PascalCase for classes: `HtmlSavePipeline`
- Descriptive names: `validate_crawl.py`

### Output Files
- Metadata: `{name}.json` or `{name}.jsonl`
- HTML: Preserves original name with hash for uniqueness
- Reports: `{type}_report_{timestamp}.json`

## Git Workflow

1. Main branch is `main`
2. Feature branches: `feature/description`
3. Commits: Descriptive messages explaining "why"
4. Never commit: HTML files, large binaries

## Support & Resources

- SolidWorks API Docs: https://help.solidworks.com/
- Scrapy Documentation: https://docs.scrapy.org/
- Python uv: https://github.com/astral-sh/uv

---

**Remember**: This project prioritizes reproducibility, modularity, and copyright compliance. When in doubt, favor these principles in your implementation decisions.
