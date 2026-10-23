# Tarang Pharma Distribution — Automated Expense Receipt Reader & Audit Engine

An automated receipt reading, information extraction, and policy compliance audit system built for **Tarang Pharma Distribution** (Nagpur Division).

This system reads receipt photographs uploaded by field medical representatives, extracts the 5 core accounting fields (Vendor, Bill Date, Bill Number, GSTIN, Total Amount), and deterministically executes **Tarang Field Expense Policy (v3.2)** to automatically approve compliant small bills (< ₹2,000) while routing high-value claims (≥ ₹2,000) and policy exceptions to finance clerks.

---

## 🚀 Quickstart: Clean Machine Setup (60 Seconds)

The entire application runs **100% offline on standard CPU** with **zero paid API keys required**.

### 1. Clone & Install Dependencies
```bash
# Clone the repository
git clone <your-repo-url>
cd Task2_BanaoTech

# Install requirements
pip install -r requirements.txt
```

### 2. Launch the Web Service
```bash
python app.py
```
Open your browser and navigate to: **[http://localhost:8000](http://localhost:8000)**

---

## 📦 Key Deliverables Index

| Deliverable | File | Description |
| :--- | :--- | :--- |
| **1. Predictions File** | [`predictions.csv`](./predictions.csv) | Final predictions for all 190 claims in `claims_test.csv` matching `sample_submission.csv`. |
| **2. Working Service** | [`app.py`](./app.py) + [`static/`](./static/) | FastAPI backend with `POST /api/check-claim` and a single-screen review dashboard. |
| **3. Evidence of Performance** | [`evaluate.py`](./evaluate.py) | Evaluation benchmark measuring accuracy against ground-truth `claims_train.csv`. |
| **4. Executive Memo** | [`memo.md`](./memo.md) | One-page business memo to Nilesh Agrawal stating savings in rupees and recommendations. |
| **5. 3-Minute Video Script**| [`demo_guide.md`](./demo_guide.md) | Cues and timestamped script for recording the 3-minute video walkthrough. |
| **6. Submission Form** | [`submission-form.md`](./submission-form.md) | Completed answers to all 11 ATSLite evaluation questions. |
| **7. Image Downloader** | [`download_images.py`](./download_images.py) | High-speed multi-threaded script that downloaded all 467 photos from ATSLite. |

---

## 🛠️ Architecture & How It Works

```
[ Receipt Photo + Claim Metadata ]
               │
               ▼
   [ RapidOCR ONNX Engine ] ────────► Extracts Raw Text & Bounding Boxes (Zero Cost)
               │
               ▼
   [ Smart Field Post-Processor ] ──► Standardizes:
                                      • Vendor (Title-case header detection)
                                      • Date (Standardized to ISO YYYY-MM-DD)
                                      • Bill Number (Regex pattern matching)
                                      • GSTIN (15-character checksum regex)
                                      • Total Amount (Keyword-anchored grand totals)
               │
               ▼
   [ Policy Audit Engine (v3.2) ] ──► Applies Tarang Business Rules:
                                      • Rule 1: Amount < ₹2,000 auto-approval ceiling
                                      • Rule 2: Claimed vs. Receipt amount tolerance (₹10)
                                      • Rule 3: Fuel vehicle registration match (employees.csv)
                                      • Rule 4: Lodging GST tax invoice verification & grade cap
                                      • Rule 5: Doctor meal cap (₹2,500)
                                      • Rule 6: Duplicate bill number detection across history
               │
               ▼
      ┌─────────────────┐
      │  Final Verdict  │ ──► "APPROVE" (Paid in weekly run without clerk)
      └─────────────────┘ ──► "REVIEW"  (Routed to clerk with detailed reasons)
```

---

## 📊 Summary of Predictions (`predictions.csv`)

For the 190 test claims in `claims_test.csv`:
- **Total Claims Processed**: 190
- **Auto-Approved (`approve`)**: 142 claims (74.7%)
- **Clerk Review (`review`)**: 48 claims (25.3%)
  - *Breakdown of Review Flags*:
    - High-value claims (≥ ₹2,000 threshold): ~16 claims
    - Missing / unreadable bill photos (failed uploads): 14 claims
    - Fuel vehicle number mismatches: ~11 claims
    - Lodging missing GST invoice / over-limit: ~5 claims
    - Amount discrepancies (> ₹10 mismatch): ~2 claims

---

## 🔬 How to Re-Run Predictions or Evaluation

### Regenerate `predictions.csv`:
```bash
python generate_predictions.py
```

### Run Accuracy Benchmark on `claims_train.csv`:
```bash
python evaluate.py
```

---

## 🌐 API Endpoint Specification

### `POST /api/check-claim`
Evaluates a single expense claim and receipt photograph.

**Form Data Parameters:**
- `file`: *(Optional)* Image file upload (JPEG/PNG).
- `existing_image`: *(Optional)* Filename of an existing receipt in `images/`.
- `claim_id`: Claim identifier (e.g. `CLM-31086`).
- `emp_id`: Representative ID (e.g. `TPD-0412`).
- `category`: `Fuel` | `Food` | `Lodging` | `Local travel` | `Courier` | `Parking`.
- `amount_claimed`: Amount claimed by representative (₹).
- `expense_date`: Date entered by representative.
- `vendor`: Vendor entered by representative.
- `rep_comment`: *(Optional)* Representative's comment.

**Example Response:**
```json
{
  "claim_id": "CLM-31086",
  "extracted_fields": {
    "vendor": "HPCL",
    "receipt_date": "2026-07-18",
    "receipt_number": "002229",
    "gstin": "27AAACH1234D1Z5",
    "total_amount": 300.0
  },
  "decision": "approve",
  "reasons": [
    "auto-approved: valid receipt under Rs 2,000 adhering to policy"
  ],
  "policy_rules": [
    {
      "name": "Under ₹2,000 Threshold",
      "passed": true,
      "detail": "Receipt amount is ₹300.00 (< ₹2,000 auto-approval threshold)"
    },
    {
      "name": "Amount Accuracy",
      "passed": true,
      "detail": "Claimed ₹300.00 matches receipt ₹300.00"
    },
    {
      "name": "Fuel Vehicle Verification",
      "passed": true,
      "detail": "Vehicle MH31 EK 4471 verified on bill"
    }
  ],
  "confidence": 94.2,
  "engine": "RapidOCR ONNX (Local Zero-Cost)"
}
```

---

## 💼 Business Impact & Savings for Nilesh

- **Manual Typing Reduction**: From 140 hours to ~15 hours/month (**89.1% time saved**).
- **Direct Clerk Payroll Savings**: **₹38,000/month** by redeploying 1 finance clerk.
- **Query Cost Reductions**: **₹6,480/month** saved in wasted clerk/rep time.
- **Leakage Prevention**: **₹25,000 to ₹35,000/month** recovered from duplicate/fraudulent claims.
- **Total Net Monthly Benefit**: **~₹74,920/month (~₹9.0 Lakhs/year)**.
- **Software Running Cost**: **₹0.00** using local ONNX inference.

---

## 📜 License
Developed for Tarang Pharma Distribution. Provided as-is under MIT License.
