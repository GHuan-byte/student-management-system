// AIActionRunner — plays a controlled visual walkthrough for structured AI
// student actions on the /students page.
//
// Safety contract:
// - The runner NEVER writes to the database. The real write is performed only
//   by the server-side Action Executor (the action_id confirm endpoint).
// - It NEVER calls the student management REST write endpoints.
// - It NEVER dispatches a real click or submit on the submit button; the submit
//   button only receives a CSS-only press effect.
// - DOM targeting uses the fixed AI_TARGETS map (data-ai-target only). No
//   fragile positional selectors, no AI-supplied selector strings.
// - Missing targets abort the animation safely without any write.

export const GUIDED_ACTION_KEY = "ai-guided-action";
export const GUIDED_ACTION_TYPES = ["create_student"];

export const AI_TARGETS = {
  addButton: '[data-ai-target="student-add-button"]',
  modal: '[data-ai-target="student-form-modal"]',
  fields: {
    student_number: '[data-ai-target="student-number-input"]',
    name: '[data-ai-target="student-name-input"]',
    gender: '[data-ai-target="student-gender-input"]',
    age: '[data-ai-target="student-age-input"]',
    major: '[data-ai-target="student-major-input"]',
    year_level: '[data-ai-target="student-year-level-select"]',
    score: '[data-ai-target="student-score-input"]',
    phone: '[data-ai-target="student-phone-input"]',
    email: '[data-ai-target="student-email-input"]'
  },
  submitButton: '[data-ai-target="student-submit-button"]'
};

export const FIELD_LABELS = {
  student_number: "学号",
  name: "姓名",
  gender: "性别",
  age: "年龄",
  major: "专业",
  year_level: "年级",
  score: "成绩",
  phone: "电话",
  email: "邮箱"
};

const WAIT_TIMEOUT_MS = 8000;

// Central animation timing — all pacing lives here. Field filling is
// deliberately slow enough for the user to follow each step (per-character
// typing) instead of completing every field in a flash.
const AI_ACTION_TIMING = Object.freeze({
  cursorMoveMs: 650,
  clickEffectMs: 220,
  modalOpenPauseMs: 700,
  characterDelayMs: 120,
  selectPauseMs: 550,
  fieldPauseMs: 650,
  beforeConfirmationMs: 800,
  successEffectMs: 300
});

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

function readGuidedRef() {
  try {
    const raw = sessionStorage.getItem(GUIDED_ACTION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.action_id !== "string" || !parsed.action_id) return null;
    if (GUIDED_ACTION_TYPES.indexOf(parsed.action_type) === -1) return null;
    return { action_id: parsed.action_id, action_type: parsed.action_type };
  } catch (_error) {
    return null;
  }
}

function clearGuidedRef() {
  try { sessionStorage.removeItem(GUIDED_ACTION_KEY); } catch (_error) { /* ignore */ }
}

function saveMinimalRef(action) {
  try {
    sessionStorage.setItem(GUIDED_ACTION_KEY, JSON.stringify({
      action_id: action.action_id,
      action_type: action.action_type
    }));
  } catch (_error) { /* memory-only fallback */ }
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function fetchSafeAction(actionId) {
  const response = await fetch(`/api/chat/actions/${encodeURIComponent(actionId)}`, {
    headers: { "Accept": "application/json" }
  });
  const payload = await response.json();
  if (!response.ok || !payload.success) return null;
  return payload.data || null;
}

class GuidedAbortError extends Error {
  constructor(message) {
    super(message);
    this.name = "GuidedAbortError";
  }
}

export class AIActionRunner {
  constructor() {
    this.action = null;
    this.ui = null;
    this.confirmResolve = null;
    this.finished = false;
  }

  async run(action) {
    if (!action || GUIDED_ACTION_TYPES.indexOf(action.action_type) === -1) return;
    this.action = action;
    this.enterGuidedMode();
    this.createGuideUi();
    try {
      this.setStatus("正在准备操作…");
      await this.runCreateStudent(action);
    } catch (error) {
      if (error instanceof GuidedAbortError) {
        this.closeStudentModal();
        this.setStatus(error.message || "操作已取消");
      } else {
        const message = (error && error.message) || "操作失败";
        this.closeStudentModal();
        this.setStatus(`操作失败：${message}`);
        this.notifyFinished(false, message);
      }
    } finally {
      this.exitGuidedMode();
      this.cleanup();
    }
  }

  async runCreateStudent(action) {
    if (window.location.pathname !== "/students") {
      saveMinimalRef(action);
      window.location.assign("/students");
      return;
    }

    this.setStatus("正在打开新增学生弹窗…");
    const addButton = await this.waitForElement(AI_TARGETS.addButton);
    if (!addButton) throw new Error("目标元素不存在");
    await this.moveCursorTo(addButton);
    this.showVisualClick(addButton);
    await delay(AI_ACTION_TIMING.clickEffectMs);
    addButton.click(); // existing page handler opens the create modal

    const modal = await this.waitForElement(AI_TARGETS.modal, true);
    if (!modal) throw new Error("新增学生弹窗未成功打开");
    await delay(AI_ACTION_TIMING.modalOpenPauseMs);

    const payload = action.payload && typeof action.payload === "object" ? action.payload : {};
    for (const field of Object.keys(payload)) {
      const selector = AI_TARGETS.fields[field];
      if (!selector) continue; // unknown payload fields are ignored by the animation
      this.setStatus(`正在填写学生信息：${FIELD_LABELS[field] || field}…`);
      const input = await this.waitForElement(selector);
      if (!input) throw new Error("目标元素不存在");
      await this.moveCursorTo(input);
      this.highlight(input);
      await this.typeIntoField(input, payload[field]);
      this.unhighlight(input);
      await delay(AI_ACTION_TIMING.fieldPauseMs);
    }

    this.setStatus("请确认是否添加该学生");
    const submitButton = await this.waitForElement(AI_TARGETS.submitButton);
    if (!submitButton) throw new Error("目标元素不存在");
    await this.moveCursorTo(submitButton);
    this.highlight(submitButton);
    this.showVisualClick(submitButton); // visual only — never fires submit
    await delay(AI_ACTION_TIMING.beforeConfirmationMs);

    const confirmed = await this.waitForConfirmation();
    if (!confirmed) {
      await this.requestCancel(action.action_id);
      this.notifyFinished(false, "操作已取消");
      throw new GuidedAbortError("操作已取消");
    }

    this.setStatus("正在执行添加…");
    const result = await this.callExecutor(action.action_id);
    if (result && result.success) {
      await delay(AI_ACTION_TIMING.successEffectMs);
      this.finishSuccess(result);
      this.notifyFinished(true, "添加成功");
    } else {
      // Backend failure: keep the modal open with the entered fields intact,
      // show the real server error, and let the user cancel. Never close the
      // modal on failure and never show a success state.
      const message = (result && result.message) || "添加失败";
      this.notifyFinished(false, message);
      this.showFailure(message);
      await this.waitForDismiss();
      this.closeStudentModal();
    }
  }

  async callExecutor(actionId) {
    const response = await fetch(`/api/chat/actions/${encodeURIComponent(actionId)}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() }
    });
    const payload = await response.json();
    if (!response.ok || !payload.success) {
      return { success: false, message: (payload && payload.message) || "添加失败" };
    }
    // The confirm endpoint uses the unified envelope {success, data, ...}; the
    // inner `data` object has no `success` key, so merge an explicit success
    // flag here. runCreateStudent decides success/failure from this flag.
    return Object.assign({ success: true }, payload.data || {});
  }

  async requestCancel(actionId) {
    try {
      await fetch(`/api/chat/actions/${encodeURIComponent(actionId)}/cancel`, {
        method: "POST",
        headers: { "X-CSRF-Token": csrfToken() }
      });
    } catch (_error) { /* best-effort server-side cancel */ }
  }

  async waitForElement(selector, visibleOnly = false) {
    const deadline = Date.now() + WAIT_TIMEOUT_MS;
    while (Date.now() < deadline) {
      const element = document.querySelector(selector);
      if (element && (!visibleOnly || !element.closest("[hidden]"))) {
        return element;
      }
      await delay(80);
    }
    return null;
  }

  async moveCursorTo(element) {
    this.showCursor();
    const rect = element.getBoundingClientRect();
    this.setCursor(rect.left + rect.width / 2, rect.top + rect.height / 2);
    await delay(AI_ACTION_TIMING.cursorMoveMs);
  }

  showVisualClick(element) {
    if (!element) return;
    element.classList.add("ai-guide-click-pulse");
    window.setTimeout(() => element.classList.remove("ai-guide-click-pulse"), 420);
  }

  // Fills one form field with an observable per-character typing effect for
  // text inputs (a standard `input` event per character, `change` at the end)
  // or a single selection for dropdowns (a standard `change` event). The field
  // is never filled in a single instant assignment.
  async typeIntoField(element, value) {
    const stringValue = value === null || value === undefined ? "" : String(value);
    element.focus();
    if (element instanceof HTMLSelectElement) {
      element.value = stringValue; // legal option only (or "" when absent)
      element.dispatchEvent(new Event("input", { bubbles: true }));
      element.dispatchEvent(new Event("change", { bubbles: true }));
      element.disabled = true; // preview lock
      await delay(AI_ACTION_TIMING.selectPauseMs);
      return;
    }
    element.readOnly = true; // preview lock
    element.value = "";
    for (const character of stringValue) {
      element.value += character;
      element.dispatchEvent(new Event("input", { bubbles: true }));
      await delay(AI_ACTION_TIMING.characterDelayMs);
    }
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }

  highlight(element) {
    if (element) element.classList.add("ai-guide-field-highlight");
  }

  unhighlight(element) {
    if (element) element.classList.remove("ai-guide-field-highlight");
  }

  waitForConfirmation() {
    return new Promise((resolve) => {
      this.confirmResolve = resolve;
      this.ui.confirmBar.hidden = false;
      this.ui.confirmOk.addEventListener("click", () => {
        this.ui.confirmBar.hidden = true;
        if (this.confirmResolve) { this.confirmResolve(true); this.confirmResolve = null; }
      }, { once: true });
      this.ui.confirmCancel.addEventListener("click", () => {
        this.ui.confirmBar.hidden = true;
        if (this.confirmResolve) { this.confirmResolve(false); this.confirmResolve = null; }
      }, { once: true });
    });
  }

  cancel() {
    if (this.confirmResolve) {
      const resolve = this.confirmResolve;
      this.confirmResolve = null;
      this.ui.confirmBar.hidden = true;
      resolve(false);
    }
  }

  // Success: close the real modal through the page UI API, refresh the list and
  // highlight the created row. The guide overlay and guided-mode flag are
  // cleaned up by the caller's finally block (exitGuidedMode + cleanup).
  finishSuccess(result) {
    this.setStatus("添加成功");
    const student = result && result.action_result && result.action_result.data;
    if (!window.StudentPageUI) return;
    window.StudentPageUI.closeModal();
    window.StudentPageUI.loadStudents().then(() => {
      if (student && typeof student.id !== "undefined") {
        window.StudentPageUI.highlightStudentRow(student.id);
      }
    });
  }

  // Failure: keep the modal open and the fields intact, show the real server
  // error, and offer only "取消" (the action is already terminal server-side).
  // The modal is closed only when the user dismisses the failure state.
  showFailure(message) {
    this.setStatus(`添加失败：${message}`);
    if (!this.ui) return;
    this.ui.confirmText.textContent = `添加失败：${message}`;
    this.ui.confirmOk.hidden = true;
    this.ui.confirmCancel.textContent = "取消";
    this.ui.confirmBar.hidden = false;
  }

  // Waits for the user to dismiss the failure state (click 取消).
  waitForDismiss() {
    return new Promise((resolve) => {
      this.dismissResolve = resolve;
      this.ui.confirmCancel.addEventListener("click", () => {
        this.ui.confirmBar.hidden = true;
        if (this.dismissResolve) { this.dismissResolve(); this.dismissResolve = null; }
      }, { once: true });
    });
  }

  closeStudentModal() {
    if (window.StudentPageUI) window.StudentPageUI.closeModal();
  }

  enterGuidedMode() {
    document.body.dataset.aiGuidedAction = "true";
  }

  exitGuidedMode() {
    delete document.body.dataset.aiGuidedAction;
    document.querySelectorAll("[data-ai-target]").forEach((element) => {
      if (element instanceof HTMLInputElement) element.readOnly = false;
      if (element instanceof HTMLSelectElement) element.disabled = false;
    });
  }

  createGuideUi() {
    if (this.ui) return;
    const root = document.createElement("div");
    root.className = "ai-guide-root";

    const mask = document.createElement("div");
    mask.className = "ai-guide-mask";

    const status = document.createElement("div");
    status.className = "ai-guide-status";
    status.setAttribute("role", "status");
    status.hidden = true;

    const cursor = document.createElement("div");
    cursor.className = "ai-guide-cursor";
    cursor.hidden = true;

    const confirmBar = document.createElement("div");
    confirmBar.className = "ai-guide-confirm";
    confirmBar.hidden = true;

    const confirmText = document.createElement("span");
    confirmText.className = "ai-guide-confirm-text";
    confirmText.textContent = "AI 已完成填写，是否确认添加该学生？";

    const confirmOk = document.createElement("button");
    confirmOk.type = "button";
    confirmOk.className = "ai-guide-confirm-ok";
    confirmOk.textContent = "确认添加";

    const confirmCancel = document.createElement("button");
    confirmCancel.type = "button";
    confirmCancel.className = "ai-guide-confirm-cancel";
    confirmCancel.textContent = "取消";

    confirmBar.append(confirmText, confirmOk, confirmCancel);
    root.append(mask, status, cursor, confirmBar);
    document.body.append(root);

    this.ui = { root, status, cursor, confirmBar, confirmText, confirmOk, confirmCancel };
  }

  setStatus(text) {
    if (this.ui && this.ui.status) {
      this.ui.status.textContent = text;
      this.ui.status.hidden = false;
    }
  }

  showCursor() {
    if (this.ui) this.ui.cursor.hidden = false;
  }

  setCursor(x, y) {
    if (!this.ui) return;
    this.ui.cursor.style.left = `${x}px`;
    this.ui.cursor.style.top = `${y}px`;
  }

  cleanup() {
    document.querySelectorAll(".ai-guide-field-highlight").forEach((element) => {
      element.classList.remove("ai-guide-field-highlight");
    });
    document.querySelectorAll(".ai-guide-click-pulse").forEach((element) => {
      element.classList.remove("ai-guide-click-pulse");
    });
    if (this.ui) {
      this.ui.root.remove();
      this.ui = null;
    }
    this.confirmResolve = null;
    this.dismissResolve = null;
    clearGuidedRef();
  }

  notifyFinished(ok, message) {
    if (this.finished) return;
    this.finished = true;
    document.dispatchEvent(new CustomEvent("ai-guided-action-finished", {
      detail: { ok, message, action_id: this.action ? this.action.action_id : null }
    }));
  }
}

async function bootstrap() {
  if (window.location.pathname !== "/students") return;
  const ref = readGuidedRef();
  if (!ref) return;
  const action = await fetchSafeAction(ref.action_id);
  if (!action || GUIDED_ACTION_TYPES.indexOf(action.action_type) === -1) {
    clearGuidedRef();
    return;
  }
  const runner = new AIActionRunner();
  await runner.run(action);
}

void bootstrap();
document.addEventListener("ai-guided-action", (event) => {
  if (document.body.dataset.aiGuidedAction === "true") return; // already running
  const action = event.detail && event.detail.action;
  if (!action || GUIDED_ACTION_TYPES.indexOf(action.action_type) === -1) return;
  const runner = new AIActionRunner();
  void runner.run(action);
});
