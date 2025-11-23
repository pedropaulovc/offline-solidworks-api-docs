"""Test configuration for examples crawler tests"""

import sys
from pathlib import Path

# Add the parent directory to sys.path so we can import solidworks_scraper
test_dir = Path(__file__).parent
phase_dir = test_dir.parent
sys.path.insert(0, str(phase_dir))
