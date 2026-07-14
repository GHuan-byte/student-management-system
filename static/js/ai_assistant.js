const aiSidebar = document.getElementById("aiSidebar");
const aiOverlay = document.getElementById("aiOverlay");
const aiOpenButton = document.getElementById("aiFloatingButton");
const aiCloseButton = document.getElementById("aiCloseButton");
const aiNewSessionButton = document.getElementById("aiNewSessionBtn");
const aiForm = document.getElementById("aiAssistantForm");
const aiInput = document.getElementById("aiAssistantInput");
const aiMessageList = document.getElementById("aiMessageList");
const aiSendButton = document.getElementById("aiSendButton");
const aiLoadingIndicator = document.getElementById("aiLoadingIndicator");
const aiErrorMessage = document.getElementById("aiErrorMessage");

let currentSessionId = localStorage.getItem("ai_assistant_session_id") || null;

document.addEventListener("DOMContentLoaded", async () => {
    bindAssistantEvents();
    await bootstrapAssistantSession();
});

function bindAssistantEvents() {
    aiOpenButton?.addEventListener("click", openSidebar);
    aiCloseButton?.addEventListener("click", closeSidebar);
    aiOverlay?.addEventListener("click", closeSidebar);
    aiNewSessionButton?.addEventListener("click", async () => {
        await createFreshSession();
        renderWelcomeMessage();
    });
    aiForm?.addEventListener("submit", handleSubmit);
    aiInput?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            aiForm.requestSubmit();
        }
    });
    window.addEventListener("open-ai-assistant", openSidebar);
}

async function bootstrapAssistantSession() {
    if (!currentSessionId) {
        return;
    }
    try {
        const response = await fetch(`/api/sessions/${currentSessionId}/messages?limit=100`);
        if (!response.ok) {
            throw new Error("session not found");
        }
        const messages = await response.json();
        if (messages.length) {
            renderMessages(messages);
        }
    } catch {
        localStorage.removeItem("ai_assistant_session_id");
        currentSessionId = null;
    }
}

function openSidebar() {
    aiSidebar.classList.add("open");
    aiOverlay.classList.add("open");
    aiSidebar.setAttribute("aria-hidden", "false");
    aiInput.focus();
}

function closeSidebar() {
    aiSidebar.classList.remove("open");
    aiOverlay.classList.remove("open");
    aiSidebar.setAttribute("aria-hidden", "true");
}

async function createFreshSession() {
    const response = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "新建会话" }),
    });
    const session = await response.json();
    currentSessionId = session.id;
    localStorage.setItem("ai_assistant_session_id", currentSessionId);
}

function renderWelcomeMessage() {
    aiMessageList.innerHTML = `
        <div class="ai-message ai-message-assistant">
            <div class="ai-message-bubble">
                欢迎使用 AI 学生管理助手。你可以继续发起新的问题。
            </div>
        </div>
    `;
}

function renderMessages(messages) {
    aiMessageList.innerHTML = "";
    messages.forEach((item) => {
        appendMessage(item.message, item.sender === "user" ? "user" : "assistant");
    });
}

async function handleSubmit(event) {
    event.preventDefault();
    const message = aiInput.value.trim();
    if (!message) {
        return;
    }

    clearAssistantError();
    setLoading(true);
    appendMessage(message, "user");
    aiInput.value = "";

    try {
        if (!currentSessionId) {
            await createFreshSession();
        }

        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, session_id: currentSessionId }),
        });
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "AI 请求失败");
        }

        currentSessionId = result.session_id;
        localStorage.setItem("ai_assistant_session_id", currentSessionId);
        appendMessage(result.bot_reply, "assistant");
    } catch (error) {
        showAssistantError(error.message || "发送消息失败");
    } finally {
        setLoading(false);
    }
}

function appendMessage(message, sender) {
    const wrapper = document.createElement("div");
    wrapper.className = `ai-message ai-message-${sender}`;
    wrapper.innerHTML = `<div class="ai-message-bubble"></div>`;
    wrapper.querySelector(".ai-message-bubble").textContent = message;
    aiMessageList.appendChild(wrapper);
    aiMessageList.scrollTop = aiMessageList.scrollHeight;
}

function setLoading(isLoading) {
    aiSendButton.disabled = isLoading;
    aiInput.disabled = isLoading;
    aiLoadingIndicator.classList.toggle("show", isLoading);
}

function showAssistantError(message) {
    aiErrorMessage.textContent = message;
    aiErrorMessage.classList.add("show");
}

function clearAssistantError() {
    aiErrorMessage.textContent = "";
    aiErrorMessage.classList.remove("show");
}
