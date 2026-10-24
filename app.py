#!/usr/bin/env python3
"""
Main Application Launcher for Tarang Pharma Expense Receipt Reader & Audit Engine
--------------------------------------------------------------------------------
Prints the Executive Memorandum to Nilesh Agrawal in the terminal and launches
the FastAPI review & audit server at http://localhost:8000.

Usage:
  python app.py
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.memo_printer import print_executive_memo

def main():
    # 1. Print formatted Executive Memo to terminal
    print_executive_memo()

    # 2. Start FastAPI Server
    import uvicorn
    print("\n" + "=" * 80)
    print("  [INFO] Launching Tarang Receipt Reader & Audit Engine on http://localhost:8000")
    print("  [INFO] Press Ctrl+C to stop the server.")
    print("=" * 80 + "\n")

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
