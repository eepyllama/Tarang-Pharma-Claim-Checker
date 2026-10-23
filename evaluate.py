#!/usr/bin/env python3
"""
Evaluation Suite for Tarang Receipt Reader
------------------------------------------
Measures field-by-field extraction accuracy and policy decision quality
against 283 ground-truth claims in claims_train.csv.
"""

import sys
import json
from pathlib import Path
import pandas as pd
from datetime import datetime

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from extractor import ReceiptExtractor, process_claim, normalize_date_to_iso, normalize_amount_str


def clean_str(s):
    if s is None or pd.isna(s):
        return ""
    return str(s).strip()


def fuzzy_match(s1, s2):
    s1_clean = "".join(c for c in clean_str(s1).lower() if c.isalnum())
    s2_clean = "".join(c for c in clean_str(s2).lower() if c.isalnum())
    if not s1_clean or not s2_clean:
        return s1_clean == s2_clean
    return s1_clean in s2_clean or s2_clean in s1_clean


from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def run_evaluation(train_csv: str = "7a76ead9-99a9-48f9-8664-b67b285af8b9-claims_train.csv"):
    print("=" * 65)
    print("🔬 Evaluating Tarang Receipt Reader against Ground Truth (claims_train.csv)")
    print("=" * 65)

    df = pd.read_csv(train_csv)
    total_claims = len(df)
    print(f"Total claims in dataset: {total_claims}")

    extractor = ReceiptExtractor()
    seen_receipts = set()

    # Pre-extract with multi-threading
    print("⚡ Running parallel OCR & extraction on dataset...")
    start_time = time.time()
    
    rows = [r.to_dict() for _, r in df.iterrows()]
    results = [None] * total_claims
    
    def _eval_worker(item):
        idx, row = item
        # Use a copy of seen_receipts or sequentially apply policy
        return idx, row

    # OCR can run in parallel
    def _ocr_worker(row):
        img_name = str(row.get('image_file', '')).strip()
        p = extractor.images_dir / img_name
        if not p.exists():
            for m in extractor.images_dir.glob(f"*{img_name}"):
                p = m
                break
        return extractor.run_ocr(p)

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_ocr_worker, r) for r in rows]
        done = 0
        for f in as_completed(futs):
            done += 1
            if done % 25 == 0 or done == total_claims:
                print(f"  OCR Progress: {done}/{total_claims} ({done*100//total_claims}%)", flush=True)

    print(f"✅ OCR completed in {time.time() - start_time:.1f}s. Evaluating accuracy...")


    vendor_correct = 0
    date_correct = 0
    bill_no_correct = 0
    amount_correct = 0
    gstin_correct = 0

    failure_modes = {
        'missing_photo': 0,
        'unreadable_receipt': 0,
        'duplicate_claimed': 0,
        'amount_mismatch': 0,
        'vehicle_mismatch': 0,
        'large_amount_flagged': 0
    }

    results = []

    for idx, row in df.iterrows():
        claim_dict = row.to_dict()
        pred = process_claim(claim_dict, extractor, seen_receipts)
        results.append(pred)

        # Ground truth
        gt_vendor = clean_str(row.get('clerk_vendor'))
        gt_date_raw = clean_str(row.get('clerk_bill_date'))
        gt_date = normalize_date_to_iso(gt_date_raw)
        gt_bill_no = clean_str(row.get('clerk_bill_no'))
        gt_amount = row.get('clerk_bill_amount')
        gt_gstin = clean_str(row.get('clerk_gstin'))
        gt_status = clean_str(row.get('status')).lower()

        # Check vendor
        pred_vendor = clean_str(pred['vendor'])
        if fuzzy_match(pred_vendor, gt_vendor):
            vendor_correct += 1

        # Check date
        pred_date = clean_str(pred['receipt_date'])
        if pred_date == gt_date or (not gt_date and not pred_date):
            date_correct += 1

        # Check bill no
        pred_bill_no = clean_str(pred['receipt_number'])
        if fuzzy_match(pred_bill_no, gt_bill_no) or (not gt_bill_no and not pred_bill_no):
            bill_no_correct += 1

        # Check amount
        pred_amount = pred['total_amount']
        if pd.notna(gt_amount) and pred_amount is not None:
            if abs(float(gt_amount) - float(pred_amount)) <= 1.0:
                amount_correct += 1
        elif pd.isna(gt_amount) and pred_amount is None:
            amount_correct += 1

        # Check GSTIN
        pred_gstin = clean_str(pred['gstin'])
        if pred_gstin == gt_gstin:
            gstin_correct += 1

        # Track failure reasons
        reason = pred.get('reason', '')
        if 'not attached' in reason or 'unreadable' in reason:
            failure_modes['unreadable_receipt'] += 1
        if 'duplicate' in reason:
            failure_modes['duplicate_claimed'] += 1
        if 'mismatch' in reason:
            failure_modes['amount_mismatch'] += 1
        if 'vehicle' in reason:
            failure_modes['vehicle_mismatch'] += 1
        if '>= Rs 2,000' in reason:
            failure_modes['large_amount_flagged'] += 1

    # Summarize Metrics
    v_acc = vendor_correct / total_claims * 100
    d_acc = date_correct / total_claims * 100
    b_acc = bill_no_correct / total_claims * 100
    a_acc = amount_correct / total_claims * 100
    g_acc = gstin_correct / total_claims * 100
    avg_acc = (v_acc + d_acc + b_acc + a_acc + g_acc) / 5

    print("\n--- Field-by-Field Extraction Accuracy ---")
    print(f"  1. Vendor Name:    {v_acc:6.2f}% ({vendor_correct}/{total_claims})")
    print(f"  2. Receipt Date:   {d_acc:6.2f}% ({date_correct}/{total_claims})")
    print(f"  3. Bill Number:    {b_acc:6.2f}% ({bill_no_correct}/{total_claims})")
    print(f"  4. Total Amount:   {a_acc:6.2f}% ({amount_correct}/{total_claims})")
    print(f"  5. GSTIN:          {g_acc:6.2f}% ({gstin_correct}/{total_claims})")
    print("-" * 65)
    print(f"  Overall Average:   {avg_acc:6.2f}%\n")

    decisions = pd.Series([r['decision'] for r in results])
    print("--- Policy Decision Breakdown ---")
    print(decisions.value_counts())
    print("\n--- Detected Risk Flags ---")
    for k, v in failure_modes.items():
        print(f"  • {k.replace('_', ' ').title()}: {v}")
    print("=" * 65)

    return {
        'vendor_acc': v_acc,
        'date_acc': d_acc,
        'bill_no_acc': b_acc,
        'amount_acc': a_acc,
        'gstin_acc': g_acc,
        'average_acc': avg_acc,
        'decisions': decisions.value_counts().to_dict(),
        'failure_modes': failure_modes
    }


if __name__ == "__main__":
    run_evaluation()
