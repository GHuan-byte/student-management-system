let studentsTableBody = null;
let searchInput = null;
let searchForm = null;
let resetButton = null;
let addStudentButton = null;
let studentModal = null;
let studentForm = null;
let modalTitle = null;
let selectAllStudents = null;
let batchDeleteButton = null;
let selectedCount = null;
let searchResultCount = null;
let importCsvButton = null;
let exportCsvButton = null;
let exportExcelButton = null;
let importFileInput = null;

let selectedStudentIds = new Set();
let currentStudents = [];
let currentSortBy = "id";
let currentSortOrder = "asc";
let currentKeyword = "";

const pageSize = 15;

let currentPage = 1;
let totalPages = 1;
let totalStudents = 0;

let paginationSummary = null;
let pageNumberButtons = null;
let firstPageButton = null;
let previousPageButton = null;
let nextPageButton = null;
let lastPageButton = null;

let studentsPageInitialized = false;

function initStudentsPage() {
    if (studentsPageInitialized) {
        return;
    }

    studentsTableBody = document.getElementById("studentsTableBody");
    searchInput = document.getElementById("searchInput");
    searchForm = document.getElementById("searchForm");
    resetButton = document.getElementById("resetButton");
    addStudentButton = document.getElementById("addStudentButton");
    studentModal = document.getElementById("studentModal");
    studentForm = document.getElementById("studentForm");
    modalTitle = document.getElementById("modalTitle");
    selectAllStudents = document.getElementById("selectAllStudents");
    batchDeleteButton = document.getElementById("batchDeleteButton");
    selectedCount = document.getElementById("selectedCount");
    searchResultCount = document.getElementById("searchResultCount");
    importCsvButton = document.getElementById("importCsvButton");
    exportCsvButton = document.getElementById("exportCsvButton");
    exportExcelButton = document.getElementById("exportExcelButton");
    importFileInput = document.getElementById("importFileInput");


    paginationSummary =
        document.getElementById("paginationSummary");

    pageNumberButtons =
        document.getElementById("pageNumberButtons");

    firstPageButton =
        document.getElementById("firstPageButton");

    previousPageButton =
        document.getElementById("previousPageButton");

    nextPageButton =
        document.getElementById("nextPageButton");

    lastPageButton =
        document.getElementById("lastPageButton");

    if (!studentsTableBody || !searchForm || !searchInput) {
        console.error("学生管理页面必要元素缺失", {
            studentsTableBody,
            searchForm,
            searchInput,
        });
        return;
    }

    studentsPageInitialized = true;

    bindEvents();
    loadStudents();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initStudentsPage, {
        once: true,
    });
} else {
    initStudentsPage();
}

function bindEvents() {
    searchForm?.addEventListener("submit", (event) => {
        event.preventDefault();

        currentKeyword = searchInput.value.trim();
        currentPage = 1;
        selectedStudentIds.clear();

        loadStudents();
    });


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
    studentModal?.addEventListener("click", (event) => {
        if (event.target === studentModal) {
            closeModal();
        }
    });

    // 首页
    firstPageButton?.addEventListener("click", () => {
        goToPage(1);
    });

    // 上一页
    previousPageButton?.addEventListener("click", () => {
        goToPage(currentPage - 1);
    });

    // 下一页
    nextPageButton?.addEventListener("click", () => {
        goToPage(currentPage + 1);
    });

    // 末页
    lastPageButton?.addEventListener("click", () => {
        goToPage(totalPages);
    });

    bindSortEvents();
}

function bindSortEvents() {
    document.querySelectorAll("th[data-sort-key]").forEach((th) => {
        const sortKey = th.dataset.sortKey;
        const btn = th.querySelector(".sort-btn");
        const handler = () => {
            if (currentSortBy === sortKey) {
                currentSortOrder = currentSortOrder === "asc" ? "desc" : "asc";
            } else {
                currentSortBy = sortKey;
                currentSortOrder = "asc";
            }

            currentPage = 1;
            selectedStudentIds.clear();

            loadStudents();
        };
        btn?.addEventListener("click", (e) => {
            e.stopPropagation();
            handler();
        });
        th.addEventListener("click", handler);
    });
}

function updateSortIndicators() {
    document.querySelectorAll("th[data-sort-key]").forEach((th) => {
        const sortKey = th.dataset.sortKey;
        const btn = th.querySelector(".sort-btn");
        if (sortKey === currentSortBy) {
            const indicator = currentSortOrder === "asc" ? "↑" : "↓";
            btn.textContent = indicator;
            th.setAttribute("aria-sort", currentSortOrder === "asc" ? "ascending" : "descending");
        } else {
            btn.textContent = "↕️";
            th.setAttribute("aria-sort", "none");
        }
    });
}

function buildApiUrl() {
    const params = new URLSearchParams();

    if (currentKeyword) {
        params.set("keyword", currentKeyword);
    }

    params.set("sort_by", currentSortBy);
    params.set("sort_order", currentSortOrder);
    params.set("page", currentPage);
    params.set("page_size", pageSize);

    return `/api/students?${params.toString()}`;
}

async function loadStudents() {
    studentsTableBody.innerHTML = '<tr><td colspan="11" class="empty-cell">正在加载学生数据...</td></tr>';

    try {
        const response = await fetch(buildApiUrl());
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "加载失败");
        }

        currentStudents = result.data;

        const pagination = result.pagination || {};

        currentPage = pagination.page || 1;
        totalPages = pagination.total_pages || 1;
        totalStudents = pagination.total || 0;

        selectedStudentIds.clear();

        syncSelectedStudents();
        renderStudents(currentStudents);
        updateBatchDeleteState();
        updateSearchResultCount();
        updateSortIndicators();
        renderPagination();
    } catch (error) {
        showToast(error.message || "加载学生数据失败");
        studentsTableBody.innerHTML = '<tr><td colspan="11" class="empty-cell">加载失败，请稍后重试。</td></tr>';
    }
}

function updateSearchResultCount() {
    if (!searchResultCount) {
        return;
    }

    if (currentKeyword) {
        searchResultCount.textContent =
            `搜索 "${currentKeyword}" 找到 ${totalStudents} 条结果`;
    } else {
        searchResultCount.textContent =
            `共 ${totalStudents} 条记录`;
    }
}

function renderStudents(students) {
    if (!students.length) {
        const message = currentKeyword
            ? '未找到符合条件的学生'
            : '暂无学生数据';
        studentsTableBody.innerHTML = `<tr><td colspan="11" class="empty-cell">${message}</td></tr>`;
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
    const currentPageIds = new Set(
        currentStudents.map((student) => student.id)
    );

    const selectedOnCurrentPage = Array
        .from(selectedStudentIds)
        .filter((studentId) => {
            return currentPageIds.has(studentId);
        })
        .length;

    if (selectedCount) {
        selectedCount.textContent =
            `已选择 ${selectedOnCurrentPage} 项`;
    }

    if (batchDeleteButton) {
        batchDeleteButton.disabled =
            selectedOnCurrentPage === 0;
    }

    if (!selectAllStudents) {
        return;
    }

    const totalOnCurrentPage =
        currentStudents.length;

    if (totalOnCurrentPage === 0) {
        selectAllStudents.checked = false;
        selectAllStudents.indeterminate = false;
        selectAllStudents.disabled = true;
        return;
    }

    selectAllStudents.disabled = false;

    selectAllStudents.checked =
        selectedOnCurrentPage === totalOnCurrentPage;

    selectAllStudents.indeterminate =
        selectedOnCurrentPage > 0 &&
        selectedOnCurrentPage < totalOnCurrentPage;
}

function toggleSelectAllStudents() {
    if (!selectAllStudents || selectAllStudents.disabled) {
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
    currentKeyword = "";
    searchInput.value = "";
    currentSortBy = "id";
    currentSortOrder = "asc";
    currentPage = 1;

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
        loadStudents();
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
        loadStudents();
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
        loadStudents();
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
        currentKeyword = searchInput.value.trim();
        loadStudents();
    } catch (error) {
        showToast(error.message || "导入失败");
    } finally {
        event.target.value = "";
    }
}

function exportStudents(format) {
    const keyword = currentKeyword || searchInput?.value.trim() || "";
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

function goToPage(page) {
    if (page < 1 || page > totalPages || page === currentPage) {
        return;
    }

    currentPage = page;
    selectedStudentIds.clear();
    loadStudents();
}

function renderPagination() {
    if (paginationSummary) {
        paginationSummary.textContent =
            `第 ${currentPage} 页，共 ${totalPages} 页，共 ${totalStudents} 条记录`;
    }

    if (firstPageButton) {
        firstPageButton.disabled = currentPage <= 1;
    }

    if (previousPageButton) {
        previousPageButton.disabled = currentPage <= 1;
    }

    if (nextPageButton) {
        nextPageButton.disabled =
            currentPage >= totalPages;
    }

    if (lastPageButton) {
        lastPageButton.disabled =
            currentPage >= totalPages;
    }

    if (!pageNumberButtons) {
        return;
    }

    pageNumberButtons.innerHTML = "";

    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(
        totalPages,
        currentPage + 2
    );

    for (
        let page = startPage;
        page <= endPage;
        page += 1
    ) {
        const button = document.createElement("button");

        button.type = "button";
        button.className =
            page === currentPage
                ? "btn btn-primary"
                : "btn btn-secondary";

        button.textContent = String(page);

        button.addEventListener("click", () => {
            goToPage(page);
        });

        pageNumberButtons.appendChild(button);
    }
}

window.editStudent = editStudent;
window.deleteStudentRecord = deleteStudentRecord;
