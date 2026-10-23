// Tarang Receipt Reader & Audit Engine - Client App
document.addEventListener("DOMContentLoaded", () => {
  const sampleSelector = document.getElementById("sampleSelector");
  const empSelect = document.getElementById("empId");
  const claimForm = document.getElementById("claimForm");
  const fileInput = document.getElementById("fileInput");
  const dropzone = document.getElementById("dropzone");
  const dropzonePrompt = document.getElementById("dropzonePrompt");
  const dropzonePreview = document.getElementById("dropzonePreview");
  const previewImg = document.getElementById("previewImg");
  const removeImgBtn = document.getElementById("removeImgBtn");
  const analyzeBtn = document.getElementById("analyzeBtn");

  const emptyState = document.getElementById("emptyState");
  const resultsContainer = document.getElementById("resultsContainer");
  const decisionBanner = document.getElementById("decisionBanner");
  const decisionBadge = document.getElementById("decisionBadge");
  const decisionText = document.getElementById("decisionText");
  const decisionTitle = document.getElementById("decisionTitle");
  const decisionReason = document.getElementById("decisionReason");
  const confidenceBadge = document.getElementById("confidenceBadge");
  const rulesList = document.getElementById("rulesList");
  const fieldsTableBody = document.getElementById("fieldsTableBody");
  const resultReceiptImg = document.getElementById("resultReceiptImg");

  let selectedExistingImage = null;
  let sampleClaimsCache = [];

  // 1. Initialize Employees
  async function loadEmployees() {
    try {
      const res = await fetch("/api/employees");
      const data = await res.json();
      empSelect.innerHTML = "";
      for (const [id, emp] of Object.entries(data)) {
        const opt = document.createElement("option");
        opt.value = id;
        opt.textContent = `${id} (${emp.name} - ${emp.grade} • ${emp.headquarter})`;
        empSelect.appendChild(opt);
      }
    } catch (err) {
      console.error("Failed to load employees:", err);
    }
  }

  // 2. Initialize Sample Claims for 1-Click Testing
  async function loadSampleClaims() {
    try {
      const res = await fetch("/api/sample-claims");
      sampleClaimsCache = await res.json();
      
      sampleClaimsCache.forEach((sample, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `[${sample.claim_id}] ${sample.category} • ₹${sample.amount_claimed} • ${sample.vendor}`;
        sampleSelector.appendChild(opt);
      });
    } catch (err) {
      console.error("Failed to load sample claims:", err);
    }
  }

  // 3. Handle Sample Claim Selection
  sampleSelector.addEventListener("change", (e) => {
    const val = e.target.value;
    if (val === "") return;
    
    const sample = sampleClaimsCache[parseInt(val)];
    if (!sample) return;

    document.getElementById("claimId").value = sample.claim_id;
    document.getElementById("category").value = sample.category;
    document.getElementById("amountClaimed").value = sample.amount_claimed;
    document.getElementById("expenseDate").value = sample.expense_date;
    document.getElementById("vendor").value = sample.vendor;
    document.getElementById("repComment").value = sample.rep_comment || "";
    
    if (sample.emp_id) {
      empSelect.value = sample.emp_id;
    }

    if (sample.image_file) {
      selectedExistingImage = sample.image_file;
      const imgUrl = `/images/${sample.image_file}`;
      previewImg.src = imgUrl;
      dropzonePrompt.classList.add("hidden");
      dropzonePreview.classList.remove("hidden");
    }

    // Automatically trigger analysis
    runAudit();
  });

  // 4. File Drop & Picker Handlers
  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  function handleFileSelected(file) {
    selectedExistingImage = null;
    const reader = new FileReader();
    reader.onload = (evt) => {
      previewImg.src = evt.target.result;
      dropzonePrompt.classList.add("hidden");
      dropzonePreview.classList.remove("hidden");
    };
    reader.readAsDataURL(file);
  }

  removeImgBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.value = "";
    selectedExistingImage = null;
    previewImg.src = "";
    dropzonePreview.classList.add("hidden");
    dropzonePrompt.classList.remove("hidden");
  });

  // 5. Submit Form & Run Audit
  claimForm.addEventListener("submit", (e) => {
    e.preventDefault();
    runAudit();
  });

  async function runAudit() {
    analyzeBtn.disabled = true;
    analyzeBtn.innerHTML = `
      <svg class="spinner" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
        <path d="M12 2a10 10 0 0 1 10 10"></path>
      </svg>
      <span>Analyzing Receipt & Audit Rules...</span>
    `;

    const formData = new FormData();
    formData.append("claim_id", document.getElementById("claimId").value);
    formData.append("emp_id", empSelect.value);
    formData.append("category", document.getElementById("category").value);
    formData.append("amount_claimed", document.getElementById("amountClaimed").value);
    formData.append("expense_date", document.getElementById("expenseDate").value);
    formData.append("vendor", document.getElementById("vendor").value);
    formData.append("rep_comment", document.getElementById("repComment").value);

    if (fileInput.files.length > 0) {
      formData.append("file", fileInput.files[0]);
    } else if (selectedExistingImage) {
      formData.append("existing_image", selectedExistingImage);
    }

    try {
      const res = await fetch("/api/check-claim", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      renderResults(data);
    } catch (err) {
      console.error("Audit error:", err);
      alert("Failed to analyze claim: " + err.message);
    } finally {
      analyzeBtn.disabled = false;
      analyzeBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        <span>Run Receipt Audit & Extraction</span>
      `;
    }
  }

  // 6. Render Results
  function renderResults(data) {
    emptyState.classList.add("hidden");
    resultsContainer.classList.remove("hidden");

    // Decision Banner
    const isApprove = data.decision.toLowerCase() === "approve";
    decisionBanner.className = `decision-banner ${isApprove ? "approve" : "review"}`;
    decisionText.textContent = isApprove ? "APPROVE" : "REVIEW REQUIRED";
    
    if (isApprove) {
      decisionTitle.textContent = "Auto-Approved for Weekly Reimbursement";
      decisionReason.textContent = "Receipt validated: amount < ₹2,000, zero policy exceptions, zero duplicate flags.";
    } else {
      decisionTitle.textContent = "Flagged for Finance Clerk Review";
      decisionReason.textContent = data.reasons.join(" • ") || "Requires manual inspection by finance clerk.";
    }

    confidenceBadge.textContent = `Confidence: ${data.confidence}% (${data.ocr_lines_count} lines)`;

    // Policy Checklist
    rulesList.innerHTML = "";
    (data.policy_rules || []).forEach(rule => {
      const item = document.createElement("div");
      item.className = `rule-item ${rule.passed ? "passed" : "failed"}`;
      item.innerHTML = `
        <span class="rule-status">${rule.passed ? "✓" : "!"}</span>
        <span class="rule-name">${rule.name}</span>
        <span class="rule-detail">${rule.detail}</span>
      `;
      rulesList.appendChild(item);
    });

    // Fields Table
    const fields = data.extracted_fields || {};
    fieldsTableBody.innerHTML = `
      <tr>
        <td class="field-name">Vendor Name</td>
        <td class="field-value">${fields.vendor || "<em>Not detected</em>"}</td>
        <td><span class="status-badge ${fields.vendor ? "verified" : "review"}">${fields.vendor ? "Extracted" : "Missing"}</span></td>
      </tr>
      <tr>
        <td class="field-name">Receipt Date</td>
        <td class="field-value">${fields.receipt_date || "<em>Not detected</em>"}</td>
        <td><span class="status-badge ${fields.receipt_date ? "verified" : "review"}">${fields.receipt_date ? "ISO Standard" : "Unverified"}</span></td>
      </tr>
      <tr>
        <td class="field-name">Bill / Receipt Number</td>
        <td class="field-value">${fields.receipt_number || "<em>None / Cash slip</em>"}</td>
        <td><span class="status-badge ${fields.receipt_number ? "verified" : "review"}">${fields.receipt_number ? "Verified" : "Optional"}</span></td>
      </tr>
      <tr>
        <td class="field-name">GSTIN</td>
        <td class="field-value">${fields.gstin || "<em>None printed</em>"}</td>
        <td><span class="status-badge ${fields.gstin ? "verified" : "review"}">${fields.gstin ? "Valid 15-char" : "None"}</span></td>
      </tr>
      <tr>
        <td class="field-name">Total Amount</td>
        <td class="field-value">₹${fields.total_amount !== null ? Number(fields.total_amount).toFixed(2) : "0.00"}</td>
        <td><span class="status-badge ${fields.total_amount ? "verified" : "review"}">${fields.total_amount ? "Matched" : "Unverified"}</span></td>
      </tr>
    `;

    // Receipt Image Preview
    if (data.image_url) {
      resultReceiptImg.src = data.image_url;
      resultReceiptImg.parentElement.classList.remove("hidden");
    } else {
      resultReceiptImg.parentElement.classList.add("hidden");
    }
  }

  // Initial Load
  loadEmployees();
  loadSampleClaims();
});
