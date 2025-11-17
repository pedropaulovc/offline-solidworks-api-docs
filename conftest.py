"""
Pytest configuration for multi-phase project.

Each phase directory (10_crawl_toc_pages, 20_extract_types, etc.)
needs to be added to the Python path so tests can import their modules.
"""

import sys
from pathlib import Path

# Add each phase directory to Python path
project_root = Path(__file__).parent
phase_dirs = [
    "10_crawl_toc_pages",
    "20_extract_types",
    "30_crawl_type_members",
    "40_extract_type_details",
    "50_extract_type_member_details",
    "60_extract_enum_members",
    "70_crawl_examples",
    "80_parse_examples",
    "90_generate_xmldoc",
    "100_crawl_programming_guide",
    "110_extract_docs_md",
    "shared",
]

for phase_dir in phase_dirs:
    phase_path = project_root / phase_dir
    if phase_path.exists():
        sys.path.insert(0, str(phase_path))
