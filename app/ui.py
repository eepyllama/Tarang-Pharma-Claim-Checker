"""
Streamlit UI for Tarang Expense Receipt Reader
---------------------------------------------
Interactive audit dashboard built with Streamlit.
Run via: streamlit run app/ui.py
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
from PIL import Image

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.pipeline import ExpensePipeline
from src.rules import load_employee_directory

st.set_page_config(
    page_title="Tarang Pharma | Expense Receipt Audit",
    page_icon="🧾",
    layout="wide"
)

# Custom header styling
st.markdown("""
<style>
.stTabs [data-baseweb="tab-list"] {
    gap: 12px;
}
.stTabs [data-baseweb="tab"] {
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
}
.metric-container {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 12px;
}
</style>
""", unsafe_allow_html=True)

st.title("🧾 Tarang Pharma Distribution — Expense Receipt Audit")
st.caption("Field Expense Policy v3.2 • Automated Audit & Extraction Engine (Offline RapidOCR • ₹0/claim)")

pipeline = ExpensePipeline()
employees = load_employee_directory()


@st.cache_data
def get_all_dataset_claims():
    """Loads all 473 field claims (190 test + 283 train) for full exploration."""
    claims = []

    # 1. Test batch (190)
    test_csv = settings.resolve_raw_file("claims_test.csv")
    if test_csv.exists():
        df_t = pd.read_csv(test_csv)
        for _, r in df_t.iterrows():
            eid = str(r.get('emp_id', '')).strip()
            ename = employees.get(eid, {}).get('name', eid)
            img = str(r.get('image_file', '')).strip() if pd.notna(r.get('image_file')) else ""
            claims.append({
                'claim_id': str(r['claim_id']).strip(),
                'emp_id': eid,
                'employee_name': ename,
                'category': str(r.get('category', '')).strip(),
                'vendor': str(r.get('vendor', '')).strip(),
                'amount_claimed': str(r.get('amount_claimed', '')).strip(),
                'expense_date': str(r.get('expense_date', '')).strip(),
                'image_file': img,
                'rep_comment': str(r.get('rep_comment', '')).strip() if pd.notna(r.get('rep_comment')) else "",
                'dataset': 'Test Batch (190 claims)',
                'batch_key': 'test',
                'has_image': bool(settings.resolve_image_path(img)) if img else False
            })

    # 2. Historical train batch (283)
    train_csv = settings.resolve_raw_file("claims_train.csv")
    if train_csv.exists():
        df_tr = pd.read_csv(train_csv)
        for _, r in df_tr.iterrows():
            eid = str(r.get('emp_id', '')).strip()
            ename = employees.get(eid, {}).get('name', eid)
            img = str(r.get('image_file', '')).strip() if pd.notna(r.get('image_file')) else ""
            claims.append({
                'claim_id': str(r['claim_id']).strip(),
                'emp_id': eid,
                'employee_name': ename,
                'category': str(r.get('category', '')).strip(),
                'vendor': str(r.get('vendor', '')).strip(),
                'amount_claimed': str(r.get('amount_claimed', '')).strip(),
                'expense_date': str(r.get('expense_date', '')).strip(),
                'image_file': img,
                'rep_comment': str(r.get('rep_comment', '')).strip() if pd.notna(r.get('rep_comment')) else "",
                'dataset': 'Historical Train (283 claims)',
                'batch_key': 'train',
                'has_image': bool(settings.resolve_image_path(img)) if img else False
            })

    return claims


all_claims = get_all_dataset_claims()

# Top metric pills
col1, col2, col3, col4 = st.columns(4)
col1.metric("Auto-Approval Ceiling", "₹2,000", "Under ₹2k Auto-approved")
col2.metric("Available Field Claims", f"{len(all_claims)} Claims", "190 Test + 283 Train")
col3.metric("Clerk Workload", "-89%", "2,400 → ~260 claims/mo")
col4.metric("Net Monthly Savings", "₹74,920", "Direct clerk ROI")

st.divider()

# Layout
left_col, right_col = st.columns([1, 1.15])

# Session state to store active audit claim
if "active_audit" not in st.session_state:
    st.session_state.active_audit = None

with left_col:
    st.subheader("1. Claim & Receipt Input")

    # Two distinct sections on the same page using tabs
    tab_field, tab_upload = st.tabs([
        "⚡ Section 1: Pre-Loaded Field Claims (473)",
        "📤 Section 2: Clerk Ad-Hoc Receipt Audit"
    ])

    # ---------------------------------------------------------
    # SECTION 1: PRE-LOADED FIELD CLAIMS (473 Claims)
    # ---------------------------------------------------------
    with tab_field:
        st.markdown("**Test real field claims submitted by medical reps in Nagpur:**")

        f_col1, f_col2 = st.columns(2)
        with f_col1:
            batch_choice = st.selectbox(
                "Filter Batch:",
                ["All Batches (473 Claims)", "Test Batch (190 claims)", "Historical Train (283 claims)"]
            )
        with f_col2:
            cat_choice = st.selectbox(
                "Filter Category:",
                ["All Categories", "Fuel", "Food", "Lodging", "Local travel", "Courier", "Parking"]
            )

        # Apply filtering
        filtered_claims = all_claims
        if "Test" in batch_choice:
            filtered_claims = [c for c in filtered_claims if c['batch_key'] == 'test']
        elif "Train" in batch_choice:
            filtered_claims = [c for c in filtered_claims if c['batch_key'] == 'train']

        if cat_choice != "All Categories":
            filtered_claims = [c for c in filtered_claims if c['category'].lower() == cat_choice.lower()]

        st.caption(f"Showing **{len(filtered_claims)}** of {len(all_claims)} available claims")

        if filtered_claims:
            claim_labels = [
                f"[{c['claim_id']}] {c['category']} • ₹{c['amount_claimed']} • {c['vendor']} ({'Test' if c['batch_key']=='test' else 'Train'})"
                for c in filtered_claims
            ]
            selected_idx = st.selectbox("Select Field Claim to Test:", range(len(claim_labels)), format_func=lambda i: claim_labels[i])
            chosen_claim = filtered_claims[selected_idx]

            # Display claim summary card
            st.info(
                f"**Claim ID:** `{chosen_claim['claim_id']}`  \n"
                f"**Representative:** {chosen_claim['employee_name']} (`{chosen_claim['emp_id']}`)  \n"
                f"**Category:** {chosen_claim['category']} | **Claimed Amount:** ₹{chosen_claim['amount_claimed']}  \n"
                f"**Vendor:** {chosen_claim['vendor']} | **Expense Date:** {chosen_claim['expense_date']}  \n"
                f"**Rep Comment:** *{chosen_claim['rep_comment'] or 'None'}*  \n"
                f"**Photo Attached:** `{chosen_claim['image_file'] or 'None'}` "
                f"({'✅ Available on disk' if chosen_claim['has_image'] else '⚠️ No file on disk'})"
            )

            if st.button("⚡ Run Audit on Selected Field Claim", type="primary", use_container_width=True):
                st.session_state.active_audit = {
                    'claim': chosen_claim,
                    'image_path': settings.resolve_image_path(chosen_claim['image_file']) if chosen_claim['image_file'] else None,
                    'source': f"Section 1: Field Claim {chosen_claim['claim_id']} ({chosen_claim['dataset']})"
                }
        else:
            st.warning("No claims match the selected filter criteria.")

    # ---------------------------------------------------------
    # SECTION 2: CLERK AD-HOC RECEIPT AUDIT
    # ---------------------------------------------------------
    with tab_upload:
        st.markdown("**Clerk Audit Desk:** Upload any receipt photo (e.g. forwarded from rep email, WhatsApp query, or physical scan) to extract fields and audit policy compliance:")

        uploaded_file = st.file_uploader(
            "Upload Receipt Photo (JPEG, JPG, PNG)",
            type=["jpg", "jpeg", "png"],
            key="custom_uploader"
        )

        with st.form("manual_claim_form"):
            custom_cid = st.text_input("Claim ID", value="CLM-CUSTOM-01")
            
            emp_keys = list(employees.keys())
            custom_eid = st.selectbox(
                "Representative (Employee ID)",
                emp_keys,
                format_func=lambda x: f"{x} - {employees[x]['name']} ({employees[x]['grade']} • {employees[x]['headquarter']})"
            )

            cat_opts = ["Fuel", "Food", "Lodging", "Local travel", "Courier", "Parking"]
            custom_cat = st.selectbox("Expense Category", cat_opts)

            u_col1, u_col2 = st.columns(2)
            with u_col1:
                custom_amt = st.text_input("Claimed Amount (₹)", value="450.00")
            with u_col2:
                custom_date = st.text_input("Expense Date (YYYY-MM-DD)", value="2026-07-20")

            custom_vendor = st.text_input("Vendor (as typed by rep)", value="Green Leaf Restaurant")
            custom_comment = st.text_input("Rep Comment", value="Lunch with Dr. Sharma")

            manual_submitted = st.form_submit_button("🔍 Extract Details & Audit Uploaded Photo", type="primary", use_container_width=True)

            if manual_submitted:
                upload_img_path = None
                if uploaded_file:
                    dest = settings.IMAGES_DIR / f"upload_{uploaded_file.name}"
                    with open(dest, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    upload_img_path = dest

                st.session_state.active_audit = {
                    'claim': {
                        'claim_id': custom_cid,
                        'emp_id': custom_eid,
                        'employee_name': employees.get(custom_eid, {}).get('name', custom_eid),
                        'category': custom_cat,
                        'amount_claimed': custom_amt,
                        'expense_date': custom_date,
                        'vendor': custom_vendor,
                        'rep_comment': custom_comment,
                        'image_file': uploaded_file.name if uploaded_file else ""
                    },
                    'image_path': upload_img_path,
                    'source': f"Section 2: Uploaded Photo ({uploaded_file.name if uploaded_file else 'Form Entry'})"
                }

# ---------------------------------------------------------
# RIGHT COLUMN: AUDIT VERDICT & EXCEPTION REPORT
# ---------------------------------------------------------
with right_col:
    st.subheader("2. Audit Verdict & Extraction Results")

    audit_entry = st.session_state.active_audit

    if audit_entry:
        claim_dict = audit_entry['claim']
        img_path = audit_entry['image_path']

        st.caption(f"**Source:** {audit_entry['source']}")

        with st.spinner("Running RapidOCR extraction & Policy v3.2 audit..."):
            res = pipeline.process_claim(claim_dict, image_path=img_path)

        # Decision Banner
        is_approve = res['decision'].lower() == "approve"
        if is_approve:
            st.success("### ✅ VERDICT: APPROVE (Auto-Approved for Direct Payment)")
            st.write("**Policy Rationale:** Clean receipt photo, amount under ₹2,000 threshold, zero policy breaches, zero duplicate flags. Eligible for payout without finance clerk touch.")
        else:
            st.warning("### ⚠️ VERDICT: REVIEW REQUIRED (Flagged for Clerk Inspection)")
            st.error(f"**Exception Reason(s):** {res['reason']}")

        st.caption(f"**OCR Engine:** RapidOCR ONNX | **Lines Detected:** {res['ocr_lines_count']} | **Confidence:** {res['confidence']}%")

        # 5 Key Accounting Fields Comparison Table
        st.markdown("#### 📋 5 Key Accounting Fields Comparison")
        
        rep_amt = f"₹{float(claim_dict.get('amount_claimed', 0)):.2f}"
        ext_amt = f"₹{float(res['total_amount']):.2f}" if res['total_amount'] is not None else "Unverified"

        comparison_df = pd.DataFrame({
            "Accounting Field": ["Vendor Name", "Receipt Date", "Bill / Receipt No", "GSTIN", "Total Amount"],
            "Claimed by Rep": [
                claim_dict.get('vendor') or "N/A",
                claim_dict.get('expense_date') or "N/A",
                "Not entered by rep",
                "Not entered by rep",
                rep_amt
            ],
            "Extracted from Photo": [
                res['vendor'] or "Not detected",
                res['receipt_date'] or "Not detected",
                res['receipt_number'] or "None / Cash slip",
                res['gstin'] or "None printed",
                ext_amt
            ],
            "Status": [
                "Extracted" if res['vendor'] else "Missing",
                "ISO Standard" if res['receipt_date'] else "Unverified",
                "Verified" if res['receipt_number'] else "Optional",
                "15-Char GST" if res['gstin'] else "Not Applicable",
                "Extracted" if res['total_amount'] is not None else "Unread"
            ]
        })
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)

        # Compliance Checklist
        st.markdown("#### ⚖️ Tarang Field Expense Policy v3.2 Checklist")
        for rule in res.get('policy_rules', []):
            if rule['passed']:
                st.write(f"✅ **{rule['name']}**: {rule['detail']}")
            else:
                st.write(f"❌ **{rule['name']}**: {rule['detail']}")

        # Receipt image preview
        if img_path and img_path.exists():
            st.markdown("#### 📷 Processed Receipt Photo")
            try:
                img = Image.open(img_path)
                st.image(img, caption=f"Receipt: {img_path.name}", use_container_width=True)
            except Exception as e:
                st.error(f"Cannot display image: {e}")
        else:
            st.info("ℹ️ No physical receipt image attached to this claim on disk.")

    else:
        st.info("👈 Select a claim from **Section 1 (473 Claims)** or upload a photo in **Section 2** on the left to see instant OCR extraction and Policy v3.2 compliance verdict.")
