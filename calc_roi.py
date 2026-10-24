#!/usr/bin/env python3
"""
CLI runner for Tarang Pharma ROI & Financial Arithmetic Calculations
--------------------------------------------------------------------
Usage:
  python calc_roi.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.roi_calculator import print_roi_breakdown

if __name__ == "__main__":
    print_roi_breakdown()
