// Popup script — handles manual claim input from the extension popup

const claimInput = document.getElementById("claim-input");
const verifyBtn = document.getElementById("verify-btn");
const statusArea = document.getElementById("status-area");
const resultArea = document.getElementById("result-area");

verifyBtn.addEventListener("click", () => {
  const claim = claimInput.value.trim();
  if (!claim) {
    statusArea.innerHTML = '<p class="status error">Please enter a claim.</p>';
    return;
  }
  verifyBtn.disabled = true;
  statusArea.innerHTML = '<p class="status"><span class="spinner"></span> Verifying…</p>';
  resultArea.innerHTML = "";

  chrome.runtime.sendMessage({ action: "api-verify", claim }, (response) => {
    verifyBtn.disabled = false;
    statusArea.innerHTML = "";

    if (response && response.ok) {
      renderResult(response.data, claim);
    } else {
      const err = response?.error || "Cannot reach server. Is the API running on localhost:5001?";
      statusArea.innerHTML = `<p class="status error">❌ ${escapeHtml(err)}</p>`;
    }
  });
});

function renderResult(data, originalClaim) {
  const v = (data.verdict || "").toLowerCase();
  let bg, border, emoji;
  if (v === "true") { bg = "#d4edda"; border = "#28a745"; emoji = "✅"; }
  else if (v === "false") { bg = "#f8d7da"; border = "#dc3545"; emoji = "❌"; }
  else if (v.includes("partial")) { bg = "#fff3cd"; border = "#ffc107"; emoji = "⚠️"; }
  else if (v.includes("misleading")) { bg = "#ffe0cc"; border = "#fd7e14"; emoji = "🟠"; }
  else { bg = "#e2e3e5"; border = "#6c757d"; emoji = "❓"; }

  const conf = data.confidence ? `${Math.round(data.confidence * 100)}%` : "N/A";

  let html = `
    <div class="result">
      <div class="verdict-banner" style="background:${bg}; border-left:4px solid ${border};">
        <h2>${emoji} ${escapeHtml(data.verdict)}</h2>
        <div class="conf">Confidence: <strong>${conf}</strong></div>
      </div>
      <div style="font-size:12px; color:#888; margin-bottom:8px;">
        Claim: <em>"${escapeHtml(data.claim || originalClaim)}"</em>
      </div>
      <div class="section-title">💡 Reasoning</div>
      <div class="reasoning">${escapeHtml(data.reasoning || "")}</div>
  `;

  if (data.evidence && data.evidence.length > 0) {
    html += `<div class="section-title">📄 Evidence (${data.evidence.length})</div>`;
    data.evidence.forEach((ev, i) => {
      const badge = ev.origin === "kb" ? "🗄️ KB" : ev.origin === "fact_check" ? "✅ FC" : "🌐 Web";
      html += `
        <div class="evidence-item">
          <span class="origin">[${i + 1}] ${badge} — ${ev.score.toFixed(2)}</span>
          <div class="text">${escapeHtml(ev.text)}</div>
          ${ev.source ? `<a href="${escapeHtml(ev.source)}" target="_blank">🔗 ${escapeHtml(ev.source)}</a>` : ""}
        </div>`;
    });
  }

  html += `</div>`;
  resultArea.innerHTML = html;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}
