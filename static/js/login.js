/**
 * 登录页面 JavaScript
 * 前后端分离方式处理登录流程
 */

(function () {
    "use strict";

    var form = document.getElementById("loginForm");
    var usernameInput = document.getElementById("loginUsername");
    var passwordInput = document.getElementById("loginPassword");
    var errorMessage = document.getElementById("loginErrorMessage");
    var submitBtn = document.getElementById("loginSubmitBtn");

    if (!form) return;

    // 如果已登录，直接跳转首页
    fetch("/api/auth/me")
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.success) {
                window.location.href = "/";
            }
        })
        .catch(function () { /* 未登录，继续显示登录页 */ });

    /**
     * 显示登录错误信息
     */
    function showError(message) {
        if (!errorMessage) return;
        errorMessage.textContent = message;
        errorMessage.style.display = "block";
    }

    /**
     * 隐藏登录错误信息
     */
    function hideError() {
        if (!errorMessage) return;
        errorMessage.textContent = "";
        errorMessage.style.display = "none";
    }

    /**
     * 设置提交按钮加载状态
     */
    function setLoading(loading) {
        if (!submitBtn) return;
        submitBtn.disabled = loading;
        submitBtn.textContent = loading ? "登录中..." : "登 录";
    }

    /**
     * 执行登录请求
     */
    async function performLogin(username, password) {
        var response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: username, password: password }),
        });

        var result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "登录失败，请重试");
        }

        return result;
    }

    /**
     * 登录成功后的跳转
     */
    function redirectAfterLogin() {
        var params = new URLSearchParams(window.location.search);
        var next = params.get("next") || "/";
        window.location.href = next;
    }

    // ──────────────────────────────────────────
    // 事件绑定
    // ──────────────────────────────────────────

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        hideError();

        var username = usernameInput.value.trim();
        var password = passwordInput.value.trim();

        if (!username) {
            showError("请输入用户名");
            usernameInput.focus();
            return;
        }

        if (!password) {
            showError("请输入密码");
            passwordInput.focus();
            return;
        }

        setLoading(true);

        try {
            await performLogin(username, password);
            redirectAfterLogin();
        } catch (error) {
            showError(error.message || "登录失败，请检查网络连接");
            setLoading(false);
            passwordInput.value = "";
            passwordInput.focus();
        }
    });

    // 按回车时清除错误提示
    usernameInput.addEventListener("input", hideError);
    passwordInput.addEventListener("input", hideError);
})();
