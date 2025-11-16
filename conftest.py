"""
Pytest configuration for multi-phase project.

Each phase directory (01_crawl_toc_pages, 02_extract_types, etc.)
needs to be added to the Python path so tests can import their modules.
"""

import sys
from pathlib import Path

# Add each phase directory to Python path
project_root = Path(__file__).parent
phase_dirs = [
    "01_crawl_toc_pages",
    "02_extract_types",
    "03_crawl_type_members",
    "04_extract_type_details",
    "06_extract_enum_members",
    "07_crawl_examples",
    "08_parse_examples",
    "09_generate_xmldoc",
    "shared",
]

for phase_dir in phase_dirs:
    phase_path = project_root / phase_dir
    if phase_path.exists():
        sys.path.insert(0, str(phase_path))
