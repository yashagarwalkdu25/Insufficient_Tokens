// Content script — injected into every page
// Handles: floating verify button on text selection, result popup overlay

(() => {
  const BUTTON_ID = "cv-verify-btn";
  const OVERLAY_ID = "cv-overlay";
  const PANEL_ID = "cv-panel";

  // ── Floating "Verify Claim" button on text selection ──────────────
  function createFloatingButton(x, y, text) {
    removeFloatingButton();
    const btn = document.createElement("button");
    btn.id = BUTTON_ID;
    btn.textContent = "🔍 Verify Claim";
    btn.style.cssText = `
      position: fixed; z-index: 2147483647;
      left: ${x}px; top: ${y}px;
      background: #1a73e8; color: #fff; border: none; border-radius: 8px;
      padding: 8px 16px; font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      cursor: pointer; box-shadow: 0 4px 16px rgba(0,0,0,0.25);
      transition: background 0.2s;
    `;
    btn.addEventListener("mouseenter", () => (btn.style.background = "#1557b0"));
    btn.addEventListener("mouseleave", () => (btn.style.background = "#1a73e8"));
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      removeFloatingButton();
      verifyClaim(text);
    });
    document.body.appendChild(btn);
  }

  function removeFloatingButton() {
    const existing = document.getElementById(BUTTON_ID);
    if (existing) existing.remove();
  }

  // Show button near selection
  document.addEventListener("mouseup", (e) => {
    setTimeout(() => {
      const sel = window.getSelection().toString().trim();
      if (sel.length > 5 && sel.length < 2000) {
        createFloatingButton(e.clientX + 10, e.clientY - 45, sel);
      } else {
        removeFloatingButton();
      }
    }, 50);
  });

  // Hide button on click elsewhere
  document.addEventListener("mousedown", (e) => {
    if (e.target.id !== BUTTON_ID) {
      removeFloatingButton();
    }
  });

  // ── Verification call ─────────────────────────────────────────────
  function verifyClaim(claim) {
    showOverlay(claim, null, true); // loading state
    chrome.runtime.sendMessage(
      { action: "api-verify", claim },
      (response) => {
        if (response && response.ok) {
          showOverlay(claim, response.data, false);
        } else {
          const errMsg = response?.error || "Could not connect to the verification server. Make sure the API is running on localhost:5000.";
          showOverlay(claim, { verdict: "Error", reasoning: errMsg, evidence: [], confidence: 0 }, false);
        }
      }
    );
  }

  // ── Result overlay ────────────────────────────────────────────────
  function showOverlay(claim, data, loading) {
    removeOverlay();

    const overlay = document.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.style.cssText = `
      position: fixed; inset: 0; z-index: 2147483646;
      background: rgba(0,0,0,0.5); display: flex;
      align-items: center; justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) removeOverlay();
    });

    const panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.style.cssText = `
      background: #fff; border-radius: 16px; padding: 28px;
      max-width: 600px; width: 90vw; max-height: 80vh; overflow-y: auto;
      box-shadow: 0 24px 64px rgba(0,0,0,0.3);
      color: #1a1a1a; line-height: 1.6;
    `;

    if (loading) {
      panel.innerHTML = `
        <div style="text-align:center; padding: 40px 0;">
          <div style="font-size: 48px; margin-bottom: 16px;">🔄</div>
          <h2 style="margin:0 0 8px; font-size:20px; color:#1a73e8;">Verifying Claim…</h2>
          <p style="color:#666; font-size:14px; margin:0;">Retrieving evidence, reranking, cross-checking…</p>
          <p style="color:#999; font-size:13px; margin-top:12px; font-style:italic;">"${escapeHtml(claim.substring(0, 100))}${claim.length > 100 ? '…' : ''}"</p>
          <div style="margin-top:20px;">
            <div style="display:inline-block; width:40px; height:40px; border:4px solid #e0e0e0; border-top-color:#1a73e8; border-radius:50%; animation:cv-spin 0.8s linear infinite;"></div>
          </div>
        </div>
        <style>@keyframes cv-spin { to { transform: rotate(360deg); } }</style>
      `;
    } else {
      panel.innerHTML = buildResultHTML(claim, data);
    }

    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    // ESC to close
    const escHandler = (e) => {
      if (e.key === "Escape") { removeOverlay(); document.removeEventListener("keydown", escHandler); }
    };
    document.addEventListener("keydown", escHandler);
  }

  function removeOverlay() {
    const el = document.getElementById(OVERLAY_ID);
    if (el) el.remove();
  }

  function buildResultHTML(claim, data) {
    const v = (data.verdict || "").toLowerCase();
    let verdictColor, verdictBg, verdictEmoji;
    if (v === "true") { verdictColor = "#28a745"; verdictBg = "#d4edda"; verdictEmoji = "✅"; }
    else if (v === "false") { verdictColor = "#dc3545"; verdictBg = "#f8d7da"; verdictEmoji = "❌"; }
    else if (v.includes("partial")) { verdictColor = "#ffc107"; verdictBg = "#fff3cd"; verdictEmoji = "⚠️"; }
    else if (v.includes("misleading")) { verdictColor = "#fd7e14"; verdictBg = "#ffe0cc"; verdictEmoji = "🟠"; }
    else if (v === "error") { verdictColor = "#dc3545"; verdictBg = "#f8d7da"; verdictEmoji = "⚙️"; }
    else { verdictColor = "#6c757d"; verdictBg = "#e2e3e5"; verdictEmoji = "❓"; }

    const confidence = data.confidence ? `${Math.round(data.confidence * 100)}%` : "N/A";
    const confBarWidth = data.confidence ? Math.round(data.confidence * 100) : 0;

    let evidenceHTML = "";
    if (data.evidence && data.evidence.length > 0) {
      evidenceHTML = `<div style="margin-top:16px;">
        <h3 style="font-size:15px; margin:0 0 8px; color:#333;">📄 Evidence (${data.evidence.length} sources)</h3>`;
      data.evidence.forEach((ev, i) => {
        const originBadge = ev.origin === "kb" ? "🗄️ KB" : ev.origin === "fact_check" ? "✅ Fact-Check" : "🌐 Web";
        evidenceHTML += `
          <div style="background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; padding:10px; margin-bottom:6px; font-size:13px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
              <span style="font-weight:600;">[${i + 1}] ${originBadge}</span>
              <span style="color:#888;">Score: ${ev.score.toFixed(2)}</span>
            </div>
            <p style="margin:0 0 4px; color:#333;">${escapeHtml(ev.text)}</p>
            ${ev.source ? `<a href="${escapeHtml(ev.source)}" target="_blank" rel="noopener" style="color:#1a73e8; font-size:12px; text-decoration:none; word-break:break-all;">🔗 ${escapeHtml(ev.source)}</a>` : ""}
          </div>`;
      });
      evidenceHTML += `</div>`;
    }

    let stepsHTML = "";
    if (data.steps && data.steps.length > 0) {
      stepsHTML = `
        <details style="margin-top:12px;">
          <summary style="cursor:pointer; font-size:14px; font-weight:600; color:#555;">🤖 Agent Trace (${data.steps.length} steps)</summary>
          <div style="margin-top:8px; background:#f0f2f6; border-radius:8px; padding:10px; font-family:monospace; font-size:12px; color:#495057; max-height:200px; overflow-y:auto;">
            ${data.steps.map((s) => `<div style="margin-bottom:2px;">${escapeHtml(s)}</div>`).join("")}
          </div>
        </details>`;
    }

    return `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <h2 style="margin:0; font-size:20px; color:#1a1a1a;">🔍 Claim Verification</h2>
        <button onclick="document.getElementById('${OVERLAY_ID}').remove()" style="background:none; border:none; font-size:22px; cursor:pointer; color:#999; padding:4px 8px;">✕</button>
      </div>

      <div style="background:${verdictBg}; border-left:5px solid ${verdictColor}; border-radius:8px; padding:14px; margin-bottom:16px;">
        <div style="font-size:22px; font-weight:700; margin-bottom:4px;">${verdictEmoji} ${escapeHtml(data.verdict)}</div>
        <div style="font-size:13px; color:#555;">
          Confidence: <strong>${confidence}</strong>
          <div style="background:#ddd; height:6px; border-radius:3px; margin-top:4px; width:100%; max-width:200px;">
            <div style="background:${verdictColor}; height:6px; border-radius:3px; width:${confBarWidth}%;"></div>
          </div>
        </div>
      </div>

      <div style="margin-bottom:12px;">
        <span style="font-size:13px; color:#888;">Verified claim:</span>
        <p style="margin:2px 0 0; font-style:italic; color:#333; font-size:14px;">"${escapeHtml(data.claim || claim)}"</p>
      </div>

      <div style="margin-bottom:12px;">
        <h3 style="font-size:15px; margin:0 0 6px; color:#333;">💡 Reasoning</h3>
        <p style="margin:0; font-size:14px; color:#444;">${escapeHtml(data.reasoning || "")}</p>
      </div>

      ${evidenceHTML}
      ${stepsHTML}

      <div style="margin-top:16px; text-align:center; font-size:11px; color:#aaa;">
        Agentic RAG Claim Verifier — ChromaDB · MiniLM · Cross-Encoder · GPT-4o-mini
      </div>
    `;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }

  // ── Listen for messages from background (context menu) ────────────
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === "verify" && msg.claim) {
      verifyClaim(msg.claim);
    }
  });
})();
