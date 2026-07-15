const studentsTableBody = document.getElementById("studentsTableBody");
const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const resetButton = document.getElementById("resetButton");
const addStudentButton = document.getElementById("addStudentButton");
const studentModal = document.getElementById("studentModal");
const studentForm = document.getElementById("studentForm");
const modalTitle = document.getElementById("modalTitle");
const selectAllStudents = document.getElementById("selectAllStudents");
const batchDeleteButton = document.getElementById("batchDeleteButton");
const selectedCount = document.getElementById("selectedCount");
const importCsvButton = document.getElementById("importCsvButton");
const exportCsvButton = document.getElementById("exportCsvButton");
const exportExcelButton = document.getElementById("exportExcelButton");
const importFileInput = document.getElementById("importFileInput");

let selectedStudentIds = new Set();
let currentStudents = [];

document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    loadStudents();
});

function bindEvents() {
    searchButton?.addEventListener("click", () => loadStudents(searchInput.value.trim()));
    resetButton?.addEventListener("click", resetSearch);
    addStudentButton?.addEventListener("click", openAddModal);
    batchDeleteButton?.addEventListener("click", batchDeleteStudents);
    importCsvButton?.addEventListener("click", () => importFileInput?.click());
    exportCsvButton?.addEventListener("click", () => exportStudents("csv"));
    exportExcelButton?.addEventListener("click", () => exportStudents("xlsx"));
    importFileInput?.addEventListener("change", importStudentsFromFile);
    selectAllStudents?.addEventListener("change", toggleSelectAllStudents);
    document.getElementById("closeModalButton")?.addEventListener("click", closeModal);
    document.getElementById("cancelModalButton")?.addEventListener("click", closeModal);
    studentForm?.addEventListener("submit", submitStudentForm);
    searchInput?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            loadStudents(searchInput.value.trim());
        }
    });
    studentModal?.addEventListener("click", (event) => {
        if (event.target === studentModal) {
            closeModal();
        }
    });
}

async function loadStudents(keyword = "") {
    studentsTableBody.innerHTML = '<tr><td colspan="11" class="empty-cell">正在加载学生数据...</td></tr>';
    const url = keyword ? `/api/students?keyword=${encodeURIComponent(keyword)}` : "/api/students";

    try {
        const response = await fetch(url);
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "加载失败");
        }

        currentStudents = result.data;
        syncSelectedStudents();
        renderStudents(currentStudents);
        updateBatchDeleteState();
    } catch (error) {
        showToast(error.message || "加载学生数据失败");
        studentsTableBody.innerHTML = '<tr><td colspan="11" class="empty-cell">加载失败，请稍后重试。</td></tr>';
    }
}

function renderStudents(students) {
    if (!students.length) {
        studentsTableBody.innerHTML = '<tr><td colspan="11" class="empty-cell">暂无学生数据</td></tr>';
        return;
    }

    studentsTableBody.innerHTML = students.map((student) => `
        <tr>
            <td class="checkbox-column">
                <input
                    type="checkbox"
                    class="student-checkbox"
                    data-student-id="${student.id}"
                    ${selectedStudentIds.has(student.id) ? "checked" : ""}
                    aria-label="选择学生 ${escapeHtml(student.name)}"
                >
            </td>
            <td>${student.id}</td>
            <td>${escapeHtml(student.student_number)}</td>
            <td>${escapeHtml(student.name)}</td>
            <td>${escapeHtml(student.gender)}</td>
            <td>${student.age}</td>
            <td>${escapeHtml(student.major)}</td>
            <td>${escapeHtml(student.grade)}</td>
            <td>${escapeHtml(student.phone || "-")}</td>
            <td>${escapeHtml(student.email || "-")}</td>
            <td>
                <div class="table-actions">
                    <button type="button" class="action-button" onclick="editStudent(${student.id})">编辑</button>
                    <button type="button" class="action-button delete" onclick="deleteStudentRecord(${student.id})">删除</button>
                </div>
            </td>
        </tr>
    `).join("");

    bindRowSelectionEvents();
}

function bindRowSelectionEvents() {
    document.querySelectorAll(".student-checkbox").forEach((checkbox) => {
        checkbox.addEventListener("change", function () {
            const studentId = Number(this.dataset.studentId);
            if (this.checked) {
                selectedStudentIds.add(studentId);
            } else {
                selectedStudentIds.delete(studentId);
            }
            updateBatchDeleteState();
        });
    });
}

function syncSelectedStudents() {
    const currentIds = new Set(currentStudents.map((student) => student.id));
    selectedStudentIds = new Set(
        Array.from(selectedStudentIds).filter((studentId) => currentIds.has(studentId))
    );
}

function updateBatchDeleteState() {
    const selected = selectedStudentIds.size;
    if (selectedCount) {
        selectedCount.textContent = `已选择 ${selected} 项`;
    }
    if (batchDeleteButton) {
        batchDeleteButton.disabled = selected === 0;
    }

    if (!selectAllStudents) {
        return;
    }

    const total = currentStudents.length;
    selectAllStudents.checked = total > 0 && selected === total;
    selectAllStudents.indeterminate = selected > 0 && selected < total;
}

function toggleSelectAllStudents() {
    if (!selectAllStudents) {
        return;
    }

    if (selectAllStudents.checked) {
        currentStudents.forEach((student) => selectedStudentIds.add(student.id));
    } else {
        currentStudents.forEach((student) => selectedStudentIds.delete(student.id));
    }

    renderStudents(currentStudents);
    updateBatchDeleteState();
}

function resetSearch() {
    searchInput.value = "";
    selectedStudentIds.clear();
    loadStudents();
}

function openAddModal() {
    modalTitle.textContent = "新增学生";
    studentForm.reset();
    document.getElementById("studentId").value = "";
    studentModal.classList.add("open");
}

function closeModal() {
    studentModal.classList.remove("open");
}

async function editStudent(studentId) {
    try {
        const response = await fetch(`/api/students/${studentId}`);
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "获取学生信息失败");
        }

        const student = result.data;
        modalTitle.textContent = "编辑学生";
        document.getElementById("studentId").value = student.id;
        document.getElementById("studentNumber").value = student.student_number;
        document.getElementById("studentName").value = student.name;
        document.getElementById("studentGender").value = student.gender;
        document.getElementById("studentAge").value = student.age;
        document.getElementById("studentMajor").value = student.major;
        document.getElementById("studentGrade").value = student.grade;
        document.getElementById("studentPhone").value = student.phone || "";
        document.getElementById("studentEmail").value = student.email || "";
        studentModal.classList.add("open");
    } catch (error) {
        showToast(error.message || "获取学生详情失败");
    }
}

async function submitStudentForm(event) {
    event.preventDefault();

    const studentId = document.getElementById("studentId").value;
    const payload = {
        student_number: document.getElementById("studentNumber").value.trim(),
        name: document.getElementById("studentName").value.trim(),
        gender: document.getElementById("studentGender").value,
        age: document.getElementById("studentAge").value,
        major: document.getElementById("studentMajor").value.trim(),
        grade: document.getElementById("studentGrade").value.trim(),
        phone: document.getElementById("studentPhone").value.trim(),
        email: document.getElementById("studentEmail").value.trim(),
    };

    const url = studentId ? `/api/students/${studentId}` : "/api/students";
    const method = studentId ? "PUT" : "POST";

    try {
        const response = await fetch(url, {
            method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "保存失败");
        }

        closeModal();
        showToast(result.message || "保存成功");
        loadStudents(searchInput.value.trim());
    } catch (error) {
        showToast(error.message || "保存学生信息失败");
    }
}

async function deleteStudentRecord(studentId) {
    if (!window.confirm("确定删除这条学生记录吗？")) {
        return;
    }

    try {
        const response = await fetch(`/api/students/${studentId}`, { method: "DELETE" });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "删除失败");
        }

        selectedStudentIds.delete(studentId);
        showToast(result.message || "删除成功");
        loadStudents(searchInput.value.trim());
    } catch (error) {
        showToast(error.message || "删除学生失败");
    }
}

async function batchDeleteStudents() {
    const ids = Array.from(selectedStudentIds);
    if (!ids.length) {
        showToast("请先选择要删除的学生");
        return;
    }

    if (!window.confirm(`确定批量删除选中的 ${ids.length} 条学生记录吗？`)) {
        return;
    }

    try {
        const response = await fetch("/api/students/batch-delete", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids }),
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "批量删除失败");
        }

        selectedStudentIds.clear();
        showToast(result.message || "批量删除成功");
        loadStudents(searchInput.value.trim());
    } catch (error) {
        showToast(error.message || "批量删除失败");
    }
}

async function importStudentsFromFile(event) {
    const file = event.target.files?.[0];
    if (!file) {
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/api/students/import", {
            method: "POST",
            body: formData,
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "导入失败");
        }

        const errorMessage = result.errors?.length ? `；${result.errors.join("；")}` : "";
        showToast((result.message || "导入成功") + errorMessage);
        selectedStudentIds.clear();
        loadStudents(searchInput.value.trim());
    } catch (error) {
        showToast(error.message || "导入失败");
    } finally {
        event.target.value = "";
    }
}

function exportStudents(format) {
    const keyword = searchInput?.value.trim() || "";
    const url = `/api/students/export?format=${encodeURIComponent(format)}&keyword=${encodeURIComponent(keyword)}`;
    window.location.href = url;
}

function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    document.body.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3200);
}

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

window.editStudent = editStudent;
window.deleteStudentRecord = deleteStudentRecord;
