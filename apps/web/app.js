const routeCatalog = [
  { key: "chats", label: "Chats" },
  { key: "dashboard", label: "Dashboard" },
  { key: "graph", label: "Graph" },
  { key: "runs", label: "Runs" },
  { key: "backends", label: "Backends" },
  { key: "terminal", label: "Terminal" },
];

const els = {
  topbarTitle: document.querySelector("#topbar-title"),
  topbarMeta: document.querySelector("#topbar-meta"),
  themeToggle: document.querySelector("#theme-toggle"),
  projectRail: document.querySelector("#project-rail"),
  workspaceSidebar: document.querySelector("#workspace-sidebar"),
  mainPanel: document.querySelector("#main-panel"),
  inspectorPanel: document.querySelector("#inspector-panel"),
  dockPanel: document.querySelector("#dock-panel"),
  dialogRoot: document.querySelector("#dialog-root"),
};

let pollHandle = null;
let threadRenameState = null;
let projectRenameState = null;
let projectCreateOpen = false;
let dialogState = null;

const themeStorageKey = "openmath:theme";

function currentTheme() {
  return window.localStorage.getItem(themeStorageKey) || "dark";
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  if (els.themeToggle) {
    els.themeToggle.textContent = theme === "light" ? "Dark" : "Light";
  }
}

function initializeThemeToggle() {
  applyTheme(currentTheme());
  if (!els.themeToggle || els.themeToggle.dataset.bound === "true") {
    return;
  }
  els.themeToggle.dataset.bound = "true";
  els.themeToggle.addEventListener("click", () => {
    const next = currentTheme() === "light" ? "dark" : "light";
    window.localStorage.setItem(themeStorageKey, next);
    applyTheme(next);
  });
}

function syncRouteChrome(routeKey) {
  document.body.dataset.route = routeKey || "home";
}

function routeFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (!parts.length || parts[0] !== "projects") {
    return { projectId: null, routeKey: "home", sessionId: null };
  }

  const projectId = parts[1] ?? null;
  const routeKey = parts[2] ?? "chats";
  const sessionId = routeKey === "chats" ? parts[3] ?? null : null;
  return { projectId, routeKey, sessionId };
}

function setPath(path, replace = false) {
  window.history[replace ? "replaceState" : "pushState"]({}, "", path);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { Accept: "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const payload = await response.json();
      if (payload?.error) {
        message = String(payload.error);
      }
    } catch (_error) {
      // Ignore JSON parse errors and keep the generic status message.
    }
    throw new Error(message);
  }
  return response.json();
}

function postJson(url, payload) {
  return fetchJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function patchJson(url, payload) {
  return fetchJson(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function deleteJson(url) {
  return fetchJson(url, { method: "DELETE" });
}

function formatCount(value) {
  return new Intl.NumberFormat().format(value ?? 0);
}

function clampInteger(value, fallback, min, max) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, parsed));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function excerpt(value, limit = 110) {
  const compact = String(value ?? "").replace(/\s+/g, " ").trim();
  if (!compact) {
    return "";
  }
  return compact.length > limit ? `${compact.slice(0, limit - 3)}...` : compact;
}

function relativeTime(value) {
  if (!value) {
    return "unknown";
  }
  const when = new Date(value);
  const now = new Date();
  const diffMs = when.getTime() - now.getTime();
  const minutes = Math.round(diffMs / 60000);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (Math.abs(minutes) < 60) {
    return formatter.format(minutes, "minute");
  }
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) {
    return formatter.format(hours, "hour");
  }
  const days = Math.round(hours / 24);
  return formatter.format(days, "day");
}

function statusPill(label) {
  return `<span class="pill">${escapeHtml(label)}</span>`;
}

function renderDialog() {
  if (!els.dialogRoot) {
    return;
  }

  if (!dialogState) {
    els.dialogRoot.hidden = true;
    els.dialogRoot.innerHTML = "";
    document.body.classList.remove("dialog-open");
    return;
  }

  document.body.classList.add("dialog-open");
  const description = dialogState.message
    ? `<p class="dialog-copy">${escapeHtml(dialogState.message)}</p>`
    : "";
  const promptField =
    dialogState.kind === "prompt"
      ? `
        <form id="dialog-form" class="dialog-form">
          <input
            id="dialog-input"
            class="dialog-input"
            type="text"
            value="${escapeHtml(dialogState.defaultValue ?? "")}"
            placeholder="${escapeHtml(dialogState.placeholder ?? "")}"
          />
        </form>
      `
      : "";
  const confirmClass = dialogState.tone === "danger" ? "danger" : "primary";

  els.dialogRoot.hidden = false;
  els.dialogRoot.innerHTML = `
    <div class="dialog-backdrop" data-action="close-dialog">
      <div class="dialog-surface" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
        <p class="panel-label">OpenMath</p>
        <h2 id="dialog-title">${escapeHtml(dialogState.title)}</h2>
        ${description}
        ${promptField}
        <div class="dialog-actions">
          <button id="dialog-cancel" class="dialog-button secondary" type="button">${escapeHtml(dialogState.cancelLabel ?? "Cancel")}</button>
          <button id="dialog-confirm" class="dialog-button ${confirmClass}" type="${dialogState.kind === "prompt" ? "submit" : "button"}" ${dialogState.kind === "prompt" ? 'form="dialog-form"' : ""}>${escapeHtml(dialogState.confirmLabel ?? "Confirm")}</button>
        </div>
      </div>
    </div>
  `;

  const backdrop = els.dialogRoot.querySelector(".dialog-backdrop");
  const surface = els.dialogRoot.querySelector(".dialog-surface");
  const cancelButton = document.querySelector("#dialog-cancel");
  const confirmButton = document.querySelector("#dialog-confirm");
  const form = document.querySelector("#dialog-form");
  const input = document.querySelector("#dialog-input");

  backdrop?.addEventListener("click", (event) => {
    if (event.target === backdrop) {
      closeDialog(null);
    }
  });
  surface?.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  cancelButton?.addEventListener("click", () => closeDialog(null));
  confirmButton?.addEventListener("click", () => {
    if (dialogState?.kind !== "confirm") {
      return;
    }
    closeDialog(true);
  });
  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    closeDialog(input?.value ?? "");
  });
  window.requestAnimationFrame(() => {
    if (input instanceof HTMLInputElement) {
      input.focus();
      input.select();
      return;
    }
    confirmButton?.focus();
  });
}

function closeDialog(result) {
  const resolver = dialogState?.resolve;
  dialogState = null;
  renderDialog();
  resolver?.(result);
}

function openConfirmDialog({ title, message, confirmLabel = "Confirm", cancelLabel = "Cancel", tone = "primary" }) {
  return new Promise((resolve) => {
    dialogState = {
      kind: "confirm",
      title,
      message,
      confirmLabel,
      cancelLabel,
      tone,
      resolve,
    };
    renderDialog();
  });
}

function openPromptDialog({
  title,
  message,
  defaultValue = "",
  placeholder = "",
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
}) {
  return new Promise((resolve) => {
    dialogState = {
      kind: "prompt",
      title,
      message,
      defaultValue,
      placeholder,
      confirmLabel,
      cancelLabel,
      tone: "primary",
      resolve,
    };
    renderDialog();
  });
}

function routeHref(projectId, routeKey, sessionId = null) {
  if (routeKey === "chats") {
    return sessionId
      ? `/projects/${projectId}/chats/${sessionId}`
      : `/projects/${projectId}/chats`;
  }
  return `/projects/${projectId}/${routeKey}`;
}

function launcherStorageKey(projectId) {
  return `openmath:launcher:${projectId}`;
}

function deriveLauncherState(state) {
  const stored = window.localStorage.getItem(launcherStorageKey(state.project.id));
  let parsed = {};
  if (stored) {
    try {
      parsed = JSON.parse(stored) ?? {};
    } catch (_error) {
      parsed = {};
    }
  }
  const readyProviders = state.agent_providers.filter((provider) => provider.available);
  const fallbackProvider =
    readyProviders.find((provider) => provider.connected) ??
    readyProviders[0] ??
    state.agent_providers[0];
  const providerId =
    state.agent_providers.find((provider) => provider.id === parsed.providerId)?.id ??
    fallbackProvider?.id ??
    "";
  const provider = state.agent_providers.find((item) => item.id === providerId);
  const model =
    provider?.models.find((item) => item.id === parsed.model)?.id ??
    provider?.default_model ??
    provider?.models?.[0]?.id ??
    "";
  const effort =
    (provider?.efforts ?? []).includes(parsed.effort)
      ? parsed.effort
      : provider?.default_effort ?? "medium";
  const runMode = parsed.runMode === "autoresearch" ? "autoresearch" : "once";
  const maxIterations = clampInteger(parsed.maxIterations, 12, 2, 500);
  const maxHours = clampInteger(parsed.maxHours, 4, 1, 24);

  return {
    providerId,
    model,
    effort,
    runMode,
    maxIterations,
    maxHours,
  };
}

function saveLauncherState(projectId, payload) {
  window.localStorage.setItem(launcherStorageKey(projectId), JSON.stringify(payload));
}

function providerThreadForSession(session, providerId) {
  return session?.provider_threads?.[providerId] ?? null;
}

function formatSessionHandle(value) {
  if (!value) {
    return "";
  }
  return value.length > 18 ? `${value.slice(0, 8)}...${value.slice(-6)}` : value;
}

function formatRunModeLabel(value) {
  return value === "autoresearch" ? "Autoresearch" : "Single turn";
}

function formatLoopLabel(runMode, iterationCount, maxIterations) {
  if (runMode !== "autoresearch") {
    return "Single turn";
  }
  return `${iterationCount ?? 0}/${maxIterations ?? 0} loops`;
}

function formatHoursLabel(maxMinutes) {
  if (!maxMinutes) {
    return "";
  }
  const hours = Math.max(1, Math.round(Number(maxMinutes) / 60));
  return `${hours}h budget`;
}

function folderLabelFromRoot(root) {
  return String(root ?? "")
    .split("/")
    .filter(Boolean)
    .pop() ?? "";
}

function renderTopbar(projects, state, route, activeSession) {
  if (!projects.length) {
    els.topbarTitle.innerHTML = `
      <p class="eyebrow">OpenMath</p>
      <h1>No projects found</h1>
      <p class="topbar-subtle">Initialize a folder to create chats, runs, and provider sessions.</p>
    `;
    els.topbarMeta.innerHTML = statusPill("No projects");
    return;
  }

  if (!state) {
    els.topbarTitle.innerHTML = `
      <p class="eyebrow">Workspace</p>
      <h1>Select a project folder</h1>
      <p class="topbar-subtle">Each folder keeps its own chats, runs, graph state, and bound provider threads.</p>
    `;
    els.topbarMeta.innerHTML = `
      ${statusPill(`${projects.length} project${projects.length === 1 ? "" : "s"}`)}
      ${statusPill("Select a folder")}
    `;
    return;
  }

  const currentTab = routeCatalog.find((item) => item.key === route.routeKey)?.label ?? "Chats";
  const sessionLabel =
    route.routeKey === "chats" && activeSession
      ? escapeHtml(activeSession.title)
      : escapeHtml(currentTab);
  const connectedProviders = state.agent_providers.filter((provider) => provider.connected).length;

  if (route.routeKey === "chats" && activeSession) {
    els.topbarTitle.innerHTML = `<h1>${sessionLabel}</h1>`;
    els.topbarMeta.innerHTML = "";
    return;
  }

  els.topbarTitle.innerHTML = `
    <p class="eyebrow">${escapeHtml(state.project.name)}</p>
    <h1>${sessionLabel}</h1>
    <p class="topbar-subtle">${escapeHtml(currentTab)} • ${escapeHtml(state.project.root)}</p>
  `;

  els.topbarMeta.innerHTML = `
    ${statusPill(`${projects.length} folder${projects.length === 1 ? "" : "s"}`)}
    ${statusPill(`${connectedProviders}/${state.agent_providers.length} providers ready`)}
    ${statusPill(`${formatCount(state.summary.active_agents)} active agents`)}
  `;
}

function renderProjectRail(projects, activeProjectId) {
  if (!projects.length) {
    els.projectRail.innerHTML = `
      <div class="sidebar-section">
        <p class="panel-label">Projects</p>
        <h2>No folders yet</h2>
        <p class="muted">Run <code>python3 -m openmath init path/to/project</code> to create the first one.</p>
      </div>
    `;
    return;
  }

  const seedProjectId = activeProjectId ?? projects[0]?.id ?? null;
  const nameCounts = projects.reduce((counts, project) => {
    counts[project.name] = (counts[project.name] ?? 0) + 1;
    return counts;
  }, {});
  els.projectRail.innerHTML = `
    <div class="sidebar-section sidebar-brand">
      <div class="sidebar-brand-row">
        <img class="brand-logo-image" src="/logo.png" alt="OpenMath logo" />
        <div>
          <h2>OpenMath</h2>
        </div>
      </div>
    </div>
    <div class="sidebar-section sidebar-actions">
      <button id="rail-new-thread" class="sidebar-action primary" type="button" ${seedProjectId ? "" : "disabled"}>New thread</button>
      <a class="sidebar-action" href="${seedProjectId ? `/projects/${seedProjectId}/runs` : "/"}">Runs</a>
      <a class="sidebar-action" href="${seedProjectId ? `/projects/${seedProjectId}/backends` : "/"}">Models</a>
    </div>
    <div class="sidebar-section project-section">
      <div class="sidebar-section-head">
        <p class="panel-label">Projects</p>
        <button id="rail-new-project" class="ghost-icon-button" type="button">+</button>
      </div>
      <div class="project-list compact">
        ${projects
          .map((project) => {
            const active = project.id === activeProjectId ? "active" : "";
            const editing = projectRenameState?.projectId === project.id;
            const duplicate = (nameCounts[project.name] ?? 0) > 1 ? "duplicate" : "";
            const folderLabel = folderLabelFromRoot(project.root) || project.id;
            const renameFormId = `project-rename-form-${project.id}`;
            return `
              <article class="project-card compact ${active} ${editing ? "editing" : ""} ${duplicate}" data-project-id="${escapeHtml(project.id)}">
                <div class="thread-card-head">
                  ${
                    editing
                      ? `
                        <form class="project-rename-form" id="${escapeHtml(renameFormId)}" data-project-id="${escapeHtml(project.id)}">
                          <input class="project-rename-input" type="text" value="${escapeHtml(projectRenameState?.name ?? project.name)}" />
                        </form>
                      `
                      : `
                        <a class="thread-card-link" href="/projects/${project.id}/chats">
                          <p class="project-card-title">${escapeHtml(project.name)}</p>
                          ${duplicate ? `<p class="project-card-path">${escapeHtml(folderLabel)}</p>` : ""}
                        </a>
                      `
                  }
                </div>
                <div class="thread-actions">
                  ${
                    editing
                      ? `
                        <button class="thread-action-button" type="submit" form="${escapeHtml(renameFormId)}">Save</button>
                        <button class="thread-action-button" type="button" data-action="cancel-rename-project" data-project-id="${escapeHtml(project.id)}">Cancel</button>
                      `
                      : `
                        <button class="thread-action-button" type="button" data-action="rename-project" data-project-id="${escapeHtml(project.id)}">Rename</button>
                        <button class="thread-action-button danger" type="button" data-action="delete-project" data-project-id="${escapeHtml(project.id)}">Delete</button>
                      `
                  }
                </div>
              </article>
            `;
          })
          .join("")}
      </div>
      ${
        projectCreateOpen
          ? `
            <form id="project-create-form" class="project-create-form">
              <input id="project-name-input" name="name" type="text" placeholder="Project name" />
              <div class="project-create-actions">
                <button class="sidebar-action primary" type="submit">Create</button>
                <button id="project-create-cancel" class="sidebar-action" type="button">Cancel</button>
              </div>
            </form>
          `
          : ""
      }
    </div>
  `;

  const newThreadButton = document.querySelector("#rail-new-thread");
  if (newThreadButton && seedProjectId) {
    newThreadButton.addEventListener("click", async () => {
      const payload = await postJson(`/api/projects/${seedProjectId}/sessions`, { title: "New Thread" });
      setPath(`/projects/${seedProjectId}/chats/${payload.session.id}`);
      await bootstrap();
    });
  }

  const newProjectButton = document.querySelector("#rail-new-project");
  if (newProjectButton) {
    newProjectButton.addEventListener("click", () => {
      projectCreateOpen = true;
      renderProjectRail(projects, activeProjectId);
      const nameInput = document.querySelector("#project-name-input");
      if (nameInput instanceof HTMLInputElement || nameInput instanceof HTMLTextAreaElement) {
        nameInput.focus();
      }
    });
  }

  const projectCreateCancel = document.querySelector("#project-create-cancel");
  if (projectCreateCancel) {
    projectCreateCancel.addEventListener("click", () => {
      projectCreateOpen = false;
      renderProjectRail(projects, activeProjectId);
    });
  }

  const projectCreateForm = document.querySelector("#project-create-form");
  if (projectCreateForm instanceof HTMLFormElement) {
    projectCreateForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = document.querySelector("#project-name-input")?.value.trim() ?? "";
      if (!name) {
        const nameInput = document.querySelector("#project-name-input");
        if (nameInput instanceof HTMLInputElement) {
          nameInput.focus();
        }
        return;
      }
      const payload = await postJson("/api/projects", { name });
      projectCreateOpen = false;
      setPath(`/projects/${payload.project.id}/chats`);
      await bootstrap();
    });
  }

  attachProjectRailActions(projects, activeProjectId);
}

function attachProjectRailActions(projects, activeProjectId) {
  document.querySelectorAll("[data-action='rename-project']").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const projectId = button.getAttribute("data-project-id");
      if (!projectId) {
        return;
      }
      const current = projects.find((item) => item.id === projectId);
      projectRenameState = {
        projectId,
        name: current?.name ?? "Untitled project",
      };
      renderProjectRail(projects, activeProjectId);
    });
  });

  document.querySelectorAll("[data-action='delete-project']").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const projectId = button.getAttribute("data-project-id");
      if (!projectId) {
        return;
      }
      const current = projects.find((item) => item.id === projectId);
      const confirmed = await openConfirmDialog({
        title: `Delete ${current?.name ?? "project"}?`,
        message: "This removes the OpenMath workspace for the project, but keeps the folder on disk.",
        confirmLabel: "Delete project",
        tone: "danger",
      });
      if (!confirmed) {
        return;
      }
      await deleteJson(`/api/projects/${projectId}`);
      projectRenameState = null;
      if (activeProjectId === projectId) {
        const remaining = projects.filter((item) => item.id !== projectId);
        setPath(remaining[0] ? `/projects/${remaining[0].id}/chats` : "/");
      }
      await bootstrap();
    });
  });

  document.querySelectorAll(".project-rename-form").forEach((form) => {
    const input = form.querySelector(".project-rename-input");
    const projectId = form.getAttribute("data-project-id");
    if (!input || !projectId) {
      return;
    }
    input.addEventListener("input", () => {
      if (!projectRenameState || projectRenameState.projectId !== projectId) {
        return;
      }
      projectRenameState = { ...projectRenameState, name: input.value };
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        projectRenameState = null;
        renderProjectRail(projects, activeProjectId);
      }
    });
    window.requestAnimationFrame(() => {
      input.focus();
      input.select();
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = input.value.trim();
      if (!name) {
        input.focus();
        return;
      }
      await patchJson(`/api/projects/${projectId}`, { name });
      projectRenameState = null;
      await bootstrap();
    });
  });

  document.querySelectorAll("[data-action='cancel-rename-project']").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      projectRenameState = null;
      renderProjectRail(projects, activeProjectId);
    });
  });
}

function renderAgentCards(activeAgents) {
  if (!activeAgents.length) {
    return `<p class="muted">No active agents.</p>`;
  }
  return `
    <div class="agent-list">
      ${activeAgents
        .map(
          (agent) => `
            <article class="agent-card">
              <div class="thread-card-head">
                <p class="thread-title">${escapeHtml(agent.provider_label ?? agent.backend ?? "agent")}</p>
                <span class="thread-count">${escapeHtml(agent.status ?? "unknown")}</span>
              </div>
              <p class="thread-preview">${escapeHtml(agent.model ?? "")} • ${escapeHtml(agent.effort ?? "medium")}</p>
              <p class="thread-meta">${escapeHtml(agent.summary ?? "")}</p>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderAgentStream(projectId, agentRuns, activeSession) {
  if (!agentRuns.length) {
    return `<p class="muted">No agent activity yet.</p>`;
  }
  return agentRuns
    .map((run) => {
      const active = run.session_id === activeSession?.id ? "active" : "";
      const status = escapeHtml(run.status ?? "unknown");
      const stopDisabled = run.stop_requested ? "disabled" : "";
      const loopLabel = formatLoopLabel(run.run_mode, run.iteration_count, run.max_iterations);
      const budgetLabel = formatHoursLabel(run.max_minutes);
      const scopeLabel = run.session_id === activeSession?.id ? "This thread" : run.session_title ?? "Another thread";
      return `
        <article class="stream-card ${active}">
          <div class="stream-card-head">
            <div class="stream-card-title">
              <p class="panel-label">${escapeHtml(run.provider_label ?? run.backend ?? "Agent")}</p>
              <h3>${escapeHtml(scopeLabel)}</h3>
            </div>
            <span class="status-chip">${status}</span>
          </div>
          <div class="stream-card-meta">
            <span>${escapeHtml(run.model ?? "")}</span>
            <span>${escapeHtml(run.effort ?? "medium")}</span>
            <span>${escapeHtml(formatRunModeLabel(run.run_mode))}</span>
          </div>
          <div class="stream-card-meta">
            <span>${escapeHtml(loopLabel)}</span>
            <span>${escapeHtml(budgetLabel)}</span>
            <span>${escapeHtml(relativeTime(run.last_activity_at ?? run.created_at))}</span>
          </div>
          <p class="stream-card-summary">${escapeHtml(excerpt(run.summary || run.prompt_excerpt || "", 160))}</p>
          <div class="stream-card-actions">
            <a class="thread-action-button" href="/projects/${projectId}/chats/${run.session_id}">Open</a>
            ${
              ["queued", "running"].includes(String(run.status ?? ""))
                ? `<button class="thread-action-button danger" type="button" data-action="stop-run" data-run-id="${escapeHtml(run.id)}" ${stopDisabled}>${run.stop_requested ? "Stopping..." : "Stop"}</button>`
                : ""
            }
          </div>
        </article>
      `;
    })
    .join("");
}

function attachThreadListActions(state, route, activeSession) {
  document.querySelectorAll("[data-action='rename-thread']").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const sessionId = button.getAttribute("data-session-id");
      if (!sessionId) {
        return;
      }
      const current = state.sessions.find((item) => item.id === sessionId);
      threadRenameState = {
        sessionId,
        title: current?.title ?? "New Thread",
      };
      renderSidebar(state, route, activeSession);
    });
  });

  document.querySelectorAll("[data-action='delete-thread']").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      const sessionId = button.getAttribute("data-session-id");
      if (!sessionId) {
        return;
      }
      const current = state.sessions.find((item) => item.id === sessionId);
      const confirmed = await openConfirmDialog({
        title: `Delete ${current?.title ?? "thread"}?`,
        message: "This removes the thread transcript from the OpenMath workspace.",
        confirmLabel: "Delete thread",
        tone: "danger",
      });
      if (!confirmed) {
        return;
      }
      await deleteJson(`/api/projects/${state.project.id}/sessions/${sessionId}`);
      threadRenameState = null;
      if (activeSession?.id === sessionId) {
        const remaining = state.sessions.filter((item) => item.id !== sessionId);
        setPath(
          remaining[0]
            ? `/projects/${state.project.id}/chats/${remaining[0].id}`
            : `/projects/${state.project.id}/chats`,
        );
      }
      await bootstrap();
    });
  });

  document.querySelectorAll(".thread-rename-form").forEach((form) => {
    const input = form.querySelector(".thread-rename-input");
    const sessionId = form.getAttribute("data-session-id");
    if (!input || !sessionId) {
      return;
    }
    input.addEventListener("input", () => {
      if (!threadRenameState || threadRenameState.sessionId !== sessionId) {
        return;
      }
      threadRenameState = { ...threadRenameState, title: input.value };
    });
    input.addEventListener("keydown", async (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        threadRenameState = null;
        renderSidebar(state, route, activeSession);
      }
    });
    window.requestAnimationFrame(() => {
      input.focus();
      input.select();
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const title = input.value.trim();
      if (!title) {
        input.focus();
        return;
      }
      await patchJson(`/api/projects/${state.project.id}/sessions/${sessionId}`, { title });
      threadRenameState = null;
      await bootstrap();
    });
  });

  document.querySelectorAll("[data-action='cancel-rename-thread']").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      threadRenameState = null;
      renderSidebar(state, route, activeSession);
    });
  });
}

function renderSidebar(state, route, activeSession) {
  if (!state) {
    els.workspaceSidebar.innerHTML = `
      <div class="sidebar-section">
        <p class="panel-label">Workspace</p>
        <h2>Select a project</h2>
        <p class="muted">Open a folder from the project picker to browse its chats, agents, runs, graph, and backends.</p>
      </div>
    `;
    return;
  }

  const routeLinks = routeCatalog
    .map((item) => {
      const href =
        item.key === "chats"
          ? routeHref(state.project.id, "chats", activeSession?.id ?? state.sessions[0]?.id ?? null)
          : routeHref(state.project.id, item.key);
      const active = item.key === route.routeKey ? "active" : "";
      return `
        <a class="nav-link ${active}" href="${href}">
          <span>${escapeHtml(item.label)}</span>
          <span class="nav-key">${escapeHtml(item.key.slice(0, 1).toUpperCase())}</span>
        </a>
      `;
    })
    .join("");

  const sessionCards = state.sessions.length
    ? state.sessions
        .map((session) => {
          const active = session.id === activeSession?.id ? "active" : "";
          const editing = threadRenameState?.sessionId === session.id;
          const renameFormId = `thread-rename-form-${session.id}`;
          return `
            <article class="thread-card ${active} ${editing ? "editing" : ""}">
              <div class="thread-card-head">
                ${
                  editing
                    ? `
                      <form class="thread-rename-form" id="${escapeHtml(renameFormId)}" data-session-id="${escapeHtml(session.id)}">
                        <input class="thread-rename-input" type="text" value="${escapeHtml(threadRenameState?.title ?? session.title)}" />
                      </form>
                    `
                    : `
                      <a class="thread-card-link" href="/projects/${state.project.id}/chats/${session.id}">
                        <p class="thread-title">${escapeHtml(session.title)}</p>
                      </a>
                    `
                }
                <span class="thread-meta">${escapeHtml(relativeTime(session.updated_at))}</span>
              </div>
              <div class="thread-actions">
                ${
                  editing
                    ? `
                      <button class="thread-action-button" type="submit" form="${escapeHtml(renameFormId)}">Save</button>
                      <button class="thread-action-button" type="button" data-action="cancel-rename-thread" data-session-id="${escapeHtml(session.id)}">Cancel</button>
                    `
                    : `
                      <button class="thread-action-button" type="button" data-action="rename-thread" data-session-id="${escapeHtml(session.id)}">Rename</button>
                      <button class="thread-action-button danger" type="button" data-action="delete-thread" data-session-id="${escapeHtml(session.id)}">Delete</button>
                    `
                }
              </div>
            </article>
          `;
        })
        .join("")
    : `<p class="muted">No chats yet.</p>`;

  if (route.routeKey === "chats") {
    els.workspaceSidebar.innerHTML = `
      <div class="sidebar-section threads-section">
        <div class="sidebar-section-head">
          <p class="panel-label">Threads</p>
        </div>
        <div class="thread-list compact">${sessionCards}</div>
      </div>
    `;
    attachThreadListActions(state, route, activeSession);
    return;
  }

  els.workspaceSidebar.innerHTML = `
    <div class="sidebar-section">
      <div class="sidebar-section-head">
        <p class="panel-label">Current project</p>
        <button id="new-chat-button" class="ghost-icon-button" type="button">+</button>
      </div>
      <h3>${escapeHtml(state.project.name)}</h3>
      <p class="muted">${escapeHtml(excerpt(state.project.objective, 104))}</p>
    </div>
    <div class="sidebar-section">
      <div class="sidebar-section-head">
        <p class="panel-label">Threads</p>
        <span class="thread-count">${formatCount(state.summary.sessions)}</span>
      </div>
      <div class="thread-list compact">${sessionCards}</div>
    </div>
    <div class="sidebar-section">
      <p class="panel-label">Views</p>
      <nav class="route-nav compact">${routeLinks}</nav>
    </div>
    <div class="sidebar-section">
      <div class="sidebar-section-head">
        <p class="panel-label">Agents</p>
        <span class="thread-count">${formatCount(state.summary.active_agents)}</span>
      </div>
      ${renderAgentCards(state.active_agents)}
    </div>
  `;

  const newChatButton = document.querySelector("#new-chat-button");
  if (newChatButton) {
    newChatButton.addEventListener("click", async () => {
      const proposed = await openPromptDialog({
        title: "New thread",
        message: "Name the new thread.",
        defaultValue: `New Chat ${state.summary.sessions + 1}`,
        placeholder: "Thread name",
        confirmLabel: "Create thread",
      });
      if (proposed === null) {
        return;
      }
      const title = proposed.trim() || `New Chat ${state.summary.sessions + 1}`;
      const payload = await postJson(`/api/projects/${state.project.id}/sessions`, { title });
      setPath(`/projects/${state.project.id}/chats/${payload.session.id}`);
      await bootstrap();
    });
  }
}

function renderLanding(projects) {
  els.mainPanel.innerHTML = `
    <section class="hero panel landing-hero">
      <div>
        <p class="panel-label">OpenMath</p>
        <h2>Project folders on the left, native agent chats on the right</h2>
      </div>
      <p class="muted">Pick a folder, select Codex, Claude Code, or Gemini in the composer, and launch as many agents as you need.</p>
    </section>
    <section class="landing-grid">
      ${projects
        .map(
          (project) => `
            <a class="landing-card panel" href="/projects/${project.id}/chats">
              <p class="panel-label">Project</p>
              <h3>${escapeHtml(project.name)}</h3>
              <p class="muted">${escapeHtml(project.root)}</p>
              <p>${escapeHtml(excerpt(project.objective, 112))}</p>
            </a>
          `,
        )
        .join("")}
    </section>
    <section class="panel">
      <p class="panel-label">Create more folders</p>
      <div class="command-list">
        <code>python3 -m openmath init path/to/second-project</code>
        <code>python3 -m openmath web /path/to/parent-directory</code>
      </div>
    </section>
  `;
  els.inspectorPanel.innerHTML = `
    <div class="sidebar-footer-block">
      <p class="panel-label">Discovery</p>
      <p>${projects.length} project${projects.length === 1 ? "" : "s"} found</p>
    </div>
    <div class="sidebar-footer-block">
      <p class="panel-label">Runtime</p>
      <p class="muted">Chats keep provider bindings per project folder.</p>
    </div>
  `;
  els.dockPanel.innerHTML = `
    <article class="panel subtle">
      <p class="panel-label">Start here</p>
      <h3>Pick a folder</h3>
      <p>Open a project from the rail to launch Codex, Claude Code, or Gemini in a chat thread.</p>
    </article>
    <article class="panel subtle">
      <p class="panel-label">Auth</p>
      <h3>ulam auth codex</h3>
      <p>OpenMath mirrors the UlamAI connection flow instead of inventing a new one.</p>
    </article>
  `;
}

function renderNoProjects() {
  els.mainPanel.innerHTML = `
    <section class="hero panel">
      <p class="panel-label">Getting started</p>
      <h2>No OpenMath projects found</h2>
      <p class="muted">
        Initialize one or more folders, then open their parent directory in the local gateway.
      </p>
      <div class="command-list">
        <code>python3 -m openmath init .</code>
        <code>python3 -m openmath init path/to/project</code>
        <code>python3 -m openmath web .</code>
      </div>
    </section>
  `;
  els.workspaceSidebar.innerHTML = `
    <div class="sidebar-section">
      <p class="panel-label">Workspace</p>
      <h2>No folders yet</h2>
      <p class="muted">Create a project to get chats, agent runs, graph state, and backend health on disk.</p>
    </div>
  `;
  els.inspectorPanel.innerHTML = `<p class="muted">Project context appears here after initialization.</p>`;
  els.dockPanel.innerHTML = "";
}

function metricCard(label, value, tone = "default") {
  return `
    <article class="metric-card ${tone}">
      <p class="metric-label">${escapeHtml(label)}</p>
      <p class="metric-value">${escapeHtml(value)}</p>
    </article>
  `;
}

function renderRunsTable(runs) {
  if (!runs.length) {
    return `<p class="muted">No runs recorded yet.</p>`;
  }
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Run</th><th>Type</th><th>Status</th><th>Backend</th><th>Summary</th></tr>
        </thead>
        <tbody>
          ${runs
            .map(
              (run) => `
                <tr>
                  <td>${escapeHtml(run.id)}</td>
                  <td>${escapeHtml(run.type ?? "unknown")}</td>
                  <td>${escapeHtml(run.status ?? "unknown")}</td>
                  <td>${escapeHtml(run.backend ?? "native")}</td>
                  <td>${escapeHtml(run.summary ?? "")}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderNodesList(nodes) {
  if (!nodes.length) {
    return `<p class="muted">The graph is still empty.</p>`;
  }
  return `
    <div class="list-grid">
      ${nodes
        .map(
          (node) => `
            <article class="list-card">
              <p class="list-card-label">${escapeHtml(node.kind ?? "node")}</p>
              <h3>${escapeHtml(node.label ?? node.id ?? "Untitled node")}</h3>
              <p class="muted">status: ${escapeHtml(node.status ?? "unknown")}</p>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderDashboard(state) {
  return `
    <section class="hero panel">
      <p class="panel-label">Dashboard</p>
      <h2>${escapeHtml(state.project.objective)}</h2>
      <p class="muted">Chats are the primary surface now, but runs, graph, and backend health still sit alongside them.</p>
    </section>
    <section class="metrics-grid">
      ${metricCard("Chats", formatCount(state.summary.sessions), "accent")}
      ${metricCard("Messages", formatCount(state.summary.messages))}
      ${metricCard("Active agents", formatCount(state.summary.active_agents), "accent")}
      ${metricCard("Runs", formatCount(state.summary.runs))}
      ${metricCard("Graph nodes", formatCount(state.summary.graph_nodes))}
      ${metricCard("Broken", formatCount(state.summary.broken_declarations), "warning")}
    </section>
    <section class="split-grid">
      <article class="panel">
        <p class="panel-label">Recent runs</p>
        ${renderRunsTable(state.recent_runs)}
      </article>
      <article class="panel">
        <p class="panel-label">Recent graph nodes</p>
        ${renderNodesList(state.recent_nodes)}
      </article>
    </section>
  `;
}

function renderGraph(state) {
  return `
    <section class="hero panel">
      <p class="panel-label">Claim graph</p>
      <h2>${formatCount(state.graph.counts.nodes)} nodes • ${formatCount(state.graph.counts.edges)} edges</h2>
      <p class="muted">Use chat agents to explore ideas, then promote accepted results into graph nodes and runs.</p>
    </section>
    <section class="metrics-grid">
      ${metricCard("Accepted", formatCount(state.graph.counts.accepted), "accent")}
      ${metricCard("Speculative", formatCount(state.graph.counts.speculative))}
      ${metricCard("Broken", formatCount(state.graph.counts.broken), "warning")}
    </section>
    <section class="panel">${renderNodesList(state.graph.nodes)}</section>
  `;
}

function renderBackends(state) {
  return `
    <section class="hero panel">
      <p class="panel-label">Backends</p>
      <h2>Lean and proving status</h2>
      <p class="muted">LLM chat agents are now separate from the proving backend cards, but both live in the same project workspace.</p>
    </section>
    <section class="backend-grid">
      ${state.backends
        .map(
          (backend) => `
            <article class="panel backend-card">
              <div class="backend-head">
                <div>
                  <p class="panel-label">${escapeHtml(backend.id)}</p>
                  <h3>${escapeHtml(backend.label)}</h3>
                </div>
                <span class="status-chip">${escapeHtml(backend.status)}</span>
              </div>
              <p class="muted">${escapeHtml(backend.executable ?? "Executable not found.")}</p>
              <p>Version: ${escapeHtml(backend.version ?? "unknown")}</p>
              <ul class="simple-list">
                ${backend.capabilities.map((capability) => `<li>${escapeHtml(capability)}</li>`).join("")}
              </ul>
            </article>
          `,
        )
        .join("")}
    </section>
  `;
}

function renderTerminal() {
  return `
    <section class="hero panel">
      <p class="panel-label">Terminal</p>
      <h2>Terminal tabs still come next</h2>
      <p class="muted">The first real agent layer is now in chat. Dedicated shell tabs for raw provider CLIs are still the next piece.</p>
    </section>
    <section class="panel">
      <div class="command-list">
        <code>ulam auth codex</code>
        <code>ulam auth claude</code>
        <code>ulam auth gemini</code>
      </div>
    </section>
  `;
}

function renderProviderOptions(providers, selectedProviderId) {
  return providers
    .map((provider) => {
      const selected = provider.id === selectedProviderId ? "selected" : "";
      const suffix =
        provider.status === "ready"
          ? ""
          : provider.status === "disconnected"
            ? " (connect)"
            : " (unavailable)";
      return `<option value="${provider.id}" ${selected}>${escapeHtml(provider.label + suffix)}</option>`;
    })
    .join("");
}

function renderModelOptions(provider, selectedModel) {
  return (provider?.models ?? [])
    .map((model) => {
      const selected = model.id === selectedModel ? "selected" : "";
      return `<option value="${model.id}" ${selected}>${escapeHtml(model.label)}</option>`;
    })
    .join("");
}

function renderEffortOptions(provider, selectedEffort) {
  return (provider?.efforts ?? [])
    .map((effort) => {
      const selected = effort === selectedEffort ? "selected" : "";
      return `<option value="${effort}" ${selected}>${escapeHtml(effort)}</option>`;
    })
    .join("");
}

function renderMessageMeta(message) {
  const parts = [];
  const status = String(message.status ?? "");
  if (status && status !== "finished") {
    if (message.provider_label) {
      parts.push(message.provider_label);
    }
    if (message.model) {
      parts.push(message.model);
    }
    if (message.effort) {
      parts.push(message.effort);
    }
    parts.push(status);
  }
  if (!parts.length) {
    return "";
  }
  return `<div class="message-inline-meta">${escapeHtml(parts.join(" • "))}</div>`;
}

function isSeedMessage(message, index) {
  const content = String(message?.content ?? "");
  if (message?.source === "session-seed") {
    return true;
  }
  return (
    index === 0 &&
    message?.role === "assistant" &&
    content.includes("is ready. This thread is stored in `.openmath/sessions/`")
  );
}

function renderChatMessages(session) {
  const visibleMessages = session.messages.filter((message, index) => !isSeedMessage(message, index));
  if (!visibleMessages.length) {
    return "";
  }
  return visibleMessages
    .map((message) => {
      const role = escapeHtml(message.role ?? "note");
      const status = escapeHtml(message.status ?? "");
      const running = status === "running" ? "running" : status === "failed" ? "failed" : "";
      const content = message.content?.trim()
        ? escapeHtml(message.content).replaceAll("\n", "<br />")
        : status === "running"
          ? "Agent is running in this project..."
          : "No output.";
      return `
        <article class="message-row ${role}">
          <div class="message-meta">
            <span>${escapeHtml(relativeTime(message.created_at))}</span>
          </div>
          ${renderMessageMeta(message)}
          <div class="message-bubble ${role} ${running}">
            <p>${content}</p>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderProviderStatus(provider, session) {
  if (!provider) {
    return "";
  }
  const providerThread = providerThreadForSession(session, provider.id);
  const activeConflict = Boolean(providerThread?.active_run_id);
  if (provider.status === "ready" && activeConflict) {
    return `
      <div class="provider-status ready">
        <span class="provider-status-copy">Another ${escapeHtml(provider.label)} run is active. A new launch will start independently.</span>
      </div>
    `;
  }
  if (provider.status === "ready") {
    return "";
  }
  return `
    <div class="provider-status warning">
      <span class="provider-status-copy">${escapeHtml(provider.status)}</span>
      <code>${escapeHtml((provider.connect_command ?? []).join(" "))}</code>
    </div>
  `;
}

function renderChats(state, session) {
  if (!session) {
    return `
      <section class="hero panel">
        <p class="panel-label">Chats</p>
        <h2>No active chat</h2>
        <p class="muted">Create a thread from the sidebar to start segmenting research work.</p>
      </section>
    `;
  }

  const launcher = deriveLauncherState(state);
  const provider = state.agent_providers.find((item) => item.id === launcher.providerId);
  const runModeOnce = launcher.runMode === "once" ? "checked" : "";
  const runModeAuto = launcher.runMode === "autoresearch" ? "checked" : "";
  const automationOpen = launcher.runMode === "autoresearch" ? "active" : "";
  const placeholder =
    launcher.runMode === "autoresearch"
      ? "Set the research goal for this long-running agent."
      : "Ask a question, continue the thread, or launch another agent in this project.";
  const submitLabel = launcher.runMode === "autoresearch" ? "Start loop" : "Run";

  return `
    <section class="chat-workspace">
      <section class="panel chat-stage">
        <div class="message-list">${renderChatMessages(session)}</div>
        <form id="agent-launch-form" class="composer composer-shell">
          <p id="composer-error" class="form-error" hidden></p>
          <div class="composer-config-row">
            <div class="mode-toggle" role="radiogroup" aria-label="Run mode">
              <label class="mode-toggle-option">
                <input type="radio" name="run_mode" value="once" ${runModeOnce} />
                <span>Once</span>
              </label>
              <label class="mode-toggle-option">
                <input type="radio" name="run_mode" value="autoresearch" ${runModeAuto} />
                <span>Autoresearch</span>
              </label>
            </div>
            <div class="launcher-grid compact composer-launcher-grid">
              <label class="select-control select-control-compact">
                <select id="provider-select" name="provider_id" aria-label="Provider">${renderProviderOptions(state.agent_providers, launcher.providerId)}</select>
              </label>
              <label class="select-control select-control-compact">
                <select id="model-select" name="model" aria-label="Model">${renderModelOptions(provider, launcher.model)}</select>
              </label>
              <label class="select-control select-control-compact">
                <select id="effort-select" name="effort" aria-label="Reasoning">${renderEffortOptions(provider, launcher.effort)}</select>
              </label>
            </div>
          </div>
          <textarea id="composer-input" name="prompt" rows="4" placeholder="${escapeHtml(placeholder)}"></textarea>
          <div class="composer-toolbar">
            <div id="automation-controls" class="composer-automation ${automationOpen}">
              <label class="inline-field">
                <span>Loops</span>
                <input id="loop-count-input" type="number" min="2" max="500" value="${launcher.maxIterations}" />
              </label>
              <label class="inline-field">
                <span>Hours</span>
                <input id="loop-hours-input" type="number" min="1" max="24" value="${launcher.maxHours}" />
              </label>
              <p class="composer-automation-note">Stops only on the loop cap or the time budget.</p>
            </div>
            <button class="action-button run-button" type="submit" ${provider?.status === "ready" ? "" : "disabled"}>${submitLabel}</button>
          </div>
          <div id="provider-status-panel" class="composer-status-row">${renderProviderStatus(provider, session)}</div>
        </form>
      </section>
      <aside class="panel agent-stream-panel">
        <div class="agent-stream-head">
          <div>
            <p class="panel-label">Agents</p>
            <h2>Working stream</h2>
          </div>
          <span class="thread-count">${formatCount(state.summary.active_agents)} active</span>
        </div>
        <div class="agent-stream-list">
          ${renderAgentStream(state.project.id, state.agent_stream ?? [], session)}
        </div>
      </aside>
    </section>
  `;
}

function renderMainPanel(state, route, activeSession, projects) {
  if (!projects.length) {
    renderNoProjects();
    return;
  }

  if (!state) {
    renderLanding(projects);
    return;
  }

  if (route.routeKey === "dashboard") {
    els.mainPanel.innerHTML = renderDashboard(state);
    return;
  }
  if (route.routeKey === "graph") {
    els.mainPanel.innerHTML = renderGraph(state);
    return;
  }
  if (route.routeKey === "runs") {
    els.mainPanel.innerHTML = `
      <section class="hero panel">
        <p class="panel-label">Runs</p>
        <h2>Inspectable research activity</h2>
        <p class="muted">Agent launches from chat are now persisted here as chat_agent runs.</p>
      </section>
      <section class="panel">${renderRunsTable(state.recent_runs)}</section>
    `;
    return;
  }
  if (route.routeKey === "backends") {
    els.mainPanel.innerHTML = renderBackends(state);
    return;
  }
  if (route.routeKey === "terminal") {
    els.mainPanel.innerHTML = renderTerminal(state);
    return;
  }

  els.mainPanel.innerHTML = renderChats(state, activeSession);
}

function renderInspector(state, session, route) {
  if (!state) {
    els.inspectorPanel.innerHTML = `
      <div class="sidebar-footer-block">
        <p class="panel-label">Status</p>
        <p class="muted">Open a folder to see provider bindings and workspace info.</p>
      </div>
    `;
    return;
  }

  if (route.routeKey === "chats") {
    els.inspectorPanel.innerHTML = "";
    return;
  }

  const providerRows = state.agent_providers
    .map((provider) => {
      const providerThread = providerThreadForSession(session, provider.id);
      const mode = providerThread?.native_session_id
        ? `bound ${formatSessionHandle(providerThread.native_session_id)}`
        : provider.native_continuation
          ? "new on first run"
          : "replay only";
      return `
        <div class="key-value-row">
          <span>${escapeHtml(provider.label)}</span>
          <strong>${escapeHtml(`${provider.status} • ${mode}`)}</strong>
        </div>
      `;
    })
    .join("");

  els.inspectorPanel.innerHTML = `
    <div class="sidebar-footer-block">
      <p class="panel-label">Project root</p>
      <p class="muted">${escapeHtml(state.project.root)}</p>
    </div>
    <div class="sidebar-footer-block">
      <p class="panel-label">Active chat</p>
      <p>${escapeHtml(session?.title ?? "None")}</p>
    </div>
    <div class="sidebar-footer-block">
      <p class="panel-label">Provider bindings</p>
      ${providerRows}
    </div>
  `;
}

function renderDock(state, projects) {
  els.dockPanel.innerHTML = "";
}

function scrollChatToLatest() {
  const messageList = document.querySelector(".message-list");
  if (!messageList) {
    return;
  }
  window.requestAnimationFrame(() => {
    messageList.scrollTop = messageList.scrollHeight;
    window.requestAnimationFrame(() => {
      messageList.scrollTop = messageList.scrollHeight;
    });
  });
}

function applyProviderControls(state, session) {
  const providerSelect = document.querySelector("#provider-select");
  const modelSelect = document.querySelector("#model-select");
  const effortSelect = document.querySelector("#effort-select");
  const providerStatusPanel = document.querySelector("#provider-status-panel");
  const submitButton = document.querySelector("#agent-launch-form button[type='submit']");
  const initial = deriveLauncherState(state);
  const loopCountInput = document.querySelector("#loop-count-input");
  const loopHoursInput = document.querySelector("#loop-hours-input");

  if (!providerSelect || !modelSelect || !effortSelect || !submitButton) {
    return;
  }

  if (initial.providerId) {
    providerSelect.value = initial.providerId;
  }

  const persistState = () => {
    const runMode =
      document.querySelector("input[name='run_mode']:checked")?.value === "autoresearch"
        ? "autoresearch"
        : "once";
    saveLauncherState(state.project.id, {
      providerId: providerSelect.value,
      model: modelSelect.value,
      effort: effortSelect.value,
      runMode,
      maxIterations: clampInteger(loopCountInput?.value, initial.maxIterations, 2, 500),
      maxHours: clampInteger(loopHoursInput?.value, initial.maxHours, 1, 24),
    });
  };

  const sync = ({ preserveSelections = true } = {}) => {
    const provider = state.agent_providers.find((item) => item.id === providerSelect.value);
    if (!provider) {
      return;
    }

    const preferredModel = preserveSelections ? modelSelect.value || initial.model : "";
    const nextModel = provider.models.some((model) => model.id === preferredModel)
      ? preferredModel
      : provider.default_model ?? provider.models[0]?.id ?? "";
    modelSelect.innerHTML = renderModelOptions(provider, nextModel);
    modelSelect.value = nextModel;

    const preferredEffort = preserveSelections ? effortSelect.value || initial.effort : "";
    const nextEffort = (provider.efforts ?? []).includes(preferredEffort)
      ? preferredEffort
      : provider.default_effort ?? provider.efforts?.[0] ?? "medium";
    effortSelect.innerHTML = renderEffortOptions(provider, nextEffort);
    effortSelect.value = nextEffort;

    if (providerStatusPanel) {
      providerStatusPanel.innerHTML = renderProviderStatus(provider, session);
    }
    submitButton.disabled = provider.status !== "ready";
    persistState();
  };

  providerSelect.addEventListener("change", () => sync({ preserveSelections: false }));
  modelSelect.addEventListener("change", persistState);
  effortSelect.addEventListener("change", persistState);
  sync();
}

function attachAgentStreamActions(state) {
  document.querySelectorAll("[data-action='stop-run']").forEach((button) => {
    button.addEventListener("click", async () => {
      const runId = button.getAttribute("data-run-id");
      if (!runId) {
        return;
      }
      button.disabled = true;
      await postJson(`/api/projects/${state.project.id}/agents/runs/${runId}/stop`, {});
      await bootstrap();
    });
  });
}

async function attachComposer(state, session) {
  const form = document.querySelector("#agent-launch-form");
  if (!form || !state || !session) {
    return;
  }

  applyProviderControls(state, session);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const providerSelect = document.querySelector("#provider-select");
    const modelSelect = document.querySelector("#model-select");
    const effortSelect = document.querySelector("#effort-select");
    const runModeInput = document.querySelector("input[name='run_mode']:checked");
    const loopCountInput = document.querySelector("#loop-count-input");
    const loopHoursInput = document.querySelector("#loop-hours-input");
    const input = document.querySelector("#composer-input");
    const errorSlot = document.querySelector("#composer-error");
    const submitButton = form.querySelector("button[type='submit']");
    const prompt = input.value.trim();
    const runMode = runModeInput?.value === "autoresearch" ? "autoresearch" : "once";
    const maxIterations = clampInteger(loopCountInput?.value, 12, 2, 500);
    const maxHours = clampInteger(loopHoursInput?.value, 4, 1, 24);
    if (!prompt) {
      return;
    }

    if (errorSlot) {
      errorSlot.hidden = true;
      errorSlot.textContent = "";
    }
    submitButton.disabled = true;
    try {
      await postJson(`/api/projects/${state.project.id}/agents/runs`, {
        session_id: session.id,
        provider_id: providerSelect.value,
        model: modelSelect.value,
        effort: effortSelect.value,
        prompt,
        run_mode: runMode,
        max_iterations: runMode === "autoresearch" ? maxIterations : 1,
        max_minutes: runMode === "autoresearch" ? maxHours * 60 : 30,
      });
      input.value = "";
      await bootstrap();
      const nextInput = document.querySelector("#composer-input");
      if (nextInput) {
        nextInput.focus();
      }
    } catch (error) {
      if (errorSlot) {
        errorSlot.hidden = false;
        errorSlot.textContent = error.message;
      }
    } finally {
      const provider = state.agent_providers.find((item) => item.id === providerSelect.value);
      submitButton.disabled = provider?.status !== "ready";
    }
  });

  const composerInput = document.querySelector("#composer-input");
  const submitButton = document.querySelector("#agent-launch-form button[type='submit']");
  const automationControls = document.querySelector("#automation-controls");
  const loopCountInput = document.querySelector("#loop-count-input");
  const loopHoursInput = document.querySelector("#loop-hours-input");
  const runModeInputs = [...document.querySelectorAll("input[name='run_mode']")];
  const syncMode = () => {
    const runMode =
      document.querySelector("input[name='run_mode']:checked")?.value === "autoresearch"
        ? "autoresearch"
        : "once";
    if (automationControls) {
      automationControls.classList.toggle("active", runMode === "autoresearch");
    }
    if (composerInput) {
      composerInput.placeholder =
        runMode === "autoresearch"
          ? "Set the research goal for this long-running agent."
          : "Ask a question, continue the thread, or launch another agent in this project.";
    }
    if (submitButton) {
      submitButton.textContent = runMode === "autoresearch" ? "Start loop" : "Run";
    }
    saveLauncherState(state.project.id, {
      ...deriveLauncherState(state),
      providerId: document.querySelector("#provider-select")?.value ?? "",
      model: document.querySelector("#model-select")?.value ?? "",
      effort: document.querySelector("#effort-select")?.value ?? "medium",
      runMode,
      maxIterations: clampInteger(loopCountInput?.value, 12, 2, 500),
      maxHours: clampInteger(loopHoursInput?.value, 4, 1, 24),
    });
  };
  runModeInputs.forEach((inputNode) => {
    inputNode.addEventListener("change", syncMode);
  });
  loopCountInput?.addEventListener("change", syncMode);
  loopHoursInput?.addEventListener("change", syncMode);
  syncMode();
}

function configurePolling(state, route) {
  if (pollHandle) {
    window.clearTimeout(pollHandle);
    pollHandle = null;
  }
  if (!state || !state.active_agents.length) {
    return;
  }
  pollHandle = window.setTimeout(() => {
    bootstrap().catch(renderError);
  }, 2500);
}

async function bootstrap() {
  const route = routeFromPath();
  syncRouteChrome(route.routeKey);
  const projectsPayload = await fetchJson("/api/projects");
  const projects = projectsPayload.projects ?? [];

  renderProjectRail(projects, route.projectId);

  if (!projects.length) {
    renderTopbar(projects, null, route, null);
    renderMainPanel(null, route, null, projects);
    renderInspector(null, null);
    renderDock(null, projects);
    configurePolling(null, route);
    return;
  }

  if (!route.projectId) {
    renderTopbar(projects, null, route, null);
    renderSidebar(null, route, null);
    renderMainPanel(null, route, null, projects);
    renderInspector(null, null);
    renderDock(null, projects);
    configurePolling(null, route);
    return;
  }

  const state = await fetchJson(`/api/projects/${route.projectId}/state`);
  let activeSession = null;
  let effectiveRoute = { ...route };
  if (route.routeKey === "chats") {
    const fallbackSessionId = route.sessionId ?? state.sessions[0]?.id ?? null;
    if (fallbackSessionId) {
      if (route.sessionId !== fallbackSessionId) {
        setPath(`/projects/${route.projectId}/chats/${fallbackSessionId}`, true);
        effectiveRoute = { ...route, sessionId: fallbackSessionId };
        syncRouteChrome(effectiveRoute.routeKey);
      }
      const payload = await fetchJson(`/api/projects/${route.projectId}/sessions/${fallbackSessionId}`);
      activeSession = payload.session;
    }
  }

  renderTopbar(projects, state, effectiveRoute, activeSession);
  renderSidebar(state, effectiveRoute, activeSession);
  renderMainPanel(state, effectiveRoute, activeSession, projects);
  renderInspector(state, activeSession, effectiveRoute);
  renderDock(state, projects);
  attachAgentStreamActions(state);
  await attachComposer(state, activeSession);
  if (effectiveRoute.routeKey === "chats" && activeSession) {
    scrollChatToLatest();
  }
  configurePolling(state, effectiveRoute);
}

window.addEventListener("popstate", () => {
  bootstrap().catch(renderError);
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && dialogState) {
    event.preventDefault();
    closeDialog(null);
  }
});

function renderError(error) {
  syncRouteChrome("error");
  els.mainPanel.innerHTML = `
    <section class="hero panel">
      <p class="panel-label">Gateway error</p>
      <h2>Unable to load the workspace shell</h2>
      <p class="muted">${escapeHtml(error.message)}</p>
    </section>
  `;
}

initializeThemeToggle();
renderDialog();
bootstrap().catch(renderError);
