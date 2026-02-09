// Background service worker — handles context menu and message routing

const API_URL = "http://localhost:5000/api/verify";

// Create right-click context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "verify-claim",
    title: '🔍 Verify Claim: "%s"',
    contexts: ["selection"],
  });
});

// Handle context menu click
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "verify-claim" && info.selectionText) {
    chrome.tabs.sendMessage(tab.id, {
      action: "verify",
      claim: info.selectionText.trim(),
    });
  }
});

// Handle messages from content script or popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "api-verify") {
    fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ claim: msg.claim }),
    })
      .then((r) => r.json())
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // keep channel open for async response
  }
});
