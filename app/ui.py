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

st.title("🧾 Tarang Pharma Distribution — Expense Receipt Audit")
st.caption("Field Expense Policy v3.2 • Automated Audit & Extraction Engine")

pipeline = ExpensePipeline()
employees = load_employee_directory()

# Top metric pills
col1, col2, col3, col4 = st.columns(4)
col1.metric("Auto-Approval Ceiling", "₹2,000", "Under ₹2k Auto-approved")
col2.metric("Target Accuracy", ">95%", "On 5 accounting fields")
col3.metric("Clerk Workload", "-89%", "2,400 → ~260 claims/mo")
col4.metric("Net Monthly Savings", "₹74,920", "Direct clerk ROI")

st.divider()

# Layout
left_col, right_col = st.columns([1, 1.2])

with left_col:
    st.subheader("1. Claim & Receipt Input")
    
    # Quick Test Selector
    test_csv = settings.resolve_raw_file("claims_test.csv")
    sample_df = None
    if test_csv.exists():
        sample_df = pd.read_csv(test_csv)
        claim_options = ["-- Select a real field claim to test --"] + [
            f"{r['claim_id']} | {r['category']} | ₹{r['amount_claimed']} | {r['vendor']}"
            for _, r in sample_df.head(20).iterrows()
        ]
        selected_option = st.selectbox("⚡ Quick Test with Field Claims:", claim_options)
    else:
        selected_option = None

    selected_claim = None
    if selected_option and selected_option != "-- Select a real field claim to test --":
        cid = selected_option.split(" | ")[0]
        selected_claim = sample_df[sample_df['claim_id'] == cid].iloc[0].to_dict()

    # Form
    with st.form("claim_input_form"):
        claim_id = st.text_input("Claim ID", value=selected_claim['claim_id'] if selected_claim else "CLM-31086")
        
        emp_keys = list(employees.keys())
        default_emp_idx = 0
        if selected_claim and selected_claim.get('emp_id') in emp_keys:
            default_emp_idx = emp_keys.index(selected_claim['emp_id'])
            
        emp_id = st.selectbox(
            "Representative (Employee ID)",
            emp_keys,
            index=default_emp_idx,
            format_func=lambda x: f"{x} - {employees[x]['name']} ({employees[x]['grade']})"
        )

        cat_options = ["Fuel", "Food", "Lodging", "Local travel", "Courier", "Parking"]
        default_cat_idx = 0
        if selected_claim and selected_claim.get('category') in cat_options:
            default_cat_idx = cat_options.index(selected_claim['category'])
            
        category = st.selectbox("Expense Category", cat_options, index=default_cat_idx)
        amount_claimed = st.text_input("Amount Claimed (₹)", value=str(selected_claim['amount_claimed']) if selected_claim else "300.00")
        expense_date = st.text_input("Expense Date", value=str(selected_claim['expense_date']) if selected_claim else "2026-06-11")
        vendor = st.text_input("Vendor (as entered by rep)", value=str(selected_claim['vendor']) if selected_claim else "Laxmi Auto Fuels")
        rep_comment = st.text_input("Rep Comment", value=str(selected_claim.get('rep_comment', '')) if selected_claim else "Two wheeler petrol")

        uploaded_file = st.file_uploader("Upload Receipt Photo (optional)", type=["jpg", "jpeg", "png"])
        submitted = st.form_submit_button("🔍 Run Receipt Audit & Policy Check", use_container_width=True)

with right_col:
    st.subheader("2. Audit Verdict & Extraction")
    
    # Determine image path
    image_path = None
    if uploaded_file:
        temp_img_path = settings.IMAGES_DIR / f"temp_{uploaded_file.name}"
        with open(temp_img_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        image_path = temp_img_path
    elif selected_claim and selected_claim.get('image_file'):
        image_path = settings.resolve_image_path(selected_claim['image_file'])

    if submitted or selected_claim:
        claim_dict = {
            'claim_id': claim_id,
            'emp_id': emp_id,
            'category': category,
            'amount_claimed': amount_claimed,
            'expense_date': expense_date,
            'vendor': vendor,
            'rep_comment': rep_comment,
            'image_file': selected_claim.get('image_file', '') if selected_claim else ""
        }

        with st.spinner("Analyzing receipt and policy rules..."):
            res = pipeline.process_claim(claim_dict, image_path=image_path)

        # Decision Banner
        if res['decision'].lower() == "approve":
            st.success("### ✅ VERDICT: APPROVE (Auto-Approved for Payment)")
            st.info(f"**Policy Rationale:** {res['reason']}")
        else:
            st.warning("### ⚠️ VERDICT: REVIEW REQUIRED (Flagged for Clerk)")
            st.error(f"**Exception Reason:** {res['reason']}")

        # Extracted fields table
        st.markdown("#### 📋 Extracted Accounting Fields")
        fields_data = {
            "Field": ["Vendor Name", "Receipt Date", "Bill / Receipt No", "GSTIN", "Total Amount"],
            "Extracted Value": [
                res['vendor'] or "Not detected",
                res['receipt_date'] or "Not detected",
                res['receipt_number'] or "None / Cash slip",
                res['gstin'] or "None printed",
                f"₹{float(res['total_amount']):.2f}" if res['total_amount'] is not None else "Unverified"
            ]
        }
        st.dataframe(pd.DataFrame(fields_data), use_container_width=True, hide_index=True)

        # Policy rules
        st.markdown("#### ⚖️ Compliance Checklist")
        for rule in res.get('policy_rules', []):
            if rule['passed']:
                st.write(f"✅ **{rule['name']}**: {rule['detail']}")
            else:
                st.write(f"❌ **{rule['name']}**: {rule['detail']}")

        # Receipt image preview
        if image_path and image_path.exists():
            st.markdown("#### 📷 Receipt Image")
            try:
                img = Image.open(image_path)
                st.image(img, caption=f"Receipt: {image_path.name}", use_container_width=True)
            except Exception as e:
                st.error(f"Cannot display image: {e}")
    else:
        st.info("👈 Select a sample claim or upload a receipt on the left to view the live audit results.")
