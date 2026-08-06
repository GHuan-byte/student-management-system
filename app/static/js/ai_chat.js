document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".ai-chat-toggle");
  const panel = document.querySelector(".ai-chat-panel");
  const closeButton = document.querySelector(".ai-chat-close");
  const clearButton = document.querySelector(".ai-chat-clear");
  const messagesElement = document.querySelector(".ai-chat-messages");
  const confirmationElement = document.querySelector(".ai-chat-confirmation");
  const confirmationSummary = document.querySelector(".ai-chat-confirmation-summary");
  const confirmationArguments = document.querySelector(".ai-chat-confirmation-arguments");
  const confirmButton = document.querySelector(".ai-chat-confirm");
  const cancelButton = document.querySelector(".ai-chat-cancel");
  const input = document.querySelector(".ai-chat-input");
  const sendButton = document.querySelector(".ai-chat-send");
  const loading = document.querySelector(".ai-chat-loading");
  const errorElement = document.querySelector(".ai-chat-error");

  if (!toggle || !panel || !closeButton || !clearButton || !messagesElement || !confirmationElement
    || !confirmationSummary || !confirmationArguments || !confirmButton || !cancelButton || !input
    || !sendButton || !loading || !errorElement || toggle.dataset.aiChatInitialized === "true") return;
  toggle.dataset.aiChatInitialized = "true";

  const HISTORY_KEY = "ai-chat-history";
  const GUIDED_ACTION_KEY = "ai-guided-action";
  const MAX_HISTORY_MESSAGES = 100;
  const messages = [];
  let sending = false;
  let confirming = false;
  let pendingAction = null;

  function csrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ?? "";
  }

  function jsonHeaders() {
    return {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken(),
    };
  }

  function setOpen(isOpen) {
    panel.hidden = !isOpen;
    panel.setAttribute("aria-hidden", String(!isOpen));
    toggle.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) input.focus(); else toggle.focus();
  }

  function renderMessage(role, content) {
    const message = document.createElement("div");
    message.className = `ai-chat-message ai-chat-message-${role}`;
    message.textContent = content;
    messagesElement.append(message);
    messagesElement.scrollTop = messagesElement.scrollHeight;
  }

  function saveHistory() {
    const history = messages.filter((message) => (message.role === "user" || message.role === "assistant") && typeof message.content === "string")
      .slice(-MAX_HISTORY_MESSAGES).map((message) => ({ role: message.role, content: message.content }));
    try { sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history)); } catch (_error) { /* memory-only fallback */ }
  }

  function restoreHistory() {
    try {
      const stored = sessionStorage.getItem(HISTORY_KEY);
      if (!stored) return;
      const parsed = JSON.parse(stored);
      if (!Array.isArray(parsed)) throw new Error("invalid history");
      for (const message of parsed.slice(-MAX_HISTORY_MESSAGES)) {
        if (!message || (message.role !== "user" && message.role !== "assistant") || typeof message.content !== "string") throw new Error("invalid history entry");
        messages.push({ role: message.role, content: message.content });
        renderMessage(message.role, message.content);
      }
    } catch (_error) {
      messages.length = 0;
      messagesElement.textContent = "";
      try { sessionStorage.removeItem(HISTORY_KEY); } catch (_storageError) { /* nothing to recover */ }
    }
  }

  function syncControls() {
    input.disabled = sending;
    sendButton.disabled = sending || Boolean(pendingAction);
  }

  function setBusy(isBusy) {
    sending = isBusy;
    loading.hidden = !isBusy;
    syncControls();
  }

  function showError(message) {
    errorElement.textContent = message;
    errorElement.hidden = false;
  }

  function clearPendingAction() {
    pendingAction = null;
    confirmationSummary.textContent = "";
    confirmationArguments.textContent = "";
    confirmationElement.hidden = true;
    syncControls();
  }

  function renderPendingAction(data) {
    if (pendingAction || !data || typeof data.confirmation_token !== "string" || !data.pending_action) return;
    const action = data.pending_action;
    pendingAction = { confirmationToken: data.confirmation_token, summary: typeof action.summary === "string" ? action.summary : "需要确认的操作", safeArguments: action.safe_arguments };
    confirmationSummary.textContent = pendingAction.summary;
    confirmationArguments.textContent = typeof pendingAction.safeArguments === "string" ? pendingAction.safeArguments : JSON.stringify(pendingAction.safeArguments ?? {}, null, 2);
    confirmationElement.hidden = false;
    syncControls();
  }

  function setConfirmationBusy(isBusy) {
    confirming = isBusy;
    confirmButton.disabled = isBusy;
    cancelButton.disabled = isBusy;
  }

  async function confirmPendingAction() {
    if (confirming || !pendingAction) return;
    setConfirmationBusy(true);
    let safeError = "暂时无法确认操作，请稍后重试。";
    try {
      const response = await fetch("/api/chat/actions/confirm", { method: "POST", headers: jsonHeaders(), body: JSON.stringify({ confirmation_token: pendingAction.confirmationToken }) });
      const payload = await response.json();
      if (!response.ok || !payload.success) { safeError = payload.message || safeError; throw new Error("confirmation request failed"); }
      const reply = payload.data && payload.data.reply;
      clearPendingAction();
      if (typeof reply === "string" && reply) {
        messages.push({ role: "assistant", content: reply });
        renderMessage("assistant", reply);
        saveHistory();
      }
    } catch (_error) {
      clearPendingAction();
      showError(safeError);
      setOpen(true);
    } finally { setConfirmationBusy(false); }
  }

  function cancelPendingAction() {
    if (confirming || !pendingAction) return;
    clearPendingAction();
    const reply = "操作已取消";
    messages.push({ role: "assistant", content: reply });
    renderMessage("assistant", reply);
    saveHistory();
  }

  function startGuidedAction(action) {
    if (!action || action.action_type !== "create_student") return;
    if (typeof action.action_id !== "string" || !action.action_id) return;
    try {
      sessionStorage.setItem(GUIDED_ACTION_KEY, JSON.stringify({
        action_id: action.action_id,
        action_type: action.action_type
      }));
    } catch (_error) { /* memory-only fallback */ }
    if (window.location.pathname !== "/students") {
      window.location.assign("/students");
    } else {
      document.dispatchEvent(new CustomEvent("ai-guided-action", { detail: { action } }));
    }
  }

  function clearSession() {
    messages.length = 0;
    messagesElement.textContent = "";
    clearPendingAction();
    errorElement.hidden = true;
    try { sessionStorage.removeItem(HISTORY_KEY); } catch (_error) { /* memory is already cleared */ }
  }

  async function sendMessage() {
    const content = input.value.trim();
    if (sending || pendingAction || !content) return;
    errorElement.hidden = true;
    messages.push({ role: "user", content });
    renderMessage("user", content);
    saveHistory();
    input.value = "";
    setBusy(true);
    let safeError = "暂时无法发送消息，请稍后重试。";
    try {
      const response = await fetch("/api/chat", { method: "POST", headers: jsonHeaders(), body: JSON.stringify({ messages }) });
      const payload = await response.json();
      if (!response.ok || !payload.success) { safeError = payload.message || safeError; throw new Error("chat request failed"); }
      const data = payload.data || {};
      if (typeof data.reply === "string" && data.reply) {
        messages.push({ role: "assistant", content: data.reply });
        renderMessage("assistant", data.reply);
        saveHistory();
      }
      if (data.action && data.action.action_type === "create_student") {
        startGuidedAction(data.action);
      } else if (data.requires_confirmation) {
        renderPendingAction(data);
      }
    } catch (_error) {
      showError(safeError);
      setOpen(true);
    } finally { setBusy(false); }
  }

  toggle.addEventListener("click", () => setOpen(panel.hidden));
  closeButton.addEventListener("click", () => setOpen(false));
  clearButton.addEventListener("click", clearSession);
  confirmButton.addEventListener("click", confirmPendingAction);
  cancelButton.addEventListener("click", cancelPendingAction);
  sendButton.addEventListener("click", sendMessage);
  input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void sendMessage(); } });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !panel.hidden) setOpen(false); });
  document.addEventListener("student-modal-opened", () => { if (!panel.hidden) setOpen(false); });
  document.addEventListener("ai-guided-action-finished", (event) => {
    const detail = event.detail || {};
    const content = detail.ok ? "添加成功。" : `添加失败：${detail.message || "请重试"}`;
    messages.push({ role: "assistant", content });
    renderMessage("assistant", content);
    saveHistory();
  });
  restoreHistory();
  syncControls();
});
