document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".ai-chat-toggle");
  const panel = document.querySelector(".ai-chat-panel");
  const closeButton = document.querySelector(".ai-chat-close");
  const messagesElement = document.querySelector(".ai-chat-messages");
  const input = document.querySelector(".ai-chat-input");
  const sendButton = document.querySelector(".ai-chat-send");
  const loading = document.querySelector(".ai-chat-loading");
  const errorElement = document.querySelector(".ai-chat-error");

  if (!toggle || !panel || toggle.dataset.aiChatInitialized === "true") return;
  toggle.dataset.aiChatInitialized = "true";

  const messages = [];
  let sending = false;

  function setOpen(isOpen) {
    panel.hidden = !isOpen;
    panel.setAttribute("aria-hidden", String(!isOpen));
    toggle.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) input.focus();
  }

  function renderMessage(role, content) {
    const message = document.createElement("div");
    message.className = `ai-chat-message ai-chat-message-${role}`;
    message.textContent = content;
    messagesElement.append(message);
    messagesElement.scrollTop = messagesElement.scrollHeight;
  }

  function setBusy(isBusy) {
    sending = isBusy;
    input.disabled = isBusy;
    sendButton.disabled = isBusy;
    loading.hidden = !isBusy;
  }

  function showError(message) {
    errorElement.textContent = message;
    errorElement.hidden = false;
  }

  async function sendMessage() {
    const content = input.value.trim();
    if (sending || !content) return;

    errorElement.hidden = true;
    messages.push({ role: "user", content });
    renderMessage("user", content);
    input.value = "";
    setBusy(true);

    let safeError = "暂时无法发送消息，请稍后重试。";
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        safeError = payload.message || safeError;
        throw new Error("chat request failed");
      }

      const data = payload.data || {};
      const reply = data.requires_confirmation ? "该操作需要确认" : data.reply;
      if (typeof reply === "string" && reply) {
        messages.push({ role: "assistant", content: reply });
        renderMessage("assistant", reply);
      }
    } catch (_error) {
      showError(safeError);
      setOpen(true);
    } finally {
      setBusy(false);
    }
  }

  toggle.addEventListener("click", () => setOpen(panel.hidden));
  closeButton.addEventListener("click", () => setOpen(false));
  sendButton.addEventListener("click", sendMessage);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });
});
