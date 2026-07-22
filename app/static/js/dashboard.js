const page = document.querySelector("[data-dashboard-page]");

if (page) {
  const elements = {
    statsLoading: page.querySelector("[data-stats-loading]"),
    statsValue: page.querySelector("[data-stats-value]"),
    statsError: page.querySelector("[data-stats-error]"),
    healthLoading: page.querySelector("[data-health-loading]"),
    healthValue: page.querySelector("[data-health-value]"),
    healthError: page.querySelector("[data-health-error]"),
  };

  void initialize();

  async function initialize() {
    await Promise.allSettled([loadStats(), loadHealth()]);
  }

  async function loadStats() {
    setCardState("stats", "loading");
    try {
      const response = await fetch("/api/students/stats");
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error("stats_failed");
      }
      elements.statsValue.textContent = String(payload.data?.total_students ?? 0);
      setCardState("stats", "success");
    } catch (error) {
      console.error(error);
      setCardState("stats", "error");
    }
  }

  async function loadHealth() {
    setCardState("health", "loading");
    try {
      const response = await fetch("/api/health");
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error("health_failed");
      }
      elements.healthValue.textContent = payload.data?.status === "ok" ? "运行正常" : "状态异常";
      setCardState("health", "success");
    } catch (error) {
      console.error(error);
      setCardState("health", "error");
    }
  }

  function setCardState(kind, state) {
    const loading = elements[`${kind}Loading`];
    const value = elements[`${kind}Value`];
    const error = elements[`${kind}Error`];

    loading.hidden = state !== "loading";
    value.hidden = state !== "success";
    error.hidden = state !== "error";
  }
}
