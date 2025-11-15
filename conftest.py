"""
Pytest configuration for multi-phase project.

Each phase directory (01-crawl-toc-pages, 02-extract-members, etc.)
needs to be added to the Python path so tests can import their modules.
"""

import sys
from pathlib import Path

# Add each phase directory to Python path
project_root = Path(__file__).parent
phase_dirs = [
    "01-crawl-toc-pages",
    "02-extract-members",
    "03-extract-type-info",
    "04-extract-enum-members",
    "shared",
]

for phase_dir in phase_dirs:
    phase_path = project_root / phase_dir
    if phase_path.exists():
        sys.path.insert(0, str(phase_path))
