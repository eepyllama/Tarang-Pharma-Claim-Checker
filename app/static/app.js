// Tarang Pharma Distribution - Expense Receipt Reader & Audit Engine
// Handles:
// 1. Section 1: Pre-loaded Field Claims Explorer (473 Claims: 190 Test + 283 Train) with batch & category filters
// 2. Section 2: Upload Receipt Photo & Manual Audit with drag-and-drop dropzone
// 3. Side-by-side policy audit verdict, rules checklist, and receipt inspection

document.addEventListener("DOMContentLoaded", () => {
  // --- Section 1 Elements (Field Claims Explorer) ---
  const datasetFilter = document.getElementById("datasetFilter");
  const categoryFilter = document.getElementById("categoryFilter");
  const fieldClaimSelect = document.getElementById("fieldClaimSelect");
  const filteredCount = document.getElementById("filteredCount");
  const auditFieldClaimBtn = document.getElementById("auditFieldClaimBtn");

  const sumClaimId = document.getElementById("sumClaimId");
  const sumEmpName = document.getElementById("sumEmpName");
  const sumCategory = document.getElementById("sumCategory");
  const sumAmount = document.getElementById("sumAmount");
  const sumVendor = document.getElementById("sumVendor");
  const sumDate = document.getElementById("sumDate");
  const sumComment = document.getElementById("sumComment");
  const sumImageFile = document.getElementById("sumImageFile");

  // --- Section 2 Elements (Photo Upload & Custom Audit) ---
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const dropzonePrompt = document.getElementById("dropzonePrompt");
  const dropzonePreview = document.getElementById("dropzonePreview");
  const previewImg = document.getElementById("previewImg");
  const removeImgBtn = document.getElementById("removeImgBtn");
  const uploadClaimForm = document.getElementById("uploadClaimForm");
  const auditUploadedPhotoBtn = document.getElementById("auditUploadedPhotoBtn");

  const customClaimId = document.getElementById("customClaimId");
  const customEmpId = document.getElementById("customEmpId");
  const customCategory = document.getElementById("customCategory");
  const customAmount = document.getElementById("customAmount");
  const customDate = document.getElementById("customDate");
  const customVendor = document.getElementById("customVendor");
  const customComment = document.getElementById("customComment");

  // --- Right Column Results Elements ---
  const emptyState = document.getElementById("emptyState");
  const resultsContainer = document.getElementById("resultsContainer");
  const auditSourceInfo = document.getElementById("auditSourceInfo");
  const decisionBanner = document.getElementById("decisionBanner");
  const decisionBadge = document.getElementById("decisionBadge");
  const decisionTitle = document.getElementById("decisionTitle");
  const decisionReason = document.getElementById("decisionReason");
  const confidenceBadge = document.getElementById("confidenceBadge");
  const fieldsTableBody = document.getElementById("fieldsTableBody");
  const rulesList = document.getElementById("rulesList");
  const resultReceiptImg = document.getElementById("resultReceiptImg");
  const receiptViewerWrapper = document.getElementById("receiptViewerWrapper");

  // --- Header Stats Elements ---
  const claimsCountStat = document.getElementById("claimsCountStat");
  const approvalRateStat = document.getElementById("approvalRateStat");
  const engineStatus = document.getElementById("engineStatus");

  // --- In-Memory State ---
  let allClaims = [];
  let filteredClaims = [];
  let selectedFieldClaim = null;
  let employeesMap = {};

  // ==========================================
  // 1. Initial Data Loaders
  // ==========================================
  async function init() {
    await Promise.all([
      loadEmployees(),
      loadAllClaims(),
      loadEngineStatus(),
      loadDashboardStats()
    ]);
  }

  async function loadEmployees() {
    try {
      const res = await fetch("/api/employees");
      employeesMap = await res.json();
      if (customEmpId) {
        customEmpId.innerHTML = "";
        for (const [id, emp] of Object.entries(employeesMap)) {
          const opt = document.createElement("option");
          opt.value = id;
          opt.textContent = `${id} (${emp.name} - ${emp.grade} • ${emp.headquarter})`;
          customEmpId.appendChild(opt);
        }
      }
    } catch (err) {
      console.error("Failed to load employees:", err);
    }
  }

  async function loadAllClaims() {
    try {
      const res = await fetch("/api/sample-claims");
      allClaims = await res.json();

      if (claimsCountStat) {
        claimsCountStat.textContent = `${allClaims.length} Claims`;
      }

      // Apply initial filters (Test batch by default, or all)
      applyFilters();
    } catch (err) {
      console.error("Failed to load claims:", err);
      fieldClaimSelect.innerHTML = `<option value="">Error loading claims: ${err.message}</option>`;
    }
  }

  async function loadEngineStatus() {
    try {
      const res = await fetch("/api/ai-status");
      const data = await res.json();
      if (engineStatus && data.active_engine) {
        engineStatus.textContent = "RapidOCR (Offline • ₹0/claim)";
      }
    } catch (e) {
      // Keep default
    }
  }

  async function loadDashboardStats() {
    try {
      const res = await fetch("/api/stats");
      const data = await res.json();
      if (approvalRateStat && data.approval_rate !== undefined) {
        approvalRateStat.textContent = `${data.approval_rate}%`;
      }
    } catch (e) {
      // Keep default
    }
  }

  // ==========================================
  // 2. Section 1: Filters & Dropdown Logic
  // ==========================================
  function applyFilters() {
    const dVal = datasetFilter.value;
    const cVal = categoryFilter.value;

    filteredClaims = allClaims.filter(c => {
      // Dataset filter
      if (dVal === "test" && !c.dataset.toLowerCase().includes("test")) return false;
      if (dVal === "train" && !c.dataset.toLowerCase().includes("train")) return false;

      // Category filter
      if (cVal !== "all" && c.category.toLowerCase() !== cVal.toLowerCase()) return false;

      return true;
    });

    // Update count indicator
    filteredCount.textContent = `Showing ${filteredClaims.length} of ${allClaims.length} claims`;

    // Rebuild select options
    fieldClaimSelect.innerHTML = "";

    if (filteredClaims.length === 0) {
      const emptyOpt = document.createElement("option");
      emptyOpt.value = "";
      emptyOpt.textContent = "-- No claims match current filter criteria --";
      fieldClaimSelect.appendChild(emptyOpt);
      clearClaimSummary();
      return;
    }

    filteredClaims.forEach((claim, idx) => {
      const opt = document.createElement("option");
      opt.value = idx;
      const batchTag = claim.dataset.includes("Test") ? "Test" : "Train";
      const imgTag = claim.has_image ? "📷" : "⚠️ No img";
      opt.textContent = `[${claim.claim_id}] ${claim.category} • ₹${claim.amount_claimed} • ${claim.vendor} (${batchTag} | ${imgTag})`;
      fieldClaimSelect.appendChild(opt);
    });

    // Auto-select first item
    fieldClaimSelect.selectedIndex = 0;
    selectFieldClaim(filteredClaims[0]);
  }

  function selectFieldClaim(claim) {
    if (!claim) {
      clearClaimSummary();
      return;
    }

    selectedFieldClaim = claim;

    sumClaimId.textContent = claim.claim_id;
    sumEmpName.textContent = `${claim.employee_name || claim.emp_id} (${claim.emp_id})`;
    sumCategory.textContent = claim.category;
    sumAmount.textContent = `₹${parseFloat(claim.amount_claimed || 0).toFixed(2)}`;
    sumVendor.textContent = claim.vendor || "Not specified";
    sumDate.textContent = claim.expense_date || "Not specified";
    sumComment.textContent = claim.rep_comment ? `"${claim.rep_comment}"` : "None";
    
    if (claim.image_file) {
      sumImageFile.textContent = claim.image_file;
      sumImageFile.className = claim.has_image ? "meta-val file-tag" : "meta-val file-tag text-muted";
    } else {
      sumImageFile.textContent = "No photo attached";
      sumImageFile.className = "meta-val file-tag text-muted";
    }

    // If it has an image on disk, pre-load in results receipt viewer
    if (claim.has_image && claim.image_file) {
      resultReceiptImg.src = `/images/${claim.image_file}`;
      receiptViewerWrapper.classList.remove("hidden");
    }
  }

  function clearClaimSummary() {
    selectedFieldClaim = null;
    sumClaimId.textContent = "-";
    sumEmpName.textContent = "-";
    sumCategory.textContent = "-";
    sumAmount.textContent = "-";
    sumVendor.textContent = "-";
    sumDate.textContent = "-";
    sumComment.textContent = "-";
    sumImageFile.textContent = "None";
  }

  // Filter change events
  datasetFilter.addEventListener("change", applyFilters);
  categoryFilter.addEventListener("change", applyFilters);

  // Dropdown select event
  fieldClaimSelect.addEventListener("change", (e) => {
    const idx = parseInt(e.target.value);
    if (!isNaN(idx) && filteredClaims[idx]) {
      selectFieldClaim(filteredClaims[idx]);
    }
  });

  // Section 1 Audit Button Click
  auditFieldClaimBtn.addEventListener("click", () => {
    if (!selectedFieldClaim) {
      alert("Please select a valid claim from the dropdown first.");
      return;
    }
    runAuditForClaim(selectedFieldClaim, "section1");
  });

  // ==========================================
  // 3. Section 2: Photo Upload & Manual Form
  // ==========================================
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
      handlePhotoSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handlePhotoSelected(e.target.files[0]);
    }
  });

  function handlePhotoSelected(file) {
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
    previewImg.src = "";
    dropzonePreview.classList.add("hidden");
    dropzonePrompt.classList.remove("hidden");
  });

  // Section 2 Form Submit (Manual Audit)
  uploadClaimForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const manualClaim = {
      claim_id: customClaimId.value.trim() || "CLM-CUSTOM",
      emp_id: customEmpId.value,
      employee_name: employeesMap[customEmpId.value]?.name || customEmpId.value,
      category: customCategory.value,
      amount_claimed: customAmount.value.trim(),
      expense_date: customDate.value.trim(),
      vendor: customVendor.value.trim(),
      rep_comment: customComment.value.trim(),
      has_upload: fileInput.files.length > 0
    };

    runAuditForClaim(manualClaim, "section2");
  });

  // ==========================================
  // 4. Shared Audit Execution & API Call
  // ==========================================
  async function runAuditForClaim(claimData, source) {
    const isSection1 = source === "section1";
    const activeBtn = isSection1 ? auditFieldClaimBtn : auditUploadedPhotoBtn;
    const originalBtnHtml = activeBtn.innerHTML;

    // Show loading spinner
    activeBtn.disabled = true;
    activeBtn.innerHTML = `
      <svg class="spinner" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
        <path d="M12 2a10 10 0 0 1 10 10"></path>
      </svg>
      <span>Analyzing Receipt with RapidOCR...</span>
    `;

    const formData = new FormData();
    formData.append("claim_id", claimData.claim_id || "CLM-MANUAL");
    formData.append("emp_id", claimData.emp_id || "TPD-0412");
    formData.append("category", claimData.category || "Fuel");
    formData.append("amount_claimed", claimData.amount_claimed || "0.00");
    formData.append("expense_date", claimData.expense_date || "2026-07-20");
    formData.append("vendor", claimData.vendor || "");
    formData.append("rep_comment", claimData.rep_comment || "");

    if (isSection1) {
      if (claimData.image_file) {
        formData.append("existing_image", claimData.image_file);
      }
    } else {
      if (fileInput.files.length > 0) {
        formData.append("file", fileInput.files[0]);
      }
    }

    try {
      const res = await fetch("/api/check-claim", {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }

      const data = await res.json();
      renderAuditResults(data, claimData, source);
    } catch (err) {
      console.error("Audit error:", err);
      alert("Failed to analyze receipt: " + err.message);
    } finally {
      activeBtn.disabled = false;
      activeBtn.innerHTML = originalBtnHtml;
    }
  }

  // ==========================================
  // 5. Render Audit Verdict & Policy Details
  // ==========================================
  function renderAuditResults(data, claimData, source) {
    emptyState.classList.add("hidden");
    resultsContainer.classList.remove("hidden");

    // Header info tag
    if (source === "section1") {
      auditSourceInfo.textContent = `Audited from Section 1: Pre-Loaded Field Claim ${claimData.claim_id} (${claimData.dataset || 'Dataset'})`;
    } else {
      const photoName = fileInput.files.length > 0 ? fileInput.files[0].name : "Custom Form Data";
      auditSourceInfo.textContent = `Audited from Section 2: Uploaded Receipt Photo (${photoName})`;
    }

    // Decision Banner
    const isApprove = String(data.decision).toLowerCase() === "approve";
    decisionBanner.className = `decision-banner ${isApprove ? "approve" : "review"}`;
    decisionBadge.className = `decision-badge ${isApprove ? "badge-approve" : "badge-review"}`;
    decisionBadge.textContent = isApprove ? "AUTO-APPROVED" : "REVIEW REQUIRED";

    if (isApprove) {
      decisionTitle.textContent = "Auto-Approved for Weekly Direct Reimbursement";
      decisionReason.textContent = "Receipt photo cleanly validated: Total < ₹2,000 ceiling, zero policy breaches, zero duplicate flags. Eligible for payout without finance clerk touch.";
    } else {
      decisionTitle.textContent = "Flagged for Finance Clerk Manual Inspection";
      const reasonsList = data.reasons && data.reasons.length > 0
        ? data.reasons.join(" • ")
        : "Failed one or more mandatory Policy v3.2 verification gates.";
      decisionReason.textContent = reasonsList;
    }

    // Confidence badge
    confidenceBadge.textContent = `OCR Confidence: ${data.confidence}% (${data.ocr_lines_count} lines)`;

    // 5 Accounting Fields Comparison Table
    const fields = data.extracted_fields || {};
    const claimedAmt = parseFloat(claimData.amount_claimed || 0).toFixed(2);
    const extractedAmt = fields.total_amount !== null && fields.total_amount !== undefined
      ? parseFloat(fields.total_amount).toFixed(2)
      : null;

    fieldsTableBody.innerHTML = `
      <tr>
        <td class="field-name"><strong>Vendor Name</strong></td>
        <td class="field-claimed">${escapeHtml(claimData.vendor || "N/A")}</td>
        <td class="field-extracted">${escapeHtml(fields.vendor || "Not detected")}</td>
        <td>
          <span class="status-badge ${fields.vendor ? "verified" : "review"}">
            ${fields.vendor ? "Extracted" : "Missing"}
          </span>
        </td>
      </tr>
      <tr>
        <td class="field-name"><strong>Receipt Date</strong></td>
        <td class="field-claimed">${escapeHtml(claimData.expense_date || "N/A")}</td>
        <td class="field-extracted">${escapeHtml(fields.receipt_date || "Not detected")}</td>
        <td>
          <span class="status-badge ${fields.receipt_date ? "verified" : "review"}">
            ${fields.receipt_date ? "ISO Standard" : "Unverified"}
          </span>
        </td>
      </tr>
      <tr>
        <td class="field-name"><strong>Bill / Receipt #</strong></td>
        <td class="field-claimed"><em>Not provided by rep</em></td>
        <td class="field-extracted">${escapeHtml(fields.receipt_number || "None / Cash slip")}</td>
        <td>
          <span class="status-badge ${fields.receipt_number ? "verified" : "neutral"}">
            ${fields.receipt_number ? "Verified" : "Optional"}
          </span>
        </td>
      </tr>
      <tr>
        <td class="field-name"><strong>GSTIN</strong></td>
        <td class="field-claimed"><em>Not provided by rep</em></td>
        <td class="field-extracted">${escapeHtml(fields.gstin || "None printed")}</td>
        <td>
          <span class="status-badge ${fields.gstin ? "verified" : "neutral"}">
            ${fields.gstin ? "15-Char GST" : "Not Applicable"}
          </span>
        </td>
      </tr>
      <tr>
        <td class="field-name"><strong>Total Amount</strong></td>
        <td class="field-claimed">₹${claimedAmt}</td>
        <td class="field-extracted">₹${extractedAmt !== null ? extractedAmt : "0.00"}</td>
        <td>
          <span class="status-badge ${extractedAmt !== null ? "verified" : "review"}">
            ${extractedAmt !== null ? "Extracted" : "Unread"}
          </span>
        </td>
      </tr>
    `;

    // Policy Checklist Rules
    rulesList.innerHTML = "";
    if (data.policy_rules && data.policy_rules.length > 0) {
      data.policy_rules.forEach(rule => {
        const item = document.createElement("div");
        item.className = `rule-item ${rule.passed ? "passed" : "failed"}`;
        item.innerHTML = `
          <span class="rule-status">${rule.passed ? "✓" : "!"}</span>
          <div class="rule-body">
            <span class="rule-name">${escapeHtml(rule.name)}</span>
            <span class="rule-detail">${escapeHtml(rule.detail)}</span>
          </div>
        `;
        rulesList.appendChild(item);
      });
    }

    // Receipt Image Viewer
    if (data.image_url) {
      resultReceiptImg.src = data.image_url;
      receiptViewerWrapper.classList.remove("hidden");
    } else if (claimData.image_file && claimData.has_image) {
      resultReceiptImg.src = `/images/${claimData.image_file}`;
      receiptViewerWrapper.classList.remove("hidden");
    } else {
      receiptViewerWrapper.classList.add("hidden");
    }

    // Scroll slightly to results if on mobile
    if (window.innerWidth <= 1024) {
      resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Run on start
  init();
});
