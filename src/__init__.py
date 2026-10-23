"""
Tarang Expense Automation - Core Package
"""

from .config import settings, get_project_paths
from .extractor import ReceiptExtractor
from .rules import evaluate_expense_policy
from .pipeline import ExpensePipeline

__all__ = [
    "settings",
    "get_project_paths",
    "ReceiptExtractor",
    "evaluate_expense_policy",
    "ExpensePipeline"
]
