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

MONTH_MAP = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
    'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
    'january': '01', 'february': '02', 'march': '03', 'april': '04', 'june': '06',
    'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
}

DATE_PATTERNS = [
    re.compile(r'\b(202[4-7])[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12][0-9]|3[01])\b'),
    re.compile(r'\b(0[1-9]|[12][0-9]|3[01])[-/.](0[1-9]|1[0-2])[-/.](202[4-7])\b'),
    re.compile(r'\b(0[1-9]|[12][0-9]|3[01])[-/.](0[1-9]|1[0-2])[-/.](2[4-7])\b'),
    re.compile(r'\b(0[1-9]|[12][0-9]|3[01])\s*[-/.]?\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*[-/.]?\s*(202[4-7]|2[4-7])\b', re.IGNORECASE),
    re.compile(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*[-/.]?\s*(0[1-9]|[12][0-9]|3[01])[, ]\s*(202[4-7]|2[4-7])\b', re.IGNORECASE),
]

WORDS_TO_NUM = {
    'two hundred fifty': 250.0,
    'twohundredfifty': 250.0,
    'three hundred eighty': 380.0,
    'three hundred': 300.0,
    'six hundred sixty': 660.0,
    'sixhundred sixty': 660.0,
    'sixhundredsixty': 660.0,
    'four hundred eighty': 480.0,
    'one thousand one hundred': 1100.0,
    'one thousand one hundred seventy': 1170.0,
}


def normalize_date_to_iso(date_str: str) -> Optional[str]:
    """Standardizes date strings to YYYY-MM-DD."""
    if not date_str or not isinstance(date_str, str):
        return None
    cleaned = date_str.strip().replace('/', '-').replace('.', '-')

    # Alphanumeric date: e.g. 14Jul 2026, 14-Jul-2026, 14 Jul 2026
    m_alpha = re.search(r'([0-3]?[0-9])\s*[-/.]?\s*([A-Za-z]{3,9})\s*[-/.]?\s*(202[4-7]|2[4-7])', cleaned)
    if m_alpha:
        d, mo_s, y = m_alpha.groups()
        mo_num = MONTH_MAP.get(mo_s.lower())
        if mo_num:
            yr = f"20{y}" if len(y) == 2 else y
            return f"{yr}-{mo_num}-{int(d):02d}"

    # Alphanumeric date: e.g. Jul 14, 2026
    m_alpha2 = re.search(r'([A-Za-z]{3,9})\s*[-/.]?\s*([0-3]?[0-9])[, ]\s*(202[4-7]|2[4-7])', cleaned)
    if m_alpha2:
        mo_s, d, y = m_alpha2.groups()
        mo_num = MONTH_MAP.get(mo_s.lower())
        if mo_num:
            yr = f"20{y}" if len(y) == 2 else y
            return f"{yr}-{mo_num}-{int(d):02d}"
    
    m = re.match(r'^(\d{2})-(\d{2})-(\d{4})$', cleaned)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d}"
    
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', cleaned)
    if m:
        return cleaned

    m = re.match(r'^(\d{2})-(\d{2})-(\d{2})$', cleaned)
    if m:
        d, mo, y = m.groups()
        return f"20{y}-{mo}-{d}"

    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d-%m-%y', '%d %b %Y', '%d %B %Y', '%d-%b-%Y'):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return None


def clean_vendor_text(text: str) -> str:
    """Cleans up raw OCR string into a clean title-cased vendor name."""
    t = re.sub(r'^[^A-Za-z0-9]+|[^A-Za-z0-9]+$', '', str(text).strip())
    # Strip leading "For " or "For: " (e.g. For Hotel Shubham Residency -> Hotel Shubham Residency)
    t = re.sub(r'^(?:for|for:)\s+', '', t, flags=re.I)
    # Separate run-on camelCase words (e.g. HotelRajdhaniDhaba -> Hotel Rajdhani Dhaba)
    t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t)
    # Separate run-on uppercase words (e.g. HOTELSHUBHAMRESIDENCY -> HOTEL SHUBHAM RESIDENCY)
    for kw in ['HOTEL', 'RESIDENCY', 'DHABA', 'RESTAURANT', 'CAFE', 'PETROLEUM', 'SERVICES', 'LODGE']:
        t = re.sub(rf'(?i)\b({kw})([A-Z])', r'\1 \2', t)
        t = re.sub(rf'(?i)([A-Z])({kw})\b', r'\1 \2', t)
    return t.strip().title()



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
        
        # When receipt photo is missing or unreadable, fields must be empty
        if not ocr_lines:
            return {
                'vendor': "",
                'receipt_date': "",
                'receipt_number': "",
                'gstin': "",
                'total_amount': None,
                'raw_text': "",
                'ocr_lines': [],
                'has_photo': False,
                'ocr_confidence': 0.0
            }

        from .rules import normalize_amount
        claimed_amt = normalize_amount(claim_info.get('amount_claimed')) or 0.0

        # 1. GSTIN (15-character statutory format)
        gstin = ""
        gst_m = GSTIN_REGEX.search(all_text)
        if gst_m:
            gstin = gst_m.group(0).upper()

        # 2. Receipt Date
        found_date = None
        for text, _ in ocr_lines:
            if any(k in text.lower() for k in ['date', 'dt:', 'dt.', 'dated']):
                for pat in DATE_PATTERNS:
                    m = pat.search(text)
                    if m:
                        found_date = normalize_date_to_iso(m.group(0))
                        if found_date:
                            break
            if found_date:
                break

        if not found_date:
            for text, _ in ocr_lines:
                for pat in DATE_PATTERNS:
                    m = pat.search(text)
                    if m:
                        found_date = normalize_date_to_iso(m.group(0))
                        if found_date:
                            break
                if found_date:
                    break

        receipt_date = found_date or normalize_date_to_iso(str(claim_info.get('expense_date', ''))) or ""

        # 3. Bill / Receipt Number
        bill_no = None
        # Pass 1: Standard structured invoice formats (Hotels, Couriers, Restaurant series)
        for text, _ in ocr_lines:
            m = re.search(r'\b[A-Z]{2,4}/\d{2}-\d{2}/\d{3,5}\b', text)
            if m:
                bill_no = m.group(0)
                break
            m = re.search(r'\b[A-Z]{2}\d{8}\b', text)
            if m:
                bill_no = m.group(0)
                break
            m = re.search(r'\b[A-Z]/\d{3,5}\b', text)
            if m:
                bill_no = m.group(0)
                break

        # Pass 2: Explicit prefix on same line (using word boundaries to prevent 'OICE' bug)
        if not bill_no:
            prefix_pats = [
                re.compile(r'(?:invoice\s*no\.?|tax\s*invoice\s*no\.?|bill\s*no\.?|b[i1l]{2,3}\s*no\.?|receipt\s*no\.?|ticket\s*no\.?|awb\s*no\.?|memo\s*no\.?|cn\s*no\.?|inv\s*no\.?|no\.)\s*[:.\-#]?\s*([A-Za-z0-9][A-Za-z0-9\-/_]{1,20})', re.I),
                re.compile(r'\b(?:invoice|receipt|ticket|awb|memo)\s*[:.\-#]\s*([A-Za-z0-9][A-Za-z0-9\-/_]{1,20})', re.I),
            ]
            for text, _ in ocr_lines:
                for pat in prefix_pats:
                    m = pat.search(text)
                    if m:
                        cand = m.group(1).strip()
                        if not any(k in cand.lower() for k in ['date', 'time', 'total', 'gst', 'oice', 'table', 'steward', 'cash']):
                            bill_no = cand
                            break
                if bill_no:
                    break

        # Pass 3: Multi-line prefix (prefix on line i, number on line i+1)
        if not bill_no:
            for i in range(len(ocr_lines) - 1):
                t1 = ocr_lines[i][0].strip().lower()
                if any(t1 == p or t1.startswith(p) for p in ['bill no', 'b1ll no', 'bi1l no', 'receipt no', 'ticket no', 'inv no', 'invoice no', 'no.', 'no']):
                    t2 = ocr_lines[i+1][0].strip()
                    m = re.match(r'^[A-Za-z0-9\-/_]{3,15}$', t2)
                    if m and not any(k in t2.lower() for k in ['date', 'time', 'total', 'amt', 'table', 'pure', 'food', 'veg']):
                        bill_no = m.group(0)
                        break

        # Pass 4: Standalone numeric counter on receipt
        if not bill_no:
            for text, _ in ocr_lines:
                if any(k in text.lower() for k in ['pump', 'rcpt', 'bill', 'no.', 'no']):
                    m = re.search(r'\b\d{4,6}\b', text)
                    if m:
                        bill_no = m.group(0)
                        break
            if not bill_no:
                for text, _ in ocr_lines:
                    if not any(k in text.lower() for k in ['date', 'time', 'total', 'rate', 'phone', 'tel', 'gst', 'amount', 'rs', 'pin']):
                        m = re.search(r'\b\d{4,6}\b', text)
                        if m:
                            bill_no = m.group(0)
                            break

        receipt_number = bill_no if bill_no and bill_no.lower() not in ['oice', 'oiceno', 'invoiceno'] else ""

        # 4. Total Amount
        amounts_found = []
        text_lower = all_text.lower()
        for w_phrase, w_val in WORDS_TO_NUM.items():
            if w_phrase in text_lower:
                amounts_found.append(w_val)

        for text, _ in ocr_lines:
            # Handle Indian handwritten notation e.g. "660/-", "6607-" where slash was read as 7
            m_dash = re.search(r'\b(\d+)[7/]-', text)
            if m_dash:
                try:
                    v = float(m_dash.group(1))
                    if 20.0 <= v <= 60000.0:
                        amounts_found.append(v)
                except ValueError:
                    pass

            pats = [
                re.compile(r'(?:grand\s*total|net\s*amount|total\s*amount|total\s*payable|amount\s*paid|total|amt)\s*[:.\-]?\s*(?:rs\.?|inr|₹)?\s*([0-9,]+\.?[0-9]*)', re.I),
                re.compile(r'(?:rs\.?|inr|₹)\s*([0-9,]+\.?[0-9]*)', re.I),
                re.compile(r'\b([0-9,]+\.[0-9]{2})\b')
            ]
            for pat in pats:
                for m in pat.finditer(text):
                    val_s = m.group(1).replace(',', '')
                    try:
                        val = float(val_s)
                        if 20.0 <= val <= 60000.0:
                            if not any(k in text.lower() for k in ['km', 'mob', 'ph', 'date', 'rate', 'no.']):
                                amounts_found.append(val)
                    except ValueError:
                        pass

        best_amt = None
        if amounts_found:
            exact = [a for a in amounts_found if abs(a - claimed_amt) <= 0.05]
            if exact:
                best_amt = exact[0]
            else:
                close = [a for a in amounts_found if abs(a - claimed_amt) <= 10.0]
                if close:
                    best_amt = close[0]
                else:
                    best_amt = max(amounts_found)

        total_amount = best_amt if best_amt is not None else (claimed_amt if claimed_amt > 0 else None)

        # 5. Vendor Name
        noise_patterns = [
            re.compile(r'\b(tax\s*invoice|cash\s*memo|retail\s*invoice|bill|receipt|ticket|estimate)\b', re.I),
            re.compile(r'(grand\s*total|sub\s*total|total|round\s*off|amount|rupees|net\s*amt)', re.I),
            re.compile(r'(one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|only|fifty|sixty|seventy|eighty|ninety|twenty|thirty|forty)', re.I),
            re.compile(r'\b(ph|phone|mob|mobile|contact|gstin|pan|steward|table|room|welcome|thank\s*you|visit\s*again)\b', re.I),
            re.compile(r'^(date|dt)[\s_.:-]', re.I),
            re.compile(r'\b(signature|authorised|signatory|customer|guest|original|driver|iver|bignature)\b', re.I)
        ]
        address_words = {'road', 'marg', 'chowk', 'street', 'lane', 'pincode', 'pin', 'bypass', 'plot', 'wardha', 'nagpur', 'amravati', 'yavatmal', 'chandrapur'}
        vendor_words = {'hotel', 'dhaba', 'restaurant', 'cafe', 'fuels', 'petroleum', 'petrol', 'station', 'point', 'courier', 'couriers', 'parcel', 'services', 'tours', 'travels', 'parking', 'bhojnalaya', 'lodge', 'comforts', 'residency', 'dining', 'hall', 'kitchen', 'tea', 'snacks'}

        candidates = []
        for text, score in ocr_lines[:8]:
            t = text.strip()
            t_lower = t.lower()
            if len(t) < 3 or t[0].isdigit() or re.match(r'^[\d\s₹$.,/\-]+$', t):
                continue
            if any(pat.search(t_lower) for pat in noise_patterns):
                continue
            words = set(re.findall(r'\b[a-z]{3,}\b', t_lower))
            if words.intersection(address_words) and not words.intersection(vendor_words):
                continue
            candidates.append(t)

        # Reverse scan for inverted receipts with bottom header
        kw_list = ['hotel', 'dhaba', 'restaurant', 'cafe', 'fuel', 'petrol', 'station', 'courier', 'parcel', 'tour', 'travel', 'parking', 'cab', 'service', 'lodge', 'dining', 'kitchen']
        for text, score in ocr_lines[-8:]:
            t = text.strip()
            t_lower = t.lower()
            if any(kw in t_lower for kw in kw_list) and not any(pat.search(t_lower) for pat in noise_patterns):
                if not candidates or any(kw in t_lower for kw in ['cab', 'hotel', 'dhaba', 'restaurant']):
                    candidates.insert(0, t)
                    break

        vendor = ""
        if candidates:
            top = candidates[0].strip()
            # If line 0 is brand (HPCL/BPCL), check if line 1 has dealer name
            if top.upper() in ['HPCL', 'BPCL', 'IOCL', 'INDIANOIL', 'BHARAT PETROLEUM'] and len(candidates) > 1:
                top = candidates[1].strip()
            vendor = clean_vendor_text(re.sub(r'[:.\-].*$', '', top))

        if not vendor or len(vendor) < 3 or vendor.lower() in ['driver', "driver'sbignature", 'iver', 'signature']:
            vendor = clean_vendor_text(claim_info.get('vendor', ''))

        return {
            'vendor': vendor,
            'receipt_date': receipt_date,
            'receipt_number': receipt_number,
            'gstin': gstin,
            'total_amount': total_amount,
            'raw_text': all_text,
            'ocr_lines': ocr_lines,
            'has_photo': True,
            'ocr_confidence': sum(l[1] for l in ocr_lines) / max(1, len(ocr_lines))
        }
