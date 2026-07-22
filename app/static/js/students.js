const state = {
  students: [],
  modalMode: "create",
  selectedStudentId: null,
  isSubmitting: false,
};

const text = {
  loading: "加载中...",
  loadFailed: "加载学生列表失败",
  createFailed: "新增学生失败",
  updateFailed: "更新学生失败",
  deleteFailed: "删除学生失败",
  deleteConfirm: "确认删除这条学生记录吗？",
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
};

const page = document.querySelector("[data-students-page]");

if (page) {
  const elements = {
    tableWrap: page.querySelector("[data-table-wrap]"),
    tableBody: page.querySelector("[data-students-body]"),
    emptyState: page.querySelector("[data-empty-state]"),
    loadingState: page.querySelector("[data-loading-state]"),
    errorState: page.querySelector("[data-error-state]"),
    searchForm: page.querySelector("[data-search-form]"),
    openCreateButton: page.querySelector("[data-open-create-modal]"),
    modalBackdrop: page.querySelector("[data-modal-backdrop]"),
    modalPanel: page.querySelector("[data-student-modal]"),
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

  initialize();

  function initialize() {
    enforceClosedModalState();
    elements.searchForm.addEventListener("submit", handleSearchSubmit);
    elements.openCreateButton.addEventListener("click", openCreateModal);
    elements.modalForm.addEventListener("submit", handleModalSubmit);
    elements.closeButton.addEventListener("click", closeModal);
    elements.cancelButton.addEventListener("click", closeModal);
    elements.modalBackdrop.addEventListener("click", handleBackdropClick);
    elements.tableBody.addEventListener("click", handleTableClick);
    document.addEventListener("keydown", handleDocumentKeydown);
    syncModalUi();
    loadStudents();
  }

  async function loadStudents() {
    setLoading(true);
    setError("");
    try {
      const keyword = new FormData(elements.searchForm).get("keyword")?.toString().trim();
      const searchParams = new URLSearchParams();
      if (keyword) {
        searchParams.set("keyword", keyword);
      }
      const endpoint = searchParams.size ? `/api/students?${searchParams}` : "/api/students";
      const response = await fetch(endpoint);
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.message || text.loadFailed);
      }
      state.students = Array.isArray(payload.data) ? payload.data : [];
      renderStudents();
    } catch (error) {
      state.students = [];
      renderStudents();
      setError(error.message || text.loadFailed);
    } finally {
      setLoading(false);
    }
  }

  async function handleModalSubmit(event) {
    event.preventDefault();
    if (state.isSubmitting) {
      return;
    }

    if (state.modalMode === "edit" && !state.selectedStudentId) {
      setModalError(text.editMissing);
      return;
    }

    setModalError("");
    setSubmitting(true);

    try {
      const payload = formToPayload(elements.modalForm);
      const isCreateMode = state.modalMode === "create";
      const response = await fetch(
        isCreateMode ? "/api/students" : `/api/students/${state.selectedStudentId}`,
        {
          method: isCreateMode ? "POST" : "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        },
      );
      const result = await response.json();
      if (!response.ok || !result.success) {
        throw new Error(result.message || (isCreateMode ? text.createFailed : text.updateFailed));
      }
      setSubmitting(false);
      closeModal();
      await loadStudents();
    } catch (error) {
      setModalError(
        error.message || (state.modalMode === "create" ? text.createFailed : text.updateFailed),
      );
    } finally {
      if (state.isSubmitting) {
        setSubmitting(false);
      }
    }
  }

  function handleSearchSubmit(event) {
    event.preventDefault();
    loadStudents();
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
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
          throw new Error(result.message || text.deleteFailed);
        }
        await loadStudents();
      } catch (error) {
        setError(error.message || text.deleteFailed);
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
      row.innerHTML = `
        <td>${student.id}</td>
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
            <button type="button" data-action="edit" data-student-id="${student.id}">
              编辑
            </button>
            <button type="button" class="secondary" data-action="delete" data-student-id="${student.id}">
              删除
            </button>
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
    focusFirstField();
  }

  function openEditModal(student) {
    resetModalState();
    state.modalMode = "edit";
    state.selectedStudentId = student.id;

    for (const field of studentFields) {
      const input = elements.modalForm.elements.namedItem(field);
      if (input) {
        input.value = student[field] ?? "";
      }
    }

    elements.modalForm.elements.namedItem("id").value = String(student.id);
    syncModalUi();
    elements.modalBackdrop.classList.add("is-open");
    elements.modalBackdrop.hidden = false;
    document.body.classList.add("modal-open");
    focusFirstField();
  }

  function closeModal() {
    if (state.isSubmitting) {
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
    state.selectedStudentId = null;
    state.isSubmitting = false;
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
    elements.submitButton.textContent = state.isSubmitting
      ? isCreateMode
        ? text.createSubmitting
        : text.editSubmitting
      : isCreateMode
        ? text.createSubmit
        : text.editSubmit;
    elements.submitButton.disabled = state.isSubmitting;
  }

  function setSubmitting(isSubmitting) {
    state.isSubmitting = isSubmitting;
    elements.openCreateButton.disabled = isSubmitting;
    elements.closeButton.disabled = isSubmitting;
    elements.cancelButton.disabled = isSubmitting;
    syncModalUi();
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
}
