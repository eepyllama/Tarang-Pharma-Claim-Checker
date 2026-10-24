# 3-Minute Video Walkthrough & Screen Recording Script
**For Tarang Pharma Expense Receipt Reading & Audit System**

Use this script to record your 3-minute demonstration video (using Loom, OBS, or Chrome screen recorder).

---

### Timing & Sequence Overview (Total: 3 minutes)
22222222222222222222222
| Timestamp | Phase | What to Show on Screen | What to Say (Voiceover) |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:35** | **The Problem & Setup** | Terminal showing `python app.py` launching, browser opening to `http://localhost:8000` | *"Hi, I'm presenting our automated Receipt Reading & Audit Engine for Tarang Pharma Distribution. Today, two finance clerks spend 140 hours every month manually typing ~2,400 receipt photos into ERP. Nilesh Agrawal asked for a tool that reads bills at >95% accuracy, auto-approves compliant claims under ₹2,000, and cuts clerical workload. Here is the working service."* |
| **0:35 – 1:15** | **Live Demo: Auto-Approval (< ₹2,000)** | Select a sample claim from dropdown (e.g. Fuel claim for ₹300 at Laxmi Auto Fuels). Click **"Analyze Claim"**. | *"Notice our intuitive audit screen. I select a live field claim: ₹300 fuel expense in Nagpur. The system runs our local RapidOCR engine in ~2 seconds. It extracts the vendor 'Laxmi Auto Fuels', receipt date '2026-06-11', receipt number '003350', GSTIN, and amount ₹300.00. Notice the vehicle registration check: it matched employee vehicle 'MH32 AY 2051'. Because all policy rules pass and the amount is under ₹2,000, it receives an instant 'APPROVE' verdict without any clerk needing to touch it."* |
| **1:15 – 2:05** | **Live Demo: Exception & Policy Review (≥ ₹2,000 & Violations)** | Select a Lodging claim (e.g. Hotel bill for ₹2,352). Click **"Analyze Claim"**. Then select a claim with a violation or duplicate. | *"Now let's examine an exception case: a hotel bill of ₹2,352. The engine correctly reads the GST invoice, vendor, and amount. Because ₹2,352 is above Nilesh's ₹2,000 threshold, the system flags it for 'REVIEW' with a clear explanation: 'Amount ₹2,352 >= ₹2,000 (clerk review required)'. Clerks don't have to type anything; they simply glance at the pre-extracted fields and hit confirm. The system also catches policy violations: missing bills, vehicle mismatches, and duplicate submissions."* |
| **2:05 – 2:45** | **The Financial Numbers for Nilesh** | Show `memo.md` on screen, highlighting the ROI table. | *"Let's talk rupees for Nilesh. 90% of Tarang's 2,400 monthly claims are under ₹2,000. By auto-approving compliant small bills, manual typing drops from 140 hours to just 15 hours a month — an 89% reduction in clerical labor. This saves ₹38,000/month by redeploying one clerk, saves ₹6,480/month in query friction, and recovers ₹25,000+ in duplicate leakage, delivering a net monthly benefit of ~₹75,000 (₹9 Lakhs annually). Best of all, our engine runs 100% offline with zero external API fees."* |
| **2:45 – 3:00** | **Conclusion & Clean Handoff** | Show terminal showing `predictions.csv` and `evaluate.py`. | *"All 190 predictions for claims_test.csv are generated in predictions.csv strictly formatted to sample_submission specifications. The system starts on any clean machine via 'python app.py' with zero configuration. Thank you!"* |

---

### Tips for Recording
1. Keep the browser window maximized to 1080p.
2. Have the web app already running so you don't waste seconds waiting for terminal boots.
3. Speak clearly and confidently; the judges look for strong business acumen and crisp technical communication.
