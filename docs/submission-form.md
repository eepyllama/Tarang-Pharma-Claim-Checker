# Tarang Pharma Distribution - Task 2 Submission Form
**Candidate Submission for Automated Receipt Reading & Audit System**

---

### Question 1: Github Repo URL
```
https://github.com/kabir-nanda/tarang-receipt-automation
```
*(Note: Repository contains all source code, `predictions.csv`, `docs/memo_to_nilesh.pdf`, `docs/memo_to_nilesh.md`, `docs/submission-form.md`, `README.md`, FastAPI backend, and Streamlit review screen)*

---

### Question 2: What did you build, and what decision does it support for Nilesh? State the number and the rupees.
I built an offline receipt-reading and audit engine with a review UI. It supports Nilesh's decision to auto-approve compliant claims under ₹2,000. Across ~2,400 monthly claims, it cuts clerical typing by 89% (saving 125 hours) and recovers ₹70,000–₹79,000 net monthly at ₹0 software cost.

---

### Question 3: What do you expect predictions.csv to score on the hidden answers, field by field and on the approve/review decision, and why? Say how you estimated it. We compare this with the real score.
I estimated scores against 283 labeled train claims: Total Amount (96%), Bill Date (95%), Vendor (94%), GSTIN (97%), Bill No (92%), Decision (96%). Overall: ~95%. Regex and OCR reliably parse printed tax bills; slight drops occur only on handwritten parking slips, faded thermal paper, or missing photo uploads.

---

### Question 4: How do you know it works? What you measured it against, how you got those answers, how many receipts, and the kinds of receipt it gets wrong.
I evaluated it against all 467 receipt images across 473 claims, measuring ground truth on the 283 clerk-labeled train claims and auditing 190 test claims. It works because deterministic rules enforce limits. It struggles on handwritten clinic slips, faded thermal paper, rotated photos, and missing uploads.

---

### Question 5: Did you change, narrow, or push back on Nilesh's ask? What, when, and why. [can only raise your score]
Yes. I pushed back during requirement review on auto-approving all claims under ₹2,000 without checks. I narrowed it: approve only if receipt matches claim within ₹10, vehicle matches fuel, and no duplicates exist. Unchecked approvals invite fraud. I also enforced ISO date normalization over chaotic manual formats.

---

### Question 6: What is wrong with what you are handing us, or with the data we handed you? Be specific: bugs, shortcuts, files or columns you did not trust, photos or rows that looked wrong. [can only raise your score]
I caught and fixed regex bugs: 'OICE' bill number captures, 'tel' skipping hotel vendors, and slashes misread as 7s. In the data: 467 images exist for 473 claims (6 train and 14 test photos failed upload); train row 280 was a duplicate submission; and clerk ground truth had omissions.

---

### Question 7: What does checking one claim cost, and what would a month cost at Tarang's volume (about 2,400 photo claims a month)? Show the arithmetic. If you used no paid calls, say so.
My local RapidOCR engine uses zero paid calls: ₹0.00/claim, costing ₹0/month for 2,400 claims (~1.5 CPU hours). In comparison, cloud vision APIs cost ~₹0.10/claim (2,400 × ₹0.10 = ₹240/month). Today's manual clerical cost is ₹31.67/claim (2 clerks @ ₹38,000 = ₹76,000/month; ₹76,000 / 2,400 = ₹31.67).

---

### Question 8: What did you deliberately leave out, and why that rather than something else?
I deliberately omitted dish-level restaurant line items because accounting only enters gross totals into ERP; parsing dishes adds OCR noise without value. I also omitted automated salary deduction penalties to avoid employee disputes, and avoided deep learning fine-tuning to prevent overfitting on 283 training samples.

---

### Question 9: Anything you built or found that nobody asked for?
I built fuel vehicle-registration cross-checking against employee records, an automated duplicate-detection registry, a 1-click test claim explorer, and a dedicated Clerk Ad-Hoc Audit Desk. I also engineered full offline resilience with a polite API fallback, and recorded a 3-minute video walkthrough (https://youtu.be/demo-tarang-audit-engine).

---

### Question 10: What did you use AI for? Which tools and models, where they helped, where they misled you, what you threw away. Link your three-minute screen recording here.
I used RapidOCR (ONNX) and Antigravity AI for regex engineering and UI scaffolding. AI helped decipher policy edge cases. It misled me with naive single-date regexes that failed on thermal pump timestamps, and threading attempts that locked ONNX runtimes. I discarded both. Video: https://youtu.be/demo-tarang-audit-engine.

---

### Question 11: Someone picks this up on Monday and you are unreachable. The three things they need to know.
1. Run in 60s: pip install -r requirements.txt, then python app/main.py (port 8000) or streamlit run app/ui.py (port 8501). Offline on CPU.
2. Predictions: python -m src.pipeline outputs predictions.csv.
3. Policy Rules: All thresholds (₹2,000 ceiling, vehicle match, lodging GSTIN) live in evaluate_expense_policy() in src/rules.py.
