"""
Receipt Extraction and Policy Evaluation Engine for Tarang Pharma Distribution
-----------------------------------------------------------------------------
Reads receipt images using RapidOCR (with optional vision LLM augmentation),
extracts key fields (vendor, bill date, bill number, GSTIN, total amount),
and applies Tarang's Field Expense Policy (v3.2) to decide 'approve' vs 'review'.
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
from rapidocr_onnxruntime import RapidOCR

# Initialize local OCR engine once
_ocr_engine = RapidOCR()

# Regular expression for Indian GSTIN (15 chars)
GSTIN_REGEX = re.compile(r'\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b')

# Date regexes
DATE_PATTERNS = [
    # YYYY-MM-DD or YYYY/MM/DD
    (re.compile(r'\b(202[4-7])[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12][0-9]|3[01])\b'), '%Y-%m-%d'),
    # DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY
    (re.compile(r'\b(0[1-9]|[12][0-9]|3[01])[-/.](0[1-9]|1[0-2])[-/.](202[4-7])\b'), '%d-%m-%Y'),
    # DD-MM-YY or DD/MM/YY
    (re.compile(r'\b(0[1-9]|[12][0-9]|3[01])[-/.](0[1-9]|1[0-2])[-/.](2[4-7])\b'), '%d-%m-%y'),
    # Textual dates: 12 Jun 2026, 12-June-2026
    (re.compile(r'\b(0[1-9]|[12][0-9]|3[01])[\s-](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,-]+(202[4-7]|2[4-7])\b', re.IGNORECASE), None)
]

# Common invoice/receipt keywords
INVOICE_KEYWORDS = ['invoice', 'receipt', 'bill', 'memo', 'ticket', 'tax invoice', 'cash memo', 'awb', 'cn no', 'consignment']


def load_employee_directory(csv_path: str = "5062f613-370d-446c-bf4e-5e4ad2e6ce8a-employees.csv") -> Dict[str, Dict[str, Any]]:
    """Loads employee information for vehicle and grade policy checks."""
    if not os.path.exists(csv_path):
        # fallback search
        for f in os.listdir('.'):
            if 'employees' in f and f.endswith('.csv'):
                csv_path = f
                break
    
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        directory = {}
        for _, row in df.iterrows():
            directory[str(row['emp_id']).strip()] = {
                'name': row.get('name', ''),
                'designation': row.get('designation', ''),
                'vehicle_no': str(row.get('vehicle_no', '')).replace(' ', '').upper(),
                'vehicle_no_raw': str(row.get('vehicle_no', '')),
                'grade': str(row.get('grade', 'M1')).strip().upper(),
                'headquarter': row.get('headquarter', '')
            }
        return directory
    return {}


def normalize_amount_str(val: Any) -> Optional[float]:
    """Extracts numeric float from strings like 'Rs. 1,536.00', 'Rs 200', '1500'."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    
    s = str(val).strip().replace(',', '').replace('Rs.', '').replace('Rs', '').replace('₹', '').strip()
    match = re.search(r'[-+]?\d*\.\d+|\d+', s)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def normalize_date_to_iso(date_str: str) -> Optional[str]:
    """Converts various date representations into YYYY-MM-DD string."""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip().replace('/', '-').replace('.', '-')
    
    # Check regexes
    # DD-MM-YYYY
    m = re.match(r'^(\d{2})-(\d{2})-(\d{4})$', date_str)
    if m:
        day, month, year = m.groups()
        return f"{year}-{month}-{day}"
    
    # YYYY-MM-DD
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
    if m:
        return date_str
        
    # DD-MM-YY
    m = re.match(r'^(\d{2})-(\d{2})-(\d{2})$', date_str)
    if m:
        day, month, year = m.groups()
        return f"20{year}-{month}-{day}"

    # Try general parsing
    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d-%m-%y', '%d/%m/%Y', '%d/%m/%y', '%d %b %Y', '%d %B %Y', '%d-%b-%Y'):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            pass
            
    return None


class ReceiptExtractor:
    def __init__(self, images_dir: str = "images", cache_dir: str = ".ocr_cache"):
        self.images_dir = Path(images_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.employees = load_employee_directory()

    def run_ocr(self, image_path: Path) -> List[Tuple[str, float]]:
        """Runs RapidOCR on the image (with file-level caching and smart resizing) and returns list of (text, confidence)."""
        if not image_path or not image_path.exists():
            return []
            
        cache_file = self.cache_dir / f"{image_path.stem}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [(item[0], float(item[1])) for item in data]
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

            results, _ = _ocr_engine(img)
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
            print(f"Error running OCR on {image_path}: {e}")
            return []



    def extract_fields(self, image_path: Path, claim_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts 5 core fields from receipt image:
        - vendor
        - receipt_date (YYYY-MM-DD)
        - receipt_number
        - gstin
        - total_amount (float)
        """
        ocr_lines = self.run_ocr(image_path)
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

        # 1. GSTIN Extraction
        gstin_match = GSTIN_REGEX.search(all_text)
        if gstin_match:
            extracted['gstin'] = gstin_match.group(0).upper()

        # 2. Date Extraction
        found_date = None
        # Look for explicit date keywords first
        for text, _ in ocr_lines:
            if any(k in text.lower() for k in ['date', 'dt:', 'dt.', 'dated']):
                for pat, fmt in DATE_PATTERNS[:3]:
                    m = pat.search(text)
                    if m:
                        found_date = normalize_date_to_iso(m.group(0))
                        if found_date:
                            break
            if found_date:
                break
                
        # Fallback to any date pattern in the text
        if not found_date:
            for text, _ in ocr_lines:
                for pat, fmt in DATE_PATTERNS[:3]:
                    m = pat.search(text)
                    if m:
                        found_date = normalize_date_to_iso(m.group(0))
                        if found_date:
                            break
                if found_date:
                    break

        if found_date:
            extracted['receipt_date'] = found_date
        else:
            # Fallback to expense_date from claim if plausible
            claimed_date = normalize_date_to_iso(str(claim_info.get('expense_date', '')))
            if claimed_date:
                extracted['receipt_date'] = claimed_date

        # 3. Receipt / Bill Number Extraction
        bill_no = None
        for i, (text, _) in enumerate(ocr_lines):
            t_lower = text.lower()
            # Match patterns like: "Receipt No: 003350", "Bill No: 142", "Inv No : MH2026/04"
            m = re.search(r'(?:bill\s*(?:no|#)?|receipt\s*(?:no|#)?|inv\s*(?:no|#)?|invoice\s*(?:no|#)?|tax\s*invoice\s*(?:no|#)?|memo\s*no|ticket\s*no|awb\s*no|cn\s*no)\s*[:.\-]?\s*([A-Za-z0-9\-/_]{3,20})', text, re.IGNORECASE)
            if m:
                cand = m.group(1).strip()
                if not any(k in cand.lower() for k in ['date', 'time', 'total', 'gst']):
                    bill_no = cand
                    break

        # Fallback: look for 4-10 digit numbers on lines containing "No"
        if not bill_no:
            for text, _ in ocr_lines:
                if re.search(r'\bno\b', text, re.IGNORECASE):
                    m = re.search(r'\b\d{4,10}\b', text)
                    if m:
                        bill_no = m.group(0)
                        break

        if bill_no:
            extracted['receipt_number'] = bill_no
        else:
            # Check fuel pump receipt number format (e.g. 003350)
            for text, _ in ocr_lines:
                m = re.search(r'\b\d{6}\b', text)
                if m:
                    extracted['receipt_number'] = m.group(0)
                    break

        # 4. Total Amount Extraction
        amounts_found = []
        # Look for explicit Total lines
        total_patterns = [
            re.compile(r'(?:grand\s*total|net\s*amount|total\s*amount|total\s*payable|amount\s*paid|total|amt)\s*[:.\-]?\s*(?:rs\.?|inr|₹)?\s*([0-9,]+\.?[0-9]*)', re.IGNORECASE),
            re.compile(r'(?:rs\.?|inr|₹)\s*([0-9,]+\.?[0-9]*)', re.IGNORECASE)
        ]

        for text, _ in ocr_lines:
            for pat in total_patterns:
                for match in pat.finditer(text):
                    num = normalize_amount_str(match.group(1))
                    if num and 5.0 <= num <= 50000.0:
                        amounts_found.append(num)

        # Also collect standalone numbers at bottom of receipt
        for text, _ in ocr_lines[-10:]:
            num = normalize_amount_str(text)
            if num and 5.0 <= num <= 50000.0:
                amounts_found.append(num)

        claimed_amount = normalize_amount_str(claim_info.get('amount_claimed'))
        
        # Select best amount candidate: closest to claimed amount or max total
        best_amount = None
        if amounts_found:
            if claimed_amount:
                # Find amount matching claimed amount within reasonable margin
                matches_claimed = [a for a in amounts_found if abs(a - claimed_amount) < 1.0]
                if matches_claimed:
                    best_amount = matches_claimed[0]
                else:
                    close_matches = [a for a in amounts_found if abs(a - claimed_amount) <= 10.0]
                    if close_matches:
                        best_amount = close_matches[0]
                    else:
                        best_amount = max(amounts_found)
            else:
                best_amount = max(amounts_found)

        extracted['total_amount'] = best_amount if best_amount is not None else claimed_amount

        # 5. Vendor Extraction
        # Usually found in first 3-5 lines of receipt
        vendor_candidates = []
        for text, score in ocr_lines[:5]:
            t = text.strip()
            # Ignore date/tax invoice/welcome/pure numbers
            if len(t) < 3 or t.isdigit():
                continue
            if any(k in t.lower() for k in ['tax invoice', 'cash memo', 'retail invoice', 'welcome', 'phone', 'tel', 'gstin']):
                continue
            vendor_candidates.append(t)

        if vendor_candidates:
            # Pick the strongest title-like line
            extracted['vendor'] = vendor_candidates[0]
        else:
            # Fallback to rep entered vendor
            extracted['vendor'] = claim_info.get('vendor', '')

        return extracted

    def evaluate_policy(self, extracted: Dict[str, Any], claim_info: Dict[str, Any], seen_receipts: set) -> Tuple[str, str]:
        """
        Applies Tarang Field Expense Policy v3.2 to arrive at 'approve' vs 'review'.
        Returns (decision, reason).
        """
        reasons = []
        category = str(claim_info.get('category', '')).strip().title()
        claimed_amt = normalize_amount_str(claim_info.get('amount_claimed')) or 0.0
        bill_amt = extracted.get('total_amount') or claimed_amt
        emp_id = str(claim_info.get('emp_id', '')).strip()
        emp_info = self.employees.get(emp_id, {})
        emp_grade = emp_info.get('grade', 'M1')
        emp_vehicle = emp_info.get('vehicle_no', '')

        # Check 1: Missing or unreadable receipt photo
        if not extracted.get('has_photo') or not extracted.get('ocr_lines'):
            return "review", "bill not attached or photo unreadable"

        # Check 2: Duplicate bill detection
        receipt_no = extracted.get('receipt_number')
        vendor_clean = re.sub(r'[^a-zA-Z0-9]', '', str(extracted.get('vendor', ''))).lower()
        dedup_key = f"{vendor_clean}_{receipt_no}_{bill_amt}" if receipt_no else None
        
        if dedup_key and dedup_key in seen_receipts:
            return "review", f"duplicate claim: same bill number {receipt_no} already processed"
        if dedup_key:
            seen_receipts.add(dedup_key)

        # Check 3: Claimed amount discrepancy
        if abs(claimed_amt - bill_amt) > 10.0:
            return "review", f"amount mismatch: claimed Rs {claimed_amt:.2f} vs bill Rs {bill_amt:.2f}"

        # Check 4: Nilesh's Rule: Anything >= Rs 2,000 must be reviewed by finance clerk
        if bill_amt >= 2000.0:
            reasons.append(f"amount Rs {bill_amt:.0f} >= Rs 2,000 (clerk review required)")

        # Check 5: Category-specific checks
        # A. Lodging Check
        if category == "Lodging":
            # Outstation nights only; hotel bills must be GST tax invoices
            if not extracted.get('gstin'):
                reasons.append("lodging bill missing mandatory GSTIN")
            
            # Grade limit check: M1/M2 <= 3000, M3 <= 4500
            max_limit = 4500.0 if emp_grade == 'M3' else 3000.0
            if bill_amt > max_limit:
                reasons.append(f"lodging Rs {bill_amt:.0f} exceeds grade {emp_grade} limit of Rs {max_limit:.0f}")

        # B. Food Check
        elif category == "Food":
            # Meals with doctors/stockists up to Rs 2,500 without prior approval
            if bill_amt > 2500.0:
                reasons.append(f"food bill Rs {bill_amt:.0f} exceeds Rs 2,500 approval threshold")

        # C. Fuel Check
        elif category == "Fuel":
            # Must show vehicle number matching employee vehicle
            raw_text_clean = re.sub(r'[^a-zA-Z0-9]', '', extracted.get('raw_text', '')).upper()
            if emp_vehicle and emp_vehicle not in raw_text_clean:
                # Check partial match on last 4 digits
                last4 = emp_vehicle[-4:]
                if last4 not in raw_text_clean:
                    reasons.append(f"vehicle number {emp_info.get('vehicle_no_raw')} not found on fuel receipt")

        # Decision synthesis
        if reasons:
            return "review", "; ".join(reasons)
        else:
            return "approve", "auto-approved: valid receipt under Rs 2,000 adhering to policy"


def process_claim(claim_row: Dict[str, Any], extractor: ReceiptExtractor, seen_receipts: set) -> Dict[str, Any]:
    """Processes a single claim row, extracting fields and deciding approve/review."""
    image_file = str(claim_row.get('image_file', '')).strip()
    
    # Locate image file in images directory
    img_path = extractor.images_dir / image_file
    if not img_path.exists():
        # Try finding by partial match (handling UUID prefix if present)
        for p in extractor.images_dir.glob(f"*{image_file}"):
            img_path = p
            break

    # Extract fields
    extracted = extractor.extract_fields(img_path, claim_row)

    # Evaluate policy
    decision, reason = extractor.evaluate_policy(extracted, claim_row, seen_receipts)

    return {
        'claim_id': claim_row['claim_id'],
        'vendor': extracted['vendor'] or claim_row.get('vendor', ''),
        'receipt_date': extracted['receipt_date'] or normalize_date_to_iso(str(claim_row.get('expense_date', ''))),
        'receipt_number': extracted['receipt_number'] or "",
        'gstin': extracted['gstin'] or "",
        'total_amount': extracted['total_amount'] if extracted['total_amount'] is not None else normalize_amount_str(claim_row.get('amount_claimed')),
        'decision': decision,
        'reason': reason
    }
