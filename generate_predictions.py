#!/usr/bin/env python3
"""
Generate predictions.csv for Tarang Pharma Distribution
-------------------------------------------------------
Runs the extraction and policy engine on all 190 claims in claims_test.csv
and outputs predictions.csv strictly formatted to sample_submission.csv specifications.
"""

import sys
import os
import time
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from extractor import ReceiptExtractor, process_claim, normalize_date_to_iso, normalize_amount_str


def generate_predictions(
    test_csv_path: str = "af4bfb61-f3ed-46b6-8be2-c50ae3cf348d-claims_test.csv",
    output_csv_path: str = "predictions.csv"
):
    print("=" * 65)
    print("🚀 Generating predictions.csv for claims_test.csv")
    print("=" * 65)

    test_df = pd.read_csv(test_csv_path)
    total_claims = len(test_df)
    print(f"Loaded {total_claims} test claims from {test_csv_path}")

    extractor = ReceiptExtractor()
    seen_receipts = set()
    predictions = []

    start_time = time.time()
    for idx, row in test_df.iterrows():
        claim_dict = row.to_dict()
        pred = process_claim(claim_dict, extractor, seen_receipts)
        
        # Ensure clean formatting
        tot_amt = pred['total_amount']
        if tot_amt is not None:
            # Format nicely as integer or float without scientific notation
            tot_amt_str = f"{tot_amt:.2f}".rstrip('0').rstrip('.')
        else:
            tot_amt_str = ""

        row_pred = {
            'claim_id': str(pred['claim_id']).strip(),
            'vendor': str(pred['vendor']).strip() if pred['vendor'] else "",
            'receipt_date': str(pred['receipt_date']).strip() if pred['receipt_date'] else "",
            'receipt_number': str(pred['receipt_number']).strip() if pred['receipt_number'] else "",
            'gstin': str(pred['gstin']).strip() if pred['gstin'] else "",
            'total_amount': tot_amt_str,
            'decision': str(pred['decision']).strip().lower(),
            'reason': str(pred['reason']).strip()
        }
        predictions.append(row_pred)
        
        if (idx + 1) % 10 == 0 or (idx + 1) == total_claims:
            elapsed = time.time() - start_time
            print(f"  Processed {idx + 1}/{total_claims} claims ({elapsed:.1f}s)", flush=True)

    pred_df = pd.DataFrame(predictions)
    # Ensure column ordering matches sample_submission.csv
    expected_cols = ['claim_id', 'vendor', 'receipt_date', 'receipt_number', 'gstin', 'total_amount', 'decision', 'reason']
    pred_df = pred_df[expected_cols]

    pred_df.to_csv(output_csv_path, index=False)
    print(f"\n🎉 predictions.csv successfully generated at: {Path(output_csv_path).resolve()}")
    print("\n--- Summary of Generated Predictions ---")
    print(f"Total claims: {len(pred_df)}")
    print("Decisions breakdown:")
    print(pred_df['decision'].value_counts())
    print("\nSample preview (first 5 rows):")
    print(pred_df.head(5).to_string())
    print("=" * 65)


if __name__ == "__main__":
    generate_predictions()
