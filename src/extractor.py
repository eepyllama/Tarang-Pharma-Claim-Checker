"""
Receipt Information Extraction Engine
------------------------------------
Extracts 5 key accounting fields from receipt images:
  1. vendor
  2. receipt_date (YYYY-MM-DD)
  3. receipt_number
  4. gstin
  5. total_amount
Uses RapidOCR ONNX runtime as the zero-cost local engine,
with optional plug-and-play multimodal Vision LLM augmentation.
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd

from .config import settings

# Initialize RapidOCR engine
from rapidocr_onnxruntime import RapidOCR
_local_ocr = RapidOCR()

GSTIN_REGEX = re.compile(r'\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b')

DATE_PATTERNS = [
    (re.compile(r'\b(202[4-7])[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12][0-9]|3[01])\b'), '%Y-%m-%d'),
    (re.compile(r'\b(0[1-9]|[12][0-9]|3[01])[-/.](0[1-9]|1[0-2])[-/.](202[4-7])\b'), '%d-%m-%Y'),
    (re.compile(r'\b(0[1-9]|[12][0-9]|3[01])[-/.](0[1-9]|1[0-2])[-/.](2[4-7])\b'), '%d-%m-%y'),
]


def normalize_date_to_iso(date_str: str) -> Optional[str]:
    """Standardizes date strings to YYYY-MM-DD."""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip().replace('/', '-').replace('.', '-')
    
    m = re.match(r'^(\d{2})-(\d{2})-(\d{4})$', date_str)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d}"
    
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
    if m:
        return date_str

    m = re.match(r'^(\d{2})-(\d{2})-(\d{2})$', date_str)
    if m:
        d, mo, y = m.groups()
        return f"20{y}-{mo}-{d}"

    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d-%m-%y', '%d %b %Y', '%d %B %Y', '%d-%b-%Y'):
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return None


class ReceiptExtractor:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or settings.CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)

    def run_ocr(self, image_path: Path) -> List[Tuple[str, float]]:
        """Runs OCR with smart downscaling and file-level caching."""
        if not image_path or not image_path.exists():
            return []

        cache_file = self.cache_dir / f"{image_path.stem}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return [(item[0], float(item[1])) for item in json.load(f)]
            except Exception:
                pass

        try:
            import cv2
            img = cv2.imread(str(image_path))
            if img is None:
                return []
            h, w = img.shape[:2]
            max_dim = 1000
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            results, _ = _local_ocr(img)
            if not results:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump([], f)
                return []

            lines = []
            for item in results:
                text = str(item[1]).strip()
                score = float(item[2]) if len(item) > 2 else 0.8
                if text:
                    lines.append((text, score))

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(lines, f)
            return lines
        except Exception as e:
            print(f"OCR execution error on {image_path}: {e}")
            return []

    def extract_fields(self, image_path: Optional[Path], claim_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts the 5 core accounting fields from receipt image."""
        ocr_lines = self.run_ocr(image_path) if image_path else []
        all_text = " ".join([l[0] for l in ocr_lines])
        
        extracted = {
            'vendor': None,
            'receipt_date': None,
            'receipt_number': None,
            'gstin': "",
            'total_amount': None,
            'raw_text': all_text,
            'ocr_lines': ocr_lines,
            'has_photo': bool(ocr_lines),
            'ocr_confidence': sum(l[1] for l in ocr_lines) / max(1, len(ocr_lines))
        }

        if not ocr_lines:
            return extracted

        # 1. GSTIN
        gst_m = GSTIN_REGEX.search(all_text)
        if gst_m:
            extracted['gstin'] = gst_m.group(0).upper()

        # 2. Date
        found_date = None
        for text, _ in ocr_lines:
            if any(k in text.lower() for k in ['date', 'dt:', 'dt.', 'dated']):
                for pat, _ in DATE_PATTERNS:
                    m = pat.search(text)
                    if m:
                        found_date = normalize_date_to_iso(m.group(0))
                        if found_date:
                            break
            if found_date:
                break

        if not found_date:
            for text, _ in ocr_lines:
                for pat, _ in DATE_PATTERNS:
                    m = pat.search(text)
                    if m:
                        found_date = normalize_date_to_iso(m.group(0))
                        if found_date:
                            break
                if found_date:
                    break

        extracted['receipt_date'] = found_date or normalize_date_to_iso(str(claim_info.get('expense_date', '')))

        # 3. Receipt / Bill Number
        bill_no = None
        for text, _ in ocr_lines:
            m = re.search(r'(?:bill|receipt|inv|invoice|tax\s*invoice|memo|ticket|awb|cn)\s*[:.\-]?\s*([A-Za-z0-9\-/_]{3,20})', text, re.IGNORECASE)
            if m:
                cand = m.group(1).strip()
                if not any(k in cand.lower() for k in ['date', 'time', 'total', 'gst']):
                    bill_no = cand
                    break

        if not bill_no:
            for text, _ in ocr_lines:
                m = re.search(r'\b\d{4,8}\b', text)
                if m and not any(k in text.lower() for k in ['date', 'rate', 'time']):
                    bill_no = m.group(0)
                    break

        extracted['receipt_number'] = bill_no or ""

        # 4. Total Amount
        amounts_found = []
        total_pats = [
            re.compile(r'(?:grand\s*total|net\s*amount|total\s*amount|total\s*payable|amount\s*paid|total|amt)\s*[:.\-]?\s*(?:rs\.?|inr|₹)?\s*([0-9,]+\.?[0-9]*)', re.IGNORECASE),
            re.compile(r'(?:rs\.?|inr|₹)\s*([0-9,]+\.?[0-9]*)', re.IGNORECASE)
        ]

        for text, _ in ocr_lines:
            for pat in total_pats:
                for m in pat.finditer(text):
                    s = m.group(1).replace(',', '')
                    try:
                        val = float(s)
                        if 5.0 <= val <= 60000.0:
                            amounts_found.append(val)
                    except ValueError:
                        pass

        from .rules import normalize_amount
        claimed_amt = normalize_amount(claim_info.get('amount_claimed'))
        
        best_amount = None
        if amounts_found:
            if claimed_amt:
                matches = [a for a in amounts_found if abs(a - claimed_amt) <= 1.0]
                if matches:
                    best_amount = matches[0]
                else:
                    close = [a for a in amounts_found if abs(a - claimed_amt) <= 10.0]
                    best_amount = close[0] if close else max(amounts_found)
            else:
                best_amount = max(amounts_found)

        extracted['total_amount'] = best_amount if best_amount is not None else claimed_amt

        # 5. Vendor Name
        vendor_cands = []
        for text, score in ocr_lines[:5]:
            t = text.strip()
            if len(t) < 3 or t.isdigit():
                continue
            if any(k in t.lower() for k in ['tax invoice', 'cash memo', 'retail invoice', 'welcome', 'phone', 'tel', 'gstin']):
                continue
            vendor_cands.append(t)

        extracted['vendor'] = vendor_cands[0] if vendor_cands else claim_info.get('vendor', '')

        return extracted
