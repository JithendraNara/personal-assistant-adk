(function () {
  const STORAGE_KEY = "mission_control_api_key";
  const state = {
    apiKey: localStorage.getItem(STORAGE_KEY) || "",
    live: true,
    refreshMs: 3000,
    snapshot: null,
    selectedSessionId: null,
    onSnapshot: null,
    onError: null,
  };

  const refs = {};

  function byId(id) {
    if (!id) return null;
    if (refs[id]) return refs[id];
    const node = document.getElementById(id);
    if (node) refs[id] = node;
    return node;
  }

  function setText(id, value) {
    const node = byId(id);
    if (!node) return;
    node.textContent = value;
  }

  function setHtml(id, value) {
    const node = byId(id);
    if (!node) return;
    node.innerHTML = value;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function truncate(value, max) {
    const source = String(value || "");
    if (source.length <= max) return source;
    return `${source.slice(0, max)}...`;
  }

  function prettyTime(isoString) {
    if (!isoString) return "-";
    const dt = new Date(isoString);
    if (Number.isNaN(dt.getTime())) return isoString;
    return dt.toLocaleString();
  }

  function setAuthStatus(message, bad) {
    const node = byId("auth-status");
    if (!node) return;
    node.textContent = message || "";
    node.className = bad ? "status-line bad" : "status-line";
  }

  function updateNavActive() {
    const current = window.location.pathname;
    document.querySelectorAll(".nav-link").forEach((link) => {
      const target = link.getAttribute("href") || "";
      const active = current === target || (target === "/mission-control" && current === "/mission-control/overview");
      link.classList.toggle("active", active);
    });
  }

  async function apiRequest(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (state.apiKey) {
      headers["X-API-Key"] = state.apiKey;
    }
    if (options.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(path, { ...options, headers });
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json();
        detail = payload.detail || JSON.stringify(payload);
      } catch (_) {
        const text = await response.text();
        if (text) detail = text;
      }
      const error = new Error(detail);
      error.status = response.status;
      throw error;
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return response.text();
  }

  function renderRuntime(runtime) {
    if (!runtime) return;
    const chips = [];
    chips.push(`<span class=\"chip good\">${escapeHtml(runtime.app_name || "personal_assistant")}</span>`);
    chips.push(`<span class=\"chip\">session:${escapeHtml(runtime.session_service || "-")}</span>`);
    chips.push(`<span class=\"chip\">memory:${escapeHtml(runtime.memory_service || "-")}</span>`);
    chips.push(`<span class=\"chip\">plugins:${escapeHtml(String(runtime.plugins_loaded ?? 0))}</span>`);
    (runtime.agents || []).slice(0, 10).forEach((agent) => {
      chips.push(`<span class=\"chip\">${escapeHtml(agent)}</span>`);
    });

    setHtml("runtime-chips", chips.join(""));
    setText("meta-backend", `${runtime.session_service || "-"} / ${runtime.memory_service || "-"}`);
    setText("meta-model", runtime.model || "-");
  }

  async function refreshSnapshot() {
    try {
      const snapshot = await apiRequest("/api/mission-control/snapshot?max_sessions=180&max_events=400");
      state.snapshot = snapshot;
      renderRuntime(snapshot.runtime || {});
      setText("meta-generated", prettyTime(snapshot.generated_at));
      setText("refresh-status", `Updated ${prettyTime(snapshot.generated_at)} · uptime ${snapshot.uptime_seconds || 0}s`);
      setAuthStatus(state.apiKey ? "API key loaded" : "No API key set (works if auth is disabled)", false);

      if (typeof state.onSnapshot === "function") {
        await state.onSnapshot(snapshot, api);
      }
    } catch (error) {
      setText("refresh-status", `Refresh failed: ${error.message}`);
      setAuthStatus(error.status === 401 ? "Unauthorized. Set valid APP_API_KEY." : error.message, true);
      if (typeof state.onError === "function") {
        state.onError(error);
      }
    }
  }

  function bindControls() {
    const keyInput = byId("api-key");
    if (keyInput) {
      keyInput.value = state.apiKey;
    }

    const saveButton = byId("save-key");
    if (saveButton) {
      saveButton.addEventListener("click", () => {
        state.apiKey = (byId("api-key")?.value || "").trim();
        if (state.apiKey) {
          localStorage.setItem(STORAGE_KEY, state.apiKey);
          setAuthStatus("API key saved", false);
        } else {
          localStorage.removeItem(STORAGE_KEY);
          setAuthStatus("API key cleared", false);
        }
        refreshSnapshot();
      });
    }

    const clearButton = byId("clear-key");
    if (clearButton) {
      clearButton.addEventListener("click", () => {
        state.apiKey = "";
        if (byId("api-key")) byId("api-key").value = "";
        localStorage.removeItem(STORAGE_KEY);
        setAuthStatus("API key cleared", false);
        refreshSnapshot();
      });
    }

    const refreshButton = byId("refresh-now");
    if (refreshButton) {
      refreshButton.addEventListener("click", refreshSnapshot);
    }

    const toggleButton = byId("toggle-live");
    if (toggleButton) {
      toggleButton.addEventListener("click", () => {
        state.live = !state.live;
        toggleButton.textContent = state.live ? "Pause Live" : "Resume Live";
      });
    }

    const docsButton = byId("open-api-docs");
    if (docsButton) {
      docsButton.addEventListener("click", () => window.open("/docs", "_blank", "noopener,noreferrer"));
    }

    const healthButton = byId("open-health");
    if (healthButton) {
      healthButton.addEventListener("click", () => window.open("/health", "_blank", "noopener,noreferrer"));
    }

    updateNavActive();
  }

  function startLoop() {
    setInterval(() => {
      if (state.live) {
        refreshSnapshot();
      }
    }, state.refreshMs);
  }

  function setSelectedSession(sessionId, route) {
    state.selectedSessionId = sessionId || null;
    setText("selected-session", sessionId || "-");
    if (route !== undefined) {
      setText("active-route", route || "-");
    }
  }

  async function loadSessionDetail(sessionId) {
    if (!sessionId) return null;
    return apiRequest(`/api/mission-control/sessions/${encodeURIComponent(sessionId)}`);
  }

  async function sendChat(payload) {
    return apiRequest("/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  const api = {
    apiRequest,
    loadSessionDetail,
    sendChat,
    prettyTime,
    escapeHtml,
    truncate,
    setSelectedSession,
    getState: () => state,
    refreshSnapshot,
  };

  async function boot(options = {}) {
    state.onSnapshot = options.onSnapshot || null;
    state.onError = options.onError || null;
    state.refreshMs = options.refreshMs || 3000;
    bindControls();
    await refreshSnapshot();
    startLoop();
  }

  window.MissionControlShared = {
    boot,
    api,
  };
})();
