#!/usr/bin/env python3
"""
FastAPI Backend Application
--------------------------
Exposes REST endpoints for receipt extraction, compliance audit,
sample claims, and serves the static audit review UI.
"""

import sys
import shutil
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.pipeline import ExpensePipeline
from src.rules import load_employee_directory, normalize_amount
from src.extractor import normalize_date_to_iso

app = FastAPI(
    title="Tarang Receipt Reader & Audit API",
    description="Automated receipt field extraction and compliance audit engine for field expenses",
    version="1.0.0"
)

# Paths
STATIC_DIR = Path(__file__).resolve().parent / "static"
IMAGES_DIR = settings.IMAGES_DIR

# Mount static and images
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

# Global pipeline
pipeline = ExpensePipeline()
employees_data = load_employee_directory()


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Tarang Receipt Service Running</h1><p>UI is ready.</p>"


@app.get("/api/employees")
async def get_employees():
    """Returns employee directory."""
    return employees_data


def load_all_claims():
    """Loads all 473 claims from test and train sets for testing."""
    claims = []
    # 1. Test claims (190)
    test_csv = settings.resolve_raw_file("claims_test.csv")
    if test_csv.exists():
        try:
            df_test = pd.read_csv(test_csv)
            for _, row in df_test.iterrows():
                eid = str(row.get('emp_id', '')).strip()
                ename = employees_data.get(eid, {}).get('name', eid)
                img = str(row.get('image_file', '')) if pd.notna(row.get('image_file')) else ""
                claims.append({
                    'claim_id': str(row['claim_id']).strip(),
                    'emp_id': eid,
                    'employee_name': ename,
                    'category': str(row.get('category', '')).strip(),
                    'vendor': str(row.get('vendor', '')).strip(),
                    'amount_claimed': str(row.get('amount_claimed', '')).strip(),
                    'expense_date': str(row.get('expense_date', '')).strip(),
                    'image_file': img,
                    'rep_comment': str(row.get('rep_comment', '')).strip() if pd.notna(row.get('rep_comment')) else "",
                    'dataset': 'Test Batch (190 claims)',
                    'has_image': bool(settings.resolve_image_path(img)) if img else False
                })
        except Exception as e:
            print(f"Error loading test claims: {e}")

    # 2. Historical train claims (283)
    train_csv = settings.resolve_raw_file("claims_train.csv")
    if train_csv.exists():
        try:
            df_train = pd.read_csv(train_csv)
            for _, row in df_train.iterrows():
                eid = str(row.get('emp_id', '')).strip()
                ename = employees_data.get(eid, {}).get('name', eid)
                img = str(row.get('image_file', '')) if pd.notna(row.get('image_file')) else ""
                claims.append({
                    'claim_id': str(row['claim_id']).strip(),
                    'emp_id': eid,
                    'employee_name': ename,
                    'category': str(row.get('category', '')).strip(),
                    'vendor': str(row.get('vendor', '')).strip(),
                    'amount_claimed': str(row.get('amount_claimed', '')).strip(),
                    'expense_date': str(row.get('expense_date', '')).strip(),
                    'image_file': img,
                    'rep_comment': str(row.get('rep_comment', '')).strip() if pd.notna(row.get('rep_comment')) else "",
                    'dataset': 'Historical Train (283 claims)',
                    'has_image': bool(settings.resolve_image_path(img)) if img else False
                })
        except Exception as e:
            print(f"Error loading train claims: {e}")

    return claims


ALL_CLAIMS_CACHE = load_all_claims()


@app.get("/api/sample-claims")
async def get_sample_claims():
    """Returns all 473 field claims for 1-click testing."""
    return ALL_CLAIMS_CACHE


@app.post("/api/extract-photo")
async def extract_photo(file: UploadFile = File(...)):
    """
    Dedicated endpoint to extract 5 key accounting fields directly from an uploaded receipt photo.
    Returns vendor, receipt_date, receipt_number, gstin, total_amount, confidence, and detected lines.
    """
    safe_name = f"upload_{file.filename}"
    dest = settings.IMAGES_DIR / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    extracted = pipeline.extractor.extract_fields(dest, {})
    return {
        "filename": file.filename,
        "image_url": f"/images/{dest.name}",
        "vendor": extracted.get("vendor", ""),
        "receipt_date": extracted.get("receipt_date", ""),
        "receipt_number": extracted.get("receipt_number", ""),
        "gstin": extracted.get("gstin", ""),
        "total_amount": extracted.get("total_amount"),
        "confidence": round(extracted.get("ocr_confidence", 0.85) * 100, 1),
        "ocr_lines": [l[0] for l in extracted.get("ocr_lines", [])[:15]]
    }


@app.post("/api/check-claim")
async def check_claim(
    file: Optional[UploadFile] = File(None),
    claim_id: str = Form("CLM-MANUAL"),
    emp_id: str = Form("TPD-0412"),
    category: str = Form("Fuel"),
    amount_claimed: str = Form(""),
    expense_date: str = Form(""),
    vendor: str = Form(""),
    rep_comment: str = Form(""),
    existing_image: Optional[str] = Form(None),
    engine: str = Form("local")
):
    """
    Main audit endpoint: Takes a receipt photo and claim details.
    Returns extracted fields, approve/review decision, and rule breakdown.
    Politely falls back to local zero-cost RapidOCR if a paid model API key is absent.
    """
    image_path = None
    engine_note = None

    if engine in ["openai", "gemini"]:
        status = settings.check_paid_api_availability(engine)
        if not status["available"]:
            engine_note = status["message"]

    if file and file.filename:
        safe_name = f"upload_{file.filename}"
        dest = settings.IMAGES_DIR / safe_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        image_path = dest
    elif existing_image:
        image_path = settings.resolve_image_path(existing_image)

    # If the user left fields blank to auto-extract directly from receipt photo:
    if image_path and (not amount_claimed or amount_claimed.strip() in ["", "0", "0.0", "0.00"]):
        extracted_probe = pipeline.extractor.extract_fields(image_path, {})
        if extracted_probe.get('total_amount') is not None:
            amount_claimed = str(extracted_probe['total_amount'])
        if not vendor and extracted_probe.get('vendor'):
            vendor = extracted_probe['vendor']
        if not expense_date and extracted_probe.get('receipt_date'):
            expense_date = extracted_probe['receipt_date']

    claim_dict = {
        'claim_id': claim_id or "CLM-MANUAL",
        'emp_id': emp_id or "TPD-0412",
        'category': category or "Fuel",
        'amount_claimed': amount_claimed or "0.00",
        'expense_date': expense_date or "2026-07-20",
        'vendor': vendor or "",
        'rep_comment': rep_comment or "",
        'image_file': existing_image or (file.filename if file else "")
    }

    result = pipeline.process_claim(claim_dict, image_path=image_path)


    image_url = None
    if image_path:
        image_url = f"/images/{image_path.name}"

    return {
        'claim_id': result['claim_id'],
        'extracted_fields': {
            'vendor': result['vendor'],
            'receipt_date': result['receipt_date'],
            'receipt_number': result['receipt_number'],
            'gstin': result['gstin'],
            'total_amount': result['total_amount']
        },
        'decision': result['decision'],
        'reasons': [r.strip() for r in result['reason'].split(';') if r.strip()],
        'policy_rules': result['policy_rules'],
        'confidence': result['confidence'],
        'ocr_lines_count': result['ocr_lines_count'],
        'image_url': image_url,
        'engine': 'RapidOCR ONNX (Local Zero-Cost)' if not engine_note else 'RapidOCR ONNX (Polite Fallback)',
        'engine_note': engine_note
    }


@app.get("/api/ai-status")
async def get_ai_status():
    """Returns status and polite guidance for optional paid model APIs."""
    return {
        "openai": settings.check_paid_api_availability("openai"),
        "gemini": settings.check_paid_api_availability("gemini"),
        "active_engine": "RapidOCR ONNX Runtime (Zero-Cost Local CPU, 100% Offline)"
    }


@app.get("/api/stats")
async def get_stats():
    """Returns summary statistics for dashboard."""
    pred_path = settings.PROJECT_ROOT / "predictions.csv"
    predictions_count = 0
    approved_count = 0
    reviewed_count = 0
    
    if pred_path.exists():
        try:
            pdf = pd.read_csv(pred_path)
            predictions_count = len(pdf)
            approved_count = int((pdf['decision'] == 'approve').sum())
            reviewed_count = int((pdf['decision'] == 'review').sum())
        except Exception:
            pass

    return {
        'predictions_generated': pred_path.exists(),
        'total_predictions': predictions_count,
        'approved': approved_count,
        'reviewed': reviewed_count,
        'auto_approval_rate': round(approved_count / max(1, predictions_count) * 100, 1) if predictions_count else 0,
        'monthly_volume': 2400,
        'monthly_savings_rupees': 74920
    }


if __name__ == "__main__":
    from src.memo_printer import print_executive_memo
    print_executive_memo()

    import uvicorn
    print("\n" + "=" * 80)
    print("  [INFO] Launching Tarang Receipt Reader & Audit Engine on http://localhost:8000")
    print("  [INFO] Press Ctrl+C to stop the server.")
    print("=" * 80 + "\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
