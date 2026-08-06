const state = {
  students: [],
  currentPage: 1,
  pageSize: 15,
  keyword: "",
  sortBy: "student_number",
  sortOrder: "asc",
  selectedIds: new Set(),
  total: 0,
  totalPages: 0,
  loading: false,
  modalMode: "create",
  editingStudentId: null,
  submitting: false,
  batchDeleting: false,
};

const text = {
  loading: "加载中...",
  loadFailed: "加载学生列表失败",
  createFailed: "新增学生失败",
  updateFailed: "更新学生失败",
  deleteFailed: "删除学生失败",
  batchDeleteFailed: "批量删除失败",
  deleteConfirm: "确认删除这条学生记录吗？",
  batchDeleteConfirm(count) {
    return `确认删除已选中的 ${count} 条学生记录吗？`;
  },
  empty: "未填写",
  createTitle: "新增学生",
  editTitle: "编辑学生",
  createEyebrow: "新增学生",
  editEyebrow: "编辑模式",
  createDescription: "必填字段：学号和姓名。",
  editDescription: "可以修改当前学生的信息，保存后会刷新列表。",
  createSubmit: "新增学生",
  editSubmit: "保存修改",
  createSubmitting: "提交中...",
  editSubmitting: "保存中...",
  editMissing: "请先选择需要编辑的学生记录。",
  totalSummary(total) {
    return `共 ${total} 条匹配记录`;
  },
  pageSummary(page, totalPages) {
    return `第 ${page} / ${Math.max(totalPages, 1)} 页`;
  },
  sortLabel(label, active, direction) {
    if (!active) {
      return label;
    }
    return `${label} ${direction === "asc" ? "↑" : "↓"}`;
  },
};

const sortLabels = {
  student_number: "学号",
  name: "姓名",
  gender: "性别",
  age: "年龄",
  major: "专业",
  year_level: "年级",
  score: "成绩",
};

const page = document.querySelector("[data-students-page]");

if (page) {
  const currentRole = document.querySelector("[data-current-role]")?.dataset.currentRole ?? "viewer";
  const elements = {
    tableWrap: page.querySelector("[data-table-wrap]"),
    tableBody: page.querySelector("[data-students-body]"),
    emptyState: page.querySelector("[data-empty-state]"),
    loadingState: page.querySelector("[data-loading-state]"),
    errorState: page.querySelector("[data-error-state]"),
    searchForm: page.querySelector("[data-search-form]"),
    keywordInput: page.querySelector("#keyword"),
    openCreateButton: page.querySelector("[data-open-create-modal]"),
    batchDeleteButton: page.querySelector("[data-batch-delete-button]"),
    totalSummary: page.querySelector("[data-total-summary]"),
    pageSummary: page.querySelector("[data-page-summary]"),
    paginationText: page.querySelector("[data-pagination-text]"),
    prevPageButton: page.querySelector("[data-prev-page]"),
    nextPageButton: page.querySelector("[data-next-page]"),
    selectAllCheckbox: page.querySelector("[data-select-all-checkbox]"),
    sortButtons: [...page.querySelectorAll("[data-sort-field]")],
    modalBackdrop: page.querySelector("[data-modal-backdrop]"),
    modalTitle: page.querySelector("[data-modal-title]"),
    modalEyebrow: page.querySelector("[data-modal-eyebrow]"),
    modalDescription: page.querySelector("[data-modal-description]"),
    modalError: page.querySelector("[data-modal-error]"),
    modalForm: page.querySelector("[data-student-form]"),
    submitButton: page.querySelector("[data-submit-button]"),
    closeButton: page.querySelector("[data-close-modal]"),
    cancelButton: page.querySelector("[data-cancel-modal]"),
  };

  const studentFields = [
    "student_number",
    "name",
    "gender",
    "age",
    "major",
    "year_level",
    "score",
    "phone",
    "email",
  ];

  void initialize();

  function highlightStudentRow(studentId) {
    const row = elements.tableBody.querySelector(`tr[data-student-id="${studentId}"]`);
    if (!row) return;
    row.classList.add("ai-guide-row-highlight");
    window.setTimeout(() => row.classList.remove("ai-guide-row-highlight"), 2600);
  }

  function csrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ?? "";
  }

  function jsonHeaders() {
    return {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken(),
    };
  }

  async function initialize() {
    try {
      enforceClosedModalState();
      bindEvents();
      syncModalUi();
      syncSortButtons();
      syncSelectionUi();
      syncPaginationUi();
      await loadStudents();
    } catch (error) {
      console.error(error);
      setError(text.loadFailed);
    }
  }

  function bindEvents() {
    elements.searchForm.addEventListener("submit", handleSearchSubmit);
    elements.openCreateButton?.addEventListener("click", openCreateModal);
    elements.batchDeleteButton?.addEventListener("click", handleBatchDelete);
    elements.prevPageButton.addEventListener("click", () => changePage(state.currentPage - 1));
    elements.nextPageButton.addEventListener("click", () => changePage(state.currentPage + 1));
    elements.selectAllCheckbox.addEventListener("change", handleToggleSelectAll);
    elements.modalForm.addEventListener("submit", handleModalSubmit);
    elements.closeButton.addEventListener("click", closeModal);
    elements.cancelButton.addEventListener("click", closeModal);
    elements.modalBackdrop.addEventListener("click", handleBackdropClick);
    elements.tableBody.addEventListener("click", handleTableClick);
    elements.tableBody.addEventListener("change", handleTableChange);
    document.addEventListener("keydown", handleDocumentKeydown);
    for (const button of elements.sortButtons) {
      button.addEventListener("click", handleSortClick);
    }
  }

  async function loadStudents() {
    state.loading = true;
    setLoading(true);
    setError("");
    syncPaginationUi();

    try {
      const searchParams = new URLSearchParams({
        page: String(state.currentPage),
        page_size: String(state.pageSize),
        sort_by: state.sortBy,
        sort_order: state.sortOrder,
      });

      if (state.keyword) {
        searchParams.set("keyword", state.keyword);
      }

      const response = await fetch(`/api/students?${searchParams.toString()}`);
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.message || text.loadFailed);
      }

      const meta = payload.meta ?? {};
      const totalPages = Number(meta.total_pages ?? 0);
      const targetPage = Math.max(totalPages, 1);

      if (state.currentPage > totalPages && state.currentPage !== targetPage) {
        state.currentPage = targetPage;
        await loadStudents();
        return;
      }

      state.students = Array.isArray(payload.data) ? payload.data : [];
      state.total = Number(meta.total ?? 0);
      state.totalPages = totalPages;
      state.currentPage = Number(meta.page ?? state.currentPage);
      state.pageSize = Number(meta.page_size ?? state.pageSize);
      state.sortBy = meta.sort_by ?? state.sortBy;
      state.sortOrder = meta.sort_order ?? state.sortOrder;
      renderStudents();
      syncSummaries();
      syncSortButtons();
      syncPaginationUi();
      syncSelectionUi();
    } catch (error) {
      state.students = [];
      state.total = 0;
      state.totalPages = 0;
      renderStudents();
      syncSummaries();
      syncPaginationUi();
      syncSelectionUi();
      setError(error instanceof Error ? error.message : text.loadFailed);
    } finally {
      state.loading = false;
      setLoading(false);
      syncPaginationUi();
    }
  }

  async function handleModalSubmit(event) {
    event.preventDefault();
    if (document.body.dataset.aiGuidedAction === "true") {
      setModalError("AI 引导操作中，请通过 AI 确认按钮完成提交。");
      return;
    }
    if (state.submitting) {
      return;
    }

    if (state.modalMode === "edit" && !state.editingStudentId) {
      setModalError(text.editMissing);
      return;
    }

    setModalError("");
    setSubmitting(true);

    try {
      const payload = formToPayload(elements.modalForm);
      const isCreateMode = state.modalMode === "create";
      const endpoint = isCreateMode ? "/api/students" : `/api/students/${state.editingStudentId}`;
      const response = await fetch(endpoint, {
        method: isCreateMode ? "POST" : "PUT",
        headers: jsonHeaders(),
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok || !result.success) {
        throw new Error(result.message || (isCreateMode ? text.createFailed : text.updateFailed));
      }
      setSubmitting(false);
      closeModal();
      await loadStudents();
    } catch (error) {
      setModalError(
        error instanceof Error
          ? error.message
          : state.modalMode === "create"
            ? text.createFailed
            : text.updateFailed,
      );
    } finally {
      if (state.submitting) {
        setSubmitting(false);
      }
    }
  }

  async function handleBatchDelete() {
    if (!state.selectedIds.size || state.batchDeleting) {
      return;
    }

    const confirmed = window.confirm(text.batchDeleteConfirm(state.selectedIds.size));
    if (!confirmed) {
      return;
    }

    state.batchDeleting = true;
    syncSelectionUi();
    setError("");

    try {
      const response = await fetch("/api/students/batch-delete", {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({
          student_ids: [...state.selectedIds],
        }),
      });
      const result = await response.json();
      if (!response.ok || !result.success) {
        throw new Error(result.message || text.batchDeleteFailed);
      }
      clearSelection();
      await loadStudents();
    } catch (error) {
      setError(error instanceof Error ? error.message : text.batchDeleteFailed);
    } finally {
      state.batchDeleting = false;
      syncSelectionUi();
    }
  }

  function handleSearchSubmit(event) {
    event.preventDefault();
    state.keyword = elements.keywordInput.value.trim();
    state.currentPage = 1;
    clearSelection();
    void loadStudents();
  }

  function handleSortClick(event) {
    const button = event.currentTarget;
    if (!(button instanceof HTMLElement)) {
      return;
    }

    const field = button.dataset.sortField;
    if (!field) {
      return;
    }

    if (state.sortBy === field) {
      state.sortOrder = state.sortOrder === "asc" ? "desc" : "asc";
    } else {
      state.sortBy = field;
      state.sortOrder = "asc";
    }

    state.currentPage = 1;
    clearSelection();
    syncSortButtons();
    void loadStudents();
  }

  function handleToggleSelectAll() {
    const visibleIds = state.students.map((student) => student.id);
    if (elements.selectAllCheckbox.checked) {
      state.selectedIds = new Set(visibleIds);
    } else {
      state.selectedIds.clear();
    }
    syncSelectionUi();
    renderStudents();
  }

  function handleBackdropClick(event) {
    if (event.target === elements.modalBackdrop) {
      closeModal();
    }
  }

  function handleDocumentKeydown(event) {
    if (event.key === "Escape" && !elements.modalBackdrop.hidden) {
      closeModal();
    }
  }

  function handleTableChange(event) {
    const checkbox = event.target.closest("[data-row-checkbox]");
    if (!(checkbox instanceof HTMLInputElement)) {
      return;
    }

    const studentId = Number(checkbox.dataset.studentId);
    if (checkbox.checked) {
      state.selectedIds.add(studentId);
    } else {
      state.selectedIds.delete(studentId);
    }
    syncSelectionUi();
  }

  async function handleTableClick(event) {
    const button = event.target.closest("button[data-action]");
    if (!button) {
      return;
    }

    const studentId = Number(button.dataset.studentId);
    const student = state.students.find((item) => item.id === studentId);
    if (!student) {
      return;
    }

    if (button.dataset.action === "edit") {
      openEditModal(student);
      return;
    }

    if (button.dataset.action === "delete") {
      const confirmed = window.confirm(text.deleteConfirm);
      if (!confirmed) {
        return;
      }

      setError("");
      try {
        const response = await fetch(`/api/students/${studentId}`, {
          method: "DELETE",
          headers: {
            "X-CSRF-Token": csrfToken(),
          },
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
          throw new Error(result.message || text.deleteFailed);
        }
        state.selectedIds.delete(studentId);
        await loadStudents();
      } catch (error) {
        setError(error instanceof Error ? error.message : text.deleteFailed);
      }
    }
  }

  function renderStudents() {
    elements.tableBody.innerHTML = "";

    if (!state.students.length) {
      elements.tableWrap.hidden = true;
      elements.emptyState.hidden = false;
      return;
    }

    elements.tableWrap.hidden = false;
    elements.emptyState.hidden = true;

    for (const student of state.students) {
      const row = document.createElement("tr");
      row.dataset.studentId = student.id;
      const isSelected = state.selectedIds.has(student.id);
      row.innerHTML = `
        <td class="checkbox-col">
          <input
            type="checkbox"
            data-row-checkbox
            data-student-id="${student.id}"
            aria-label="选择学生 ${escapeHtml(student.name)}"
            ${isSelected ? "checked" : ""}
          >
        </td>
        <td>${escapeHtml(student.student_number)}</td>
        <td>${escapeHtml(student.name)}</td>
        <td>${renderValue(student.gender)}</td>
        <td>${renderValue(student.age)}</td>
        <td>${renderValue(student.major)}</td>
        <td>${renderValue(student.year_level)}</td>
        <td>${renderValue(student.score)}</td>
        <td>${renderValue(student.phone)}</td>
        <td>${renderValue(student.email)}</td>
        <td>
          <div class="row-actions">
            ${currentRole === "staff" || currentRole === "admin" ? `<button type="button" data-action="edit" data-student-id="${student.id}">编辑</button>` : ""}
            ${currentRole === "admin" ? `<button type="button" class="secondary" data-action="delete" data-student-id="${student.id}">删除</button>` : ""}
          </div>
        </td>
      `;
      elements.tableBody.appendChild(row);
    }
  }

  function setLoading(isLoading) {
    elements.loadingState.hidden = !isLoading;
    elements.loadingState.textContent = text.loading;
  }

  function setError(message) {
    elements.errorState.hidden = !message;
    elements.errorState.textContent = message;
  }

  function setModalError(message) {
    elements.modalError.hidden = !message;
    elements.modalError.textContent = message;
  }

  function openCreateModal() {
    resetModalState();
    state.modalMode = "create";
    syncModalUi();
    elements.modalBackdrop.classList.add("is-open");
    elements.modalBackdrop.hidden = false;
    document.body.classList.add("modal-open");
    document.dispatchEvent(new CustomEvent("student-modal-opened"));
    focusFirstField();
  }

  function openEditModal(student) {
    resetModalState();
    state.modalMode = "edit";
    state.editingStudentId = student.id;

    for (const field of studentFields) {
      const input = elements.modalForm.elements.namedItem(field);
      if (input instanceof HTMLInputElement || input instanceof HTMLSelectElement) {
        input.value = student[field] ?? "";
      }
    }

    elements.modalForm.elements.namedItem("id").value = String(student.id);
    syncModalUi();
    elements.modalBackdrop.classList.add("is-open");
    elements.modalBackdrop.hidden = false;
    document.body.classList.add("modal-open");
    document.dispatchEvent(new CustomEvent("student-modal-opened"));
    focusFirstField();
  }

  function closeModal() {
    if (state.submitting) {
      return;
    }
    enforceClosedModalState();
    resetModalState();
  }

  function enforceClosedModalState() {
    elements.modalBackdrop.hidden = true;
    elements.modalBackdrop.classList.remove("is-open");
    document.body.classList.remove("modal-open");
  }

  function resetModalState() {
    state.modalMode = "create";
    state.editingStudentId = null;
    state.submitting = false;
    elements.modalForm.reset();
    elements.modalForm.elements.namedItem("id").value = "";
    setModalError("");
    syncModalUi();
  }

  function syncModalUi() {
    const isCreateMode = state.modalMode === "create";
    elements.modalEyebrow.textContent = isCreateMode ? text.createEyebrow : text.editEyebrow;
    elements.modalTitle.textContent = isCreateMode ? text.createTitle : text.editTitle;
    elements.modalDescription.textContent = isCreateMode
      ? text.createDescription
      : text.editDescription;
    elements.submitButton.textContent = state.submitting
      ? isCreateMode
        ? text.createSubmitting
        : text.editSubmitting
      : isCreateMode
        ? text.createSubmit
        : text.editSubmit;
    elements.submitButton.disabled = state.submitting;
  }

  function setSubmitting(isSubmitting) {
    state.submitting = isSubmitting;
    if (elements.openCreateButton) {
      elements.openCreateButton.disabled = isSubmitting;
    }
    elements.closeButton.disabled = isSubmitting;
    elements.cancelButton.disabled = isSubmitting;
    syncModalUi();
  }

  function syncSummaries() {
    elements.totalSummary.textContent = text.totalSummary(state.total);
    const pageText = text.pageSummary(state.currentPage, state.totalPages);
    elements.pageSummary.textContent = pageText;
    elements.paginationText.textContent = pageText;
  }

  function syncPaginationUi() {
    elements.prevPageButton.disabled = state.loading || state.currentPage <= 1;
    elements.nextPageButton.disabled =
      state.loading || state.totalPages === 0 || state.currentPage >= state.totalPages;
    elements.paginationText.textContent = text.pageSummary(state.currentPage, state.totalPages);
    elements.pageSummary.textContent = text.pageSummary(state.currentPage, state.totalPages);
  }

  function syncSortButtons() {
    for (const button of elements.sortButtons) {
      const field = button.dataset.sortField;
      if (!field) {
        continue;
      }
      const active = state.sortBy === field;
      button.classList.toggle("is-active", active);
      button.textContent = text.sortLabel(sortLabels[field], active, state.sortOrder);
    }
  }

  function syncSelectionUi() {
    const visibleIds = state.students.map((student) => student.id);
    const selectedVisibleCount = visibleIds.filter((id) => state.selectedIds.has(id)).length;
    const allVisibleSelected = visibleIds.length > 0 && selectedVisibleCount === visibleIds.length;
    const partiallySelected = selectedVisibleCount > 0 && selectedVisibleCount < visibleIds.length;

    elements.selectAllCheckbox.checked = allVisibleSelected;
    elements.selectAllCheckbox.indeterminate = partiallySelected;
    elements.selectAllCheckbox.disabled = !visibleIds.length || state.loading;

    const disableBatchDelete = state.batchDeleting || state.selectedIds.size === 0;
    if (elements.batchDeleteButton) {
      elements.batchDeleteButton.disabled = disableBatchDelete;
      elements.batchDeleteButton.classList.toggle("disabled", disableBatchDelete);
    }
  }

  function changePage(nextPage) {
    const maxPage = Math.max(state.totalPages, 1);
    const clampedPage = Math.min(Math.max(nextPage, 1), maxPage);
    if (clampedPage === state.currentPage) {
      return;
    }
    state.currentPage = clampedPage;
    clearSelection();
    void loadStudents();
  }

  function clearSelection() {
    state.selectedIds.clear();
    syncSelectionUi();
  }

  function focusFirstField() {
    const firstInput = elements.modalForm.elements.namedItem("student_number");
    if (firstInput instanceof HTMLElement) {
      firstInput.focus();
    }
  }

  function formToPayload(form) {
    const payload = {};
    const formData = new FormData(form);

    for (const field of studentFields) {
      let value = formData.get(field);
      if (value === null) {
        continue;
      }
      if (field === "age" || field === "score") {
        value = value === "" ? "" : Number(value);
      }
      payload[field] = value;
    }

    return payload;
  }

  function renderValue(value) {
    if (value === null || value === undefined || value === "") {
      return `<span class="muted">${text.empty}</span>`;
    }
    return escapeHtml(String(value));
  }

  function escapeHtml(value) {
    return value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  // Controlled page UI API for the AI action runner. The runner reuses the real
  // modal/list functions instead of duplicating DOM manipulation.
  if (!window.StudentPageUI) {
    window.StudentPageUI = Object.freeze({
      openCreateModal,
      closeModal,
      loadStudents,
      highlightStudentRow
    });
  }
}
