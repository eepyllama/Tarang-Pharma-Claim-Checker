# Tarang Pharma Distribution — Automated Expense Receipt Reader & Audit Engine

An automated receipt reading, information extraction, and policy compliance audit system built for **Tarang Pharma Distribution** (Nagpur Division).

The system processes mobile receipt photographs uploaded by field medical representatives, extracts the 5 core accounting fields (Vendor, Bill Date, Bill Number, GSTIN, Total Amount), and deterministically executes **Tarang Field Expense Policy (v3.2)** to automatically approve compliant small bills (< ₹2,000) while routing high-value claims (≥ ₹2,000) and policy exceptions to finance clerks.

---

## 📁 Project Folder Structure

```text
tarang-expense-automation/
├── data/
│   ├── raw/                  # Original CSVs, PDFs, and text files provided
│   └── images/               # All receipt JPG/PNG files
├── src/
│   ├── __init__.py
│   ├── config.py             # API key loading and polite failure logic
│   ├── extractor.py          # Vision LLM/OCR API calls and JSON parsing
│   ├── rules.py              # Business logic (Rs 2000 threshold, approval routing)
│   └── pipeline.py           # Glues extractor and rules together for batch processing
├── app/
│   ├── main.py               # FastAPI backend endpoint & static UI server
│   ├── ui.py                 # Streamlit frontend audit screen
│   └── static/               # Modern single-screen review UI assets (HTML/CSS/JS)
├── notebooks/
│   └── evaluation.ipynb      # Accuracy measurement against claims_train.csv
├── docs/
│   ├── memo_to_nilesh.pdf    # 1-page executive business memo (PDF)
│   ├── memo_to_nilesh.md     # 1-page executive business memo (Markdown)
│   ├── submission-form.md    # Completed form with video link and expected score
│   └── demo_guide.md         # 3-minute screen recording script
├── predictions.csv           # Final output for claims_test.csv (Root directory)
├── requirements.txt          # Python dependencies
├── .env.example              # Template for optional API keys
├── .gitignore
└── README.md                 # Setup and run instructions
```

---

## 🚀 Quickstart: Clean Machine Setup (60 Seconds)

The entire application runs **100% offline on standard CPU** with **zero paid API keys required**.

### 1. Clone & Install Dependencies
```bash
git clone <your-repo-url>
cd Task2_BanaoTech

pip install -r requirements.txt
```

### 2. Launch the Application Screen

You can run either the **FastAPI Web Application** or the **Streamlit Dashboard**:

#### Option A: FastAPI Single-Screen Web App (Recommended)
```bash
python app/main.py
```
Open **[http://localhost:8000](http://localhost:8000)** in any browser.

#### Option B: Streamlit Dashboard
```bash
streamlit run app/ui.py
```
Open **[http://localhost:8501](http://localhost:8501)**.

---

## 📦 Key Deliverables Index

| Deliverable | File | Description |
| :--- | :--- | :--- |
| **1. Predictions File** | [`predictions.csv`](./predictions.csv) | Final predictions for all 190 claims in `claims_test.csv` strictly matching `sample_submission.csv`. |
| **2. Working Service** | [`app/main.py`](./app/main.py) & [`app/ui.py`](./app/ui.py) | FastAPI backend (`POST /api/check-claim`) and Streamlit dashboard. |
| **3. Evidence of Performance** | [`notebooks/evaluation.ipynb`](./notebooks/evaluation.ipynb) & [`evaluate.py`](./evaluate.py) | Benchmark measuring extraction accuracy and policy agreement against ground truth. |
| **4. Executive Memo** | [`docs/memo_to_nilesh.pdf`](./docs/memo_to_nilesh.pdf) / [`.md`](./docs/memo_to_nilesh.md) | One-page business memo to Nilesh Agrawal stating workload reduction (-89%) and savings in rupees. |
| **5. 3-Minute Video Script**| [`docs/demo_guide.md`](./docs/demo_guide.md) | Timestamped script and cues for recording the 3-minute video walkthrough. |
| **6. Submission Form** | [`docs/submission-form.md`](./docs/submission-form.md) | Completed answers to all 11 ATSLite evaluation questions. |
| **7. Image Downloader** | [`download_images.py`](./download_images.py) | High-speed multi-threaded downloader that retrieved all 467 photos from ATSLite. |

---

## 🛠️ Architecture & Pipeline Flow

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
- **Auto-Approved (`approve`)**: 152 claims (80.0%)
- **Clerk Review (`review`)**: 38 claims (20.0%)
  - *Breakdown of Review Flags*:
    - Missing / unreadable bill photos (failed uploads): 15 claims
    - High-value claims (≥ ₹2,000 threshold): 12 claims
    - Lodging policy exceptions (missing GSTIN / grade limit): 5 claims
    - Fuel vehicle number mismatches: 3 claims
    - Amount discrepancies (> ₹10 mismatch): 3 claims

---

## 🔬 How to Re-Run Predictions or Evaluation

### Regenerate `predictions.csv`:
```bash
python -m src.pipeline
```

### Run Evaluation Suite:
Open and execute [`notebooks/evaluation.ipynb`](./notebooks/evaluation.ipynb) in Jupyter / VS Code or inspect the benchmark logs.

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
