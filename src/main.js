import {
  METHODENSAMMLUNG_DATA,
  sheets,
  getFinderIntents,
  getFinderContextualOptions,
  getFinderFilterOptions,
  getFinderResults,
  getLibraryFeed,
  getCollectionDetail,
  getMethodDetail,
  getComposerPool,
  getSessionHydration,
  getActiveSessionViewModel,
  createDraftBlock,
  vectorById,
  formatMethodDuration,
} from "./data-model.js?v=20260324c";

const app = document.querySelector("#app");
const DRAFTS_KEY = "methodensammlung:drafts:v1";
const SESSION_KEY = "methodensammlung:session:v1";

const uiState = {
  finderQuery: "",
  finderIntentId: null,
  finderGoal: "",
  finderPhase: "",
  finderGroup: "",
  finderTime: "",
  finderMaterial: "",
  finderOpenChooser: "goal",
  finderShowAllResults: false,
  libraryQuery: "",
  libraryVectorId: null,
  composerQuery: "",
  composerPhase: "",
  composerEnergy: "",
  dragPayload: null,
  libraryMode: "all",
  lastRouteName: null,
  sessionDetailTab: "ablauf",
  sessionFlowExpanded: false,
  sessionNotesExpanded: false,
  sessionManualMinutesInput: "5",
};

const ICONS = {
  finder: "explore",
  library: "library_books",
  composer: "architecture",
  session: "play_circle",
  collections: "grid_view",
  vectors: "network_node",
  draft: "draft",
  live: "timer",
  timer: "timer",
  notifications: "notifications",
  duplicate: "content_copy",
  launch: "bolt",
  add: "add_circle",
  forward: "arrow_forward",
  detail: "chevron_right",
  search: "north_east",
  stats: "insert_chart",
};

const ROUTE_VISUALS = {
  finder: {
    shellClass: "route-shell-finder",
    contentClass: "route-content-finder",
    topbarClass: "topbar-finder",
    utilities: [
      { action: "jump-composer", icon: ICONS.draft, label: "Zum Entwurf" },
      { action: "jump-session", icon: ICONS.live, label: "Zur Live-Session" },
    ],
  },
  library: {
    shellClass: "route-shell-library",
    contentClass: "route-content-library",
    topbarClass: "topbar-library",
    utilities: [
      { action: "jump-composer", icon: ICONS.draft, label: "Zum Entwurf" },
      { action: "jump-session", icon: ICONS.live, label: "Zur Live-Session" },
    ],
  },
  collection: {
    shellClass: "route-shell-library",
    contentClass: "route-content-library",
    topbarClass: "topbar-library",
    utilities: [
      { action: "jump-composer", icon: ICONS.draft, label: "Zum Entwurf" },
      { action: "jump-session", icon: ICONS.live, label: "Zur Live-Session" },
    ],
  },
  method: {
    shellClass: "route-shell-method",
    contentClass: "route-content-method",
    topbarClass: "topbar-method",
    utilities: [
      { action: "jump-composer", icon: ICONS.draft, label: "Zum Entwurf" },
      { action: "jump-session", icon: ICONS.live, label: "Zur Live-Session" },
    ],
  },
  composer: {
    shellClass: "route-shell-composer",
    contentClass: "route-content-composer",
    topbarClass: "topbar-composer",
    utilities: [
      { action: "jump-composer", icon: ICONS.draft, label: "Zum Entwurf" },
      { action: "jump-session", icon: ICONS.live, label: "Zur Live-Session" },
    ],
  },
  session: {
    shellClass: "route-shell-session",
    contentClass: "route-content-session",
    topbarClass: "topbar-session",
    utilities: [
      { action: "jump-composer", icon: ICONS.draft, label: "Zum Entwurf" },
      { action: "jump-session", icon: ICONS.live, label: "Zur Live-Session" },
    ],
  },
};

function ensureHash() {
  if (!window.location.hash) {
    window.location.hash = "#/finder";
  }
}

function parseHash() {
  const raw = window.location.hash.slice(1) || "/finder";
  const [pathPart, queryPart = ""] = raw.split("?");
  const query = new URLSearchParams(queryPart);
  const parts = pathPart.split("/").filter(Boolean);
  if (parts[0] === "library" && parts[1] === "collections" && parts[2]) {
    return { name: "collection", params: { collectionId: parts[2] }, query };
  }
  if (parts[0] === "library" && parts[1] === "method" && parts[2]) {
    return { name: "method", params: { methodId: parts[2] }, query };
  }
  if (parts[0] === "composer" && parts[1]) {
    return { name: "composer", params: { draftId: parts[1] }, query };
  }
  if (parts[0] === "composer") {
    return { name: "composer", params: { draftId: getDefaultDraft().id }, query };
  }
  if (parts[0] === "session" && parts[1] && parts[2] === "active") {
    return { name: "session", params: { sessionId: parts[1] }, query };
  }
  if (parts[0] === "library") {
    return { name: "library", params: {}, query };
  }
  return { name: parts[0] || "finder", params: {}, query };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderIcon(name, className = "") {
  return `<span class="material-symbols-outlined ${className}" aria-hidden="true">${escapeHtml(name)}</span>`;
}

function storageRead(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function storageWrite(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function loadDrafts() {
  const drafts = storageRead(DRAFTS_KEY, []);
  return Array.isArray(drafts) ? drafts : [];
}

function saveDrafts(drafts) {
  storageWrite(DRAFTS_KEY, drafts);
}

function getDefaultDraft() {
  const drafts = loadDrafts();
  if (drafts.length) {
    return drafts.sort((left, right) => right.updatedAt - left.updatedAt)[0];
  }
  const seedBlocks = sheets.finderIntents[0]?.recommended_method_ids_or_variant_ids?.slice(0, 2) ?? [];
  const firstDraft = {
    id: "draft-default",
    name: "Polarstern Session",
    blocks: seedBlocks
      .map((sourceId) => {
        const blockRef = sheets.composerBlocksReference.find((item) => item.source_id === sourceId);
        return blockRef ? createDraftBlock(blockRef.block_ref_id) : null;
      })
      .filter(Boolean),
    updatedAt: Date.now(),
  };
  saveDrafts([firstDraft]);
  return firstDraft;
}

function getDraftById(id) {
  return loadDrafts().find((draft) => draft.id === id) ?? getDefaultDraft();
}

function upsertDraft(updatedDraft) {
  const drafts = loadDrafts();
  const next = [...drafts.filter((draft) => draft.id !== updatedDraft.id), { ...updatedDraft, updatedAt: Date.now() }];
  saveDrafts(next);
  render();
}

function duplicateDraft(sourceDraft) {
  const clone = {
    ...sourceDraft,
    id: `draft-${Date.now()}`,
    name: `${sourceDraft.name} Kopie`,
    updatedAt: Date.now(),
    blocks: sourceDraft.blocks.map((block) => ({ ...block, id: `${block.id}-copy-${Math.random().toString(36).slice(2, 7)}` })),
  };
  const drafts = loadDrafts();
  drafts.push(clone);
  saveDrafts(drafts);
  window.location.hash = `#/composer/${clone.id}`;
}

function appendBlockToDraft(draftId, blockRefId, insertIndex = null) {
  const draft = getDraftById(draftId);
  const block = createDraftBlock(blockRefId);
  if (!block) {
    return;
  }
  const blocks = [...draft.blocks];
  if (typeof insertIndex === "number") {
    blocks.splice(insertIndex, 0, block);
  } else {
    blocks.push(block);
  }
  upsertDraft({ ...draft, blocks });
}

function duplicateDraftBlock(draftId, blockId) {
  const draft = getDraftById(draftId);
  const index = draft.blocks.findIndex((block) => block.id === blockId);
  if (index === -1) {
    return;
  }
  const sourceBlock = draft.blocks[index];
  const copy = {
    ...sourceBlock,
    id: `session-block-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  };
  const blocks = [...draft.blocks];
  blocks.splice(index + 1, 0, copy);
  upsertDraft({ ...draft, blocks });
}

function moveDraftBlock(draftId, blockId, direction) {
  const draft = getDraftById(draftId);
  const index = draft.blocks.findIndex((block) => block.id === blockId);
  if (index === -1) {
    return;
  }
  const target = direction === "up" ? index - 1 : index + 1;
  if (target < 0 || target >= draft.blocks.length) {
    return;
  }
  const blocks = [...draft.blocks];
  const [item] = blocks.splice(index, 1);
  blocks.splice(target, 0, item);
  upsertDraft({ ...draft, blocks });
}

function moveDraftBlockToIndex(draftId, blockId, insertIndex) {
  const draft = getDraftById(draftId);
  const currentIndex = draft.blocks.findIndex((block) => block.id === blockId);
  if (currentIndex === -1) {
    return;
  }
  const blocks = [...draft.blocks];
  const [item] = blocks.splice(currentIndex, 1);
  const normalizedInsertIndex = currentIndex < insertIndex ? insertIndex - 1 : insertIndex;
  blocks.splice(Math.max(0, Math.min(blocks.length, normalizedInsertIndex)), 0, item);
  upsertDraft({ ...draft, blocks });
}

function removeDraftBlock(draftId, blockId) {
  const draft = getDraftById(draftId);
  const blocks = draft.blocks.filter((block) => block.id !== blockId);
  upsertDraft({ ...draft, blocks });
}

function updateDraftName(draftId, name) {
  const draft = getDraftById(draftId);
  upsertDraft({ ...draft, name });
}

function updateBlockDuration(draftId, blockId, value) {
  const draft = getDraftById(draftId);
  const blocks = draft.blocks.map((block) =>
    block.id === blockId ? { ...block, manualDuration: value ? Number(value) : null } : block,
  );
  upsertDraft({ ...draft, blocks });
}

function updateBlockNote(draftId, blockId, value) {
  const draft = getDraftById(draftId);
  const blocks = draft.blocks.map((block) =>
    block.id === blockId ? { ...block, customNote: value || null } : block,
  );
  upsertDraft({ ...draft, blocks });
}

function updateSessionState(sessionId, patch) {
  const current = storageRead(SESSION_KEY, {});
  storageWrite(SESSION_KEY, {
    ...current,
    [sessionId]: {
      ...(current[sessionId] ?? {}),
      ...patch,
    },
  });
}

function getSessionState(sessionId) {
  const current = storageRead(SESSION_KEY, {});
  return current[sessionId] ?? { currentIndex: 0, secondsRemaining: null, activeBlockId: null, notes: [] };
}

function resetActiveSessionUi() {
  uiState.sessionDetailTab = "ablauf";
  uiState.sessionFlowExpanded = false;
  uiState.sessionNotesExpanded = false;
}

function setSessionIndex(sessionId, currentIndex) {
  resetActiveSessionUi();
  updateSessionState(sessionId, { currentIndex, secondsRemaining: null, activeBlockId: null });
  render();
}

function addSessionNote(sessionId, note) {
  const current = getSessionState(sessionId);
  updateSessionState(sessionId, {
    notes: [{ id: `note-${Date.now()}`, body: note, createdAt: Date.now() }, ...(current.notes ?? [])],
  });
  render();
}

function setSessionTimer(sessionId, activeBlockId, secondsRemaining) {
  updateSessionState(sessionId, { secondsRemaining, activeBlockId });
  render();
}

function startSessionFromMethod(sourceType, sourceId) {
  const draft = getDefaultDraft();
  const blockRef = sheets.composerBlocksReference.find((item) => item.source_type === sourceType && item.source_id === sourceId);
  if (!blockRef) {
    window.location.hash = `#/composer/${draft.id}`;
    return;
  }
  appendBlockToDraft(draft.id, blockRef.block_ref_id);
  window.location.hash = `#/session/${draft.id}/active`;
}

function renderTopbarTabs(items = []) {
  if (!items.length) {
    return "";
  }
  return `
    <div class="topbar-tabs" role="tablist" aria-label="Ansicht wechseln">
      ${items
        .map(
          (item) => `
            <button
              class="topbar-tab ${item.isActive ? "is-active" : ""}"
              data-action="${item.action}"
              data-mode="${item.mode ?? ""}"
              role="tab"
              aria-selected="${item.isActive ? "true" : "false"}"
            >
              ${escapeHtml(item.label)}
            </button>
          `,
        )
        .join("")}
    </div>
  `;
}

function buildLayout(route, content, topbarEyebrow, topbarTitle, options = {}) {
  const nav = [
    { href: "#/finder", key: "finder", label: "Method Finder", detail: "Situation-first", icon: ICONS.finder },
    { href: "#/library", key: "library", label: "Library", detail: "Editorial Browse", icon: ICONS.library },
    { href: `#/composer/${getDefaultDraft().id}`, key: "composer", label: "Composer", detail: "Session Blocks", icon: ICONS.composer },
    { href: `#/session/${getDefaultDraft().id}/active`, key: "session", label: "Active Session", detail: "Facilitator Mode", icon: ICONS.session },
  ];

  const active = route.name === "collection" || route.name === "method" ? "library" : route.name;
  const visualKey = route.name in ROUTE_VISUALS ? route.name : active;
  const visual = ROUTE_VISUALS[visualKey] ?? ROUTE_VISUALS.finder;
  const utilities = options.utilities ?? visual.utilities ?? [];

  return `
    <div class="app-shell ${visual.shellClass ?? ""}" data-route="${escapeHtml(active)}" data-visual="${escapeHtml(visualKey)}">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-mark">Polarstern</div>
          <div class="brand-subline">The Human Technologist</div>
        </div>
        <nav class="nav-list">
          ${nav
            .map(
              (item) => `
                <a class="nav-link ${active === item.key ? "is-active" : ""}" href="${item.href}">
                  ${renderIcon(item.icon, "nav-icon")}
                  <span class="nav-copy">
                    <span>${item.label}</span>
                    <small>${item.detail}</small>
                  </span>
                </a>
              `,
            )
            .join("")}
        </nav>
        <div class="sidebar-cta">
          <button class="button-primary" data-action="new-draft">${renderIcon(ICONS.add, "button-symbol")}Neue Session</button>
        </div>
        <div class="sidebar-footer">
          <button class="nav-link" data-action="jump-library-mode" data-mode="collections">
            ${renderIcon(ICONS.collections, "nav-icon")}
            <span class="nav-copy"><span>Kollektionen</span><small>Kuratiert aus SSOT</small></span>
          </button>
          <button class="nav-link" data-action="jump-library-mode" data-mode="all">
            ${renderIcon(ICONS.vectors, "nav-icon")}
            <span class="nav-copy"><span>Vektoren</span><small>Kontrollierte Browse-Ebene</small></span>
          </button>
        </div>
      </aside>
      <div class="main-shell">
        <header class="topbar ${visual.topbarClass ?? ""}">
          <div class="topbar-leading">
            <div class="topbar-title">
              <span class="eyebrow">${escapeHtml(topbarEyebrow)}</span>
              <h1>${escapeHtml(topbarTitle)}</h1>
            </div>
            ${renderTopbarTabs(options.topbarTabs)}
          </div>
          <div class="topbar-tools">
            ${utilities
              .map(
                (item) => `
                  <button class="tool-pill" data-action="${item.action}" aria-label="${escapeHtml(item.label)}" title="${escapeHtml(item.label)}">
                    ${renderIcon(item.icon)}
                  </button>
                `,
              )
              .join("")}
            <button class="tool-pill" aria-label="Timer" title="Timer">
              ${renderIcon(ICONS.timer)}
            </button>
            <button class="tool-pill" aria-label="Benachrichtigungen" title="Benachrichtigungen">
              ${renderIcon(ICONS.notifications)}
            </button>
            <div class="avatar" aria-hidden="true"></div>
          </div>
        </header>
        <main class="content ${visual.contentClass ?? ""}">${content}</main>
      </div>
    </div>
  `;
}

function renderSessionFlowSection(section, expanded) {
  if (!section?.hasContent) {
    return "";
  }
  const visibleSteps = expanded ? section.steps : section.steps.slice(0, 3);
  return `
    <section class="session-detail-card">
      <h4>${escapeHtml(section.label)}</h4>
      <div class="session-flow-list">
        ${visibleSteps
          .map(
            (step, index) => `
              <div class="session-flow-item">
                <span class="session-flow-index">${String(index + 1).padStart(2, "0")}</span>
                <p>${escapeHtml(step)}</p>
              </div>
            `,
          )
          .join("")}
      </div>
      ${
        section.steps.length > 3
          ? `<button class="button-tertiary button-small" data-action="toggle-session-flow">${expanded ? "Weniger anzeigen" : "Mehr anzeigen"}</button>`
          : ""
      }
    </section>
  `;
}

function renderSessionFrameSection(section) {
  if (!section?.hasContent) {
    return "";
  }
  return `
    <section class="session-detail-card">
      <h4>${escapeHtml(section.label)}</h4>
      <div class="session-frame-list">
        ${section.items
          .map(
            (item) => `
              <div class="session-frame-item">
                <span>${escapeHtml(item.label)}</span>
                <strong>${escapeHtml(item.value)}</strong>
              </div>
            `,
          )
          .join("")}
      </div>
      ${
        section.vectors.length
          ? `
            <div class="chip-row">
              ${section.vectors.map((vector) => `<span class="chip chip-muted">${escapeHtml(vector)}</span>`).join("")}
            </div>
          `
          : ""
      }
    </section>
  `;
}

function renderSessionHintsSection(section) {
  if (!section?.hasContent) {
    return "";
  }
  return `
    <section class="session-detail-card">
      <h4>${escapeHtml(section.label)}</h4>
      <div class="session-hint-stack">
        ${section.notes
          .map(
            (note) => `
              <div class="session-hint-card">
                <strong>Facilitator Tip</strong>
                <p>${escapeHtml(note)}</p>
              </div>
            `,
          )
          .join("")}
        ${section.risks
          .map(
            (risk) => `
              <div class="session-hint-card is-risk">
                <strong>Risk Alert</strong>
                <p>${escapeHtml(risk)}</p>
              </div>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderSessionMobileDetails(detailModel, activeTab) {
  if (!detailModel) {
    return "";
  }
  const sections = detailModel.sections;
  const availableTabs = ["ablauf", "rahmen", "hinweise"].filter((key) => sections[key].hasContent);
  if (!availableTabs.length) {
    return "";
  }
  const activeSection = sections[activeTab] ?? sections[availableTabs[0]];
  return `
    <div class="mobile-only session-mobile-details">
      <div class="session-segmented">
        ${availableTabs
          .map(
            (tabKey) => `
              <button class="segment-button ${activeTab === tabKey ? "is-active" : ""}" data-action="session-detail-tab" data-tab="${tabKey}">
                ${escapeHtml(sections[tabKey].label)}
              </button>
            `,
          )
          .join("")}
      </div>
      ${
        activeSection.key === "ablauf"
          ? renderSessionFlowSection(activeSection, uiState.sessionFlowExpanded)
          : activeSection.key === "rahmen"
            ? renderSessionFrameSection(activeSection)
            : renderSessionHintsSection(activeSection)
      }
    </div>
  `;
}

function renderSessionDesktopDetails(detailModel) {
  if (!detailModel) {
    return "";
  }
  return `
    <div class="desktop-only session-detail-stack">
      ${renderSessionFlowSection(detailModel.sections.ablauf, uiState.sessionFlowExpanded)}
      ${renderSessionFrameSection(detailModel.sections.rahmen)}
      ${renderSessionHintsSection(detailModel.sections.hinweise)}
    </div>
  `;
}

function renderSessionTimerPanel({ draftId, currentBlock, defaultSeconds, remainingSeconds }) {
  const manualMinutes = uiState.sessionManualMinutesInput || "5";
  return `
    <section class="session-control-card session-timer-card">
      <span class="session-utility-label">${defaultSeconds === null ? "Manueller Timer" : "Timer"}</span>
      <div class="timer-display">${escapeHtml(remainingSeconds === null ? "Manuell" : toClock(remainingSeconds))}</div>
      ${
        remainingSeconds === null
          ? `
            <div class="session-manual-setup">
              <label class="session-inline-label">
                <span>Minuten</span>
                <input class="inline-field session-minute-input" name="session-manual-minutes" type="number" min="1" step="1" value="${escapeHtml(manualMinutes)}" />
              </label>
              <div class="session-controls">
                <button class="button-secondary button-small" data-action="session-manual-adjust" data-delta="-1">-1</button>
                <button class="button-secondary button-small" data-action="session-manual-adjust" data-delta="1">+1</button>
                <button class="button-primary button-small" data-action="session-start-manual" data-session-id="${draftId}" data-block-id="${currentBlock.runtimeId}">
                  Timer starten
                </button>
              </div>
            </div>
          `
          : `
            <div class="session-controls">
              <button class="button-secondary button-small" data-action="session-adjust" data-session-id="${draftId}" data-block-id="${currentBlock.runtimeId}" data-seconds="-60">-1:00</button>
              <button class="button-primary button-small" data-action="session-adjust" data-session-id="${draftId}" data-block-id="${currentBlock.runtimeId}" data-seconds="60">+1:00</button>
              <button class="button-tertiary button-small" data-action="session-clear-timer" data-session-id="${draftId}">Neu setzen</button>
            </div>
          `
      }
      <p class="helper-copy">${escapeHtml(defaultSeconds === null ? "Keine gesicherte Dauer. Der Timer bleibt bewusst manuell." : "Mit gesicherter Blockdauer vorbefüllt.")}</p>
    </section>
  `;
}

function renderSessionOutlinePanel(summary, currentIndex, draftId) {
  return `
    <section class="session-control-card">
      <div class="section-head">
        <div>
          <h4>Session Outline</h4>
          <p>Sprungmarken für den laufenden Ablauf.</p>
        </div>
      </div>
      <div class="session-outline compact">
        ${summary.hydratedBlocks
          .map(
            (block, index) => `
              <div class="session-outline-item ${index === currentIndex ? "is-active" : ""}">
                <button data-action="session-jump" data-session-id="${draftId}" data-index="${index}">
                  <strong>${escapeHtml(block.title)}</strong>
                  <span>${escapeHtml(block.durationLabel ?? "offen")} · ${escapeHtml(block.phase ?? "ohne Phase")}</span>
                </button>
              </div>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderSessionNotesPanel(sessionId, notes) {
  const visibleNotes = uiState.sessionNotesExpanded ? notes : notes.slice(0, 3);
  return `
    <section class="active-session-notes">
      <div class="session-note-composer">
        <div class="section-head">
          <div>
            <h3>Lokales Log</h3>
            <p>Beobachtungen und Anpassungen bleiben lokal in dieser Session.</p>
          </div>
        </div>
        <textarea class="notes-input" name="session-note" placeholder="Beobachtung, Anpassung oder Stimmung der Gruppe notieren"></textarea>
        <div class="session-controls">
          <button class="button-primary" data-action="add-session-note" data-session-id="${sessionId}">Notiz speichern</button>
          <span class="helper-copy">${escapeHtml(notes.length ? `${notes.length} Einträge gespeichert.` : "Noch keine Einträge.")}</span>
        </div>
      </div>
      <div class="session-note-log">
        <div class="section-head">
          <div>
            <h4>Letzte Einträge</h4>
          </div>
        </div>
        <div class="note-log">
          ${
            visibleNotes.length
              ? visibleNotes
                  .map(
                    (note) => `
                      <div class="note-item">
                        <strong>${new Date(note.createdAt).toLocaleString("de-AT")}</strong>
                        <span>${escapeHtml(note.body)}</span>
                      </div>
                    `,
                  )
                  .join("")
              : `<div class="empty-state"><strong>Noch keine Notizen</strong><span>Die Logfläche bleibt absichtlich lokal und leichtgewichtig.</span></div>`
          }
        </div>
        ${
          notes.length > 3
            ? `<button class="button-tertiary button-small" data-action="toggle-session-notes">${uiState.sessionNotesExpanded ? "Weniger anzeigen" : "Weitere Einträge"}</button>`
            : ""
        }
      </div>
    </section>
  `;
}

function renderMethodCard(item, variant = "default") {
  const energyLabel = item.energyRole ? item.energyRole : item.energyLevel ? `Energie ${item.energyLevel}` : null;
  const primaryMeta = [
    item.phase ? `<span class="chip chip-primary">${escapeHtml(item.phase)}</span>` : "",
    item.durationLabel ? `<span class="chip chip-tertiary">${escapeHtml(item.durationLabel)}</span>` : "",
    energyLabel ? `<span class="chip chip-secondary">${escapeHtml(energyLabel)}</span>` : "",
  ]
    .filter(Boolean)
    .join("");

  const supportingMeta = [
    item.groupSetting ? `<span class="chip chip-muted">${escapeHtml(item.groupSetting)}</span>` : "",
    ...item.vectors.slice(0, variant === "library" ? 1 : 2).map((vector) => `<span class="chip chip-muted">${escapeHtml(vector.vector_name_de)}</span>`),
  ]
    .filter(Boolean)
    .join("");

  const detailHref = `#/library/method/${encodeURIComponent(item.method.method_id)}${item.variant ? `?variant=${encodeURIComponent(item.variant.variant_id)}` : ""}`;

  return `
    <article class="card method-card method-card--${variant}">
      <div class="method-card-visual" style="${item.decoration}">
        <small>${escapeHtml(item.phase ?? item.method.primary_purpose ?? "Methode")}</small>
        <strong>${escapeHtml(item.title)}</strong>
      </div>
      ${primaryMeta ? `<div class="card-tags card-tags--primary">${primaryMeta}</div>` : ""}
      <p class="card-copy">${escapeHtml(item.summary ?? "")}</p>
      ${supportingMeta ? `<div class="card-tags card-tags--supporting">${supportingMeta}</div>` : ""}
      <div class="card-links">
        <a class="text-link" href="${detailHref}">Details</a>
        <button class="button-tertiary button-small" data-action="start-from-source" data-source-type="${item.sourceType}" data-source-id="${item.sourceId}">
          In Session
        </button>
      </div>
    </article>
  `;
}

function getFinderFilterState() {
  return {
    goal: uiState.finderGoal,
    phase: uiState.finderPhase,
    group: uiState.finderGroup,
    time: uiState.finderTime,
    material: uiState.finderMaterial,
  };
}

const FINDER_TIME_PROMPT_LABELS = {
  short: "kurz",
  medium: "bis 20 Min.",
  long: "mehr Zeit",
  open: "offen",
};

function getFinderPromptTimeOptions(filterOptions) {
  return filterOptions.timeBuckets.map((option) => ({
    ...option,
    label: FINDER_TIME_PROMPT_LABELS[option.value] ?? option.label,
  }));
}

function markFinderDirty() {
  uiState.finderShowAllResults = false;
}

function clearFinderAfterBaseSelection() {
  uiState.finderTime = "";
  uiState.finderPhase = "";
  uiState.finderGroup = "";
  uiState.finderMaterial = "";
  uiState.finderQuery = "";
  uiState.finderShowAllResults = false;
}

function clearFinderAfterTimeSelection() {
  uiState.finderPhase = "";
  uiState.finderGroup = "";
  uiState.finderMaterial = "";
  uiState.finderQuery = "";
  uiState.finderShowAllResults = false;
}

function toggleFinderFilter(key, value) {
  if (key === "finderGoal") {
    const nextValue = uiState.finderGoal === value ? "" : value;
    const baseChanged = nextValue !== uiState.finderGoal || Boolean(uiState.finderIntentId);
    uiState.finderGoal = nextValue;
    uiState.finderIntentId = null;
    if (baseChanged) {
      clearFinderAfterBaseSelection();
    }
    uiState.finderOpenChooser = nextValue ? "time" : "goal";
    return;
  }

  if (key === "finderTime") {
    const nextValue = uiState.finderTime === value ? "" : value;
    const timeChanged = nextValue !== uiState.finderTime;
    uiState.finderTime = nextValue;
    if (timeChanged) {
      clearFinderAfterTimeSelection();
    }
    uiState.finderOpenChooser = nextValue ? "" : "time";
    return;
  }

  uiState[key] = uiState[key] === value ? "" : value;
  uiState.finderOpenChooser = key === "finderPhase" || key === "finderGroup" || key === "finderMaterial" ? "refine" : uiState.finderOpenChooser;
  markFinderDirty();
}

function setFinderChooser(chooser) {
  const hasBaseSelection = Boolean(uiState.finderGoal || uiState.finderIntentId);
  if (!hasBaseSelection && (chooser === "goal" || chooser === "more-goals")) {
    uiState.finderOpenChooser = chooser;
    return;
  }
  uiState.finderOpenChooser = uiState.finderOpenChooser === chooser ? "" : chooser;
}

function clearFinderState() {
  uiState.finderQuery = "";
  uiState.finderIntentId = null;
  uiState.finderGoal = "";
  uiState.finderPhase = "";
  uiState.finderGroup = "";
  uiState.finderTime = "";
  uiState.finderMaterial = "";
  uiState.finderOpenChooser = "goal";
  uiState.finderShowAllResults = false;
}

function renderFinderFilterGroup(title, filterKey, options, selectedValue, tone = "default") {
  return `
    <section class="finder-filter-group finder-filter-group--${tone}">
      <div class="finder-filter-head">
        <h3>${escapeHtml(title)}</h3>
      </div>
      <div class="finder-chip-grid finder-chip-grid--${tone}">
        ${options
          .map((option) => {
            const value = option.value ?? option.label;
            const label = option.label ?? option.value;
            return `
              <button
                class="finder-filter-chip ${selectedValue === value ? "is-active" : ""}"
                data-action="toggle-finder-filter"
                data-filter-key="${filterKey}"
                data-value="${escapeHtml(value)}"
              >
                <span>${escapeHtml(label)}</span>
              </button>
            `;
          })
          .join("")}
      </div>
    </section>
  `;
}

function getFinderPromptItems(filterOptions, timeOptions) {
  const lookup = (options, value) => options.find((item) => item.value === value)?.label ?? value;
  return [
    uiState.finderIntentId
      ? {
          key: "finderIntentId",
          value: uiState.finderIntentId,
          label: `Quick Start: ${
            getFinderIntents().find((intent) => intent.intent_id === uiState.finderIntentId)?.intent_label_de ?? "Quick Start"
          }`,
          action: "choose-intent",
          dataAttr: `data-intent-id="${uiState.finderIntentId}"`,
        }
      : null,
    uiState.finderGoal
      ? {
          key: "finderGoal",
          value: uiState.finderGoal,
          label: `Ziel: ${uiState.finderGoal}`,
          action: "toggle-finder-filter",
          dataAttr: `data-filter-key="finderGoal" data-value="${escapeHtml(uiState.finderGoal)}"`,
        }
      : null,
    uiState.finderTime
      ? {
          key: "finderTime",
          value: uiState.finderTime,
          label: `Zeit: ${lookup(timeOptions, uiState.finderTime)}`,
          action: "toggle-finder-filter",
          dataAttr: `data-filter-key="finderTime" data-value="${escapeHtml(uiState.finderTime)}"`,
        }
      : null,
    uiState.finderPhase
      ? {
          key: "finderPhase",
          value: uiState.finderPhase,
          label: `Phase: ${uiState.finderPhase}`,
          action: "toggle-finder-filter",
          dataAttr: `data-filter-key="finderPhase" data-value="${escapeHtml(uiState.finderPhase)}"`,
        }
      : null,
    uiState.finderGroup
      ? {
          key: "finderGroup",
          value: uiState.finderGroup,
          label: `Gruppe: ${uiState.finderGroup}`,
          action: "toggle-finder-filter",
          dataAttr: `data-filter-key="finderGroup" data-value="${escapeHtml(uiState.finderGroup)}"`,
        }
      : null,
    uiState.finderMaterial
      ? {
          key: "finderMaterial",
          value: uiState.finderMaterial,
          label: `Material: ${lookup(filterOptions.materialBuckets, uiState.finderMaterial)}`,
          action: "toggle-finder-filter",
          dataAttr: `data-filter-key="finderMaterial" data-value="${escapeHtml(uiState.finderMaterial)}"`,
        }
      : null,
    uiState.finderQuery.trim()
      ? {
          key: "finderQuery",
          value: uiState.finderQuery.trim(),
          label: `Hinweis: ${uiState.finderQuery.trim()}`,
          action: "clear-finder-query",
          dataAttr: "",
        }
      : null,
  ].filter(Boolean);
}

function renderFinderPromptBar(promptItems, actionSlot) {
  return `
    <div class="finder-prompt-bar" aria-label="Aktive Auswahl">
      <div class="finder-prompt-trail">
        ${promptItems.length
          ? promptItems
              .map(
                (item) => `
                  <button class="finder-prompt-token" data-action="${item.action}" ${item.dataAttr}>
                    ${escapeHtml(item.label)} <span aria-hidden="true">×</span>
                  </button>
                `,
              )
              .join("")
          : ""}
        ${
          actionSlot
            ? `<button class="finder-prompt-slot" data-action="set-finder-chooser" data-chooser="${actionSlot.chooser}">${escapeHtml(actionSlot.label)}</button>`
            : ""
        }
      </div>
      ${
        promptItems.length
          ? `<button class="button-tertiary button-small" data-action="finder-reset" aria-label="Zurücksetzen">${renderIcon("restart_alt", "button-symbol")}</button>`
          : ""
      }
    </div>
  `;
}

function renderFinderQuickStarts(quickStarts, isCompact = false) {
  return `
    <div class="finder-quickstart-row ${isCompact ? "finder-quickstart-row--compact" : ""}">
      ${quickStarts
        .map(
          (intent) => `
            <button
              class="quick-start-inline ${uiState.finderIntentId === intent.intent_id ? "is-active" : ""}"
              data-action="choose-intent"
              data-intent-id="${intent.intent_id}"
            >
              <strong>${escapeHtml(intent.intent_label_de)}</strong>
            </button>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderFinderChooser({
  chooser,
  primaryGoals,
  extraGoals,
  timeOptions,
  contextualOptions,
  quickStarts,
}) {
  if (chooser === "more-goals") {
    return `
      <div class="finder-chooser">
        <div class="finder-chooser-actions">
          <button class="button-tertiary button-small" data-action="set-finder-chooser" data-chooser="goal">Zurück</button>
        </div>
        ${renderFinderFilterGroup("Weitere Ziele", "finderGoal", extraGoals, uiState.finderGoal, "goal")}
      </div>
    `;
  }

  if (chooser === "time") {
    return `
      <div class="finder-chooser">
        ${renderFinderFilterGroup("Zeit", "finderTime", timeOptions, uiState.finderTime, "time")}
      </div>
    `;
  }

  if (chooser === "refine") {
    return `
      <div class="finder-chooser">
        <div class="finder-refine-stack">
          ${
            contextualOptions.phases.length
              ? renderFinderFilterGroup("Phase", "finderPhase", contextualOptions.phases, uiState.finderPhase)
              : ""
          }
          ${
            contextualOptions.groups.length
              ? renderFinderFilterGroup("Gruppe", "finderGroup", contextualOptions.groups, uiState.finderGroup)
              : ""
          }
          ${
            contextualOptions.materialBuckets.length
              ? renderFinderFilterGroup("Material", "finderMaterial", contextualOptions.materialBuckets, uiState.finderMaterial)
              : ""
          }
          <section class="finder-filter-group finder-filter-group--query">
            <div class="finder-filter-head">
              <h3>Freitext</h3>
            </div>
            <div class="finder-query-panel">
              <textarea
                class="finder-input finder-input--compact"
                name="finder-query"
                placeholder="Freitext"
              >${escapeHtml(uiState.finderQuery)}</textarea>
              <div class="finder-actions">
                <button class="button-primary button-small" data-action="finder-submit">${renderIcon(ICONS.forward, "button-symbol")}Anwenden</button>
              </div>
            </div>
          </section>
        </div>
      </div>
    `;
  }

  if (chooser === "intents") {
    return `
      <div class="finder-chooser finder-chooser--quiet">
        ${renderFinderQuickStarts(quickStarts, true)}
      </div>
    `;
  }

  return `
    <div class="finder-chooser">
      ${renderFinderFilterGroup("Hauptziele", "finderGoal", primaryGoals, uiState.finderGoal, "goal")}
      ${
        extraGoals.length
          ? `<div class="finder-chooser-actions"><button class="button-tertiary button-small" data-action="set-finder-chooser" data-chooser="more-goals">Mehr</button></div>`
          : ""
      }
    </div>
  `;
}

function renderFinder() {
  const intents = getFinderIntents();
  const filterOptions = getFinderFilterOptions();
  const timeOptions = getFinderPromptTimeOptions(filterOptions);
  const baseResults = getFinderResults({
    intentId: uiState.finderIntentId,
    goal: uiState.finderGoal,
    time: uiState.finderTime,
  });
  const contextualOptions = getFinderContextualOptions(baseResults.items, {
    selectedPhase: uiState.finderPhase,
    selectedGroup: uiState.finderGroup,
    selectedMaterial: uiState.finderMaterial,
  });
  const results = getFinderResults({
    query: uiState.finderQuery,
    intentId: uiState.finderIntentId,
    ...getFinderFilterState(),
  });
  const quickStarts = intents.slice(0, 3);
  const hasBaseSelection = Boolean(uiState.finderIntentId || uiState.finderGoal);
  const primaryGoals = filterOptions.goals.slice(0, 5);
  const extraGoals = filterOptions.goals.slice(5);
  const promptItems = getFinderPromptItems(filterOptions, timeOptions);
  const actionSlot = !hasBaseSelection
    ? { chooser: "goal", label: "Ziel" }
    : !uiState.finderTime
      ? { chooser: "time", label: "Zeit" }
      : { chooser: "refine", label: "Mehr" };
  const effectiveChooser = hasBaseSelection ? uiState.finderOpenChooser : uiState.finderOpenChooser || "goal";
  const visibleItems = uiState.finderShowAllResults ? results.items : results.items.slice(0, 4);
  return buildLayout(
    { name: "finder" },
    `
      <section class="finder-prompt-shell">
        <article class="glass-panel finder-prompt-panel">
          <div class="finder-prompt-head">
            <div>
              <h2 class="finder-prompt-title">Was braucht eure <span class="accent">Gruppe</span> gerade?</h2>
            </div>
          </div>

          ${renderFinderPromptBar(promptItems, actionSlot)}
          ${renderFinderChooser({
            chooser: effectiveChooser,
            primaryGoals,
            extraGoals,
            timeOptions,
            contextualOptions,
            quickStarts,
          })}

          ${
            hasBaseSelection
              ? `
                <div class="finder-quiet-utility">
                  <button class="button-tertiary button-small" data-action="set-finder-chooser" data-chooser="intents">Schnell</button>
                </div>
              `
              : `
                <section class="finder-low-priority-row" aria-label="Quick Starts">
                  ${renderFinderQuickStarts(quickStarts)}
                </section>
              `
          }
        </article>
      </section>

      <section class="section-copy finder-results-section">
        ${renderCards(visibleItems, "Keine passenden Methoden im aktuellen Zustand. Entferne einzelne Filter oder gehe einen Schritt zurück.", {
          gridClass: "finder-card-grid",
          variant: "finder",
        })}
        ${
          results.items.length > 4
            ? `
              <div class="finder-results-actions">
                <button class="button-tertiary button-small" data-action="finder-show-more">
                  ${uiState.finderShowAllResults ? "Weniger zeigen" : `Mehr zeigen (${results.items.length - 4})`}
                </button>
              </div>
            `
            : ""
        }
      </section>
    `,
    "Entry Moment",
    "Method Finder",
  );
}

function renderCards(items, emptyMessage, options = {}) {
  const { gridClass = "", variant = "default" } = options;
  if (!items.length) {
    return `<div class="empty-state card ${variant !== "default" ? `card-${variant}` : ""}"><strong>Leerer Zustand</strong><span>${escapeHtml(emptyMessage)}</span></div>`;
  }
  return `
    <div class="grid-cards ${gridClass}">
      ${items.map((item) => renderMethodCard(item, variant)).join("")}
    </div>
  `;
}

function renderLibrary() {
  const vectorId = uiState.libraryVectorId;
  const feed = getLibraryFeed({ query: uiState.libraryQuery, vectorId });
  const featuredCollection = sheets.collections[0];
  const featuredMethod = feed[0];
  const visibleCollections = uiState.libraryMode === "collections";
  return buildLayout(
    { name: "library" },
    `
      <section class="editorial-grid library-hero-grid">
        <article class="feature-panel glass-panel library-feature-panel">
          <span class="floating-word">${escapeHtml((featuredCollection?.name_de ?? "Fokus").split(" ")[0].toUpperCase())}</span>
          <div class="chip-row">
            <span class="chip chip-tertiary">Kuratiertes Signal</span>
            ${featuredMethod?.phase ? `<span class="chip chip-primary">${escapeHtml(featuredMethod.phase)}</span>` : ""}
            ${featuredMethod?.durationLabel ? `<span class="chip chip-muted">${escapeHtml(featuredMethod.durationLabel)}</span>` : ""}
          </div>
          <h2>${escapeHtml(featuredMethod?.title ?? "Methodensammlung")}</h2>
          <p class="helper-copy">${escapeHtml(featuredCollection?.short_description ?? featuredMethod?.summary ?? "")}</p>
          <div class="header-actions">
            ${featuredMethod ? `<a class="button-primary" href="#/library/method/${featuredMethod.method.method_id}">${renderIcon(ICONS.detail, "button-symbol")}Methodendetail</a>` : ""}
            ${featuredCollection ? `<a class="button-secondary" href="#/library/collections/${featuredCollection.collection_id}">Kollektion öffnen</a>` : ""}
          </div>
        </article>
        <aside class="library-grid library-side-stack">
          <article class="editorial-panel library-utility-card">
            <span class="card-badge">Bibliotheksstatus</span>
            <div class="stat-list">
              <div class="split-row">
                <span>Methoden</span>
                <strong>${escapeHtml(String(sheets.methods.length))}</strong>
              </div>
              <div class="split-row">
                <span>Kollektionen</span>
                <strong>${escapeHtml(String(sheets.collections.length))}</strong>
              </div>
              <div class="split-row">
                <span>Vektoren</span>
                <strong>${escapeHtml(String(sheets.vectors.length))}</strong>
              </div>
            </div>
          </article>
          <article class="stat-panel library-utility-card">
            <span class="card-badge">Aurora Hinweis</span>
            <p class="card-copy">${escapeHtml(featuredCollection?.editorial_rationale ?? "Keine Kollektion aktiv.")}</p>
            <div class="line-meter"><span style="width:${Math.min(95, feed.length * 2)}%"></span></div>
            <span class="helper-copy">${escapeHtml(`${feed.length} sichtbare Karten im aktuellen Browse-Modus.`)}</span>
          </article>
        </aside>
      </section>

      <section class="section-copy library-toolbar">
        <div class="search-row search-row--library">
          <input class="search-input" name="library-query" value="${escapeHtml(uiState.libraryQuery)}" placeholder="Methoden, Beschreibungen oder Themen durchsuchen" />
          <button class="button-secondary" data-action="apply-library-search">${renderIcon(ICONS.search, "button-symbol")}Filtern</button>
        </div>
        <div class="vector-cloud vector-cloud--library">
          <button class="vector-button ${!vectorId ? "is-active" : ""}" data-action="filter-vector" data-vector-id="">Alle</button>
          ${sheets.vectors
            .map(
              (vector) => `
                <button class="vector-button ${vectorId === vector.vector_id ? "is-active" : ""}" data-action="filter-vector" data-vector-id="${vector.vector_id}">
                  ${escapeHtml(vector.vector_name_de)}
                </button>
              `,
            )
            .join("")}
        </div>
      </section>

      ${
        visibleCollections
          ? `
            <section class="section-copy">
              <div class="section-head">
                <div>
                  <h3>Kollektionen</h3>
                  <p>Kuratiert aus <code>Collections</code> und <code>Collection_Items</code>.</p>
                </div>
              </div>
              <div class="grid-cards library-collection-grid">
                ${sheets.collections
                  .map(
                    (collection) => `
                      <a class="collection-tile card collection-tile--editorial" href="#/library/collections/${collection.collection_id}" data-mark="${escapeHtml(collection.name_de.slice(0, 1))}">
                        <span class="card-badge">${escapeHtml(collection.visibility ?? "visible")}</span>
                        <h4 class="card-title">${escapeHtml(collection.name_de)}</h4>
                        <p class="card-copy">${escapeHtml(collection.short_description ?? "")}</p>
                        <span class="text-link">Zur Kollektion</span>
                      </a>
                    `,
                  )
                  .join("")}
              </div>
            </section>
          `
          : ""
      }

      <section class="section-copy">
        <div class="section-head">
          <div>
            <h3>Alle Methoden</h3>
            <p>Karten blenden sparse Felder aus, statt Platzhalterdaten zu erfinden.</p>
          </div>
          <div class="results-meta">
            <span>${escapeHtml(String(feed.length))} Treffer</span>
            <span>${vectorId ? escapeHtml(vectorById.get(vectorId)?.vector_name_de ?? "") : "ohne Vektorfilter"}</span>
          </div>
        </div>
        ${renderCards(feed, "Keine Methoden im aktuellen Filter.", { gridClass: "library-method-grid", variant: "library" })}
      </section>
    `,
    "Editorial Browse",
    "Library",
    {
      topbarTabs: [
        { label: "Alle Methoden", action: "set-library-mode", mode: "all", isActive: !visibleCollections },
        { label: "Kollektionen", action: "set-library-mode", mode: "collections", isActive: visibleCollections },
      ],
    },
  );
}

function renderCollection(route) {
  const detail = getCollectionDetail(route.params.collectionId);
  if (!detail) {
    return renderNotFound("Kollektion nicht gefunden.");
  }
  return buildLayout(
    route,
    `
      <section class="hero collection-hero">
        <span class="hero-kicker">Kollektion</span>
        <h2 class="hero-title">${escapeHtml(detail.collection.name_de)}</h2>
        <p class="hero-copy">${escapeHtml(detail.collection.short_description ?? "")}</p>
        <div class="footer-note footer-note--quiet">${escapeHtml(detail.collection.editorial_rationale ?? "")}</div>
      </section>
      <section class="section-copy">
        <div class="section-head">
          <div>
            <h3>Kuratiertes Set</h3>
            <p>${escapeHtml(String(detail.items.length))} verknüpfte Methoden oder Varianten aus der SSOT.</p>
          </div>
          <a class="button-secondary" href="#/library">Zur Library</a>
        </div>
        ${renderCards(detail.items, "Diese Kollektion enthält derzeit keine auflösbaren Einträge.", { gridClass: "library-method-grid", variant: "library" })}
      </section>
    `,
    "Collection Detail",
    detail.collection.name_de,
  );
}

function renderMethodDetail(route) {
  const detail = getMethodDetail(route.params.methodId, route.query.get("variant"));
  if (!detail) {
    return renderNotFound("Methode nicht gefunden.");
  }
  const duration = formatMethodDuration(detail.method);
  return buildLayout(
    route,
    `
      <section class="detail-grid method-detail-hero">
        <div class="detail-feature glass-panel method-hero-panel">
          <div class="chip-row">
            ${detail.phase ? `<span class="chip chip-tertiary">${escapeHtml(detail.phase)}</span>` : ""}
            ${duration ? `<span class="chip chip-secondary">${escapeHtml(duration)}</span>` : ""}
            ${detail.energyRole ? `<span class="chip chip-primary">${escapeHtml(detail.energyRole)}</span>` : detail.energyLevel ? `<span class="chip chip-primary">${escapeHtml(`Energie ${detail.energyLevel}`)}</span>` : ""}
            <span class="chip chip-muted">${escapeHtml(detail.variant ? "Variante" : "Methode")}</span>
          </div>
          <h2>${escapeHtml(detail.title)}</h2>
          <p class="detail-copy">${escapeHtml(detail.subtitle ?? detail.method.short_description ?? "")}</p>
          <div class="detail-actions">
            <button class="button-primary" data-action="start-from-source" data-source-type="${detail.sourceType}" data-source-id="${detail.sourceId}">
              Direkt in Session
            </button>
            <a class="button-secondary" href="#/composer/${getDefaultDraft().id}">Im Composer öffnen</a>
          </div>
        </div>
        <aside class="detail-sidebar method-detail-sidebar">
          <div class="detail-panel method-meta-panel">
            <span class="card-badge">Methodenrahmen</span>
            <div class="detail-list">
              ${detail.phase ? `<div class="detail-list-item"><strong>Phase</strong><span>${escapeHtml(detail.phase)}</span></div>` : ""}
              ${duration ? `<div class="detail-list-item"><strong>Dauer</strong><span>${escapeHtml(duration)}</span></div>` : ""}
              ${detail.energyRole ? `<div class="detail-list-item"><strong>Energie</strong><span>${escapeHtml(detail.energyRole)}</span></div>` : ""}
              ${detail.method.group_form ? `<div class="detail-list-item"><strong>Setting</strong><span>${escapeHtml(detail.method.group_form)}</span></div>` : ""}
            </div>
            ${detail.method.materials ? `<div class="meta-chips"><span class="chip chip-muted">${escapeHtml(detail.method.materials)}</span></div>` : ""}
            ${!detail.phase && !duration && !detail.energyRole && !detail.method.group_form && !detail.method.materials ? `<p class="helper-copy">Keine gesicherten Metadaten vorhanden. Die Oberfläche bleibt absichtlich reduziert.</p>` : ""}
          </div>
          ${detail.relatedCollections.length ? `
            <div class="detail-panel">
              <h4>Kollektionen</h4>
              <div class="detail-list">
                ${detail.relatedCollections.map((collection) => `
                  <a class="detail-list-item" href="#/library/collections/${collection.collection_id}">
                    <strong>${escapeHtml(collection.name_de)}</strong>
                    <span>${escapeHtml(collection.short_description ?? "")}</span>
                  </a>
                `).join("")}
              </div>
            </div>
          ` : ""}
        </aside>
      </section>

      <section class="detail-grid method-detail-body">
        <div class="detail-panel method-guide-panel">
          <div class="section-head">
            <div>
              <h3>Operational Guide</h3>
              <p>Die Beschreibung bleibt quellentreu und blendet fehlende Angaben bewusst aus.</p>
            </div>
          </div>
          ${
            detail.descriptionParagraphs.length
              ? `<div class="detail-steps">
                  ${detail.descriptionParagraphs
                    .map(
                      (paragraph, index) => `
                        <div class="detail-step">
                          <div class="detail-step-index">${String(index + 1).padStart(2, "0")}</div>
                          <p class="detail-copy">${escapeHtml(paragraph)}</p>
                        </div>
                      `,
                    )
                    .join("")}
                </div>`
              : `<p class="detail-copy">Keine längere Beschreibung im Workbook vorhanden.</p>`
          }
        </div>
        <div class="detail-panel method-facilitator-panel">
          <h4>Facilitator Notes</h4>
          ${
            detail.notes.length || detail.risks.length
              ? `
                <div class="warning-stack">
                  ${detail.notes.map((note) => `<div class="warning-card"><strong>Hinweis</strong><span>${escapeHtml(note)}</span></div>`).join("")}
                  ${detail.risks.map((risk) => `<div class="warning-card"><strong>Risiko / Schutz</strong><span>${escapeHtml(risk)}</span></div>`).join("")}
                </div>
              `
              : `<p class="helper-copy">Keine zusätzlichen Hinweise vorhanden. Leere Panels werden absichtlich nicht simuliert.</p>`
          }
          ${detail.relatedVariants.length ? `
            <div class="detail-list">
              <strong>Varianten</strong>
              ${detail.relatedVariants.map((variant) => `
                <a class="detail-list-item" href="#/library/method/${detail.method.method_id}?variant=${variant.variant_id}">
                  <strong>${escapeHtml(variant.variant_name)}</strong>
                  <span>${escapeHtml(variant.variant_label ?? variant.use_case ?? "")}</span>
                </a>
              `).join("")}
            </div>
          ` : ""}
        </div>
      </section>
    `,
    "Operational View",
    detail.title,
  );
}

function normalizeToken(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function energyLevelValue(level) {
  const normalized = normalizeToken(level);
  if (normalized.includes("hoch")) return 0.84;
  if (normalized.includes("mittel")) return 0.58;
  if (normalized.includes("niedrig")) return 0.32;
  return 0.54;
}

function energyRoleAdjustment(role) {
  const normalized = normalizeToken(role);
  if (normalized.includes("aktiv")) return 0.1;
  if (normalized.includes("vertief")) return 0.04;
  if (normalized.includes("fokus")) return -0.03;
  if (normalized.includes("start")) return -0.04;
  if (normalized.includes("beruh")) return -0.18;
  if (normalized.includes("absch")) return -0.12;
  return 0;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function curveColorForRole(role) {
  const normalized = normalizeToken(role);
  if (normalized.includes("aktiv")) return "#FFB1C2";
  if (normalized.includes("vertief")) return "#7CD6CD";
  if (normalized.includes("fokus")) return "#7CD6CD";
  if (normalized.includes("beruh")) return "#E8C500";
  if (normalized.includes("absch")) return "#E8C500";
  return "#FFB1C2";
}

function buildCurvePath(points) {
  if (!points.length) {
    return "";
  }
  if (points.length === 1) {
    return `M 80 132 C 180 132, 260 ${points[0].y}, ${points[0].x} ${points[0].y} C 720 ${points[0].y}, 820 132, 920 132`;
  }
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const controlX = (previous.x + current.x) / 2;
    path += ` C ${controlX} ${previous.y}, ${controlX} ${current.y}, ${current.x} ${current.y}`;
  }
  return path;
}

function buildComposerCurve(blocks) {
  if (!blocks.length) {
    return {
      modeLabel: "Wartet auf Blöcke",
      contextLabel: "Noch keine ausgewählten Methoden in der Timeline.",
      averageLabel: "Kein Signal",
      peakLabel: "Kein Peak",
      points: [],
      path: "",
    };
  }

  const weightedByDuration = blocks.every((block) => typeof block.resolvedDuration === "number" && block.resolvedDuration > 0);
  const weights = weightedByDuration ? blocks.map((block) => block.resolvedDuration) : blocks.map(() => 1);
  const totalWeight = weights.reduce((sum, weight) => sum + weight, 0) || 1;
  let cursor = 0;

  const points = blocks.map((block, index) => {
    const midpoint = cursor + weights[index] / 2;
    cursor += weights[index];
    const x = blocks.length === 1 ? 500 : 80 + (midpoint / totalWeight) * 840;
    const score = clamp(energyLevelValue(block.energyLevel) + energyRoleAdjustment(block.energyRole), 0.16, 0.92);
    const y = 152 - score * 102;
    return {
      ...block,
      x,
      y,
      score,
      color: curveColorForRole(block.energyRole),
      label: block.phase ?? block.title,
      footLabel: weightedByDuration ? block.durationLabel ?? "offen" : `Block ${index + 1}`,
    };
  });

  const average = points.reduce((sum, point) => sum + point.score, 0) / points.length;
  const peak = points.reduce((currentPeak, point) => (point.score > currentPeak.score ? point : currentPeak), points[0]);

  return {
    modeLabel: weightedByDuration ? "Zeitgewichtet" : "Sequenzbasiert",
    contextLabel: weightedByDuration
      ? "Abstände folgen den bekannten Blockdauern."
      : "Abstände folgen der Reihenfolge, weil nicht alle Dauern gesichert sind.",
    averageLabel: average > 0.72 ? "Hohe Gesamtenergie" : average > 0.5 ? "Mittlere Gesamtenergie" : "Ruhige Gesamtenergie",
    peakLabel: peak.title,
    points,
    path: buildCurvePath(points),
  };
}

function renderComposer(route) {
  const draft = getDraftById(route.params.draftId);
  const summary = getSessionHydration(draft);
  const curve = buildComposerCurve(summary.hydratedBlocks);
  const pool = getComposerPool({
    query: uiState.composerQuery,
    phase: uiState.composerPhase,
    energy: uiState.composerEnergy,
  });
  return buildLayout(
    route,
    `
      <section class="section-copy composer-header">
        <div class="section-head">
          <div>
            <span class="eyebrow">Live Orchestration</span>
            <h2 class="hero-title">Workshop Composer<span class="accent">.</span></h2>
          </div>
          <div class="header-actions">
            <button class="button-secondary" data-action="duplicate-draft" data-draft-id="${draft.id}">${renderIcon(ICONS.duplicate, "button-symbol")}Entwurf duplizieren</button>
            <a class="button-primary" href="#/session/${draft.id}/active">${renderIcon(ICONS.launch, "button-symbol")}Session starten</a>
          </div>
        </div>
        <div class="composer-toolbar composer-toolbar--header">
          <input class="inline-field" name="draft-name" value="${escapeHtml(draft.name)}" placeholder="Entwurfsname" />
          <span class="helper-copy">${escapeHtml(summary.totalLabel)}</span>
        </div>
      </section>

      <section class="composer-curve glass-panel composer-curve-panel">
        <div class="section-head">
          <div>
            <h3>Dramaturgie & Energie</h3>
            <p>Die Kurve wird aus den aktuell gewählten Blöcken und ihren SSOT-Energiesignalen aufgebaut.</p>
          </div>
          <div class="curve-legend">
            <span><span class="legend-dot" style="background:var(--primary)"></span> Verbindung</span>
            <span><span class="legend-dot" style="background:var(--secondary)"></span> Fokus</span>
            <span><span class="legend-dot" style="background:var(--tertiary)"></span> Output</span>
          </div>
        </div>
        <div class="results-meta">
          <span>${escapeHtml(curve.modeLabel)}</span>
          <span>${escapeHtml(curve.averageLabel)}</span>
          <span>${escapeHtml(`Peak: ${curve.peakLabel}`)}</span>
        </div>
        <div class="curve-shell">
          ${
            curve.points.length
              ? `
                <svg viewBox="0 0 1000 180" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="curveGradient" x1="0%" x2="100%" y1="0%" y2="0%">
                      <stop offset="0%" stop-color="#FFB1C2"></stop>
                      <stop offset="50%" stop-color="#7CD6CD"></stop>
                      <stop offset="100%" stop-color="#E8C500"></stop>
                    </linearGradient>
                  </defs>
                  <path d="M 40 148 L 960 148" stroke="rgba(255,255,255,0.08)" stroke-width="2" fill="none"></path>
                  <path d="${curve.path}" fill="none" stroke="url(#curveGradient)" stroke-width="6" stroke-linecap="round"></path>
                  ${curve.points
                    .map(
                      (point) => `
                        <circle cx="${point.x}" cy="${point.y}" r="9" fill="${point.color}"></circle>
                        <circle cx="${point.x}" cy="${point.y}" r="18" fill="${point.color}" fill-opacity="0.12"></circle>
                      `,
                    )
                    .join("")}
                </svg>
              `
              : `<div class="empty-state"><strong>Noch keine Kurve</strong><span>Füge Methoden hinzu, damit die Energie dramaturgisch sichtbar wird.</span></div>`
          }
        </div>
        <div class="curve-ticks">
          ${curve.points
            .map(
              (point) => `
                <div class="curve-tick">
                  <strong>${escapeHtml(point.label)}</strong>
                  <span>${escapeHtml(point.footLabel)}</span>
                </div>
              `,
            )
            .join("")}
        </div>
        <p class="helper-copy">${escapeHtml(curve.contextLabel)}</p>
      </section>

      <section class="composer-grid composer-grid--fidelity">
        <div class="timeline-toolbar">
          <div class="section-head">
            <div>
              <h3>Session Timeline</h3>
              <p>Kuratiert als Session-Strip: Dauer, Energie und Reihenfolge führen, Detailsteuerung bleibt kompakt.</p>
            </div>
            <span class="chip chip-muted">${escapeHtml(summary.totalLabel)}</span>
          </div>
          <div class="timeline-stack timeline-stack--curated">
            <div class="dropzone card dropzone--slot" data-dropzone="timeline" data-insert-index="0">
              An den Anfang ziehen
            </div>
            ${summary.hydratedBlocks
              .map(
                (block, index) => `
                  <article class="timeline-item card timeline-item--curated" draggable="true" data-runtime-id="${block.runtimeId}">
                    <div class="timeline-marker">
                      <span class="timeline-duration">${escapeHtml(block.durationLabel ?? "offen")}</span>
                      <div class="timeline-ordinal">${String(index + 1).padStart(2, "0")}</div>
                    </div>
                    <div class="composer-meta">
                      <div class="chip-row">
                        ${block.phase ? `<span class="chip chip-primary">${escapeHtml(block.phase)}</span>` : ""}
                        ${block.durationLabel ? `<span class="chip chip-tertiary">${escapeHtml(block.durationLabel)}</span>` : ""}
                        ${block.energyRole ? `<span class="chip chip-secondary">${escapeHtml(block.energyRole)}</span>` : ""}
                        ${block.manualDuration ? `<span class="chip chip-tertiary">Manuell ${escapeHtml(String(block.manualDuration))} Min.</span>` : ""}
                      </div>
                      <h4 class="timeline-title">${escapeHtml(block.title)}</h4>
                      <p class="timeline-copy">${escapeHtml(block.summary ?? "")}</p>
                      <div class="chip-row">
                        ${block.groupSetting ? `<span class="chip chip-muted">${escapeHtml(block.groupSetting)}</span>` : ""}
                        ${block.materials ? `<span class="chip chip-muted">${escapeHtml(block.materials)}</span>` : ""}
                      </div>
                      <div class="timeline-utilities">
                        <label class="timeline-duration-field">
                          <span>Manuelle Dauer</span>
                          <input
                            class="inline-field"
                            type="number"
                            min="1"
                            step="1"
                            placeholder="Min."
                            value="${escapeHtml(block.manualDuration ?? "")}"
                            data-action="manual-duration"
                            data-block-id="${block.runtimeId}"
                          />
                        </label>
                        <div class="timeline-utility-actions">
                          <button class="icon-action" data-action="move-block" data-direction="up" data-block-id="${block.runtimeId}" aria-label="Nach oben" title="Nach oben">${renderIcon("arrow_upward")}</button>
                          <button class="icon-action" data-action="move-block" data-direction="down" data-block-id="${block.runtimeId}" aria-label="Nach unten" title="Nach unten">${renderIcon("arrow_downward")}</button>
                          <button class="icon-action" data-action="duplicate-block" data-block-id="${block.runtimeId}" aria-label="Duplizieren" title="Duplizieren">${renderIcon(ICONS.duplicate)}</button>
                          <button class="icon-action" data-action="remove-block" data-block-id="${block.runtimeId}" aria-label="Entfernen" title="Entfernen">${renderIcon("delete")}</button>
                        </div>
                      </div>
                      <details class="timeline-note-shell" ${block.customNote ? "open" : ""}>
                        <summary>Block-Notiz</summary>
                        <textarea
                          class="notes-input notes-input-inline"
                          placeholder="Block-Notiz fuer Moderation oder Umbau"
                          data-action="block-note"
                          data-block-id="${block.runtimeId}"
                        >${escapeHtml(block.customNote ?? "")}</textarea>
                      </details>
                    </div>
                    <a class="text-link" href="#/library/method/${block.method.method_id}${block.variant ? `?variant=${block.variant.variant_id}` : ""}">Detail</a>
                  </article>
                  <div class="dropzone card dropzone--slot" data-dropzone="timeline" data-insert-index="${index + 1}">
                    ${index === summary.hydratedBlocks.length - 1 ? "An das Ende ziehen" : "Zwischen zwei Blöcke ziehen"}
                  </div>
                `,
              )
              .join("")}
            ${!summary.hydratedBlocks.length ? `<div class="empty-state card"><strong>Leerer Entwurf</strong><span>Ziehe einen Block aus dem Pool in die Timeline oder füge ihn per Button hinzu.</span></div>` : ""}
          </div>
        </div>

        <aside class="pool-toolbar">
          <div class="detail-panel pool-shell">
            <h4>Method Pool</h4>
            <div class="search-grid pool-filter-grid">
              <input class="search-input" name="composer-query" value="${escapeHtml(uiState.composerQuery)}" placeholder="Methoden suchen" />
              <select class="select-input" name="composer-phase">
                <option value="">Alle Phasen</option>
                ${["Ankommen", "Aktivieren", "Reflektieren", "Feedback", "Abschluss"]
                  .map((phase) => `<option value="${phase}" ${uiState.composerPhase === phase ? "selected" : ""}>${phase}</option>`)
                  .join("")}
              </select>
              <select class="select-input" name="composer-energy">
                <option value="">Alle Rollen</option>
                ${["starten", "aktivieren", "abschliessen", "fokussieren"]
                  .map((energy) => `<option value="${energy}" ${uiState.composerEnergy === energy ? "selected" : ""}>${energy}</option>`)
                  .join("")}
              </select>
              <button class="button-secondary button-small" data-action="apply-composer-search">Pool filtern</button>
            </div>
          </div>
          <div class="pool-stack">
            ${pool
              .slice(0, 18)
              .map(
                (item) => `
                  <article class="pool-card card pool-card--dense" draggable="true" data-block-ref-id="${item.blockRef.block_ref_id}">
                    <div class="chip-row">
                      ${item.durationLabel ? `<span class="chip chip-tertiary">${escapeHtml(item.durationLabel)}</span>` : ""}
                      ${item.phase ? `<span class="chip chip-primary">${escapeHtml(item.phase)}</span>` : ""}
                    </div>
                    <h4 class="card-title">${escapeHtml(item.title)}</h4>
                    <p class="card-copy">${escapeHtml(item.summary ?? "")}</p>
                    <div class="card-links">
                      <button class="button-secondary button-small" data-action="add-pool-block" data-block-ref-id="${item.blockRef.block_ref_id}" data-draft-id="${draft.id}">
                        Hinzufügen
                      </button>
                      <span class="muted-link">${escapeHtml(item.icon)}</span>
                    </div>
                  </article>
                `,
              )
              .join("")}
          </div>
        </aside>
      </section>
    `,
    "Workshop Composer",
    draft.name,
  );
}

function renderSession(route) {
  const draft = getDraftById(route.params.sessionId);
  const summary = getSessionHydration(draft);
  if (!summary.hydratedBlocks.length) {
    return buildLayout(
      route,
      `
        <div class="empty-state card">
          <strong>Keine Session-Blöcke verfügbar</strong>
          <span>Füge im Composer zuerst mindestens einen Block hinzu.</span>
          <a class="button-primary" href="#/composer/${draft.id}">Zum Composer</a>
        </div>
      `,
      "Facilitator Mode",
      draft.name,
    );
  }

  const sessionState = getSessionState(route.params.sessionId);
  const currentIndex = Math.min(sessionState.currentIndex ?? 0, summary.hydratedBlocks.length - 1);
  const currentBlock = summary.hydratedBlocks[currentIndex];
  const detailModel = getActiveSessionViewModel(currentBlock);
  const activeDetailTab = detailModel && detailModel.sections[uiState.sessionDetailTab]?.hasContent
    ? uiState.sessionDetailTab
    : ["ablauf", "rahmen", "hinweise"].find((key) => detailModel?.sections[key].hasContent) ?? "ablauf";
  const defaultSeconds = typeof currentBlock.resolvedDuration === "number" ? currentBlock.resolvedDuration * 60 : null;
  const remainingSeconds = sessionState.activeBlockId === currentBlock.runtimeId ? sessionState.secondsRemaining : defaultSeconds;

  return buildLayout(
    route,
    `
      <section class="active-session-status active-session-status--compact">
        <div class="active-session-status-copy">
          <span class="eyebrow">Facilitator Mode</span>
          <h2>${escapeHtml(draft.name)}</h2>
        </div>
        <div class="chip-row">
          <span class="chip chip-secondary">${escapeHtml(`Block ${currentIndex + 1} / ${summary.hydratedBlocks.length}`)}</span>
          ${currentBlock.phase ? `<span class="chip chip-primary">${escapeHtml(currentBlock.phase)}</span>` : ""}
          ${currentBlock.durationLabel ? `<span class="chip chip-tertiary">${escapeHtml(currentBlock.durationLabel)}</span>` : ""}
        </div>
      </section>

      <section class="active-session-shell active-session-shell--fidelity">
        <div class="active-session-stage">
          <article class="active-session-livecard glass-panel active-session-livecard--hero">
            <div class="chip-row active-session-livehead">
              <span class="chip chip-secondary">Aktueller Block</span>
              ${detailModel?.overview.variantLabel ? `<span class="chip chip-muted">${escapeHtml(detailModel.overview.variantLabel)}</span>` : ""}
            </div>
            <h3>${escapeHtml(currentBlock.title)}</h3>
            <p class="session-prompt">${escapeHtml(currentBlock.prompt ?? currentBlock.summary ?? "")}</p>
            ${
              detailModel?.overview.lines?.length
                ? `
                  <div class="active-session-overview-lines">
                    ${detailModel.overview.lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("")}
                  </div>
                `
                : ""
            }
            ${currentBlock.customNote ? `<div class="active-session-blocknote"><strong>Block-Notiz</strong><p>${escapeHtml(currentBlock.customNote)}</p></div>` : ""}
            ${renderSessionMobileDetails(detailModel, activeDetailTab)}
            <div class="session-controls">
              <button class="button-secondary" data-action="session-prev" data-session-id="${draft.id}">Zurück</button>
              <button class="button-primary" data-action="session-next" data-session-id="${draft.id}">Weiter</button>
            </div>
          </article>
          ${renderSessionNotesPanel(draft.id, sessionState.notes ?? [])}
        </div>

        <aside class="active-session-rail">
          ${renderSessionTimerPanel({ draftId: draft.id, currentBlock, defaultSeconds, remainingSeconds })}
          ${
            detailModel?.overview.hasContent
              ? `
                <section class="session-overview-card session-overview-card--quiet">
                  <div class="section-head">
                    <div>
                      <h4>${escapeHtml(detailModel.overview.title)}</h4>
                    </div>
                    <a class="text-link" href="${detailModel.methodHref}">Volles Detail</a>
                  </div>
                  <div class="session-overview-copy">
                    ${detailModel.overview.lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("")}
                  </div>
                  <span class="helper-copy">${escapeHtml(detailModel.overview.sourceLabel)}</span>
                </section>
              `
              : ""
          }

          ${renderSessionDesktopDetails(detailModel)}
          ${renderSessionOutlinePanel(summary, currentIndex, draft.id)}
        </aside>
      </section>
    `,
    "Active Session",
    draft.name,
  );
}

function renderNotFound(message) {
  return buildLayout(
    { name: "finder" },
    `<div class="empty-state card"><strong>Nicht gefunden</strong><span>${escapeHtml(message)}</span><a class="button-primary" href="#/finder">Zur Übersicht</a></div>`,
    "Methodensammlung",
    "Status",
  );
}

function toClock(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function render() {
  try {
    ensureHash();
    const route = parseHash();
    if (route.name === "session" && uiState.lastRouteName !== "session") {
      resetActiveSessionUi();
    }
    let html = "";
    if (route.name === "finder") html = renderFinder(route);
    else if (route.name === "library") html = renderLibrary(route);
    else if (route.name === "collection") html = renderCollection(route);
    else if (route.name === "method") html = renderMethodDetail(route);
    else if (route.name === "composer") html = renderComposer(route);
    else if (route.name === "session") html = renderSession(route);
    else html = renderNotFound("Die Route ist nicht verfügbar.");
    app.innerHTML = html;
    uiState.lastRouteName = route.name;
  } catch (error) {
    console.error(error);
    app.innerHTML = `
      <main class="content">
        <div class="empty-state card">
          <strong>Render-Fehler</strong>
          <span>${escapeHtml(error?.message ?? "Unbekannter Fehler")}</span>
          <span>${escapeHtml(error?.stack ?? "")}</span>
        </div>
      </main>
    `;
  }
}

document.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  if (target.matches('[name="finder-query"]')) {
    uiState.finderQuery = target.value;
  }
  if (target.matches('[name="library-query"]')) {
    uiState.libraryQuery = target.value;
  }
  if (target.matches('[name="composer-query"]')) {
    uiState.composerQuery = target.value;
  }
  if (target.matches('[name="composer-phase"]')) {
    uiState.composerPhase = target.value;
    render();
  }
  if (target.matches('[name="composer-energy"]')) {
    uiState.composerEnergy = target.value;
    render();
  }
  if (target.matches('[name="session-manual-minutes"]')) {
    uiState.sessionManualMinutesInput = target.value;
  }
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  if (target.matches('[name="draft-name"]')) {
    const route = parseHash();
    updateDraftName(route.params.draftId, target.value || "Unbenannter Entwurf");
  }
  if (target.matches('[data-action="manual-duration"]')) {
    const route = parseHash();
    updateBlockDuration(route.params.draftId, target.dataset.blockId, target.value);
  }
  if (target.matches('[data-action="block-note"]')) {
    const route = parseHash();
    updateBlockNote(route.params.draftId, target.dataset.blockId, target.value);
  }
});

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!(target instanceof HTMLElement)) return;

  const action = target.dataset.action;
  if (action === "finder-submit") {
    uiState.finderOpenChooser = "";
    markFinderDirty();
    render();
  }
  if (action === "finder-reset") {
    clearFinderState();
    render();
  }
  if (action === "choose-intent") {
    const nextIntentId = uiState.finderIntentId === target.dataset.intentId ? null : target.dataset.intentId;
    const baseChanged = nextIntentId !== uiState.finderIntentId || Boolean(uiState.finderGoal);
    uiState.finderIntentId = nextIntentId;
    uiState.finderGoal = "";
    if (baseChanged) {
      clearFinderAfterBaseSelection();
    }
    uiState.finderOpenChooser = nextIntentId ? "time" : "goal";
    render();
  }
  if (action === "toggle-finder-filter") {
    toggleFinderFilter(target.dataset.filterKey, target.dataset.value);
    render();
  }
  if (action === "set-finder-chooser") {
    setFinderChooser(target.dataset.chooser);
    render();
  }
  if (action === "clear-finder-query") {
    uiState.finderQuery = "";
    uiState.finderOpenChooser = "refine";
    markFinderDirty();
    render();
  }
  if (action === "finder-show-more") {
    uiState.finderShowAllResults = !uiState.finderShowAllResults;
    render();
  }
  if (action === "filter-vector") {
    uiState.libraryVectorId = target.dataset.vectorId || null;
    render();
  }
  if (action === "set-library-mode" || action === "jump-library-mode") {
    uiState.libraryMode = target.dataset.mode;
    window.location.hash = "#/library";
    render();
  }
  if (action === "apply-library-search" || action === "apply-composer-search") {
    render();
  }
  if (action === "add-pool-block") {
    appendBlockToDraft(target.dataset.draftId, target.dataset.blockRefId);
  }
  if (action === "move-block") {
    const route = parseHash();
    moveDraftBlock(route.params.draftId, target.dataset.blockId, target.dataset.direction);
  }
  if (action === "duplicate-block") {
    const route = parseHash();
    duplicateDraftBlock(route.params.draftId, target.dataset.blockId);
  }
  if (action === "remove-block") {
    const route = parseHash();
    removeDraftBlock(route.params.draftId, target.dataset.blockId);
  }
  if (action === "duplicate-draft") {
    duplicateDraft(getDraftById(target.dataset.draftId));
  }
  if (action === "start-from-source") {
    startSessionFromMethod(target.dataset.sourceType, target.dataset.sourceId);
  }
  if (action === "new-draft") {
    const template = getDefaultDraft();
    duplicateDraft(template);
  }
  if (action === "jump-composer") {
    window.location.hash = `#/composer/${getDefaultDraft().id}`;
  }
  if (action === "jump-session") {
    window.location.hash = `#/session/${getDefaultDraft().id}/active`;
  }
  if (action === "session-prev") {
    const current = getSessionState(target.dataset.sessionId).currentIndex ?? 0;
    setSessionIndex(target.dataset.sessionId, Math.max(0, current - 1));
  }
  if (action === "session-next") {
    const summary = getSessionHydration(getDraftById(target.dataset.sessionId));
    const current = getSessionState(target.dataset.sessionId).currentIndex ?? 0;
    setSessionIndex(target.dataset.sessionId, Math.min(summary.hydratedBlocks.length - 1, current + 1));
  }
  if (action === "session-jump") {
    setSessionIndex(target.dataset.sessionId, Number(target.dataset.index));
  }
  if (action === "session-detail-tab") {
    uiState.sessionDetailTab = target.dataset.tab;
    render();
  }
  if (action === "toggle-session-flow") {
    uiState.sessionFlowExpanded = !uiState.sessionFlowExpanded;
    render();
  }
  if (action === "toggle-session-notes") {
    uiState.sessionNotesExpanded = !uiState.sessionNotesExpanded;
    render();
  }
  if (action === "session-adjust") {
    const currentState = getSessionState(target.dataset.sessionId);
    const current = currentState.activeBlockId === target.dataset.blockId ? currentState.secondsRemaining ?? 0 : 0;
    setSessionTimer(target.dataset.sessionId, target.dataset.blockId, Math.max(0, current + Number(target.dataset.seconds)));
  }
  if (action === "session-manual-adjust") {
    const next = Math.max(1, Number(uiState.sessionManualMinutesInput || "5") + Number(target.dataset.delta));
    uiState.sessionManualMinutesInput = String(next);
    render();
  }
  if (action === "session-start-manual") {
    const minutes = Math.max(1, Number(uiState.sessionManualMinutesInput || "5"));
    setSessionTimer(target.dataset.sessionId, target.dataset.blockId, minutes * 60);
  }
  if (action === "session-clear-timer") {
    updateSessionState(target.dataset.sessionId, { secondsRemaining: null, activeBlockId: null });
    render();
  }
  if (action === "add-session-note") {
    const textarea = document.querySelector('[name="session-note"]');
    if (textarea instanceof HTMLTextAreaElement && textarea.value.trim()) {
      addSessionNote(target.dataset.sessionId, textarea.value.trim());
    }
  }
});

document.addEventListener("keydown", (event) => {
  const rawTarget = event.target;
  if (!(rawTarget instanceof Element)) return;
  const target = rawTarget.closest('[role="button"][data-action]');
  if (!(target instanceof HTMLElement)) return;
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  target.click();
});

document.addEventListener("dragstart", (event) => {
  const target = event.target.closest("[data-block-ref-id], [data-runtime-id]");
  if (!(target instanceof HTMLElement)) return;
  if (target.dataset.blockRefId) {
    uiState.dragPayload = { kind: "pool", blockRefId: target.dataset.blockRefId };
  }
  if (target.dataset.runtimeId) {
    uiState.dragPayload = { kind: "timeline", runtimeId: target.dataset.runtimeId };
  }
  if (target.dataset.runtimeId) {
    target.classList.add("is-dragging");
  }
});

document.addEventListener("dragend", (event) => {
  const target = event.target.closest("[data-block-ref-id], [data-runtime-id]");
  if (!(target instanceof HTMLElement)) return;
  target.classList.remove("is-dragging");
});

document.addEventListener("dragover", (event) => {
  const target = event.target.closest("[data-dropzone]");
  if (!(target instanceof HTMLElement)) return;
  event.preventDefault();
  target.classList.add("is-over");
});

document.addEventListener("dragleave", (event) => {
  const target = event.target.closest("[data-dropzone]");
  if (!(target instanceof HTMLElement)) return;
  target.classList.remove("is-over");
});

document.addEventListener("drop", (event) => {
  const target = event.target.closest("[data-dropzone]");
  if (!(target instanceof HTMLElement)) return;
  event.preventDefault();
  target.classList.remove("is-over");
  if (!uiState.dragPayload) return;
  const route = parseHash();
  if (uiState.dragPayload.kind === "pool") {
    appendBlockToDraft(route.params.draftId, uiState.dragPayload.blockRefId, Number(target.dataset.insertIndex));
  }
  if (uiState.dragPayload.kind === "timeline") {
    moveDraftBlockToIndex(route.params.draftId, uiState.dragPayload.runtimeId, Number(target.dataset.insertIndex));
  }
  uiState.dragPayload = null;
});

window.addEventListener("hashchange", render);
ensureHash();
render();
