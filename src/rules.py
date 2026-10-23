"""
Tarang Expense Policy (v3.2) Business Rules & Decision Engine
-----------------------------------------------------------
Implements deterministic compliance checks for claims:
  - Auto-approve: Amount < Rs 2,000, receipt matches claim, valid vehicle for fuel, no duplicates.
  - Review: Amount >= Rs 2,000, missing/unreadable bill, duplicate bill, policy limit breach.
"""

import re
from typing import Dict, Any, Tuple, Optional, Set
import pandas as pd
from .config import settings


def load_employee_directory() -> Dict[str, Dict[str, Any]]:
    """Loads employee information for vehicle and grade policy verification."""
    csv_path = settings.resolve_raw_file("employees.csv")
    directory = {}
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                directory[str(row['emp_id']).strip()] = {
                    'name': row.get('name', ''),
                    'designation': row.get('designation', ''),
                    'vehicle_no': str(row.get('vehicle_no', '')).replace(' ', '').upper(),
                    'vehicle_no_raw': str(row.get('vehicle_no', '')),
                    'grade': str(row.get('grade', 'M1')).strip().upper(),
                    'headquarter': row.get('headquarter', '')
                }
        except Exception as e:
            print(f"Error loading employee directory from {csv_path}: {e}")
            
    # Clean fallback demo directory when proprietary employees.csv is excluded for public repos
    if not directory:
        directory = {
            'TPD-0412': {'name': 'Rohan Wankhede', 'designation': 'Medical Representative', 'vehicle_no': 'MH31EK4471', 'vehicle_no_raw': 'MH31 EK 4471', 'grade': 'M1', 'headquarter': 'Nagpur'},
            'TPD-0431': {'name': 'Pooja Meshram', 'designation': 'Senior Medical Representative', 'vehicle_no': 'MH31DX0981', 'vehicle_no_raw': 'MH31 DX 0981', 'grade': 'M2', 'headquarter': 'Nagpur'},
            'TPD-0452': {'name': 'Kalyani Deshmukh', 'designation': 'Senior Medical Representative', 'vehicle_no': 'MH32BB1205', 'vehicle_no_raw': 'MH32 BB 1205', 'grade': 'M2', 'headquarter': 'Wardha'},
            'TPD-0484': {'name': 'Tushar Barde', 'designation': 'Medical Representative', 'vehicle_no': 'MH29AR4419', 'vehicle_no_raw': 'MH29 AR 4419', 'grade': 'M1', 'headquarter': 'Yavatmal'},
            'TPD-0388': {'name': 'Nilesh Agrawal', 'designation': 'Finance Controller', 'vehicle_no': '', 'vehicle_no_raw': '', 'grade': 'M3', 'headquarter': 'Nagpur'}
        }
    return directory



def normalize_amount(val: Any) -> Optional[float]:
    """Converts strings like 'Rs. 1,536.00', 'Rs 200' into standard float."""
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


def evaluate_expense_policy(
    extracted_fields: Dict[str, Any],
    claim_info: Dict[str, Any],
    seen_receipts: Optional[Set[str]] = None,
    employees: Optional[Dict[str, Dict[str, Any]]] = None
) -> Tuple[str, str, list]:
    """
    Applies Tarang Field Expense Policy v3.2 to arrive at 'approve' vs 'review'.
    Returns (decision, primary_reason, detailed_rules_list).
    """
    if seen_receipts is None:
        seen_receipts = set()
    if employees is None:
        employees = load_employee_directory()

    reasons = []
    policy_rules = []

    category = str(claim_info.get('category', '')).strip().title()
    claimed_amt = normalize_amount(claim_info.get('amount_claimed')) or 0.0
    bill_amt = extracted_fields.get('total_amount')
    if bill_amt is None:
        bill_amt = claimed_amt

    emp_id = str(claim_info.get('emp_id', '')).strip()
    emp_info = employees.get(emp_id, {})
    emp_grade = emp_info.get('grade', 'M1')
    emp_vehicle = emp_info.get('vehicle_no', '')

    has_photo = extracted_fields.get('has_photo', False)
    raw_text = extracted_fields.get('raw_text', '')

    # 1. Receipt Quality / Attachment Rule
    if not has_photo or not raw_text.strip():
        policy_rules.append({
            'name': 'Receipt Attachment',
            'passed': False,
            'detail': 'Bill not attached or photograph unreadable'
        })
        return "review", "bill not attached or photo unreadable", policy_rules
    else:
        policy_rules.append({
            'name': 'Receipt Attachment',
            'passed': True,
            'detail': 'Legible receipt image present'
        })

    # 2. Duplicate Submission Detection Rule
    receipt_no = extracted_fields.get('receipt_number', '')
    vendor_clean = re.sub(r'[^a-zA-Z0-9]', '', str(extracted_fields.get('vendor', ''))).lower()
    dedup_key = f"{vendor_clean}_{receipt_no}_{bill_amt}" if receipt_no and len(str(receipt_no).strip()) >= 3 else None

    if dedup_key and dedup_key in seen_receipts:
        policy_rules.append({
            'name': 'Duplicate Prevention',
            'passed': False,
            'detail': f'Duplicate submission: bill number {receipt_no} already processed'
        })
        return "review", f"duplicate claim: same bill number {receipt_no} already processed", policy_rules
    elif dedup_key:
        seen_receipts.add(dedup_key)
        policy_rules.append({
            'name': 'Duplicate Prevention',
            'passed': True,
            'detail': 'Zero duplicate claims detected'
        })

    # 3. Amount Discrepancy Rule (Rs 10 tolerance)
    amt_diff = abs(claimed_amt - bill_amt)
    amt_match = amt_diff <= settings.AMOUNT_TOLERANCE_RUPEES
    policy_rules.append({
        'name': 'Amount Verification',
        'passed': amt_match,
        'detail': f"Claimed Rs {claimed_amt:.2f} matches bill Rs {bill_amt:.2f}" if amt_match else f"Discrepancy of Rs {amt_diff:.2f} between claim and bill"
    })
    if not amt_match:
        reasons.append(f"amount mismatch: claimed Rs {claimed_amt:.2f} vs bill Rs {bill_amt:.2f}")

    # 4. Nilesh's Rule: Auto-approve < Rs 2,000, review >= Rs 2,000
    under_threshold = bill_amt < settings.AUTO_APPROVE_MAX_AMOUNT
    policy_rules.append({
        'name': 'Rs 2,000 Threshold',
        'passed': under_threshold,
        'detail': f"Receipt amount Rs {bill_amt:.2f} < Rs 2,000 ceiling" if under_threshold else f"Amount Rs {bill_amt:.2f} >= Rs 2,000 (clerk review required)"
    })
    if not under_threshold:
        reasons.append(f"amount Rs {bill_amt:.0f} >= Rs 2,000 (clerk review required)")

    # 5. Category-Specific Policy Checks
    # A. Lodging
    if category == "Lodging":
        has_gstin = bool(extracted_fields.get('gstin'))
        policy_rules.append({
            'name': 'Hotel GST Tax Invoice',
            'passed': has_gstin,
            'detail': f"Valid GSTIN {extracted_fields.get('gstin')} verified" if has_gstin else "Lodging requires valid GST tax invoice"
        })
        if not has_gstin:
            reasons.append("lodging bill missing mandatory GSTIN")

        limit = settings.LODGING_M3_LIMIT if emp_grade == 'M3' else settings.LODGING_M1_M2_LIMIT
        within_grade = bill_amt <= limit
        policy_rules.append({
            'name': f'Grade {emp_grade} Lodging Limit',
            'passed': within_grade,
            'detail': f"Bill Rs {bill_amt:.0f} within Rs {limit:.0f} limit" if within_grade else f"Exceeds grade {emp_grade} limit of Rs {limit:.0f}"
        })
        if not within_grade:
            reasons.append(f"lodging Rs {bill_amt:.0f} exceeds grade {emp_grade} limit of Rs {limit:.0f}")

    # B. Food
    elif category == "Food":
        food_ok = bill_amt <= settings.FOOD_MAX_AMOUNT
        policy_rules.append({
            'name': 'Doctor / Stockist Meal Limit',
            'passed': food_ok,
            'detail': f"Bill Rs {bill_amt:.0f} <= Rs {settings.FOOD_MAX_AMOUNT:.0f}" if food_ok else f"Bill Rs {bill_amt:.0f} exceeds Rs {settings.FOOD_MAX_AMOUNT:.0f} threshold"
        })
        if not food_ok:
            reasons.append(f"food bill Rs {bill_amt:.0f} exceeds Rs 2,500 threshold")

    # C. Fuel
    elif category == "Fuel":
        text_clean = raw_text.replace(' ', '').upper()
        veh_matched = False
        if emp_vehicle:
            veh_matched = emp_vehicle in text_clean or emp_vehicle[-4:] in text_clean
            
        policy_rules.append({
            'name': 'Fuel Vehicle Verification',
            'passed': veh_matched,
            'detail': f"Vehicle {emp_info.get('vehicle_no_raw')} verified on bill" if veh_matched else f"Vehicle {emp_info.get('vehicle_no_raw', 'Registered Vehicle')} not found on receipt"
        })
        if not veh_matched:
            reasons.append(f"vehicle number {emp_info.get('vehicle_no_raw')} not found on fuel receipt")

    # Final Synthesis
    if reasons:
        return "review", "; ".join(reasons), policy_rules
    else:
        return "approve", "auto-approved: valid receipt under Rs 2,000 adhering to policy", policy_rules
