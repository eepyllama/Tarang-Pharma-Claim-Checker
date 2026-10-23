# Tarang Pharma Distribution — Dataset Guidelines

## 🔒 Confidentiality & Data Protection Notice
To comply with corporate privacy guidelines and protect sensitive client information:
- **Raw receipt photographs** (`data/images/*.jpg`), which contain real phone numbers, doctor clinic names, hotel rooms, UPI IDs, and driver signatures, are excluded from public source control.
- **Internal email correspondence** (`data/raw/email-thread.txt`), which contains private executive communications, is excluded from public source control.
- **Proprietary employee database** (`data/raw/employees.csv`), which contains medical representatives' personal vehicle registration numbers and headquarters, is excluded from public source control.
- **Historical raw claims batches** (`data/raw/claims_train.csv`, `data/raw/claims_test.csv`) are excluded from public source control.

---

## 📁 Local Dataset Mounting (For Authorized Evaluators)
If you have received the official proprietary test pack from Nilesh Agrawal / Tarang Pharma Distribution:
1. Place `claims_train.csv`, `claims_test.csv`, and `employees.csv` directly into this directory (`data/raw/`).
2. Place all receipt image files into `data/images/`.
3. The system will automatically detect the files and populate the 473-claim explorer.

## 🚀 Running Without the Proprietary Dataset
The application includes:
- Built-in sanitized demo representatives for testing.
- Live Drag & Drop receipt photo dropzone on the web UI (`http://localhost:8000` and `http://localhost:8501`) that works with **any receipt photo** uploaded by the evaluator.
- Pre-computed predictions in [`predictions.csv`](../../predictions.csv) strictly formatted to [`sample_submission.csv`](./sample_submission.csv).
