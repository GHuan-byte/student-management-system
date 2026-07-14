const studentsTableBody = document.getElementById("studentsTableBody");
const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const resetButton = document.getElementById("resetButton");
const addStudentButton = document.getElementById("addStudentButton");
const studentModal = document.getElementById("studentModal");
const studentForm = document.getElementById("studentForm");
const modalTitle = document.getElementById("modalTitle");

document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    loadStudents();
});

function bindEvents() {
    searchButton?.addEventListener("click", () => loadStudents(searchInput.value.trim()));
    resetButton?.addEventListener("click", resetSearch);
    addStudentButton?.addEventListener("click", openAddModal);
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
    studentsTableBody.innerHTML = '<tr><td colspan="10" class="empty-cell">正在加载学生数据...</td></tr>';
    const url = keyword ? `/api/students?keyword=${encodeURIComponent(keyword)}` : "/api/students";

    try {
        const response = await fetch(url);
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "加载失败");
        }
        renderStudents(result.data);
    } catch (error) {
        showToast(error.message || "加载学生数据失败");
        studentsTableBody.innerHTML = '<tr><td colspan="10" class="empty-cell">加载失败，请稍后重试。</td></tr>';
    }
}

function renderStudents(students) {
    if (!students.length) {
        studentsTableBody.innerHTML = '<tr><td colspan="10" class="empty-cell">暂无学生数据</td></tr>';
        return;
    }

    studentsTableBody.innerHTML = students.map((student) => `
        <tr>
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
}

function resetSearch() {
    searchInput.value = "";
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
        showToast(result.message || "删除成功");
        loadStudents(searchInput.value.trim());
    } catch (error) {
        showToast(error.message || "删除学生失败");
    }
}

function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    document.body.appendChild(toast);
    window.setTimeout(() => toast.remove(), 2600);
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
