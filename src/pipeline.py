"""
Expense Processing Pipeline
---------------------------
Glues together the extraction and policy evaluation engines
for single-claim audit, batch predictions generation, and evaluation benchmarking.
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, Set, List
import pandas as pd

from .config import settings
from .extractor import ReceiptExtractor, normalize_date_to_iso
from .rules import evaluate_expense_policy, normalize_amount, load_employee_directory


class ExpensePipeline:
    def __init__(self):
        self.extractor = ReceiptExtractor()
        self.employees = load_employee_directory()

    def process_claim(
        self,
        claim_dict: Dict[str, Any],
        image_path: Optional[Path] = None,
        seen_receipts: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """Processes a single expense claim and receipt."""
        if seen_receipts is None:
            seen_receipts = set()

        if image_path is None:
            img_file = claim_dict.get('image_file')
            image_path = settings.resolve_image_path(img_file) if img_file else None

        # 1. Field extraction
        extracted = self.extractor.extract_fields(image_path, claim_dict)

        # 2. Policy evaluation
        decision, reason, policy_rules = evaluate_expense_policy(
            extracted, claim_dict, seen_receipts, self.employees
        )

        return {
            'claim_id': str(claim_dict.get('claim_id', '')).strip(),
            'vendor': str(extracted.get('vendor') or claim_dict.get('vendor', '')).strip(),
            'receipt_date': str(extracted.get('receipt_date') or normalize_date_to_iso(str(claim_dict.get('expense_date', '')))).strip(),
            'receipt_number': str(extracted.get('receipt_number') or "").strip(),
            'gstin': str(extracted.get('gstin') or "").strip(),
            'total_amount': extracted.get('total_amount'),
            'decision': decision,
            'reason': reason,
            'policy_rules': policy_rules,
            'confidence': round(extracted.get('ocr_confidence', 0.85) * 100, 1),
            'ocr_lines_count': len(extracted.get('ocr_lines', [])),
            'image_path': str(image_path) if image_path else None
        }

    def generate_predictions_csv(
        self,
        test_csv: Optional[Path] = None,
        output_csv: Optional[Path] = None
    ) -> pd.DataFrame:
        """Processes all test claims and outputs predictions.csv strictly formatted to sample_submission."""
        if test_csv is None:
            test_csv = settings.resolve_raw_file("claims_test.csv")
        if output_csv is None:
            output_csv = settings.PROJECT_ROOT / "predictions.csv"

        df_test = pd.read_csv(test_csv)
        total = len(df_test)
        print(f"Generating predictions for {total} claims from {test_csv}...")

        seen_receipts = set()
        predictions = []

        start_time = time.time()
        for idx, row in df_test.iterrows():
            claim_info = row.to_dict()
            res = self.process_claim(claim_info, seen_receipts=seen_receipts)
            
            tot_amt = res['total_amount']
            tot_amt_str = f"{tot_amt:.2f}".rstrip('0').rstrip('.') if tot_amt is not None else ""

            predictions.append({
                'claim_id': res['claim_id'],
                'vendor': res['vendor'],
                'receipt_date': res['receipt_date'],
                'receipt_number': res['receipt_number'],
                'gstin': res['gstin'],
                'total_amount': tot_amt_str,
                'decision': res['decision'],
                'reason': res['reason']
            })

        pred_df = pd.DataFrame(predictions)
        expected_cols = ['claim_id', 'vendor', 'receipt_date', 'receipt_number', 'gstin', 'total_amount', 'decision', 'reason']
        pred_df = pred_df[expected_cols]

        pred_df.to_csv(output_csv, index=False)
        print(f"Predictions successfully written to {output_csv} in {time.time() - start_time:.1f}s")
        return pred_df
