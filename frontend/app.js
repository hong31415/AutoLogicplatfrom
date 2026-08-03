// The frontend proxy keeps API calls same-origin, which also makes a single
// Cpolar HTTP tunnel sufficient for sharing the complete application.
const API_BASE = "/api/v1";
const STORAGE_KEY = "autologic-history-v2";
const MY_DFA_STORAGE_KEY = "autologic-user-dfas-v1";
const COMPOSER_DFA_STORAGE_KEY = "autologic-composer-dfa-v1";
const NODE_W = 208;
const NODE_H = 78;
const IS_ENGLISH = window.AutoLogicI18n?.language === "en";
const ui = (chinese, english) => IS_ENGLISH ? english : chinese;
const THRESHOLD_PRESETS = Object.freeze({
  core: { theta: 0.70, tau: 0.45, topK: 2, summary: "核心 · 只保留关键状态" },
  balanced: { theta: 0.50, tau: 0.20, topK: 3, summary: "均衡 · 兼顾核心与覆盖" },
  comprehensive: { theta: 0.30, tau: 0.10, topK: 8, summary: "全面 · 扩大状态覆盖" }
});
const INTERNAL_DFA_STAGE_LABELS = Object.freeze({
  entry: ui("入口状态", "Entry State"),
  material: ui("材料绑定", "Material Binding"),
  evidence: ui("证据汇合", "Evidence Aggregation"),
  event: ui("证据事件", "Evidence Event"),
  condition: ui("条件决策", "Condition Decision"),
  generation: ui("段落生成", "Section Generation"),
  validation: ui("引用校验", "Citation Validation"),
  output: ui("段落输出", "Section Output")
});
const DFA_DOMAIN_LABELS = Object.freeze({
  precious_metals: ui("贵金属 / 有色", "Precious & Base Metals"),
  etf: "ETF",
  macro: ui("宏观", "Macro"),
  cotton: ui("棉花", "Cotton"),
  agriculture: ui("农产品", "Agriculture")
});

const state = {
  language: IS_ENGLISH ? "en" : "zh",
  health: null,
  analysis: null,
  response: null,
  events: [],
  eventIndex: 0,
  activeQuery: "",
  activeHistoryId: null,
  selectedNodeId: null,
  graphView: "construction",
  graphExpanded: false,
  reportReady: false,
  busy: false,
  playToken: 0,
  pendingTimer: null,
  pendingStartedAt: 0,
  reportGenerationTimer: null,
  reportGenerationStartedAt: 0,
  healthCheckInFlight: false,
  healthCheckTimer: null,
  revisions: [],
  expandedReportDfaKey: null,
  myDfas: loadMyDfas(),
  composerDfaId: loadComposerDfaId(),
  activeMyDfaId: null,
  myDfaDraft: null,
  myDfaSelectedNodeId: null,
  myDfaDirty: false,
  offlineDfaTemplate: null,
  offlineDfaSelectedNodeId: null,
  history: loadHistory()
};

const els = {
  newChat: document.getElementById("newChatButton"),
  historyList: document.getElementById("historyList"),
  historyCount: document.getElementById("historyCount"),
  domain: document.getElementById("domainSelect"),
  theta: document.getElementById("thetaInput"),
  thetaValue: document.getElementById("thetaValue"),
  tau: document.getElementById("tauInput"),
  tauValue: document.getElementById("tauValue"),
  fallbackTopK: document.getElementById("fallbackTopKInput"),
  thresholdPresetSummary: document.getElementById("thresholdPresetSummary"),
  thresholdPresetControl: document.getElementById("composerThresholdControl"),
  thresholdPresetButtonLabel: document.getElementById("thresholdPresetButtonLabel"),
  thresholdPresetButtonMeta: document.getElementById("thresholdPresetButtonMeta"),
  composerDfaSourceControl: document.getElementById("composerDfaSourceControl"),
  composerDfaSourceLabel: document.getElementById("composerDfaSourceLabel"),
  composerDfaSourceMeta: document.getElementById("composerDfaSourceMeta"),
  composerDfaSelect: document.getElementById("composerDfaSelect"),
  composerDfaSourceHint: document.getElementById("composerDfaSourceHint"),
  manageComposerDfa: document.getElementById("manageComposerDfaButton"),
  composerTheta: document.getElementById("composerThetaInput"),
  composerThetaValue: document.getElementById("composerThetaValue"),
  composerTau: document.getElementById("composerTauInput"),
  composerTauValue: document.getElementById("composerTauValue"),
  composerFallbackTopK: document.getElementById("composerFallbackTopKInput"),
  remoteEmbedding: document.getElementById("remoteEmbeddingInput"),
  dataSource: document.getElementById("dataSourceSelect"),
  sourceLearning: document.getElementById("sourceLearningInput"),
  forceRelearn: document.getElementById("forceRelearnInput"),
  runtimeDot: document.getElementById("runtimeDot"),
  runtimeStatus: document.getElementById("runtimeStatus"),
  dfaRuntime: document.getElementById("dfaRuntime"),
  evidenceRuntime: document.getElementById("evidenceRuntime"),
  modelRuntime: document.getElementById("modelRuntime"),
  apiStatus: document.getElementById("apiStatus"),
  conversation: document.getElementById("conversationScroll"),
  emptyState: document.getElementById("emptyState"),
  pastMessages: document.getElementById("pastMessages"),
  currentTurn: document.getElementById("currentTurn"),
  queryEcho: document.getElementById("queryEcho"),
  runTitle: document.getElementById("runTitle"),
  runSubtitle: document.getElementById("runSubtitle"),
  runBadge: document.getElementById("runBadge"),
  skipAnimation: document.getElementById("skipAnimationButton"),
  stageRail: document.getElementById("stageRail"),
  primaryKicker: document.getElementById("primaryKicker"),
  primaryTitle: document.getElementById("primaryTitle"),
  reportProgress: document.getElementById("reportProgress"),
  reportMeta: document.getElementById("reportMeta"),
  reportPreview: document.getElementById("reportPreview"),
  copyReport: document.getElementById("copyReportButton"),
  downloadReport: document.getElementById("downloadReportButton"),
  revisionThread: document.getElementById("revisionThread"),
  traceCounter: document.getElementById("traceCounter"),
  executionPane: document.querySelector(".execution-pane"),
  graphShell: document.getElementById("graphShell"),
  graphSummary: document.getElementById("graphSummary"),
  graphExpand: document.getElementById("graphExpandButton"),
  svg: document.getElementById("dfaSvg"),
  decisionContextLabel: document.getElementById("decisionContextLabel"),
  decisionIndex: document.getElementById("decisionIndex"),
  decisionTitle: document.getElementById("decisionTitle"),
  evidenceLabel: document.getElementById("evidenceLabel"),
  evidenceText: document.getElementById("evidenceText"),
  conditionLabel: document.getElementById("conditionLabel"),
  conditionText: document.getElementById("conditionText"),
  eventTimeline: document.getElementById("eventTimeline"),
  runDetailGrid: document.getElementById("runDetailGrid"),
  offlineDfa: document.getElementById("offlineDfaButton"),
  offlineDfaModal: document.getElementById("offlineDfaModal"),
  closeOfflineDfa: document.getElementById("closeOfflineDfaButton"),
  offlineDfaDomain: document.getElementById("offlineDfaDomainSelect"),
  refreshOfflineDfa: document.getElementById("refreshOfflineDfaButton"),
  offlineDfaSummary: document.getElementById("offlineDfaSummary"),
  offlineDfaMetrics: document.getElementById("offlineDfaMetrics"),
  offlineDfaSvg: document.getElementById("offlineDfaSvg"),
  offlineDfaDetail: document.getElementById("offlineDfaDetail"),
  myDfa: document.getElementById("myDfaButton"),
  myDfaModal: document.getElementById("myDfaModal"),
  closeMyDfa: document.getElementById("closeMyDfaButton"),
  myDfaSummary: document.getElementById("myDfaSummary"),
  myDfaDomain: document.getElementById("myDfaDomainSelect"),
  importMyDfa: document.getElementById("importMyDfaButton"),
  myDfaCount: document.getElementById("myDfaCount"),
  myDfaList: document.getElementById("myDfaList"),
  myDfaEmpty: document.getElementById("myDfaEmpty"),
  myDfaEditor: document.getElementById("myDfaEditor"),
  myDfaName: document.getElementById("myDfaNameInput"),
  addMyDfaNode: document.getElementById("addMyDfaNodeButton"),
  saveMyDfa: document.getElementById("saveMyDfaButton"),
  deleteMyDfa: document.getElementById("deleteMyDfaButton"),
  myDfaMetrics: document.getElementById("myDfaMetrics"),
  myDfaSvg: document.getElementById("myDfaSvg"),
  myDfaNodeEditor: document.getElementById("myDfaNodeEditor"),
  myDfaEdgeCount: document.getElementById("myDfaEdgeCount"),
  myDfaEdgeList: document.getElementById("myDfaEdgeList"),
  myDfaEdgeSource: document.getElementById("myDfaEdgeSource"),
  myDfaEdgeTarget: document.getElementById("myDfaEdgeTarget"),
  myDfaEdgeCondition: document.getElementById("myDfaEdgeCondition"),
  addMyDfaEdge: document.getElementById("addMyDfaEdgeButton"),
  scope: document.getElementById("scopeInput"),
  timeRange: document.getElementById("timeRangeInput"),
  timeRangePreset: document.getElementById("timeRangePresetSelect"),
  composer: document.getElementById("mainComposer"),
  composerFields: document.getElementById("composerFields"),
  modeButton: document.getElementById("modeButton"),
  query: document.getElementById("queryInput"),
  composerRun: document.getElementById("composerRunButton")
};

function buildTimeRangeChoices() {
  const english = state.language === "en";
  return {
    presets: {
      "complete-week": english ? "2025-06-02 to 2025-06-08" : "2025-06-02 至 2025-06-08",
      "earlier-week": "2025/11/24-2025/11/30",
      "chinese-week": english ? "Dec 1–7, 2025" : "2025年12月1日至12月7日",
      "complete-data-month": english ? "January 2026" : "2026年1月",
      "complete-quarter": english ? "Q1 2026" : "2026年第一季度",
      cutoff: english ? "As of 2026-03-31" : "截至 2026-03-31"
    },
    recommendations: [
      { preset: "complete-week", label: english ? "2025-06-02 to 2025-06-08" : "2025-06-02 至 2025-06-08", title: english ? "Historical week in hyphenated format" : "2025 年历史周区间，横线日期格式", recommended: true },
      { preset: "earlier-week", label: "2025/11/24-2025/11/30", title: english ? "Historical week in slash format" : "2025 年历史周区间，斜杠日期格式" },
      { preset: "chinese-week", label: english ? "Dec 1–7, 2025" : "2025年12月1日至12月7日", title: english ? "Historical week in written-date format" : "2025 年历史周区间，中文日期格式" },
      { preset: "complete-data-month", label: english ? "January 2026" : "2026年1月", title: english ? "An earlier month in 2026" : "2026 年较早月份" },
      { preset: "complete-quarter", label: english ? "Q1 2026" : "2026年第一季度", title: english ? "A complete quarter in 2026" : "2026 年完整季度" },
      { preset: "cutoff", label: english ? "As of 2026-03-31" : "截至 2026-03-31", title: english ? "Explicit historical cutoff date" : "明确历史截止日期" }
    ]
  };
}

function initializeTimeRangeChoices() {
  const choices = buildTimeRangeChoices();
  els.timeRangePreset.innerHTML = `<option value="">${state.language === "en" ? "Select Example" : "选择示例"}</option>`;
  choices.recommendations.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.preset;
    option.textContent = item.recommended ? `${state.language === "en" ? "Recommended" : "推荐"} · ${item.label}` : item.label;
    option.title = item.title;
    els.timeRangePreset.appendChild(option);
  });
}

function updateThresholdPresetUi() {
  const theta = Number(els.theta.value);
  const tau = Number(els.tau.value);
  const topK = Number(els.fallbackTopK.value);
  const matched = Object.entries(THRESHOLD_PRESETS).find(([, preset]) => (
    Math.abs(theta - preset.theta) < 0.001
    && Math.abs(tau - preset.tau) < 0.001
    && topK === preset.topK
  ));
  document.querySelectorAll("[data-threshold-preset]").forEach((button) => {
    const active = button.dataset.thresholdPreset === matched?.[0];
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  els.thresholdPresetSummary.textContent = matched
    ? `${matched[1].summary} · θ ${theta.toFixed(2)} / τ ${tau.toFixed(2)} / Top-${topK}`
    : `自定义 · θ ${theta.toFixed(2)} / τ ${tau.toFixed(2)} / Top-${topK}`;
  els.thresholdPresetButtonLabel.textContent = matched ? matched[1].summary.split(" · ")[0] : "自定义";
  els.thresholdPresetButtonMeta.textContent = `θ ${theta.toFixed(2)} · τ ${tau.toFixed(2)} · Top-${topK}`;
  els.composerTheta.value = String(theta);
  els.composerThetaValue.textContent = theta.toFixed(2);
  els.composerTau.value = String(tau);
  els.composerTauValue.textContent = tau.toFixed(2);
  els.composerFallbackTopK.value = String(topK);
}

function applyComposerThresholdControls() {
  els.theta.value = els.composerTheta.value;
  els.tau.value = els.composerTau.value;
  els.fallbackTopK.value = els.composerFallbackTopK.value;
  els.thetaValue.textContent = Number(els.theta.value).toFixed(2);
  els.tauValue.textContent = Number(els.tau.value).toFixed(2);
  updateThresholdPresetUi();
}

function applyThresholdPreset(name) {
  const preset = THRESHOLD_PRESETS[name];
  if (!preset) return;
  els.theta.value = String(preset.theta);
  els.tau.value = String(preset.tau);
  els.fallbackTopK.value = String(preset.topK);
  els.thetaValue.textContent = preset.theta.toFixed(2);
  els.tauValue.textContent = preset.tau.toFixed(2);
  updateThresholdPresetUi();
}

function resolveTimePreset(preset) {
  return buildTimeRangeChoices().presets[preset] || "";
}

function loadMyDfas() {
  try {
    const value = JSON.parse(localStorage.getItem(MY_DFA_STORAGE_KEY) || "[]");
    return Array.isArray(value) ? value : [];
  } catch (_error) {
    return [];
  }
}

function loadComposerDfaId() {
  return localStorage.getItem(COMPOSER_DFA_STORAGE_KEY) || "system";
}

function selectedComposerDfa() {
  if (state.composerDfaId === "system") return null;
  return state.myDfas.find((dfa) => dfa.id === state.composerDfaId) || null;
}

function renderComposerDfaOptions() {
  const selected = selectedComposerDfa();
  if (state.composerDfaId !== "system" && !selected) state.composerDfaId = "system";
  els.composerDfaSelect.innerHTML = [
    '<option value="system">系统 DFA · 按垂类自动选择</option>',
    ...state.myDfas.map((dfa) => `<option value="${escapeHtml(dfa.id)}">我的 DFA · ${escapeHtml(dfa.name || "未命名结构")}</option>`)
  ].join("");
  els.composerDfaSelect.value = state.composerDfaId;
  const active = selectedComposerDfa();
  els.composerDfaSourceControl.classList.toggle("is-custom", Boolean(active));
  els.composerDfaSourceLabel.textContent = active ? "我的 DFA" : "系统 DFA";
  els.composerDfaSourceMeta.textContent = active ? active.name || "自定义结构" : "按垂类自动选择";
  els.composerDfaSourceHint.textContent = active
    ? `本次将使用“${active.name || "未命名结构"}”的 ${active.nodes?.length || 0} 个状态和 ${active.edges?.length || 0} 条转移构建 SubDFA。`
    : state.myDfas.length
      ? "当前使用系统训练得到的全局 DFA；也可以从上方切换到自己的结构。"
      : "当前使用系统训练得到的全局 DFA。请先构建或导入“我的 DFA”，再回到这里选择。";
  localStorage.setItem(COMPOSER_DFA_STORAGE_KEY, state.composerDfaId);
}

function persistMyDfas() {
  localStorage.setItem(MY_DFA_STORAGE_KEY, JSON.stringify(state.myDfas));
  renderComposerDfaOptions();
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function loadHistory() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(value) ? value : [];
  } catch (_error) {
    return [];
  }
}

function saveHistory() {
  const persisted = state.history.slice(0, 20).map((item) => ({ ...item }));
  while (persisted.length) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted));
      return;
    } catch (_error) {
      const snapshotIndex = persisted.map((item) => Boolean(item.analysisSnapshot)).lastIndexOf(true);
      if (snapshotIndex >= 0) {
        delete persisted[snapshotIndex].analysisSnapshot;
      } else {
        persisted.pop();
      }
    }
  }
}

function compactAnalysisForHistory(analysis) {
  if (!analysis) return null;
  const snapshot = JSON.parse(JSON.stringify(analysis));
  delete snapshot.steps;
  delete snapshot.raw_subtree;
  delete snapshot.logicrag_source;
  Object.values(snapshot.materials || {}).forEach((material) => {
    delete material.evidence_bindings;
    material.retrieved_facts = (material.retrieved_facts || []).slice(0, 3);
    (material.ifind_bindings || []).forEach((binding) => delete binding.raw_text);
  });
  return snapshot;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function renderHistory() {
  els.historyCount.textContent = String(state.history.length);
  els.historyList.innerHTML = "";
  if (!state.history.length) {
    els.historyList.innerHTML = '<div class="history-empty">生成过的报告会保留在这里。</div>';
    return;
  }

  state.history.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `history-item ${item.id === state.activeHistoryId ? "active" : ""}`;
    const status = item.status === "complete"
      ? `${item.sectionCount || 0} 段`
      : item.status === "blocked"
        ? "证据受阻"
        : item.status === "failed"
          ? "失败"
          : "运行中";
    button.innerHTML = `
      <span class="history-query">${escapeHtml(item.query)}</span>
      <span class="history-meta"><span>${escapeHtml(item.domain || "自动识别")}</span><span>${status} · ${formatTime(item.createdAt)}</span></span>
    `;
    button.addEventListener("click", () => showHistoryItem(item));
    els.historyList.appendChild(button);
  });
}

function renderHistoryFallback(item, message = "") {
  const sections = Array.isArray(item.sections) ? item.sections : [];
  els.currentTurn.classList.add("turn-hidden");
  els.pastMessages.innerHTML = `
    <section class="history-report-view">
      <header class="history-report-header">
        <div>
          <span>Archived Report</span>
          <h2>${escapeHtml(item.domain || "AutoLogic 报告")}</h2>
        </div>
        <span>${sections.length} 个状态片段</span>
      </header>
      <div class="history-report-query">${escapeHtml(item.query)}</div>
      ${message ? `<p class="history-report-notice">${escapeHtml(message)}</p>` : ""}
      <div class="history-report-sections">
        ${sections.length ? sections.map((section, index) => `
          <article class="report-section">
            <h4><span>S${String(index + 1).padStart(2, "0")}</span>${escapeHtml(section.order || index + 1)}. ${escapeHtml(section.label || "报告片段")}</h4>
            <p>${escapeHtml(section.content || "")}</p>
          </article>
        `).join("") : '<div class="report-empty">该历史任务没有保存可恢复的报告内容。</div>'}
      </div>
    </section>
  `;
  window.requestAnimationFrame(() => els.conversation.scrollTo({ top: 0, behavior: "auto" }));
}

function restoreHistoryRun(item, run) {
  const analysis = run?.analysis;
  if (!analysis || !Array.isArray(analysis.report_sections)) {
    renderHistoryFallback(item, "该任务来自早期版本，已展示当时保存的报告正文。完整执行轨迹不可用。");
    return;
  }

  state.activeQuery = item.query;
  state.analysis = analysis;
  state.response = {
    run_id: run.run_id,
    model: run.model,
    ai_used: run.ai_used,
    report_status: analysis.report_status || run.status
  };
  state.events = buildExecutionEvents(analysis);
  state.eventIndex = Math.max(0, state.events.length - 1);
  state.selectedNodeId = null;
  state.expandedReportDfaKey = null;
  state.reportReady = true;
  state.revisions = Array.isArray(item.revisions)
    ? item.revisions.map((revision, index) => ({
        ...revision,
        version: Number(revision.version || index + 2),
        status: "complete",
        sections: Array.isArray(revision.sections) ? revision.sections : []
      }))
    : [];
  setGraphView("construction");
  setGraphExpanded(false);
  els.pastMessages.innerHTML = "";
  els.currentTurn.classList.remove("turn-hidden");
  els.queryEcho.textContent = item.query;
  els.query.value = "";
  autoResizeComposer();
  renderRevisionThread();
  updateComposerMode();
  renderCurrentEvent();
  window.requestAnimationFrame(() => els.conversation.scrollTo({ top: 0, behavior: "auto" }));
}

async function showHistoryItem(item) {
  if (state.busy) return;
  const token = ++state.playToken;
  state.activeHistoryId = item.id;
  state.analysis = null;
  state.response = null;
  state.events = [];
  state.reportReady = false;
  state.revisions = [];
  state.expandedReportDfaKey = null;
  renderRevisionThread();
  updateComposerMode();
  els.currentTurn.classList.add("turn-hidden");
  els.emptyState.classList.add("hidden");
  els.pastMessages.innerHTML = `
    <section class="history-loading" aria-live="polite">
      <img class="history-loading-mark" src="./assets/autologic-studio-mark-light.png?v=20260802a" alt="" aria-hidden="true" />
      <div><strong>正在恢复历史任务</strong><p>加载 SubDFA、执行轨迹、数据证据和完整报告</p></div>
    </section>
  `;
  renderHistory();
  window.requestAnimationFrame(() => els.conversation.scrollTo({ top: 0, behavior: "auto" }));

  if (!item.runId) {
    if (item.analysisSnapshot) {
      restoreHistoryRun(item, { analysis: item.analysisSnapshot, model: "Local snapshot", run_id: null });
    } else {
      renderHistoryFallback(item, "该任务来自早期版本，未保存完整执行轨迹。已展示可用的报告正文。");
    }
    return;
  }

  try {
    const run = await apiGet(`/runs/${encodeURIComponent(item.runId)}`);
    if (token !== state.playToken || state.activeHistoryId !== item.id) return;
    restoreHistoryRun(item, run);
  } catch (error) {
    if (token !== state.playToken || state.activeHistoryId !== item.id) return;
    if (item.analysisSnapshot) {
      restoreHistoryRun(item, { analysis: item.analysisSnapshot, model: "Local snapshot", run_id: item.runId });
    } else {
      renderHistoryFallback(item, `完整运行轨迹加载失败：${error.message}`);
    }
  }
}

function createHistoryRun(query) {
  const item = {
    id: `run-${Date.now()}`,
    query,
    status: "running",
    createdAt: new Date().toISOString(),
    domain: "自动识别",
    sectionCount: 0,
    sections: [],
    revisions: []
  };
  state.history.unshift(item);
  state.activeHistoryId = item.id;
  saveHistory();
  renderHistory();
  return item;
}

function updateHistoryRun(patch) {
  const item = state.history.find((entry) => entry.id === state.activeHistoryId);
  if (!item) return;
  Object.assign(item, patch);
  saveHistory();
  renderHistory();
}

async function apiPost(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `请求失败 (${response.status})`);
  }
  return data;
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `请求失败 (${response.status})`);
  }
  return data;
}

function scheduleApiCheck(delay) {
  window.clearTimeout(state.healthCheckTimer);
  state.healthCheckTimer = window.setTimeout(checkApi, delay);
}

async function checkApi() {
  if (state.healthCheckInFlight) return;
  state.healthCheckInFlight = true;
  let connected = false;
  try {
    const response = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    if (!response.ok) throw new Error("offline");
    const data = await response.json();
    const firstConnection = !state.health;
    state.health = data;
    connected = true;
    const embeddingReady = Boolean(data.embedding?.has_api_key);
    const sources = data.data_sources || {};
    const akshareReady = Boolean(sources.akshare?.installed);
    const tushareReady = Boolean(sources.tushare?.installed && sources.tushare?.configured);
    const ifindReady = Boolean(data.ifind?.has_credentials);
    const demoMode = Boolean(data.demo_mode);
    if (firstConnection) els.remoteEmbedding.checked = embeddingReady;
    const tushareOption = els.dataSource.querySelector('option[value="tushare"]');
    const ifindOption = els.dataSource.querySelector('option[value="ifind"]');
    const demoOption = els.dataSource.querySelector('option[value="demo"]');
    tushareOption.disabled = !tushareReady;
    tushareOption.textContent = tushareReady ? "Tushare" : "Tushare（需配置 Token）";
    ifindOption.disabled = !ifindReady;
    ifindOption.textContent = ifindReady ? "iFinD" : "iFinD（未配置）";
    demoOption.disabled = !demoMode;
    if (!akshareReady && els.dataSource.value === "akshare") els.dataSource.value = "auto";
    if (demoMode && !akshareReady) els.dataSource.value = "demo";
    els.runtimeDot.className = "runtime-dot ready";
    els.runtimeStatus.textContent = "服务已连接";
    if (!state.analysis) els.dfaRuntime.textContent = "等待任务";
    els.modelRuntime.textContent = data.has_api_key ? data.model : "本地回退";
    els.evidenceRuntime.textContent = demoMode && !akshareReady
      ? "离线演示证据"
      : akshareReady ? (tushareReady ? "AkShare + Tushare" : "AkShare") : "未配置";
    const parts = [data.has_api_key ? data.model : "Fallback"];
    parts.push(embeddingReady ? "Semantic" : "Local embedding");
    if (demoMode) parts.push("Demo evidence");
    if (akshareReady) parts.push("AkShare");
    if (tushareReady) parts.push("Tushare");
    if (data.database?.connected) parts.push("DB Ready");
    els.apiStatus.textContent = parts.join(" · ");
    els.apiStatus.classList.remove("error");
  } catch (_error) {
    state.health = null;
    els.runtimeDot.className = "runtime-dot error";
    els.runtimeStatus.textContent = "后端未连接";
    if (!state.analysis) els.dfaRuntime.textContent = "等待连接";
    els.modelRuntime.textContent = "-";
    els.apiStatus.textContent = "API 离线";
    els.apiStatus.classList.add("error");
  } finally {
    state.healthCheckInFlight = false;
    scheduleApiCheck(connected ? 15000 : 2500);
  }
}

function requestPayload(query) {
  const customDfa = selectedComposerDfa();
  return {
    query,
    domain: customDfa?.baseDomain || els.domain.value,
    dfa_source: customDfa ? "user" : "system",
    custom_dfa: customDfa ? cloneJson(customDfa) : null,
    language: state.language,
    tau: Number(els.tau.value),
    theta: Number(els.theta.value),
    fallback_top_k: Number(els.fallbackTopK.value),
    preview_top_k: 8,
    remote_embedding: els.remoteEmbedding.checked,
    data_source: els.dataSource.value,
    use_ifind: els.dataSource.value === "ifind",
    source_learning: els.sourceLearning.checked,
    force_relearn: els.forceRelearn.checked,
    use_ai: true
  };
}

function composeQuery() {
  const request = els.query.value.trim();
  const scope = els.scope.value.trim();
  const timeRange = els.timeRange.value.trim();
  return [
    request,
    scope ? `${state.language === "en" ? "Research scope" : "需求范围"}：${scope}` : "",
    timeRange ? `${state.language === "en" ? "Time range" : "时间范围"}：${timeRange}` : ""
  ].filter(Boolean).join("\n");
}

function canRefineCurrentReport() {
  return Boolean(
    state.reportReady
    && state.analysis?.report_status !== "blocked"
    && state.analysis?.report_sections?.length
  );
}

function updateComposerMode() {
  const revisionMode = canRefineCurrentReport();
  els.composer.classList.toggle("revision-mode", revisionMode);
  els.composerFields.hidden = revisionMode;
  els.query.placeholder = revisionMode
    ? "继续调整报告，例如：缩短结论，并加强风险提示"
    : "输入报告主题、目标读者和关注重点";
  els.modeButton.innerHTML = revisionMode
    ? "<span></span> 继续调整报告"
    : "<span></span> 证据驱动";
  els.composerRun.title = revisionMode ? "发送修改要求" : "发送并生成报告";
  els.composerRun.setAttribute("aria-label", els.composerRun.title);
}

function renderRevisionThread() {
  els.revisionThread.innerHTML = state.revisions.map((revision) => {
    const pending = revision.status === "pending";
    const failed = revision.status === "error";
    const sections = Array.isArray(revision.sections) ? revision.sections : [];
    const hasReport = revision.status === "complete" && sections.length > 0;
    const replyTitle = pending ? "正在调整报告" : failed ? "调整失败" : "报告已更新";
    const replyText = pending
      ? "正在根据你的要求重写报告，并保留当前证据与时间边界。"
      : failed
        ? revision.message
        : revision.message || "已按要求生成完整的新版本，上一版本继续保留。";
    const reportContent = hasReport ? `
      <header class="revision-report-header">
        <div><span>Revised Report · V${Number(revision.version || 2)}</span><h3>完整修订报告</h3></div>
        <div class="revision-report-tools">
          <small>${escapeHtml(revision.model || state.response?.model || "AutoLogic")}</small>
          <button type="button" class="icon-button" data-revision-action="copy" data-revision-id="${escapeHtml(revision.id)}" title="复制 V${Number(revision.version || 2)} 报告" aria-label="复制 V${Number(revision.version || 2)} 报告">⧉</button>
          <button type="button" class="icon-button" data-revision-action="download" data-revision-id="${escapeHtml(revision.id)}" title="下载 V${Number(revision.version || 2)} Markdown 报告" aria-label="下载 V${Number(revision.version || 2)} Markdown 报告">⇩</button>
        </div>
      </header>
      <div class="revision-report-note">${escapeHtml(replyText)}</div>
      <div class="revision-report-body">
        ${sections.map((section, index) => reportSectionHtml(section, index, `v${Number(revision.version || 2)}`)).join("")}
      </div>
    ` : `
      <span>${escapeHtml(replyTitle)}</span>
      <p>${escapeHtml(replyText)}</p>
    `;
    return `
      <section class="revision-exchange">
        <div class="user-message-row revision-user-row">
          <div class="user-bubble"><span>你的调整</span><p>${escapeHtml(revision.instruction)}</p></div>
          <div class="user-avatar" aria-hidden="true">你</div>
        </div>
        <div class="assistant-message-row revision-assistant-row">
          <img class="assistant-avatar" src="./assets/autologic-studio-mark-light.png?v=20260802a" alt="" aria-hidden="true" />
          <article class="revision-reply ${failed ? "error" : pending ? "pending" : "complete"} ${hasReport ? "has-report" : ""}">${reportContent}</article>
        </div>
      </section>
    `;
  }).join("");
}

function latestReportSections() {
  for (let index = state.revisions.length - 1; index >= 0; index -= 1) {
    const revision = state.revisions[index];
    if (revision.status === "complete" && Array.isArray(revision.sections) && revision.sections.length) {
      return revision.sections;
    }
  }
  return state.analysis?.report_sections || [];
}

function submitComposer() {
  if (canRefineCurrentReport()) {
    refineReport();
    return;
  }
  generateReport();
}

function setBusy(busy) {
  state.busy = busy;
  els.composerRun.disabled = busy;
  els.query.disabled = busy;
  els.newChat.disabled = busy;
  els.stageRail.querySelectorAll("button").forEach((button) => { button.disabled = busy; });
  els.eventTimeline.querySelectorAll("button").forEach((button) => { button.disabled = busy; });
}

function startPendingClock() {
  stopPendingClock();
  state.pendingStartedAt = Date.now();
  const customDfa = selectedComposerDfa();
  const phases = [
    customDfa ? `载入我的 DFA · ${customDfa.name || "自定义结构"}` : "载入系统全局 DFA",
    "解析对话并匹配语义状态",
    "抽取本次对话 SubDFA",
    "等待模型返回状态片段"
  ];
  let phaseIndex = 0;
  const update = () => {
    const seconds = Math.max(1, Math.round((Date.now() - state.pendingStartedAt) / 1000));
    els.runSubtitle.textContent = `${phases[phaseIndex % phases.length]} · ${seconds}s`;
    els.apiStatus.textContent = `AutoLogic 运行中 · ${seconds}s`;
    phaseIndex += 1;
  };
  update();
  state.pendingTimer = window.setInterval(update, 1600);
}

function stopPendingClock() {
  if (state.pendingTimer) {
    window.clearInterval(state.pendingTimer);
    state.pendingTimer = null;
  }
}

function startReportGenerationClock() {
  stopReportGenerationClock();
  state.reportGenerationStartedAt = Date.now();
  const update = () => {
    const seconds = Math.max(1, Math.round((Date.now() - state.reportGenerationStartedAt) / 1000));
    els.runTitle.textContent = "正在调用模型生成报告";
    els.runSubtitle.textContent = `报告生成中 · 已等待 ${seconds}s`;
    els.runBadge.textContent = "生成中";
    els.runBadge.className = "run-badge running";
    els.apiStatus.textContent = `正在调用模型生成报告 · ${seconds}s`;
    els.apiStatus.classList.remove("error");
  };
  update();
  state.reportGenerationTimer = window.setInterval(update, 1000);
}

function stopReportGenerationClock() {
  if (state.reportGenerationTimer) {
    window.clearInterval(state.reportGenerationTimer);
    state.reportGenerationTimer = null;
  }
}

function beginRun(query) {
  stopReportGenerationClock();
  state.playToken += 1;
  state.activeQuery = query;
  state.analysis = null;
  state.response = null;
  state.events = [];
  state.eventIndex = 0;
  state.selectedNodeId = null;
  state.reportReady = false;
  state.revisions = [];
  state.expandedReportDfaKey = null;
  setGraphView("construction");
  setGraphExpanded(false);
  createHistoryRun(query);
  setBusy(true);
  els.emptyState.classList.add("hidden");
  els.pastMessages.innerHTML = "";
  els.currentTurn.classList.remove("turn-hidden");
  els.queryEcho.textContent = query;
  els.query.value = "";
  els.scope.value = "";
  els.timeRange.value = "";
  autoResizeComposer();
  renderRevisionThread();
  updateComposerMode();
  els.runTitle.textContent = "正在启动 AutoLogic";
  const customDfa = selectedComposerDfa();
  els.runSubtitle.textContent = customDfa ? `载入我的 DFA · ${customDfa.name || "自定义结构"}` : "载入系统全局 DFA";
  els.runBadge.textContent = "运行中";
  els.runBadge.className = "run-badge running";
  els.skipAnimation.disabled = true;
  renderPending();
  startPendingClock();
  scrollToBottom(false);
}

function renderPending() {
  renderStageRail("dfa", []);
  els.reportProgress.textContent = "等待生成";
  els.reportMeta.innerHTML = "";
  els.reportPreview.className = "report-preview is-loading";
  els.reportPreview.innerHTML = '<div class="loading-lines"><i></i><i></i><i></i><i></i></div>';
  els.traceCounter.textContent = "0 / 0";
  els.decisionIndex.textContent = "S0";
  els.decisionContextLabel.textContent = "当前构建对象";
  els.decisionTitle.textContent = "初始化全局 DFA";
  els.evidenceLabel.textContent = "构建依据";
  els.evidenceText.textContent = "等待解析用户对话";
  els.conditionLabel.textContent = "当前产出";
  els.conditionText.textContent = "等待构建本次 SubDFA";
  els.eventTimeline.innerHTML = "";
  els.runDetailGrid.innerHTML = "";
  drawGraph();
}

function graphData() {
  const analysis = state.analysis;
  if (!analysis) return { nodes: [], edges: [] };
  return {
    nodes: analysis.template?.nodes || [],
    edges: analysis.template?.edges || []
  };
}

function findTransition(sourceId, targetId) {
  const { edges } = graphData();
  return edges.find((edge) => edge.source === sourceId && edge.target === targetId) || null;
}

function conditionForEdge(edge) {
  if (!edge) return "达到终止状态 F";
  if (edge.condition_label) return edge.condition_label;
  if (edge.direct) return "唯一稳定后继，直接转移";
  return edge.label || `${edge.source} → ${edge.target}`;
}

function materialSummary(nodeId) {
  const material = state.analysis?.materials?.[nodeId] || {};
  const bindings = Array.isArray(material.ifind_bindings) ? material.ifind_bindings : [];
  const verified = bindings.filter((binding) => (
    binding?.status === "found" && (binding?.raw_text || binding?.records?.length) && !binding?.error
  ));
  if (!verified.length && state.analysis?.report_status === "blocked") return evidenceProblem(state.analysis);
  const facts = Array.isArray(material.retrieved_facts) ? material.retrieved_facts : [];
  const internalMarkers = [
    "当前阶段展示",
    "State source:",
    "Required materials:",
    "DFA state-level",
    "iFinD enabled but no binding"
  ];
  const usefulFacts = facts.filter((fact) => !internalMarkers.some((marker) => String(fact).includes(marker)));
  if (usefulFacts.length) return usefulFacts.slice(0, 2).join("；");
  const required = Array.isArray(material.required_materials) ? material.required_materials : [];
  return required.length ? `已绑定：${required.slice(0, 5).join("、")}` : "该状态不需要外部证据";
}

const EVIDENCE_PERIOD_KEYS = new Set([
  "date", "trade_date", "month", "quarter", "DATE", "TRADE_DATE", "MONTH", "QUARTER",
  "日期", "月份", "季度", "报告期", "统计时间"
]);

function periodSortKey(value) {
  const text = String(value ?? "").trim();
  const quarter = text.match(/((?:19|20)\d{2})\s*[Qq]([1-4])/);
  if (quarter) return `${quarter[1]}${String(Number(quarter[2]) * 3).padStart(2, "0")}01`;
  const digits = text.replace(/[^0-9]/g, "");
  if (digits.length >= 8) return digits.slice(0, 8);
  if (digits.length === 6) return `${digits}01`;
  return text;
}

function recordPeriod(record) {
  if (!record || typeof record !== "object") return "";
  for (const key of EVIDENCE_PERIOD_KEYS) {
    if (record[key] != null && record[key] !== "") return String(record[key]);
  }
  return "";
}

function latestEvidenceRecord(records) {
  if (!Array.isArray(records) || !records.length) return null;
  return [...records].sort((left, right) => periodSortKey(recordPeriod(left)).localeCompare(periodSortKey(recordPeriod(right)))).at(-1);
}

function evidenceInventory(analysis = state.analysis) {
  const inventory = new Map();
  Object.entries(analysis?.materials || {}).forEach(([nodeId, material]) => {
    const stateLabel = material?.label || nodeId;
    const bindings = Array.isArray(material?.ifind_bindings) ? material.ifind_bindings : [];
    bindings.forEach((binding) => {
      if (binding?.status !== "found" || binding?.error) return;
      const records = Array.isArray(binding.records) ? binding.records : [];
      if (!records.length && !binding.raw_text) return;
      const provider = binding.provider || "Market Data";
      const endpoint = binding.endpoint || binding.indicator || "verified-source";
      const instrument = binding.instrument || binding.state_label || stateLabel;
      const key = `${provider}|${endpoint}|${instrument}`;
      if (!inventory.has(key)) {
        inventory.set(key, {
          provider,
          endpoint,
          instrument,
          records,
          queryDate: binding.date || analysis?.date || "",
          nodeIds: new Set(),
          stateLabels: new Set()
        });
      }
      const item = inventory.get(key);
      if (records.length > item.records.length) item.records = records;
      item.nodeIds.add(nodeId);
      item.stateLabels.add(binding.state_label || stateLabel);
    });
  });
  return [...inventory.values()].map((item) => ({
    ...item,
    nodeIds: [...item.nodeIds],
    stateLabels: [...item.stateLabels]
  }));
}

function sourceInitial(provider) {
  if (/akshare/i.test(provider)) return "AK";
  if (/tushare/i.test(provider)) return "TS";
  if (/ifind/i.test(provider)) return "IF";
  return String(provider).slice(0, 2).toUpperCase();
}

function signalLabel(key) {
  const labels = {
    close: "收盘", open: "开盘", high: "最高", low: "最低", volume: "成交量", vol: "成交量",
    pct_chg: "涨跌幅", change: "变动", oi: "持仓量", gdp_yoy: "GDP同比", cpi_yoy: "CPI同比",
    ppi_yoy: "PPI同比", PMI010000: "制造业PMI", "制造业-指数": "制造业PMI",
    "非制造业-指数": "非制造业PMI", "全国-同比增长": "CPI同比", "全国-环比增长": "CPI环比",
    "当月同比增长": "PPI同比", "国内生产总值-同比增长": "GDP同比"
  };
  return labels[key] || key;
}

function formatSignalValue(key, value) {
  if (typeof value !== "number") return String(value);
  const formatted = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
  return /(yoy|mom|pct|chg|同比|环比|涨跌|增长)/i.test(key) ? `${formatted}%` : formatted;
}

function bindingSignals(binding) {
  const record = latestEvidenceRecord(binding.records);
  if (!record) return "已通过来源校验";
  const preferred = [
    "全国-同比增长", "全国-环比增长", "当月同比增长", "制造业-指数",
    "非制造业-指数", "国内生产总值-同比增长", "gdp_yoy", "cpi_yoy", "ppi_yoy",
    "pct_chg", "close", "change", "volume", "vol", "oi", "high", "low"
  ];
  const usable = Object.entries(record).filter(([key, value]) => (
    value != null && value !== "" && !EVIDENCE_PERIOD_KEYS.has(key) && !/^(id|create_|update_)/i.test(key)
  ));
  usable.sort(([left], [right]) => {
    const leftRank = preferred.indexOf(left);
    const rightRank = preferred.indexOf(right);
    return (leftRank < 0 ? 999 : leftRank) - (rightRank < 0 ? 999 : rightRank);
  });
  return usable.slice(0, 2).map(([key, value]) => `${signalLabel(key)} ${formatSignalValue(key, value)}`).join(" · ") || "记录已验证";
}

function nodeSourceSummary(nodeId, analysis = state.analysis) {
  const items = evidenceInventory(analysis).filter((item) => item.nodeIds.includes(nodeId));
  const providers = [...new Set(items.map((item) => item.provider))];
  const records = items.reduce((sum, item) => sum + Math.max(1, item.records.length), 0);
  if (!items.length) return evidenceProblem(analysis);
  return `来自 ${providers.join(" + ")} · ${items.length} 个数据集 · ${records} 条时点记录`;
}

function renderEvidenceConsole(analysis, event) {
  const order = analysis.execution_order || [];
  const activeIndex = Math.max(0, order.indexOf(event.nodeId));
  const scannedNodes = new Set(order.slice(0, activeIndex + 1));
  const inventory = evidenceInventory(analysis).filter((item) => item.nodeIds.some((nodeId) => scannedNodes.has(nodeId)));
  const runtime = analysis.runtime?.evidence || analysis.runtime?.ifind || {};
  const providerNames = [...new Set([
    ...(runtime.providers_used || []),
    ...inventory.map((item) => item.provider)
  ])];
  const recordCount = inventory.reduce((sum, item) => sum + Math.max(1, item.records.length), 0);
  const latestPeriods = inventory.map((item) => recordPeriod(latestEvidenceRecord(item.records))).filter(Boolean);
  const latestPeriod = latestPeriods.sort((left, right) => periodSortKey(left).localeCompare(periodSortKey(right))).at(-1) || analysis.date;
  const providerDetail = runtime.providers || {};

  els.primaryKicker.textContent = "Evidence Operations";
  els.primaryTitle.textContent = "数据获取与证据血缘";
  els.copyReport.hidden = true;
  els.downloadReport.hidden = true;
  els.reportProgress.textContent = `${activeIndex + 1} / ${order.length} 状态`;
  els.reportMeta.innerHTML = [
    `截止 ${analysis.date}`,
    `${providerNames.length} 个数据源`,
    `${inventory.length} 个数据集`,
    "Point-in-time 已校验"
  ].map((item) => `<span>${escapeHtml(item)}</span>`).join("");

  const providerRows = providerNames.map((provider) => {
    const detail = providerDetail[provider] || {};
    const errorCount = Array.isArray(detail.errors) ? detail.errors.length : 0;
    const status = detail.status === "found" ? (errorCount ? "部分可用" : "已连接") : "待检查";
    const calls = Number(detail.calls || inventory.filter((item) => item.provider === provider).length);
    const found = Number(detail.found || inventory.filter((item) => item.provider === provider).length);
    return `
      <div class="source-health-row">
        <span class="source-logo">${escapeHtml(sourceInitial(provider))}</span>
        <div><strong>${escapeHtml(provider)}</strong><small>${escapeHtml(status)} · ${found}/${calls || found} 接口返回</small></div>
        <span class="source-pulse ${errorCount ? "partial" : ""}">${errorCount ? `${errorCount} 项降级` : "Healthy"}</span>
      </div>`;
  }).join("");

  const datasetRows = inventory.map((binding) => {
    const period = recordPeriod(latestEvidenceRecord(binding.records)) || binding.queryDate || "-";
    const coverage = binding.stateLabels.slice(0, 2).join("、");
    const more = Math.max(0, binding.stateLabels.length - 2);
    return `
      <div class="dataset-row ${binding.nodeIds.includes(event.nodeId) ? "active" : ""}">
        <div class="dataset-source"><span>${escapeHtml(sourceInitial(binding.provider))}</span><strong>${escapeHtml(binding.instrument)}</strong></div>
        <div class="dataset-endpoint"><code>${escapeHtml(binding.endpoint)}</code><small>${escapeHtml(bindingSignals(binding))}</small></div>
        <div class="dataset-period"><strong>${escapeHtml(period)}</strong><small>${Math.max(1, binding.records.length)} 条记录</small></div>
        <div class="dataset-coverage"><strong>${escapeHtml(coverage || "当前状态")}${more ? ` +${more}` : ""}</strong><small>状态绑定</small></div>
        <span class="dataset-status">已验证</span>
      </div>`;
  }).join("");

  els.reportPreview.className = "report-preview evidence-preview";
  els.reportPreview.innerHTML = `
    <div class="evidence-console">
      <div class="evidence-commandbar">
        <div><span>LIVE DATA LINEAGE</span><strong>${escapeHtml(event.nodeId || "S")} · ${escapeHtml(analysis.template?.nodes?.find((node) => node.id === event.nodeId)?.label || "状态证据")}</strong></div>
        <span class="lineage-cutoff">AS OF ${escapeHtml(analysis.date)}</span>
      </div>
      <div class="evidence-stats">
        <div><span>连接数据源</span><strong>${providerNames.length}</strong><small>${escapeHtml(providerNames.join(" + ") || "待配置")}</small></div>
        <div><span>已验证数据集</span><strong>${inventory.length}</strong><small>接口级去重</small></div>
        <div><span>时点记录</span><strong>${recordCount}</strong><small>纳入证据缓存</small></div>
        <div><span>最新数据期</span><strong>${escapeHtml(latestPeriod)}</strong><small>发布日校验通过</small></div>
      </div>
      <section class="source-registry">
        <div class="evidence-section-heading"><div><span>01</span><strong>数据源连接</strong></div><small>Provider health</small></div>
        <div class="source-health-list">${providerRows || '<div class="evidence-empty">未获得可用数据源</div>'}</div>
      </section>
      <section class="dataset-registry">
        <div class="evidence-section-heading"><div><span>02</span><strong>已获取数据</strong></div><small>${inventory.length} datasets · ${recordCount} records</small></div>
        <div class="dataset-head"><span>来源 / 标的</span><span>接口 / 关键信号</span><span>数据期</span><span>覆盖状态</span><span>质量</span></div>
        <div class="dataset-list">${datasetRows || '<div class="evidence-empty">当前状态没有可验证数据</div>'}</div>
      </section>
    </div>`;
}

function buildExecutionEvents(analysis) {
  const sections = analysis.report_sections || [];
  const blocked = analysis.report_status === "blocked";
  const order = analysis.execution_order?.length
    ? analysis.execution_order
    : sections.map((section) => section.node_id);
  const nodes = analysis.template?.nodes || [];
  const edges = analysis.template?.edges || [];
  const ranked = analysis.ranked || [];
  const matched = analysis.matched || [];
  const rawNodes = analysis.raw_subdfa?.node_ids || [];
  const rawEdges = analysis.raw_subdfa?.edge_ids || [];
  const routeNodes = analysis.subdfa?.node_ids || order;
  const routeEdges = analysis.subdfa?.edge_ids || [];
  const removedAlternatives = Math.max(0, rawEdges.length - routeEdges.length);
  const usingUserDfa = analysis.runtime?.dfa_source === "user";
  const userDfaName = analysis.runtime?.user_dfa?.name || "我的 DFA";
  const constraintSummary = [
    analysis.constraints?.domain,
    analysis.constraints?.date,
    analysis.constraints?.report_type
  ].filter(Boolean).join(" · ");
  const events = [
    {
      stage: "dfa",
      type: "dfa",
      graphScope: "full",
      title: usingUserDfa ? "读取我的 DFA" : "读取系统全局 DFA",
      subtitle: usingUserDfa
        ? `使用“${userDfaName}”的 ${nodes.length} 个状态与 ${edges.length} 条自定义转移`
        : `复用 ${nodes.length} 个状态与 ${edges.length} 条稳定转移，本次不重新学习`,
      activeNodes: [],
      activeEdges: [],
      generatedUntil: 0
    },
    {
      stage: "query",
      type: "query",
      graphScope: "full",
      title: "解析当前对话",
      subtitle: constraintSummary || "提取领域、时间范围与报告约束",
      activeNodes: [],
      activeEdges: [],
      generatedUntil: 0
    },
    {
      stage: "match",
      type: "ranked",
      graphScope: "ranked",
      title: "计算 Query 与状态的语义匹配",
      subtitle: `得到 Top-${ranked.length} 候选状态，准备应用阈值 τ=${Number(analysis.tau || 0).toFixed(2)}`,
      activeNodes: ranked.map((item) => item.id),
      activeEdges: [],
      generatedUntil: 0
    },
    {
      stage: "match",
      type: "matched",
      graphScope: "matched",
      title: "筛选命中状态",
      subtitle: `保留 ${matched.length} 个状态；低于阈值时按 fallback top-k 补足`,
      activeNodes: matched.map((item) => item.id),
      activeEdges: [],
      generatedUntil: 0
    },
    {
      stage: "subdfa",
      type: "raw",
      graphScope: "raw",
      title: "合并候选状态路径",
      subtitle: `从初始状态到命中状态形成 ${rawNodes.length} 个状态、${rawEdges.length} 条条件转移的候选子图`,
      activeNodes: rawNodes,
      activeEdges: rawEdges,
      generatedUntil: 0
    },
    {
      stage: "subdfa",
      type: "closure",
      graphScope: "subdfa",
      title: "应用条件约束选择路径",
      subtitle: removedAlternatives
        ? `依据当前对话、历史频率和条件优先级排除 ${removedAlternatives} 条分支`
        : "候选子图已经是一条确定性的可执行路径",
      activeNodes: routeNodes,
      activeEdges: routeEdges,
      generatedUntil: 0
    },
    {
      stage: "subdfa",
      type: "finalized",
      graphScope: "subdfa",
      title: "本次对话 SubDFA 构建完成",
      subtitle: `${routeNodes.length} 个状态 · ${routeEdges.length} 条转移 · ${order.length} 个可执行写作状态`,
      activeNodes: routeNodes,
      activeEdges: routeEdges,
      generatedUntil: 0
    }
  ];

  order.forEach((nodeId, index) => {
    const node = nodes.find((item) => item.id === nodeId);
    const section = sections.find((item) => item.node_id === nodeId) || sections[index];
    const label = node?.label || section?.label || nodeId;
    events.push({
      stage: "evidence",
      type: "evidence",
      graphScope: "execution",
      title: `${blocked ? "检查" : "获取"}数据与证据 · ${label}`,
      subtitle: nodeSourceSummary(nodeId, analysis),
      nodeId,
      activeNodes: [nodeId],
      activeEdges: [],
      generatedUntil: 0
    });
  });

  order.forEach((nodeId, index) => {
    const node = nodes.find((item) => item.id === nodeId);
    const section = sections.find((item) => item.node_id === nodeId) || sections[index];
    const nextId = order[index + 1];
    const edge = nextId ? findTransition(nodeId, nextId) : null;
    const label = node?.label || section?.label || nodeId;
    events.push({
      stage: "assembly",
      type: "generation",
      graphScope: "assembly",
      title: `${blocked ? "跳过" : "生成"}报告片段 · ${label}`,
      subtitle: blocked ? evidenceProblem(analysis) : `引用已验证证据，生成第 ${index + 1} / ${sections.length} 个状态片段`,
      nodeId,
      activeNodes: [nodeId],
      activeEdges: [],
      generatedUntil: index + 1
    });
    if (nextId) {
      events.push({
        stage: "assembly",
        type: "transition",
        graphScope: "assembly",
        title: `组装路径判定 · ${label}`,
        subtitle: conditionForEdge(edge),
        nodeId,
        nextId,
        edgeId: edge?.id || null,
        activeNodes: [nodeId, nextId],
        activeEdges: edge ? [edge.id] : [],
        generatedUntil: index + 1
      });
    }
  });

  events.push({
    stage: "assembly",
    type: "assembly",
    graphScope: "assembly",
    title: blocked ? "报告组装受阻" : "报告组装完成",
    subtitle: blocked ? evidenceProblem(analysis) : `沿已执行路径组装 ${sections.length} 个状态片段`,
    activeNodes: routeNodes,
    activeEdges: routeEdges,
    generatedUntil: sections.length
  });
  return events;
}

function currentEvent() {
  return state.events[state.eventIndex] || null;
}

function evidenceSourceLabel(analysis = state.analysis) {
  const runtime = analysis?.runtime?.evidence || analysis?.runtime?.ifind || {};
  if (runtime.mode === "demo-snapshot") return "内置演示证据";
  const providers = Array.isArray(runtime.providers_used) ? runtime.providers_used : [];
  if (runtime.status === "found" && Number(runtime.summary?.found || 0) > 0) {
    return `${providers.join(" + ") || analysis?.evidence_summary?.provider || "市场数据"} 已验证`;
  }
  if (runtime.status === "error") return "市场数据接口异常";
  if (runtime.status === "unresolved") return "指标未映射";
  if (runtime.status === "no_data") return "市场数据无记录";
  if (runtime.status === "not_configured") return "数据源未配置";
  if (runtime.status === "disabled") return "真实证据未启用";
  return runtime.enabled ? "市场数据待验证" : "无真实证据";
}

function evidenceProblem(analysis = state.analysis) {
  const runtime = analysis?.runtime?.evidence || analysis?.runtime?.ifind || {};
  const error = String(runtime.error || analysis?.evidence_summary?.error || "");
  if (error.includes("code -9")) return "iFinD 登录失败（错误码 -9），当前账号凭据或数据权限不可用。";
  if (error.includes("TUSHARE_TOKEN")) return "尚未配置 Tushare Token，请切换为 AkShare 或在后端环境变量中配置 Token。";
  if (error.includes("No futures CODES resolved")) return "当前领域的状态材料尚未映射到可查询的 iFinD 代码与指标。";
  if (error) return `市场数据接口返回错误：${error}`;
  if (runtime.status === "disabled") return "本次运行没有启用真实数据源，报告生成器没有可引用的市场证据。";
  if (runtime.status === "not_configured") return "所选数据源尚未配置访问凭据。";
  if (runtime.status === "no_data") return "数据源已执行检索，但目标日期和指标没有返回可用记录。";
  return "所选写作状态均未取得可验证的市场数据。";
}

function completedStages(index = state.eventIndex) {
  const order = ["dfa", "query", "match", "subdfa", "evidence", "assembly"];
  const current = state.events[index]?.stage;
  const currentIndex = Math.max(0, order.indexOf(current));
  return order.slice(0, currentIndex);
}

function renderStageRail(activeStage, doneStages) {
  els.stageRail.querySelectorAll("button").forEach((button) => {
    const stage = button.dataset.stage;
    button.classList.toggle("active", stage === activeStage);
    button.classList.toggle("done", doneStages.includes(stage));
  });
}

function renderCurrentEvent() {
  const event = currentEvent();
  if (!event) return;
  const finalEvent = state.eventIndex === state.events.length - 1;
  const blocked = finalEvent && state.analysis?.report_status === "blocked";
  const reviewing = !state.busy && !finalEvent;
  els.runTitle.textContent = event.title;
  els.runSubtitle.textContent = event.subtitle;
  els.runBadge.textContent = blocked ? "证据受阻" : finalEvent ? "已完成" : reviewing ? "回看" : "执行中";
  els.runBadge.className = `run-badge ${blocked ? "error" : finalEvent ? "complete" : reviewing ? "" : "running"}`;
  els.traceCounter.textContent = `${state.eventIndex + 1} / ${state.events.length}`;
  els.skipAnimation.disabled = finalEvent;
  renderStageRail(event.stage, completedStages());
  renderReport();
  renderDecision();
  renderTimeline();
  renderRuntimeDetail();
  drawGraph();
}

function templateNodeForReportSection(section) {
  const nodes = state.analysis?.template?.nodes || [];
  const nodeId = String(section?.node_id || section?.nodeId || "");
  return nodes.find((node) => node.id === nodeId)
    || nodes.find((node) => node.label === section?.label)
    || null;
}

function reportInternalDfaHtml(node) {
  const internalDfa = node?.internal_dfa || {};
  const states = Array.isArray(internalDfa.states) ? internalDfa.states : [];
  const transitions = Array.isArray(internalDfa.transitions) ? internalDfa.transitions : [];
  const patterns = Array.isArray(internalDfa.sequence_patterns) ? internalDfa.sequence_patterns : [];
  if (!states.length) return "";
  const groups = Object.keys(INTERNAL_DFA_STAGE_LABELS)
    .map((stage) => ({ stage, states: states.filter((item) => item.stage === stage) }))
    .filter((group) => group.states.length);
  return `
    <section class="report-internal-dfa" aria-label="${escapeHtml(node.label || node.id)}内部 DFA">
      <header>
        <div><span>Paragraph Automaton</span><strong>${escapeHtml(node.label || node.id)} · 内部 DFA</strong></div>
        <small>${states.length} 个状态 · ${transitions.length} 条转移${internalDfa.source_case_files ? ` · ${Number(internalDfa.source_case_files).toLocaleString()} 个 Case` : ""}</small>
      </header>
      <div class="report-dfa-flow" aria-label="内部 DFA 阶段顺序">
        ${groups.map((group, index) => `
          <span><b>${escapeHtml(INTERNAL_DFA_STAGE_LABELS[group.stage])}</b><small>${group.states.length}</small></span>
          ${index < groups.length - 1 ? '<i aria-hidden="true">→</i>' : ""}
        `).join("")}
      </div>
      <div class="report-dfa-state-groups">
        ${groups.map((group) => `
          <section data-stage="${escapeHtml(group.stage)}">
            <header><strong>${escapeHtml(INTERNAL_DFA_STAGE_LABELS[group.stage])}</strong><small>${group.states.length} states</small></header>
            <div>${group.states.map((item) => `
              <article>
                <div><span>${escapeHtml(item.id)}</span>${item.support_documents ? `<small>${Number(item.support_documents).toLocaleString()} 篇支持</small>` : ""}</div>
                <strong>${escapeHtml(item.label || item.id)}</strong>
                <p>${escapeHtml(item.detail || "")}</p>
              </article>
            `).join("")}</div>
          </section>
        `).join("")}
      </div>
      <details class="report-dfa-transitions">
        <summary>查看全部 ${transitions.length} 条内部转移</summary>
        <div>${transitions.map((item) => `
          <article><strong>${escapeHtml(item.source)} → ${escapeHtml(item.target)}</strong><span>${escapeHtml(item.condition || "TRUE")}</span>${item.support_documents ? `<small>${Number(item.support_documents).toLocaleString()} 篇关联支持</small>` : ""}</article>
        `).join("")}</div>
      </details>
      ${patterns.length ? `
        <details class="report-dfa-patterns">
          <summary>查看 ${patterns.length} 种关联训练序列</summary>
          <div>${patterns.map((pattern, index) => `
            <article><span>P${String(index + 1).padStart(2, "0")}</span><strong>${(pattern.states || []).map((item) => escapeHtml(item)).join(" → ")}</strong><small>${Number(pattern.documents || 0).toLocaleString()} 篇 · ${(Number(pattern.frequency || 0) * 100).toFixed(2)}%</small></article>
          `).join("")}</div>
        </details>
      ` : ""}
    </section>
  `;
}

function reportSectionHtml(section, index, versionKey = "v1") {
  const node = templateNodeForReportSection(section);
  const nodeId = node?.id || String(section?.node_id || section?.nodeId || "");
  const dfaKey = `${versionKey}:${nodeId || index}`;
  const hasInternalDfa = Boolean(node?.internal_dfa?.states?.length);
  const expanded = hasInternalDfa && state.expandedReportDfaKey === dfaKey;
  return `
    <article class="report-section${hasInternalDfa ? " has-internal-dfa" : ""}${expanded ? " dfa-expanded" : ""}">
      <div class="report-section-main"${hasInternalDfa ? ` role="button" tabindex="0" data-report-dfa-node="${escapeHtml(nodeId)}" data-report-dfa-key="${escapeHtml(dfaKey)}" aria-expanded="${expanded}"` : ""}>
        <h4>
          <span>S${String(index + 1).padStart(2, "0")}</span>
          ${escapeHtml(section.order || index + 1)}. ${escapeHtml(section.label || "报告片段")}
          ${hasInternalDfa ? `<small class="report-dfa-hint">◇ ${expanded ? "收起内部 DFA" : "查看内部 DFA"}</small>` : ""}
        </h4>
        <p>${escapeHtml(section.content || "")}</p>
      </div>
      ${expanded ? reportInternalDfaHtml(node) : ""}
    </article>
  `;
}

function toggleReportInternalDfa(target) {
  const key = target?.dataset?.reportDfaKey;
  if (!key) return;
  state.expandedReportDfaKey = state.expandedReportDfaKey === key ? null : key;
  renderReport();
  renderRevisionThread();
}

function constructionStepDetail(analysis, event) {
  const labelById = Object.fromEntries((analysis.template?.nodes || []).map((node) => [node.id, node.label || node.id]));
  const labels = (event.activeNodes || []).map((id) => labelById[id] || id);
  if (event.type === "dfa") {
    return {
      metric: `${analysis.template?.nodes?.length || 0} 个状态 · ${analysis.template?.edges?.length || 0} 条转移`,
      chips: [analysis.runtime?.dfa_source === "user" ? analysis.runtime?.user_dfa?.name || "我的 DFA" : "系统全局 DFA"]
    };
  }
  if (event.type === "query") {
    return {
      metric: `${analysis.domain || "自动识别"} · ${analysis.date || "未指定时间"}`,
      chips: [analysis.constraints?.report_type || "报告任务", analysis.runtime?.dfa_source === "user" ? "用户结构" : "系统结构"]
    };
  }
  if (event.type === "ranked") {
    const ranked = (analysis.ranked || []).slice(0, 8);
    return {
      metric: `${ranked.length} 个候选状态`,
      chips: ranked.map((item) => `${item.label} ${Number(item.score || item.similarity || 0).toFixed(2)}`)
    };
  }
  if (event.type === "matched") {
    return { metric: `${labels.length} 个状态通过筛选`, chips: labels };
  }
  if (event.type === "raw") {
    return { metric: `${event.activeNodes?.length || 0} 个状态 · ${event.activeEdges?.length || 0} 条候选转移`, chips: labels };
  }
  if (event.type === "closure") {
    return { metric: `${event.activeNodes?.length || 0} 个状态 · ${event.activeEdges?.length || 0} 条可执行转移`, chips: labels };
  }
  return {
    metric: `${analysis.execution_order?.length || 0} 个写作状态已确定`,
    chips: (analysis.execution_order || []).map((id) => labelById[id] || id)
  };
}

function renderSubDfaConstruction(analysis, event) {
  const constructionEvents = state.events.filter((item) => ["dfa", "query", "match", "subdfa"].includes(item.stage));
  const currentIndex = Math.max(0, constructionEvents.indexOf(event));
  const detail = constructionStepDetail(analysis, event);
  const ready = event.type === "finalized";
  els.primaryKicker.textContent = "SubDFA Construction";
  els.primaryTitle.textContent = ready ? "本次 SubDFA 已构建完成" : "SubDFA 构建过程";
  els.copyReport.hidden = true;
  els.downloadReport.hidden = true;
  els.reportProgress.textContent = `步骤 ${currentIndex + 1} / ${constructionEvents.length}`;
  els.reportMeta.innerHTML = [
    analysis.runtime?.dfa_source === "user" ? `我的 DFA · ${analysis.runtime?.user_dfa?.name || "自定义结构"}` : "系统全局 DFA",
    `τ ${Number(analysis.tau || 0).toFixed(2)}`,
    `Top-${Number(analysis.runtime?.fallback_top_k || 0)}`
  ].map((item) => `<span>${escapeHtml(item)}</span>`).join("");
  els.reportPreview.className = "report-preview construction-preview";
  els.reportPreview.innerHTML = `
    <section class="subdfa-construction${ready ? " is-ready" : ""}">
      <div class="construction-stepper" aria-label="SubDFA 构建步骤">
        ${constructionEvents.map((item, index) => `
          <article class="${index < currentIndex ? "done" : index === currentIndex ? "active" : "pending"}">
            <span>${index < currentIndex ? "✓" : String(index + 1).padStart(2, "0")}</span>
            <div><strong>${escapeHtml(item.title)}</strong><small>${index < currentIndex ? "已完成" : index === currentIndex ? "正在执行" : "等待执行"}</small></div>
          </article>
        `).join("")}
      </div>
      <div class="construction-focus">
        <header><span>${ready ? "SUBDFA READY" : "CURRENT STEP"}</span><strong>${escapeHtml(event.title)}</strong></header>
        <p>${escapeHtml(event.subtitle || "")}</p>
        <div class="construction-metric">${escapeHtml(detail.metric)}</div>
        <div class="construction-chips">${detail.chips.length ? detail.chips.map((item) => `<span>${escapeHtml(item)}</span>`).join("") : "<span>等待状态输出</span>"}</div>
      </div>
      <footer>${ready ? "结构已锁定，下一步开始逐状态检索证据；完整正文将在全部状态生成后统一展示。" : "当前只展示结构推导，不提前显示报告正文。"}</footer>
    </section>`;
}

function renderArticleAssembly(analysis, event) {
  const sections = analysis.report_sections || [];
  const completed = Math.min(Number(event.generatedUntil || 0), sections.length);
  els.primaryKicker.textContent = "Report Assembly";
  els.primaryTitle.textContent = "报告生成过程";
  els.copyReport.hidden = true;
  els.downloadReport.hidden = true;
  els.reportProgress.textContent = `${completed} / ${sections.length} 个状态片段`;
  els.reportMeta.innerHTML = [analysis.domain, analysis.date, "SubDFA 已锁定", evidenceSourceLabel(analysis)]
    .filter(Boolean).map((item) => `<span>${escapeHtml(item)}</span>`).join("");
  els.reportPreview.className = "report-preview assembly-preview";
  els.reportPreview.innerHTML = `
    <section class="article-assembly-process">
      <header><span>COMPOSE FROM SUBDFA</span><strong>${escapeHtml(event.title)}</strong><p>${escapeHtml(event.subtitle || "")}</p></header>
      <div>
        ${sections.map((section, index) => {
          const done = index < completed;
          const active = event.nodeId === section.node_id;
          return `<article class="${done ? "done" : active ? "active" : "pending"}"><span>${done ? "✓" : String(index + 1).padStart(2, "0")}</span><div><strong>${escapeHtml(section.label || `状态 ${index + 1}`)}</strong><small>${done ? "状态片段已生成" : active ? "正在生成" : "等待前序状态"}</small></div></article>`;
        }).join("")}
      </div>
      <footer>所有状态片段完成并按 SubDFA 顺序组装后，再统一显示最终文章。</footer>
    </section>`;
}

function renderReport() {
  const analysis = state.analysis;
  if (!analysis) return;
  const event = currentEvent();
  if (["dfa", "query", "match", "subdfa"].includes(event?.stage)) {
    renderSubDfaConstruction(analysis, event);
    return;
  }
  if (event?.stage === "evidence") {
    renderEvidenceConsole(analysis, event);
    return;
  }
  if (event?.stage === "assembly" && event.type !== "assembly") {
    renderArticleAssembly(analysis, event);
    return;
  }
  const sections = analysis.report_sections || [];
  const generatedUntil = event?.type === "assembly" ? sections.length : 0;
  const hasCompleteRevision = state.revisions.some((revision) => revision.status === "complete");
  els.primaryKicker.textContent = hasCompleteRevision ? "Original Report · V1" : "Primary Output";
  els.primaryTitle.textContent = hasCompleteRevision ? "原始报告（已保留）" : "生成报告";
  els.copyReport.hidden = false;
  els.downloadReport.hidden = false;
  els.reportMeta.innerHTML = [
    analysis.domain,
    analysis.date,
    `${sections.length} 个写作状态`,
    evidenceSourceLabel(analysis)
  ].filter(Boolean).map((item) => `<span>${escapeHtml(item)}</span>`).join("");
  els.reportProgress.textContent = generatedUntil >= sections.length && sections.length ? "完整报告" : `${generatedUntil} / ${sections.length}`;

  if (generatedUntil === 0) {
    els.reportPreview.className = "report-preview";
    els.reportPreview.innerHTML = '<div class="report-empty">SubDFA 已就绪，正在准备报告状态片段。</div>';
    return;
  }

  if (analysis.report_status === "blocked") {
    const labels = sections.map((section) => section.label).filter(Boolean);
    els.reportProgress.textContent = "未生成";
    els.reportPreview.className = "report-preview";
    els.reportPreview.innerHTML = `
      <section class="report-blocked" role="alert">
        <span class="report-blocked-code">EVIDENCE BLOCKED</span>
        <h4>报告正文未生成</h4>
        <p>${escapeHtml(evidenceProblem(analysis))}</p>
        <dl>
          <div><dt>可验证证据</dt><dd>${Number(analysis.evidence_summary?.found_bindings || 0)} 条</dd></div>
          <div><dt>计划章节</dt><dd>${sections.length} 个</dd></div>
        </dl>
        <div class="report-blocked-sections">${labels.map((label) => `<span>${escapeHtml(label)}</span>`).join("")}</div>
      </section>`;
    return;
  }

  els.reportPreview.className = "report-preview";
  els.reportPreview.innerHTML = sections.slice(0, generatedUntil).map((section, index) => reportSectionHtml(section, index, "v1")).join("");
}

function markdownForSections(sections, { title, version = "", instruction = "" } = {}) {
  if (!Array.isArray(sections) || !sections.length) return "";
  const versionLabel = version ? ` · V${version}` : "";
  const lines = [
    `# ${title || `${state.analysis?.domain || "AutoLogic"}研究报告`}${versionLabel}`,
    "",
    `- 生成日期：${state.analysis?.date || new Date().toISOString().slice(0, 10)}`,
    `- 报告需求：${state.analysis?.query || state.activeQuery}`
  ];
  if (instruction) lines.push(`- 调整要求：${instruction}`);
  lines.push("", "---", "");
  sections.forEach((section, index) => {
    lines.push(`## ${section.order || index + 1}. ${section.label || "报告章节"}`, "", section.content || "", "");
  });
  return lines.join("\n");
}

function reportMarkdown() {
  const analysis = state.analysis;
  const sections = analysis?.report_sections || [];
  if (!analysis) return "";
  return markdownForSections(sections);
}

function downloadMarkdown(markdown, filename) {
  if (!markdown) return;
  const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadReport() {
  const markdown = reportMarkdown();
  if (!markdown) return;
  const slug = String(state.analysis?.domain || "report").replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]+/g, "-");
  const date = state.analysis?.date || new Date().toISOString().slice(0, 10);
  downloadMarkdown(markdown, `${slug}-${date}.md`);
}

function revisionMarkdown(revision) {
  return markdownForSections(revision.sections, {
    title: `${state.analysis?.domain || "AutoLogic"}修订报告`,
    version: Number(revision.version || 2),
    instruction: revision.instruction || ""
  });
}

function downloadRevisionReport(revision) {
  const markdown = revisionMarkdown(revision);
  if (!markdown) return;
  const slug = String(state.analysis?.domain || "report").replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]+/g, "-");
  const date = state.analysis?.date || new Date().toISOString().slice(0, 10);
  downloadMarkdown(markdown, `${slug}-${date}-V${Number(revision.version || 2)}.md`);
}

async function refineReport() {
  const instruction = els.query.value.trim();
  if (!instruction || state.busy || !state.analysis?.report_sections?.length) return;
  const revision = {
    id: `revision-${Date.now()}`,
    version: state.revisions.filter((item) => item.status === "complete").length + 2,
    instruction,
    status: "pending",
    message: "",
    sections: []
  };
  state.revisions.push(revision);
  els.query.value = "";
  autoResizeComposer();
  setBusy(true);
  renderRevisionThread();
  els.apiStatus.textContent = "正在按要求调整报告";
  els.apiStatus.classList.remove("error");
  scrollToBottom();
  try {
    const data = await apiPost("/reports/refine", {
      instruction,
      query: state.analysis.query || state.activeQuery,
      date: state.analysis.date,
      sections: latestReportSections(),
      materials: state.analysis.materials || {},
      language: state.language
    });
    if (!Array.isArray(data.report_sections) || data.report_sections.length === 0) {
      throw new Error("模型未返回完整报告，请重新发送调整要求");
    }
    state.response = { ...state.response, ai_used: data.ai_used, model: data.model };
    revision.status = "complete";
    revision.sections = data.report_sections;
    revision.model = data.model;
    revision.message = data.ai_used
      ? `已使用 ${data.model || "当前模型"} 生成完整 V${revision.version}，V${revision.version - 1} 继续保留。`
      : `已生成完整 V${revision.version}，V${revision.version - 1} 继续保留。`;
    renderReport();
    els.reportProgress.textContent = "原始版本 · 已保留";
    els.apiStatus.textContent = data.ai_used ? `调整完成 · ${data.model}` : "调整完成 · 本地处理";
    updateHistoryRun({
      sections: state.analysis.report_sections,
      analysisSnapshot: compactAnalysisForHistory(state.analysis),
      revisions: state.revisions.filter((item) => item.status === "complete").map((item) => ({
        id: item.id,
        version: item.version,
        instruction: item.instruction,
        status: item.status,
        message: item.message,
        model: item.model,
        sections: item.sections
      }))
    });
  } catch (error) {
    revision.status = "error";
    revision.message = error.message;
    els.reportProgress.textContent = `重写失败：${error.message}`;
    els.apiStatus.textContent = "调整失败";
    els.apiStatus.classList.add("error");
  } finally {
    setBusy(false);
    updateComposerMode();
    renderRevisionThread();
    scrollToBottom();
  }
}

function userDfaFromTemplate(template, domain) {
  const now = new Date().toISOString();
  return {
    id: `user-dfa-${Date.now()}`,
    name: `${DFA_DOMAIN_LABELS[domain] || domain} · 我的 DFA`,
    baseDomain: domain,
    createdAt: now,
    updatedAt: now,
    nodes: (template?.nodes || []).map((node) => ({
      id: String(node.id),
      label: String(node.label || node.id),
      type: String(node.type || "leaf"),
      level: Number(node.level || 0),
      parent: node.parent == null ? null : String(node.parent),
      children: Array.isArray(node.children) ? node.children.map(String) : [],
      guideline: String(node.guideline || ""),
      materials: Array.isArray(node.materials) ? node.materials.map(String) : [],
      support_documents: Number(node.support_documents || 0),
      frequency: node.frequency == null ? null : Number(node.frequency)
    })),
    edges: (template?.edges || []).map((edge, index) => ({
      id: String(edge.id || `E${index + 1}`),
      source: String(edge.source || ""),
      target: String(edge.target || ""),
      condition_label: String(edge.condition_label || edge.label || "稳定转移"),
      predicate: String(edge.predicate || (edge.direct ? "TRUE" : "user.condition")),
      support_documents: Number(edge.support_documents || 0),
      origin: "system"
    }))
  };
}

function markMyDfaDirty() {
  state.myDfaDirty = true;
  els.saveMyDfa.textContent = "保存结构 · 未保存";
  els.myDfaSummary.textContent = "正在编辑用户副本；修改尚未保存到本机。";
}

function renderMyDfaLibrary() {
  els.myDfaCount.textContent = String(state.myDfas.length);
  els.myDfaList.innerHTML = state.myDfas.length ? state.myDfas.map((dfa) => `
    <button type="button" data-my-dfa-id="${escapeHtml(dfa.id)}" class="${dfa.id === state.activeMyDfaId ? "active" : ""}">
      <strong>${escapeHtml(dfa.name || "未命名 DFA")}</strong>
      <span>${escapeHtml(DFA_DOMAIN_LABELS[dfa.baseDomain] || dfa.baseDomain || "自定义")} · ${(dfa.nodes || []).length} 状态 · ${(dfa.edges || []).length} 转移</span>
    </button>
  `).join("") : '<div class="my-dfa-list-empty">尚未导入垂类结构</div>';
}

function selectMyDfa(id) {
  const saved = state.myDfas.find((dfa) => dfa.id === id);
  if (!saved) return;
  state.activeMyDfaId = id;
  state.myDfaDraft = cloneJson(saved);
  state.myDfaSelectedNodeId = state.myDfaDraft.nodes.find((node) => node.type !== "root" && Number(node.level || 0) > 0)?.id
    || state.myDfaDraft.nodes[0]?.id
    || null;
  state.myDfaDirty = false;
  renderMyDfaStudio();
}

function myDfaPositions(nodes) {
  const root = nodes.find((node) => node.type === "root" || Number(node.level || 0) === 0) || nodes[0];
  const others = nodes.filter((node) => node !== root);
  const rows = Math.min(3, Math.max(1, Math.ceil(Math.sqrt(others.length || 1))));
  const positions = {};
  if (root) positions[root.id] = { x: 110, y: 280 };
  others.forEach((node, index) => {
    const column = Math.floor(index / rows);
    const row = index % rows;
    const yGap = rows === 1 ? 0 : 340 / (rows - 1);
    positions[node.id] = { x: 360 + column * 250, y: rows === 1 ? 280 : 110 + row * yGap };
  });
  return positions;
}

function drawMyDfa() {
  const svg = els.myDfaSvg;
  const draft = state.myDfaDraft;
  svg.innerHTML = "";
  if (!draft?.nodes?.length) return;
  const positions = myDfaPositions(draft.nodes);
  const maxX = Math.max(980, ...Object.values(positions).map((point) => point.x + 130));
  svg.setAttribute("viewBox", `0 0 ${maxX} 560`);
  svg.style.minWidth = `${maxX}px`;
  draft.edges.forEach((edge) => {
    const source = positions[edge.source];
    const target = positions[edge.target];
    if (!source || !target) return;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", source.x + 84);
    line.setAttribute("y1", source.y);
    line.setAttribute("x2", target.x - 84);
    line.setAttribute("y2", target.y);
    line.setAttribute("class", "my-dfa-edge");
    svg.appendChild(line);
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", (source.x + target.x) / 2);
    label.setAttribute("y", (source.y + target.y) / 2 - 7);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "my-dfa-edge-label");
    label.textContent = String(edge.condition_label || "稳定转移").slice(0, 18);
    svg.appendChild(label);
  });
  draft.nodes.forEach((node) => {
    const point = positions[node.id];
    if (!point) return;
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", `my-dfa-node${node.id === state.myDfaSelectedNodeId ? " active" : ""}`);
    group.setAttribute("role", "button");
    group.setAttribute("tabindex", "0");
    group.setAttribute("aria-label", `编辑 ${node.label || node.id} 节点`);
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", point.x - 84);
    rect.setAttribute("y", point.y - 34);
    rect.setAttribute("width", "168");
    rect.setAttribute("height", "68");
    rect.setAttribute("rx", "7");
    const id = document.createElementNS("http://www.w3.org/2000/svg", "text");
    id.setAttribute("x", point.x - 68);
    id.setAttribute("y", point.y - 11);
    id.setAttribute("class", "my-dfa-node-id");
    id.textContent = node.id;
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", point.x - 68);
    label.setAttribute("y", point.y + 8);
    label.setAttribute("class", "my-dfa-node-label");
    label.textContent = String(node.label || node.id).slice(0, 17);
    const meta = document.createElementNS("http://www.w3.org/2000/svg", "text");
    meta.setAttribute("x", point.x - 68);
    meta.setAttribute("y", point.y + 23);
    meta.setAttribute("class", "my-dfa-node-meta");
    meta.textContent = node.type === "root" ? "入口状态" : `${(node.materials || []).length} 项材料规则`;
    const selectNode = () => {
      state.myDfaSelectedNodeId = node.id;
      renderMyDfaStudio();
    };
    group.addEventListener("click", selectNode);
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode();
      }
    });
    group.append(rect, id, label, meta);
    svg.appendChild(group);
  });
}

function renderMyDfaNodeEditor() {
  const draft = state.myDfaDraft;
  const node = draft?.nodes?.find((item) => item.id === state.myDfaSelectedNodeId);
  if (!node) {
    els.myDfaNodeEditor.innerHTML = '<div class="my-dfa-inspector-empty">点击结构图中的节点开始编辑</div>';
    return;
  }
  const root = node.type === "root" || Number(node.level || 0) === 0;
  els.myDfaNodeEditor.innerHTML = `
    <header><div><span>${escapeHtml(node.id)}</span><strong>${escapeHtml(node.label || node.id)}</strong></div><small>${root ? "入口节点" : "段落节点"}</small></header>
    <label><span>节点名称</span><input data-my-dfa-node-field="label" type="text" maxlength="60" value="${escapeHtml(node.label || "")}" /></label>
    <label><span>写作规则</span><textarea data-my-dfa-node-field="guideline" rows="5" placeholder="描述该段落应该如何生成">${escapeHtml(node.guideline || "")}</textarea></label>
    <label><span>材料要求 <small>每行一项</small></span><textarea data-my-dfa-node-field="materials" rows="6" placeholder="价格走势 (market.price)">${escapeHtml((node.materials || []).join("\n"))}</textarea></label>
    <button data-my-dfa-node-action="delete" type="button" ${root ? "disabled" : ""}>删除该段落节点</button>
  `;
}

function renderMyDfaEdges() {
  const draft = state.myDfaDraft;
  if (!draft) return;
  const labelById = Object.fromEntries(draft.nodes.map((node) => [node.id, node.label || node.id]));
  els.myDfaEdgeCount.textContent = `${draft.edges.length} 条`;
  els.myDfaEdgeList.innerHTML = draft.edges.length ? draft.edges.map((edge) => `
    <article>
      <div><strong>${escapeHtml(edge.source)} → ${escapeHtml(edge.target)}</strong><span>${escapeHtml(labelById[edge.source] || edge.source)} → ${escapeHtml(labelById[edge.target] || edge.target)}</span></div>
      <p>${escapeHtml(edge.condition_label || "稳定转移")}</p>
      <button type="button" data-my-dfa-edge-remove="${escapeHtml(edge.id)}" title="删除这条转移" aria-label="删除 ${escapeHtml(edge.source)} 到 ${escapeHtml(edge.target)} 的转移">×</button>
    </article>
  `).join("") : '<div class="my-dfa-edge-empty">暂无状态转移</div>';
  const options = draft.nodes.map((node) => `<option value="${escapeHtml(node.id)}">${escapeHtml(node.id)} · ${escapeHtml(node.label || node.id)}</option>`).join("");
  const previousSource = els.myDfaEdgeSource.value;
  const previousTarget = els.myDfaEdgeTarget.value;
  els.myDfaEdgeSource.innerHTML = options;
  els.myDfaEdgeTarget.innerHTML = options;
  if (draft.nodes.some((node) => node.id === previousSource)) els.myDfaEdgeSource.value = previousSource;
  if (draft.nodes.some((node) => node.id === previousTarget)) els.myDfaEdgeTarget.value = previousTarget;
  if (!previousTarget && draft.nodes.length > 1) els.myDfaEdgeTarget.value = draft.nodes[1].id;
}

function renderMyDfaStudio() {
  renderMyDfaLibrary();
  const draft = state.myDfaDraft;
  els.myDfaEmpty.hidden = Boolean(draft);
  els.myDfaEditor.hidden = !draft;
  if (!draft) {
    els.myDfaSummary.textContent = "从系统垂类导入副本，自主调整段落状态与转移结构。";
    return;
  }
  if (document.activeElement !== els.myDfaName) els.myDfaName.value = draft.name || "";
  els.saveMyDfa.textContent = state.myDfaDirty ? "保存结构 · 未保存" : "保存结构";
  els.myDfaSummary.textContent = `${DFA_DOMAIN_LABELS[draft.baseDomain] || draft.baseDomain} · 用户副本 · ${draft.nodes.length} 个状态 · ${draft.edges.length} 条转移${state.myDfaDirty ? " · 有未保存修改" : ""}`;
  els.myDfaMetrics.innerHTML = [
    ["基础垂类", DFA_DOMAIN_LABELS[draft.baseDomain] || draft.baseDomain],
    ["段落状态", `${draft.nodes.filter((node) => node.type !== "root").length} 个`],
    ["状态转移", `${draft.edges.length} 条`],
    ["材料规则", `${draft.nodes.reduce((sum, node) => sum + (node.materials || []).length, 0)} 项`]
  ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
  drawMyDfa();
  renderMyDfaNodeEditor();
  renderMyDfaEdges();
}

async function importMyDfaDomain() {
  const domain = els.myDfaDomain.value;
  els.importMyDfa.disabled = true;
  els.importMyDfa.textContent = "正在导入…";
  els.myDfaSummary.textContent = `正在读取${DFA_DOMAIN_LABELS[domain] || domain}系统模板。`;
  try {
    const preview = await apiPost("/pipeline/preview", {
      query: "用户 DFA 工作区垂类模板导入",
      domain,
      data_source: "none",
      use_ai: false,
      source_learning: false,
      force_relearn: false,
      remote_embedding: false
    });
    const dfa = userDfaFromTemplate(preview.analysis?.template || {}, domain);
    state.myDfas.unshift(dfa);
    persistMyDfas();
    selectMyDfa(dfa.id);
  } catch (error) {
    els.myDfaSummary.textContent = `导入失败：${error.message}`;
  } finally {
    els.importMyDfa.disabled = false;
    els.importMyDfa.textContent = "导入为我的 DFA";
  }
}

function saveMyDfaDraft() {
  const draft = state.myDfaDraft;
  if (!draft) return;
  draft.name = els.myDfaName.value.trim() || `${DFA_DOMAIN_LABELS[draft.baseDomain] || draft.baseDomain} · 我的 DFA`;
  draft.updatedAt = new Date().toISOString();
  const index = state.myDfas.findIndex((dfa) => dfa.id === draft.id);
  if (index >= 0) state.myDfas[index] = cloneJson(draft);
  else state.myDfas.unshift(cloneJson(draft));
  state.myDfaDirty = false;
  persistMyDfas();
  renderMyDfaStudio();
}

function addMyDfaNode() {
  const draft = state.myDfaDraft;
  if (!draft) return;
  const numericIds = draft.nodes.map((node) => Number(String(node.id).replace(/\D/g, ""))).filter(Number.isFinite);
  let number = Math.max(0, ...numericIds) + 1;
  let nodeId = `S${number}`;
  while (draft.nodes.some((node) => node.id === nodeId)) {
    number += 1;
    nodeId = `S${number}`;
  }
  const root = draft.nodes.find((node) => node.type === "root" || Number(node.level || 0) === 0);
  draft.nodes.push({
    id: nodeId,
    label: "新段落",
    type: "leaf",
    level: 1,
    parent: root?.id || null,
    children: [],
    guideline: "描述该段落的写作目标、证据要求和输出边界。",
    materials: [],
    support_documents: 0,
    frequency: null
  });
  if (root) {
    root.children = Array.from(new Set([...(root.children || []), nodeId]));
    draft.edges.push({
      id: `U${Date.now()}`,
      source: root.id,
      target: nodeId,
      condition_label: "用户意图要求该段落",
      predicate: `query.intent == '${nodeId}'`,
      support_documents: 0,
      origin: "user"
    });
  }
  state.myDfaSelectedNodeId = nodeId;
  markMyDfaDirty();
  renderMyDfaStudio();
}

function deleteMyDfaNode(nodeId) {
  const draft = state.myDfaDraft;
  const node = draft?.nodes?.find((item) => item.id === nodeId);
  if (!draft || !node || node.type === "root" || Number(node.level || 0) === 0) return;
  draft.nodes = draft.nodes.filter((item) => item.id !== nodeId);
  draft.edges = draft.edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId);
  draft.nodes.forEach((item) => { item.children = (item.children || []).filter((child) => child !== nodeId); });
  state.myDfaSelectedNodeId = draft.nodes.find((item) => item.type !== "root")?.id || draft.nodes[0]?.id || null;
  markMyDfaDirty();
  renderMyDfaStudio();
}

function addMyDfaEdge() {
  const draft = state.myDfaDraft;
  if (!draft) return;
  const source = els.myDfaEdgeSource.value;
  const target = els.myDfaEdgeTarget.value;
  if (!source || !target || source === target) {
    els.myDfaSummary.textContent = "转移起点和终点必须是两个不同节点。";
    return;
  }
  const condition = els.myDfaEdgeCondition.value.trim() || "稳定直接转移";
  draft.edges.push({
    id: `U${Date.now()}`,
    source,
    target,
    condition_label: condition,
    predicate: condition === "稳定直接转移" ? "TRUE" : "user.condition",
    support_documents: 0,
    origin: "user"
  });
  els.myDfaEdgeCondition.value = "";
  markMyDfaDirty();
  renderMyDfaStudio();
}

function removeMyDfaEdge(edgeId) {
  if (!state.myDfaDraft) return;
  state.myDfaDraft.edges = state.myDfaDraft.edges.filter((edge) => edge.id !== edgeId);
  markMyDfaDirty();
  renderMyDfaStudio();
}

function deleteActiveMyDfa() {
  const draft = state.myDfaDraft;
  if (!draft || !window.confirm(`确定删除“${draft.name}”吗？系统原始模板不会受影响。`)) return;
  state.myDfas = state.myDfas.filter((dfa) => dfa.id !== draft.id);
  persistMyDfas();
  state.activeMyDfaId = null;
  state.myDfaDraft = null;
  state.myDfaSelectedNodeId = null;
  state.myDfaDirty = false;
  if (state.myDfas.length) selectMyDfa(state.myDfas[0].id);
  else renderMyDfaStudio();
}

function openMyDfaStudio() {
  if (!els.myDfaModal.open) els.myDfaModal.showModal();
  if (!state.myDfaDraft && state.myDfas.length) selectMyDfa(state.myDfas[0].id);
  else renderMyDfaStudio();
}

function closeMyDfaStudio() {
  if (state.myDfaDirty && !window.confirm("当前 DFA 有未保存修改，确定放弃并关闭吗？")) return;
  if (state.activeMyDfaId) {
    const saved = state.myDfas.find((dfa) => dfa.id === state.activeMyDfaId);
    state.myDfaDraft = saved ? cloneJson(saved) : null;
  }
  state.myDfaDirty = false;
  els.myDfaModal.close();
}

function renderOfflineDfaDetail(template, nodeId) {
  const nodes = template?.nodes || [];
  const edges = template?.edges || [];
  const node = nodes.find((item) => item.id === nodeId);
  if (!node) {
    els.offlineDfaDetail.innerHTML = `<div class="offline-detail-empty"><strong>${ui("选择一个段落节点", "Select a Section Node")}</strong><p>${ui("点击左侧节点，查看该段落内部的 DFA 执行细节。", "Select a node on the left to inspect its internal DFA execution details.")}</p></div>`;
    return;
  }
  const isRoot = node.type === "root" || Number(node.level || 0) === 0;
  const materials = Array.isArray(node.materials) ? node.materials : [];
  const incoming = edges.filter((edge) => edge.target === node.id);
  const outgoing = edges.filter((edge) => edge.source === node.id);
  const fallbackStates = [
    { id: "I00", stage: "entry", label: ui("状态入口", "State Entry"), detail: ui("读取用户约束与上游摘要", "Load user constraints and upstream summaries") },
    { id: "V00", stage: "evidence", label: ui("证据校验", "Evidence Validation"), detail: ui("检查来源、截止日期和记录完整性", "Validate sources, cutoff dates, and record completeness") },
    { id: "G00", stage: "generation", label: ui(`生成“${node.label || node.id}”`, `Generate “${node.label || node.id}”`), detail: ui("依据写作规则形成可发布段落", "Create a publishable section from the writing rules") },
    { id: "O00", stage: "output", label: ui("摘要传递", "Summary Handoff"), detail: ui("向下一状态传递本段结论和证据边界", "Pass conclusions and evidence limitations to the next state") }
  ];
  const internalDfa = node.internal_dfa || {};
  const internalStates = Array.isArray(internalDfa.states) && internalDfa.states.length ? internalDfa.states : fallbackStates;
  const internalTransitions = Array.isArray(internalDfa.transitions) ? internalDfa.transitions : [];
  const sequencePatterns = Array.isArray(internalDfa.sequence_patterns) ? internalDfa.sequence_patterns : [];
  const stageLabels = {
    entry: ui("入口状态", "Entry State"),
    material: ui("材料绑定状态", "Material Binding States"),
    evidence: ui("证据汇合状态", "Evidence Aggregation States"),
    event: ui("归一化证据事件", "Normalized Evidence Events"),
    condition: ui("条件决策状态", "Condition Decision States"),
    generation: ui("段落生成状态", "Section Generation States"),
    validation: ui("引用校验状态", "Citation Validation States"),
    output: ui("输出状态", "Output States")
  };
  const stageOrder = Object.keys(stageLabels);
  const stateGroups = stageOrder
    .map((stage) => ({ stage, states: internalStates.filter((item) => item.stage === stage) }))
    .filter((group) => group.states.length);
  const transitionCards = [
    ...incoming.map((edge) => ({ ...edge, direction: ui("进入", "Incoming") })),
    ...outgoing.map((edge) => ({ ...edge, direction: ui("离开", "Outgoing") }))
  ];
  els.offlineDfaDetail.innerHTML = `
    <header class="offline-detail-header">
      <div><span>${escapeHtml(node.id)}</span><h3>${escapeHtml(node.label || ui("路由状态", "Routing State"))}</h3></div>
      <small>${node.support_documents ? ui(`${Number(node.support_documents).toLocaleString()} 篇历史支持`, `${Number(node.support_documents).toLocaleString()} supporting documents`) : ui("全局入口", "Global Entry")}<br>${internalDfa.source_case_files ? ui(`源自 ${Number(internalDfa.source_case_files).toLocaleString()} 个 Case`, `Derived from ${Number(internalDfa.source_case_files).toLocaleString()} cases`) : ""}</small>
    </header>
    <div class="offline-detail-meta">
      <span>${escapeHtml(node.type || "state")}</span>
      <span>${ui("层级", "Level")} ${Number(node.level || 0)}</span>
      <span>${node.frequency != null ? ui(`出现频率 ${(Number(node.frequency) * 100).toFixed(1)}%`, `Frequency ${(Number(node.frequency) * 100).toFixed(1)}%`) : ui("路由节点", "Routing Node")}</span>
      <span>${internalStates.length} ${ui("个内部状态", "internal states")}</span>
      <span>${internalTransitions.length} ${ui("条内部转移", "internal transitions")}</span>
    </div>
    <section class="offline-detail-section">
      <div class="offline-detail-title"><strong>${ui("完整段落内部 DFA", "Complete Section-Level DFA")}</strong><small>${internalStates.length} states · ${internalTransitions.length} transitions</small></div>
      <div class="offline-internal-stage-list">
        ${stateGroups.map((group) => `
          <section class="offline-internal-stage" data-stage="${escapeHtml(group.stage)}">
            <header><strong>${escapeHtml(stageLabels[group.stage])}</strong><small>${IS_ENGLISH ? `${group.states.length} ${group.states.length === 1 ? "state" : "states"}` : `${group.states.length} 个状态`}</small></header>
            <div>${group.states.map((item) => `
              <article>
                <div><span>${escapeHtml(item.id)}</span>${item.support_documents ? `<small>${ui(`${Number(item.support_documents).toLocaleString()} 篇支持`, `${Number(item.support_documents).toLocaleString()} supporting documents`)}</small>` : ""}</div>
                <strong>${escapeHtml(item.label || item.id)}</strong>
                <p>${escapeHtml(item.detail || "")}</p>
              </article>
            `).join("")}</div>
          </section>
        `).join("")}
      </div>
      <details class="offline-internal-transitions" open>
        <summary>${ui(`全部 ${internalTransitions.length} 条内部状态转移`, `All ${internalTransitions.length} Internal State Transitions`)}</summary>
        <div>${internalTransitions.length ? internalTransitions.map((item) => `
          <article>
            <strong>${escapeHtml(item.source)} → ${escapeHtml(item.target)}</strong>
            <span>${escapeHtml(item.condition || "TRUE")}</span>
            ${item.support_documents ? `<small>${ui(`${Number(item.support_documents).toLocaleString()} 篇关联支持`, `${Number(item.support_documents).toLocaleString()} supporting documents`)}</small>` : ""}
          </article>
        `).join("") : `<p class="offline-transition-empty">${ui("缓存中暂无内部转移明细", "No internal transition details are available in the cache.")}</p>`}</div>
      </details>
    </section>
    ${sequencePatterns.length ? `
      <section class="offline-detail-section">
        <div class="offline-detail-title"><strong>${ui("关联训练序列模式", "Related Training Sequence Patterns")}</strong><small>${sequencePatterns.length} patterns</small></div>
        <div class="offline-sequence-patterns">${sequencePatterns.map((pattern, index) => `
          <article>
            <span>P${String(index + 1).padStart(2, "0")}</span>
            <strong>${(pattern.states || []).map((item) => escapeHtml(item)).join(" → ")}</strong>
            <small>${Number(pattern.documents || 0).toLocaleString()} ${ui("篇", "documents")} · ${(Number(pattern.frequency || 0) * 100).toFixed(2)}%</small>
          </article>
        `).join("")}</div>
      </section>
    ` : ""}
    <section class="offline-detail-section">
      <div class="offline-detail-title"><strong>${ui("写作规则", "Writing Rules")}</strong><small>Generation contract</small></div>
      <p class="offline-guideline">${escapeHtml(node.guideline || (isRoot ? ui("根据用户意图和可用证据选择第一个可执行写作状态。", "Select the first executable writing state from user intent and available evidence.") : ui("依据状态材料完成独立语义写作任务。", "Complete an independent semantic writing task from the state materials.")))}</p>
    </section>
    <section class="offline-detail-section">
      <div class="offline-detail-title"><strong>${ui("材料要求", "Material Requirements")}</strong><small>${materials.length} bindings</small></div>
      <div class="offline-material-tags">${materials.length ? materials.map((item) => `<span>${escapeHtml(item)}</span>`).join("") : `<em>${ui("该状态不要求独立材料", "This state does not require independent materials.")}</em>`}</div>
    </section>
    <section class="offline-detail-section">
      <div class="offline-detail-title"><strong>${ui("状态转移", "State Transitions")}</strong><small>${transitionCards.length} transitions</small></div>
      <div class="offline-transition-list">${transitionCards.length ? transitionCards.map((edge) => `
        <article>
          <span>${escapeHtml(edge.direction)}</span>
          <strong>${escapeHtml(edge.source)} → ${escapeHtml(edge.target)}</strong>
          <p>${escapeHtml(edge.condition_label || edge.label || ui("稳定直接转移", "Stable Direct Transition"))}</p>
          <small>${escapeHtml(edge.predicate || edge.condition_mode || (edge.direct ? "TRUE" : ui("历史条件", "Historical Condition")))}${edge.support_documents ? ` · ${Number(edge.support_documents).toLocaleString()} ${ui("篇支持", "supporting documents")}` : ""}</small>
        </article>
      `).join("") : `<div class="offline-transition-empty">${ui("暂无相邻转移", "No adjacent transitions.")}</div>`}</div>
    </section>
  `;
}

function drawOfflineDfa(template) {
  const svg = els.offlineDfaSvg;
  const nodes = template?.nodes || [];
  const edges = template?.edges || [];
  svg.innerHTML = "";
  if (!nodes.length) {
    svg.innerHTML = `<text x="480" y="270" text-anchor="middle" class="offline-empty">${ui("本地尚未找到该领域的 DFA 缓存", "No local DFA cache was found for this domain.")}</text>`;
    renderOfflineDfaDetail(null, null);
    return;
  }
  renderOfflineDfaDetail(template, state.offlineDfaSelectedNodeId);
  const orderedNodes = [...nodes].sort((left, right) => (Number(left.level) || 0) - (Number(right.level) || 0));
  const positions = Object.fromEntries(orderedNodes.map((node, index) => [node.id, {
    x: 100 + (index / Math.max(1, orderedNodes.length - 1)) * 760,
    y: index === 0 ? 270 : [135, 405, 135, 270, 405][(index - 1) % 5]
  }]));
  edges.forEach((edge) => {
    const source = positions[edge.source];
    const target = positions[edge.target];
    if (!source || !target) return;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", source.x); line.setAttribute("y1", source.y); line.setAttribute("x2", target.x); line.setAttribute("y2", target.y);
    line.setAttribute("class", "offline-dfa-edge");
    svg.appendChild(line);
    if (edge.condition_label) {
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", (source.x + target.x) / 2); label.setAttribute("y", (source.y + target.y) / 2 - 7);
      label.setAttribute("text-anchor", "middle"); label.setAttribute("class", "offline-dfa-edge-label");
      label.textContent = String(edge.condition_label).slice(0, 18);
      svg.appendChild(label);
    }
  });
  nodes.forEach((node) => {
    const point = positions[node.id];
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", `offline-dfa-node${node.id === state.offlineDfaSelectedNodeId ? " active" : ""}`);
    group.setAttribute("role", "button");
    group.setAttribute("tabindex", "0");
    group.setAttribute("aria-label", ui(`查看 ${node.label || node.id} 的内部 DFA 细节`, `View internal DFA details for ${node.label || node.id}`));
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", point.x - 82); rect.setAttribute("y", point.y - 31); rect.setAttribute("width", "164"); rect.setAttribute("height", "62"); rect.setAttribute("rx", "5");
    const id = document.createElementNS("http://www.w3.org/2000/svg", "text");
    id.setAttribute("x", point.x - 68); id.setAttribute("y", point.y - 10); id.setAttribute("class", "offline-dfa-node-id"); id.textContent = node.id;
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", point.x - 68); label.setAttribute("y", point.y + 8); label.setAttribute("class", "offline-dfa-node-label"); label.textContent = String(node.label || node.id).slice(0, 16);
    const support = document.createElementNS("http://www.w3.org/2000/svg", "text");
    support.setAttribute("x", point.x - 68); support.setAttribute("y", point.y + 22); support.setAttribute("class", "offline-dfa-node-support");
    support.textContent = node.support_documents
      ? ui(`历史支持 ${node.support_documents} 篇`, `${node.support_documents} supporting documents`)
      : ui("起始路由状态", "Initial routing state");
    const selectNode = () => {
      state.offlineDfaSelectedNodeId = node.id;
      drawOfflineDfa(template);
    };
    group.addEventListener("click", selectNode);
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode();
      }
    });
    group.append(rect, id, label, support); svg.appendChild(group);
  });
}

async function openOfflineDfa() {
  if (!els.offlineDfaModal.open) els.offlineDfaModal.showModal();
  els.offlineDfaSummary.textContent = ui("正在读取本地已诱导的写作结构。", "Loading the locally induced writing structure.");
  els.refreshOfflineDfa.disabled = true;
  try {
    const preview = await apiPost("/pipeline/preview", {
      query: ui("离线全局写作 DFA 结构查看", "Inspect the offline global writing DFA structure"),
      domain: els.offlineDfaDomain.value,
      language: state.language,
      data_source: "none",
      use_ai: false,
      source_learning: false,
      force_relearn: false,
      remote_embedding: false
    });
    const template = preview.analysis?.template || {};
    const induction = preview.analysis?.runtime?.induction || {};
    state.offlineDfaTemplate = template;
    const selectedStillExists = template.nodes?.some((node) => node.id === state.offlineDfaSelectedNodeId);
    if (!selectedStillExists) {
      state.offlineDfaSelectedNodeId = template.nodes?.find((node) => Number(node.level || 0) > 0)?.id || template.nodes?.[0]?.id || null;
    }
    const internalStateCount = (template.nodes || []).reduce((sum, node) => sum + Number(node.internal_dfa?.states?.length || 0), 0);
    const internalTransitionCount = (template.nodes || []).reduce((sum, node) => sum + Number(node.internal_dfa?.transitions?.length || 0), 0);
    els.offlineDfaSummary.textContent = IS_ENGLISH
      ? `${preview.analysis?.domain || "Current Domain"} · ${template.nodes?.length || 0} section states · ${internalStateCount} internal states · ${internalTransitionCount} internal transitions`
      : `${preview.analysis?.domain || "当前领域"} · ${template.nodes?.length || 0} 个段落状态 · ${internalStateCount} 个内部状态 · ${internalTransitionCount} 条内部转移`;
    els.offlineDfaMetrics.innerHTML = [
      [ui("历史文档", "Historical Documents"), induction.documents ? ui(`${Number(induction.documents).toLocaleString()} 篇`, `${Number(induction.documents).toLocaleString()} documents`) : ui("读取中", "Loading")],
      [ui("Case 文件", "Case Files"), induction.case_files ? ui(`${Number(induction.case_files).toLocaleString()} 个`, `${Number(induction.case_files).toLocaleString()} cases`) : ui("读取中", "Loading")],
      [ui("内部状态", "Internal States"), internalStateCount ? ui(`${Number(internalStateCount).toLocaleString()} 个`, Number(internalStateCount).toLocaleString()) : "-"],
      [ui("序列模式", "Sequence Patterns"), induction.sequence_patterns ? ui(`${Number(induction.sequence_patterns).toLocaleString()} 种`, Number(induction.sequence_patterns).toLocaleString()) : "-"],
      [ui("保留阈值", "Retention Threshold"), induction.frequency_threshold != null ? `${(Number(induction.frequency_threshold) * 100).toFixed(1)}%` : "-"]
    ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
    drawOfflineDfa(template);
  } catch (error) {
    state.offlineDfaTemplate = null;
    state.offlineDfaSelectedNodeId = null;
    els.offlineDfaSummary.textContent = ui(`无法读取离线 DFA：${error.message}`, `Unable to load the offline DFA: ${error.message}`);
    els.offlineDfaMetrics.innerHTML = "";
    drawOfflineDfa(null);
  } finally {
    els.refreshOfflineDfa.disabled = false;
  }
}

function renderDecision() {
  const event = currentEvent();
  const analysis = state.analysis;
  if (!event || !analysis) return;
  const nodes = analysis.template?.nodes || [];
  const nodeById = Object.fromEntries(nodes.map((item) => [item.id, item]));
  const labelsFor = (ids) => (ids || []).map((id) => nodeById[id]?.label || id).join("、") || "无";
  const selectedId = ["evidence", "assembly"].includes(event.stage) ? (state.selectedNodeId || event.nodeId) : null;
  const node = analysis.template?.nodes?.find((item) => item.id === selectedId);
  const index = Math.max(0, (analysis.execution_order || []).indexOf(selectedId));
  const evidenceStage = event.stage === "evidence";
  const assemblyStage = event.stage === "assembly" && event.type !== "assembly";
  els.decisionContextLabel.textContent = evidenceStage ? "当前证据状态" : assemblyStage ? "当前写作状态" : "当前构建对象";
  els.evidenceLabel.textContent = evidenceStage || assemblyStage ? "状态级证据" : "构建依据";
  els.conditionLabel.textContent = evidenceStage ? "数据处理" : assemblyStage ? "报告产出" : "当前产出";

  if (event.type === "dfa") {
    els.decisionIndex.textContent = "DFA";
    els.decisionTitle.textContent = "离线全局写作自动机";
    els.evidenceText.textContent = `${nodes.length} 个语义状态，${analysis.template?.edges?.length || 0} 条稳定转移`;
    els.conditionText.textContent = analysis.runtime?.rebuilt ? "全局 DFA 本次已重建" : "直接复用已构建的 DFA 缓存";
  } else if (event.type === "query") {
    els.decisionIndex.textContent = "Q";
    els.decisionTitle.textContent = "当前对话约束";
    els.evidenceText.textContent = analysis.query;
    els.conditionText.textContent = [analysis.domain, analysis.date, analysis.constraints?.report_type].filter(Boolean).join(" · ");
  } else if (event.type === "ranked") {
    const top = (analysis.ranked || []).slice(0, 5);
    els.decisionIndex.textContent = "Top-K";
    els.decisionTitle.textContent = "候选语义状态";
    els.evidenceText.textContent = top.map((item) => `${item.label} ${Number(item.score || item.similarity || 0).toFixed(2)}`).join(" · ") || "没有候选状态";
    els.conditionText.textContent = `按语义相似度排序，下一步应用 τ=${Number(analysis.tau || 0).toFixed(2)}`;
  } else if (event.type === "matched") {
    els.decisionIndex.textContent = "τ";
    els.decisionTitle.textContent = "对话命中状态";
    els.evidenceText.textContent = `Query 与全局状态索引的相似度超过阈值`;
    els.conditionText.textContent = labelsFor(event.activeNodes);
  } else if (event.type === "raw") {
    els.decisionIndex.textContent = "G′";
    els.decisionTitle.textContent = "原始 Query 子图";
    els.evidenceText.textContent = labelsFor(event.activeNodes);
    els.conditionText.textContent = `从公共祖先 ${analysis.subtree_root || "root"} 抽取相关路径`;
  } else if (event.type === "closure") {
    const raw = new Set(analysis.raw_subdfa?.node_ids || []);
    const added = (event.activeNodes || []).filter((id) => !raw.has(id));
    els.decisionIndex.textContent = "δ";
    els.decisionTitle.textContent = "路径与转移闭包";
    els.evidenceText.textContent = added.length ? `补入连接状态：${labelsFor(added)}` : "原始子图已经连通";
    els.conditionText.textContent = `保留 ${event.activeNodes?.length || 0} 个状态和 ${event.activeEdges?.length || 0} 条可执行转移`;
  } else if (event.type === "finalized") {
    els.decisionIndex.textContent = "Sub";
    els.decisionTitle.textContent = "本次对话 SubDFA";
    els.evidenceText.textContent = `${event.activeNodes?.length || 0} 个状态 · ${event.activeEdges?.length || 0} 条转移`;
    els.conditionText.textContent = `执行顺序：${labelsFor(analysis.execution_order)}`;
  } else if (event.type === "assembly") {
    els.decisionIndex.textContent = "F";
    const blocked = analysis.report_status === "blocked";
    els.decisionTitle.textContent = blocked ? "报告受阻" : "最终报告";
    els.evidenceText.textContent = blocked
      ? `0 / ${analysis.report_sections?.length || 0} 个状态片段取得可验证证据`
      : `${analysis.report_sections?.length || 0} 个状态片段已生成`;
    els.conditionText.textContent = blocked ? evidenceProblem(analysis) : "到达终止状态 F，按执行顺序组装文档";
  } else {
    els.decisionIndex.textContent = selectedId ? `S${String(index + 1).padStart(2, "0")}` : "S";
    els.decisionTitle.textContent = node?.label || "写作状态";
    els.evidenceText.textContent = selectedId ? materialSummary(selectedId) : "等待状态级证据";
  }

  if (event.type === "transition") {
    const edge = analysis.template?.edges?.find((item) => item.id === event.edgeId);
    els.conditionText.textContent = conditionForEdge(edge);
  } else if (event.type === "evidence") {
    els.conditionText.textContent = "完成截止日、发布日与记录完整性校验";
  } else if (event.type === "generation") {
    els.conditionText.textContent = `基于已验证证据生成片段 ${Math.min((event.generatedUntil || 0), analysis.report_sections?.length || 0)} / ${analysis.report_sections?.length || 0}`;
  }
}

function timelineStageCode(stage) {
  return ({ dfa: "DFA", query: "PARSE", match: "MATCH", subdfa: "SUBDFA", evidence: "SOURCE", assembly: "COMPOSE" })[stage] || stage;
}

function renderTimeline() {
  els.eventTimeline.innerHTML = "";
  state.events.forEach((event, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.disabled = state.busy;
    button.className = `event-chip ${index < state.eventIndex ? "done" : ""} ${index === state.eventIndex ? "active" : ""}`;
    button.innerHTML = `<span>${escapeHtml(timelineStageCode(event.stage))}</span><strong>${escapeHtml(event.title)}</strong>`;
    button.addEventListener("click", () => {
      if (state.busy) return;
      state.playToken += 1;
      state.eventIndex = index;
      renderCurrentEvent();
      if (index === state.events.length - 1) finishRun();
    });
    els.eventTimeline.appendChild(button);
  });
  const active = els.eventTimeline.children[state.eventIndex];
  active?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
}

function renderRuntimeDetail() {
  const analysis = state.analysis;
  if (!analysis) return;
  const runtime = analysis.runtime || {};
  const dfaSource = runtime.dfa_source === "user"
    ? `我的 DFA · ${runtime.user_dfa?.name || "自定义结构"}`
    : `系统 DFA · ${runtime.artifact_mode || "cache"}${runtime.rebuilt ? " · 本次重建" : " · 已复用"}`;
  const items = [
    ["写作领域", analysis.domain || "自动识别"],
    ["DFA 来源", dfaSource],
    ["语义表示", runtime.embedding?.mode === "semantic-api" ? runtime.embedding?.model || "Semantic API" : "Local hash"],
    ["证据来源", evidenceSourceLabel(analysis)]
  ];
  els.runDetailGrid.innerHTML = items.map(([label, value]) => `
    <div class="detail-item"><span>${escapeHtml(label)}</span><strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong></div>
  `).join("");
  els.dfaRuntime.textContent = runtime.dfa_source === "user" ? "我的 DFA" : (runtime.rebuilt ? "本次重建" : "复用缓存");
  els.evidenceRuntime.textContent = evidenceSourceLabel(analysis);
  els.modelRuntime.textContent = state.response?.model || state.health?.model || "Fallback";
}

function splitLabel(value, max = 9) {
  const text = String(value || "");
  if (text.length <= max) return [text];
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length > 1) {
    let firstLine = "";
    let consumed = 0;
    for (const word of words) {
      const candidate = firstLine ? `${firstLine} ${word}` : word;
      if (candidate.length > max && firstLine) break;
      firstLine = candidate;
      consumed += 1;
    }
    const rest = words.slice(consumed).join(" ");
    if (rest) return [firstLine, `${rest.slice(0, max - 1)}${rest.length > max - 1 ? "…" : ""}`];
  }
  return [text.slice(0, max), `${text.slice(max, max * 2 - 1)}${text.length > max * 2 - 1 ? "…" : ""}`];
}

function makeSvg(tag) {
  return document.createElementNS("http://www.w3.org/2000/svg", tag);
}

function addSvgText(group, value, x, y, className, max = 9) {
  const text = makeSvg("text");
  text.setAttribute("x", String(x));
  text.setAttribute("y", String(y));
  text.setAttribute("class", className);
  splitLabel(value, max).forEach((line, index) => {
    const span = makeSvg("tspan");
    span.setAttribute("x", String(x));
    span.setAttribute("dy", index ? "15" : "0");
    span.textContent = line;
    text.appendChild(span);
  });
  group.appendChild(text);
}

function edgePath(edge, nodeById) {
  const source = nodeById[edge.source];
  const target = nodeById[edge.target];
  if (!source || !target) return "";
  if (Math.abs(source.x - target.x) < 26) {
    const sx = source.x + NODE_W / 2;
    const sy = source.y + NODE_H;
    const tx = target.x + NODE_W / 2;
    const ty = target.y;
    const mid = (sy + ty) / 2;
    return `M ${sx} ${sy} C ${sx} ${mid}, ${tx} ${mid}, ${tx} ${ty}`;
  }
  const sx = source.x + NODE_W;
  const sy = source.y + NODE_H / 2;
  const tx = target.x;
  const ty = target.y + NODE_H / 2;
  const mid = (sx + tx) / 2;
  return `M ${sx} ${sy} C ${mid} ${sy}, ${mid} ${ty}, ${tx} ${ty}`;
}

function uniqueNodeIds(values) {
  const seen = new Set();
  return values.filter((value) => {
    const id = String(value || "");
    if (!id || seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

function topologicalNodeOrder(nodeIds, edges) {
  if (!edges.length) return nodeIds;
  const orderIndex = Object.fromEntries(nodeIds.map((id, index) => [id, index]));
  const included = new Set(nodeIds);
  const indegree = Object.fromEntries(nodeIds.map((id) => [id, 0]));
  const outgoing = Object.fromEntries(nodeIds.map((id) => [id, []]));
  edges.forEach((edge) => {
    if (!included.has(edge.source) || !included.has(edge.target)) return;
    indegree[edge.target] += 1;
    outgoing[edge.source].push(edge.target);
  });
  const queue = nodeIds.filter((id) => indegree[id] === 0);
  const ordered = [];
  while (queue.length) {
    queue.sort((a, b) => orderIndex[a] - orderIndex[b]);
    const id = queue.shift();
    ordered.push(id);
    outgoing[id].forEach((target) => {
      indegree[target] -= 1;
      if (indegree[target] === 0) queue.push(target);
    });
  }
  return uniqueNodeIds([...ordered, ...nodeIds]);
}

function graphRenderData(nodes, edges, event, routeNodes, routeEdges, activeNodes, activeEdges) {
  const showFullGraph = state.graphView === "dfa" || event.graphScope === "full";
  if (showFullGraph) {
    return {
      nodes,
      edges,
      full: true,
      viewport: state.analysis.template?.viewport || [0, 0, 980, 560]
    };
  }

  const routeOrder = uniqueNodeIds([
    ...(state.analysis.execution_order || []),
    ...(state.analysis.subdfa?.node_ids || [])
  ]);
  let visibleOrder = routeOrder;
  if (["ranked", "matched", "raw"].includes(event.graphScope)) {
    visibleOrder = uniqueNodeIds(event.activeNodes || []);
  }
  visibleOrder = uniqueNodeIds([...visibleOrder, ...(event.activeNodes || [])]);
  if (!visibleOrder.length) visibleOrder = uniqueNodeIds([...routeNodes]);

  const sourceById = Object.fromEntries(nodes.map((node) => [node.id, node]));
  const preliminaryIds = new Set(visibleOrder);
  const focusedEdges = edges.filter((edge) => {
    if (!preliminaryIds.has(edge.source) || !preliminaryIds.has(edge.target)) return false;
    if (event.graphScope === "raw") return activeEdges.has(edge.id);
    if (["subdfa", "execution", "assembly"].includes(event.graphScope)) return routeEdges.has(edge.id);
    return activeEdges.has(edge.id);
  });
  visibleOrder = topologicalNodeOrder(visibleOrder, focusedEdges);
  const gap = 58;
  const top = 42;
  const left = 60;
  const focusedNodes = visibleOrder
    .filter((id) => sourceById[id])
    .map((id, index) => ({ ...sourceById[id], x: left, y: top + index * (NODE_H + gap) }));
  const height = Math.max(300, top * 2 + focusedNodes.length * NODE_H + Math.max(0, focusedNodes.length - 1) * gap);
  return {
    nodes: focusedNodes,
    edges: focusedEdges,
    full: false,
    viewport: [0, 0, NODE_W + left * 2, height]
  };
}

function drawGraph() {
  els.svg.innerHTML = "";
  if (!state.analysis) {
    els.svg.setAttribute("viewBox", "0 0 720 420");
    els.svg.style.width = "100%";
    els.svg.style.height = "100%";
    els.graphSummary.textContent = "等待 SubDFA 构建";
    const text = makeSvg("text");
    text.setAttribute("x", "360");
    text.setAttribute("y", "210");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("class", "graph-placeholder");
    text.textContent = "等待条件标注写作 DFA";
    els.svg.appendChild(text);
    return;
  }

  const { nodes, edges } = graphData();
  const routeNodes = new Set(state.analysis.subdfa?.node_ids || state.analysis.execution_order || []);
  const routeEdges = new Set(state.analysis.subdfa?.edge_ids || []);
  const event = currentEvent() || {};
  const activeNodes = new Set(event.activeNodes || []);
  const activeEdges = new Set(event.activeEdges || []);
  const renderData = graphRenderData(nodes, edges, event, routeNodes, routeEdges, activeNodes, activeEdges);
  const renderNodes = renderData.nodes;
  const renderEdges = renderData.edges;
  const viewport = renderData.viewport;
  els.svg.setAttribute("viewBox", viewport.join(" "));
  els.svg.setAttribute("preserveAspectRatio", "xMidYMin meet");
  if (renderData.full) {
    els.svg.style.width = `${Math.max(viewport[2], els.graphShell.clientWidth)}px`;
    els.svg.style.height = `${Math.max(viewport[3], els.graphShell.clientHeight)}px`;
  } else {
    els.svg.style.width = "100%";
    els.svg.style.height = `${Math.max(viewport[3], els.graphShell.clientHeight - 2)}px`;
  }
  const nodeById = Object.fromEntries(renderNodes.map((node) => [node.id, node]));
  const rankedById = Object.fromEntries((state.analysis.ranked || []).map((item) => [item.id, item]));
  const showFullGraph = renderData.full;
  const showFinalRoute = ["subdfa", "execution", "assembly"].includes(event.graphScope);
  const generatedUntil = event.generatedUntil || 0;
  const visited = new Set((state.analysis.execution_order || []).slice(0, generatedUntil));
  const activeLabel = activeNodes.size <= 2 ? renderNodes.find((node) => activeNodes.has(node.id))?.label : "";
  els.graphSummary.textContent = `${showFullGraph ? "全局 DFA" : "当前子图"} · ${renderNodes.length} 个状态 · ${renderEdges.length} 条转移${activeLabel ? ` · 当前：${activeLabel}` : ""}`;

  const defs = makeSvg("defs");
  defs.innerHTML = `
    <marker id="arrow-default" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#aeb9b5"></path></marker>
    <marker id="arrow-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#c55a3e"></path></marker>
  `;
  els.svg.appendChild(defs);

  renderEdges.forEach((edge) => {
    const path = makeSvg("path");
    path.setAttribute("d", edgePath(edge, nodeById));
    path.setAttribute(
      "class",
      `dfa-edge ${showFullGraph ? "full" : ""} ${showFinalRoute && routeEdges.has(edge.id) ? "route" : ""} ${activeEdges.has(edge.id) ? "active" : ""}`
    );
    path.setAttribute("marker-end", activeEdges.has(edge.id) ? "url(#arrow-active)" : "url(#arrow-default)");
    const pathTitle = makeSvg("title");
    pathTitle.textContent = conditionForEdge(edge);
    path.appendChild(pathTitle);
    els.svg.appendChild(path);

    if ((showFinalRoute && routeEdges.has(edge.id)) || activeEdges.has(edge.id)) {
      const source = nodeById[edge.source];
      const target = nodeById[edge.target];
      if (source && target) {
        const x = (source.x + target.x + NODE_W) / 2;
        const y = (source.y + target.y + NODE_H) / 2 - 8;
        const label = conditionForEdge(edge);
        const width = Math.min(188, Math.max(72, label.length * 10));
        const bg = makeSvg("rect");
        bg.setAttribute("x", String(x - width / 2));
        bg.setAttribute("y", String(y - 12));
        bg.setAttribute("width", String(width));
        bg.setAttribute("height", "19");
        bg.setAttribute("rx", "4");
        bg.setAttribute("class", "edge-label-bg");
        els.svg.appendChild(bg);
        const text = makeSvg("text");
        text.setAttribute("x", String(x));
        text.setAttribute("y", String(y + 1));
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("class", "edge-label");
        text.textContent = label.length > 18 ? `${label.slice(0, 17)}…` : label;
        els.svg.appendChild(text);
      }
    }
  });

  renderNodes.forEach((node) => {
    const group = makeSvg("g");
    const classNames = ["dfa-node"];
    if (showFullGraph) classNames.push("full");
    if (event.type === "ranked" && activeNodes.has(node.id)) classNames.push("candidate");
    if (["matched", "raw"].includes(event.type) && activeNodes.has(node.id)) classNames.push("matched");
    if (showFinalRoute && routeNodes.has(node.id)) classNames.push("route");
    if (visited.has(node.id)) classNames.push("visited");
    if ((["evidence", "assembly"].includes(event.stage) && activeNodes.has(node.id)) || state.selectedNodeId === node.id) classNames.push("active");
    group.setAttribute("class", classNames.join(" "));
    group.setAttribute("transform", `translate(${node.x}, ${node.y})`);
    const nodeTitle = makeSvg("title");
    nodeTitle.textContent = `${node.id} · ${node.label}`;
    group.appendChild(nodeTitle);
    group.addEventListener("click", () => {
      state.selectedNodeId = node.id;
      renderDecision();
      drawGraph();
    });
    const rect = makeSvg("rect");
    rect.setAttribute("width", String(NODE_W));
    rect.setAttribute("height", String(NODE_H));
    rect.setAttribute("rx", "6");
    rect.setAttribute("class", "dfa-node-card");
    group.appendChild(rect);
    addSvgText(group, node.label, 14, 25, "dfa-node-title", 13);
    const meta = makeSvg("text");
    meta.setAttribute("x", "14");
    meta.setAttribute("y", "66");
    meta.setAttribute("class", "dfa-node-meta");
    meta.textContent = `${node.id} · ${node.type === "leaf" ? "writing state" : node.type || "state"}`;
    group.appendChild(meta);

    if (event.type === "ranked" && rankedById[node.id]) {
      const scoreBadge = makeSvg("rect");
      scoreBadge.setAttribute("x", String(NODE_W - 50));
      scoreBadge.setAttribute("y", String(NODE_H - 23));
      scoreBadge.setAttribute("width", "40");
      scoreBadge.setAttribute("height", "17");
      scoreBadge.setAttribute("rx", "4");
      scoreBadge.setAttribute("class", "dfa-score-badge");
      group.appendChild(scoreBadge);
      const scoreText = makeSvg("text");
      scoreText.setAttribute("x", String(NODE_W - 44));
      scoreText.setAttribute("y", String(NODE_H - 11));
      scoreText.setAttribute("class", "dfa-score-text");
      scoreText.textContent = Number(rankedById[node.id].score || rankedById[node.id].similarity || 0).toFixed(2);
      group.appendChild(scoreText);
    }
    els.svg.appendChild(group);
  });

  if (!showFullGraph) {
    const focusId = state.selectedNodeId || (event.activeNodes || [])[0];
    const focusNode = nodeById[focusId];
    window.requestAnimationFrame(() => {
      els.graphShell.scrollLeft = 0;
      if (focusNode) {
        els.graphShell.scrollTo({
          top: Math.max(0, focusNode.y + NODE_H / 2 - els.graphShell.clientHeight / 2),
          behavior: "smooth"
        });
      }
    });
  }
}

function reportText() {
  const sections = state.analysis?.report_sections || [];
  return sections.map((section) => `${section.order}. ${section.label}\n${section.content}`).join("\n\n");
}

async function playEventRange(token, startIndex, endIndex) {
  for (let index = startIndex; index <= endIndex; index += 1) {
    if (token !== state.playToken) return;
    state.eventIndex = index;
    renderCurrentEvent();
    const event = state.events[index] || {};
    const delay = event.type === "finalized"
      ? 1500
      : ["dfa", "query", "match", "subdfa"].includes(event.stage)
        ? 850
        : event.stage === "evidence"
          ? 560
          : 620;
    await new Promise((resolve) => window.setTimeout(resolve, delay));
  }
}

function finishRun() {
  stopReportGenerationClock();
  if (!state.analysis) return;
  if (state.busy && !state.reportReady) return;
  state.eventIndex = Math.max(0, state.events.length - 1);
  renderCurrentEvent();
  setBusy(false);
  updateComposerMode();
  renderReport();
  els.skipAnimation.disabled = true;
  const blocked = state.analysis.report_status === "blocked";
  if (blocked) {
    els.runTitle.textContent = "报告未生成";
    els.runSubtitle.textContent = evidenceProblem(state.analysis);
    els.runBadge.textContent = "证据受阻";
    els.runBadge.className = "run-badge error";
    els.apiStatus.textContent = "报告受阻 · 检查证据源";
    els.apiStatus.classList.add("error");
  } else {
    const demoEvidence = (state.analysis.runtime?.evidence || state.analysis.runtime?.ifind)?.mode === "demo-snapshot";
    els.apiStatus.textContent = state.response?.ai_used
      ? `生成完成 · ${state.response.model}`
      : demoEvidence ? "生成完成 · 离线演示证据" : "生成完成 · 本地回退";
    els.apiStatus.classList.remove("error");
  }
  updateHistoryRun({
    status: blocked ? "blocked" : "complete",
    domain: state.analysis.domain,
    sectionCount: state.analysis.report_sections?.length || 0,
    sections: state.analysis.report_sections || [],
    runId: state.response?.run_id || null,
    analysisSnapshot: compactAnalysisForHistory(state.analysis)
  });
}

function skipAnimation() {
  if (!state.events.length) return;
  state.playToken += 1;
  finishRun();
}

async function generateReport() {
  if (state.busy) return;
  const query = composeQuery();
  if (!query) {
    els.query.focus();
    els.apiStatus.textContent = "请先输入报告需求";
    return;
  }

  beginRun(query);
  const token = state.playToken;
  const payload = requestPayload(query);
  try {
    const preview = await apiPost("/pipeline/preview", { ...payload, use_ai: false, use_ifind: false });
    if (token !== state.playToken) return;
    stopPendingClock();
    state.analysis = preview.analysis;
    state.response = { ...preview, ai_used: false };
    state.events = buildExecutionEvents(preview.analysis);
    state.eventIndex = 0;
    els.skipAnimation.disabled = true;
    renderRuntimeDetail();

    const reportPromise = apiPost("/reports/generate", payload).then(
      (data) => ({ data, error: null }),
      (error) => ({ data: null, error })
    );
    const constructionEnd = Math.max(0, state.events.findIndex((event) => event.type === "finalized"));
    await playEventRange(token, 0, constructionEnd);
    if (token !== state.playToken) return;
    const previewEvidenceStart = state.events.findIndex((event) => event.stage === "evidence");
    const previewEvidenceEnd = state.events.reduce((last, event, index) => event.stage === "evidence" ? index : last, -1);
    if (previewEvidenceStart >= 0 && previewEvidenceEnd >= previewEvidenceStart) {
      await playEventRange(token, previewEvidenceStart, previewEvidenceEnd);
    }
    if (token !== state.playToken) return;
    startReportGenerationClock();

    const reportResult = await reportPromise;
    stopReportGenerationClock();
    if (token !== state.playToken) return;
    const data = reportResult.data || {
      ...preview,
      analysis: preview.analysis,
      report_sections: preview.analysis.report_sections,
      ai_used: false,
      ai_error: reportResult.error?.message || "报告模型暂不可用"
    };
    state.analysis = data.analysis;
    state.response = data;
    state.reportReady = true;
    state.events = buildExecutionEvents(data.analysis);
    const assemblyStart = state.events.findIndex((event) => event.stage === "assembly");
    const resumeAt = assemblyStart >= 0 ? assemblyStart : Math.max(0, constructionEnd + 1);
    els.skipAnimation.disabled = false;
    await playEventRange(token, resumeAt, state.events.length - 1);
    if (token === state.playToken) finishRun();
  } catch (error) {
    stopPendingClock();
    stopReportGenerationClock();
    setBusy(false);
    state.reportReady = false;
    updateComposerMode();
    els.runTitle.textContent = "生成失败";
    els.runSubtitle.textContent = error.message;
    els.runBadge.textContent = "失败";
    els.runBadge.className = "run-badge error";
    els.reportPreview.className = "report-preview";
    els.reportPreview.innerHTML = `<div class="report-empty">${escapeHtml(error.message)}</div>`;
    els.apiStatus.textContent = "运行失败";
    els.apiStatus.classList.add("error");
    updateHistoryRun({ status: "failed", error: error.message });
  }
}

function resetWorkspace() {
  if (state.busy) return;
  stopPendingClock();
  stopReportGenerationClock();
  state.playToken += 1;
  state.activeQuery = "";
  state.activeHistoryId = null;
  state.analysis = null;
  state.response = null;
  state.events = [];
  state.eventIndex = 0;
  state.selectedNodeId = null;
  state.reportReady = false;
  state.revisions = [];
  state.expandedReportDfaKey = null;
  setGraphExpanded(false);
  els.currentTurn.classList.add("turn-hidden");
  els.emptyState.classList.remove("hidden");
  els.pastMessages.innerHTML = "";
  els.query.value = "";
  els.scope.value = "";
  els.timeRange.value = "";
  autoResizeComposer();
  renderRevisionThread();
  updateComposerMode();
  renderHistory();
  els.query.focus();
}

function autoResizeComposer() {
  els.query.style.height = "auto";
  els.query.style.height = `${Math.min(160, Math.max(52, els.query.scrollHeight))}px`;
}

function scrollToBottom(smooth = true) {
  window.requestAnimationFrame(() => {
    els.conversation.scrollTo({
      top: els.conversation.scrollHeight,
      behavior: smooth ? "smooth" : "auto"
    });
  });
}

function setGraphView(view) {
  state.graphView = view === "dfa" ? "dfa" : "construction";
  document.querySelectorAll(".graph-toolbar [data-view]").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === state.graphView);
  });
  if (state.analysis) drawGraph();
}

function setGraphExpanded(expanded) {
  state.graphExpanded = Boolean(expanded);
  els.executionPane.classList.toggle("graph-expanded", state.graphExpanded);
  document.body.classList.toggle("graph-overlay-open", state.graphExpanded);
  els.graphExpand.textContent = state.graphExpanded ? "×" : "⛶";
  els.graphExpand.title = state.graphExpanded ? "退出放大查看" : "放大查看 SubDFA";
  els.graphExpand.setAttribute("aria-label", els.graphExpand.title);
  if (state.analysis) window.requestAnimationFrame(drawGraph);
}

function bindEvents() {
  els.theta.addEventListener("input", () => {
    els.thetaValue.textContent = Number(els.theta.value).toFixed(2);
    updateThresholdPresetUi();
  });
  els.tau.addEventListener("input", () => {
    els.tauValue.textContent = Number(els.tau.value).toFixed(2);
    updateThresholdPresetUi();
  });
  els.fallbackTopK.addEventListener("input", updateThresholdPresetUi);
  els.composerTheta.addEventListener("input", applyComposerThresholdControls);
  els.composerTau.addEventListener("input", applyComposerThresholdControls);
  els.composerFallbackTopK.addEventListener("input", applyComposerThresholdControls);
  document.querySelectorAll("[data-threshold-preset]").forEach((button) => {
    button.addEventListener("click", () => applyThresholdPreset(button.dataset.thresholdPreset));
  });
  els.composerDfaSelect.addEventListener("change", () => {
    state.composerDfaId = els.composerDfaSelect.value || "system";
    const customDfa = selectedComposerDfa();
    if (customDfa?.baseDomain && Array.from(els.domain.options).some((option) => option.value === customDfa.baseDomain)) {
      els.domain.value = customDfa.baseDomain;
    }
    renderComposerDfaOptions();
  });
  els.manageComposerDfa.addEventListener("click", () => {
    els.composerDfaSourceControl.open = false;
    openMyDfaStudio();
  });
  els.sourceLearning.addEventListener("change", () => {
    if (!els.sourceLearning.checked) els.forceRelearn.checked = false;
  });
  els.forceRelearn.addEventListener("change", () => {
    if (els.forceRelearn.checked) els.sourceLearning.checked = true;
  });
  els.query.addEventListener("input", autoResizeComposer);
  els.query.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      submitComposer();
    }
  });
  els.composerRun.addEventListener("click", submitComposer);
  [els.reportPreview, els.revisionThread].forEach((container) => {
    container.addEventListener("click", (event) => {
      const target = event.target.closest?.(".report-section-main[data-report-dfa-key]");
      if (target) toggleReportInternalDfa(target);
    });
    container.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const target = event.target.closest?.(".report-section-main[data-report-dfa-key]");
      if (!target) return;
      event.preventDefault();
      toggleReportInternalDfa(target);
    });
  });
  els.timeRangePreset.addEventListener("change", () => {
    if (!els.timeRangePreset.value) return;
    els.timeRange.value = resolveTimePreset(els.timeRangePreset.value);
    els.timeRangePreset.value = "";
    els.timeRange.focus();
  });
  els.newChat.addEventListener("click", resetWorkspace);
  els.skipAnimation.addEventListener("click", skipAnimation);
  els.copyReport.addEventListener("click", async () => {
    const text = reportText();
    if (!text) return;
    await navigator.clipboard.writeText(text);
    els.reportProgress.textContent = "已复制";
    window.setTimeout(() => renderReport(), 900);
  });
  els.downloadReport.addEventListener("click", downloadReport);
  els.revisionThread.addEventListener("click", async (event) => {
    const button = event.target.closest?.("[data-revision-action]");
    if (!button) return;
    const revision = state.revisions.find((item) => item.id === button.dataset.revisionId);
    if (!revision || revision.status !== "complete" || !revision.sections?.length) return;
    if (button.dataset.revisionAction === "download") {
      downloadRevisionReport(revision);
      return;
    }
    if (button.dataset.revisionAction === "copy") {
      const text = revision.sections
        .map((section, index) => `${section.order || index + 1}. ${section.label || "报告章节"}\n${section.content || ""}`)
        .join("\n\n");
      await navigator.clipboard.writeText(text);
      const previousText = button.textContent;
      button.textContent = "✓";
      button.title = `V${Number(revision.version || 2)} 已复制`;
      window.setTimeout(() => {
        if (!button.isConnected) return;
        button.textContent = previousText;
        button.title = `复制 V${Number(revision.version || 2)} 报告`;
      }, 900);
    }
  });
  els.offlineDfa.addEventListener("click", openOfflineDfa);
  els.closeOfflineDfa.addEventListener("click", () => els.offlineDfaModal.close());
  els.refreshOfflineDfa.addEventListener("click", openOfflineDfa);
  els.myDfa.addEventListener("click", openMyDfaStudio);
  els.closeMyDfa.addEventListener("click", closeMyDfaStudio);
  els.importMyDfa.addEventListener("click", importMyDfaDomain);
  els.myDfaList.addEventListener("click", (event) => {
    const button = event.target.closest?.("[data-my-dfa-id]");
    if (!button || button.dataset.myDfaId === state.activeMyDfaId) return;
    if (state.myDfaDirty && !window.confirm("切换会放弃当前未保存修改，是否继续？")) return;
    selectMyDfa(button.dataset.myDfaId);
  });
  els.myDfaName.addEventListener("input", () => {
    if (!state.myDfaDraft) return;
    state.myDfaDraft.name = els.myDfaName.value;
    markMyDfaDirty();
  });
  els.addMyDfaNode.addEventListener("click", addMyDfaNode);
  els.saveMyDfa.addEventListener("click", saveMyDfaDraft);
  els.deleteMyDfa.addEventListener("click", deleteActiveMyDfa);
  els.myDfaNodeEditor.addEventListener("input", (event) => {
    const field = event.target.dataset?.myDfaNodeField;
    const node = state.myDfaDraft?.nodes?.find((item) => item.id === state.myDfaSelectedNodeId);
    if (!field || !node) return;
    if (field === "materials") node.materials = event.target.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
    else node[field] = event.target.value;
    markMyDfaDirty();
    if (field === "label") drawMyDfa();
  });
  els.myDfaNodeEditor.addEventListener("click", (event) => {
    const button = event.target.closest?.("[data-my-dfa-node-action='delete']");
    if (button) deleteMyDfaNode(state.myDfaSelectedNodeId);
  });
  els.myDfaEdgeList.addEventListener("click", (event) => {
    const button = event.target.closest?.("[data-my-dfa-edge-remove]");
    if (button) removeMyDfaEdge(button.dataset.myDfaEdgeRemove);
  });
  els.addMyDfaEdge.addEventListener("click", addMyDfaEdge);
  const englishExamples = [
    {
      prompt: "Generate a gold market research weekly covering investment recommendations, industry views, market performance, industry tracking, and risk factors. Explain allocation strategy and instruments; assess gold and silver trends and macro drivers; review price, volume, and positioning; track inventories, mine supply, downstream demand, and policy changes; and identify rate, FX, price, and liquidity risks.",
      scope: "Spot gold, COMEX gold, and the Chinese market, with silver and related non-ferrous metals"
    },
    {
      prompt: "Generate a base-metals industry tracking report covering investment recommendations, industry views, market performance, industry tracking, and risk factors. Compare copper, aluminum, precious metals, minor metals, and energy-transition metals, and assess supply-demand, inventories, smelting, imports, processing, and downstream operating rates.",
      scope: "Copper and aluminum value chains, with precious, minor, and energy-transition metals"
    },
    {
      prompt: "Generate a macro research report using high-frequency evidence on manufacturing and industrial activity, real estate, consumption and investment, exports, CPI/PPI, the US dollar, interest rates, and policy transmission. Provide a growth assessment and explicit risk factors.",
      scope: "Global macro variables and the Chinese economy, focusing on their impact on commodities"
    }
  ];
  document.querySelectorAll("[data-prompt]").forEach((button, index) => {
    button.addEventListener("click", () => {
      const localizedExample = state.language === "en" ? englishExamples[index] : null;
      els.query.value = localizedExample?.prompt || button.dataset.prompt || "";
      els.scope.value = localizedExample?.scope || button.dataset.scope || "";
      els.timeRange.value = button.dataset.timePreset
        ? resolveTimePreset(button.dataset.timePreset)
        : button.dataset.time || "";
      if (button.dataset.domain) els.domain.value = button.dataset.domain;
      if (button.dataset.fallbackTopK) els.fallbackTopK.value = button.dataset.fallbackTopK;
      updateThresholdPresetUi();
      autoResizeComposer();
      els.query.focus();
    });
  });
  document.querySelectorAll(".graph-toolbar [data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      setGraphView(button.dataset.view);
    });
  });
  els.graphExpand.addEventListener("click", () => setGraphExpanded(!state.graphExpanded));
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (state.graphExpanded) setGraphExpanded(false);
    if (els.thresholdPresetControl.open) els.thresholdPresetControl.open = false;
    if (els.composerDfaSourceControl.open) els.composerDfaSourceControl.open = false;
  });
  document.addEventListener("click", (event) => {
    if (els.thresholdPresetControl.open && !els.thresholdPresetControl.contains(event.target)) {
      els.thresholdPresetControl.open = false;
    }
    if (els.composerDfaSourceControl.open && !els.composerDfaSourceControl.contains(event.target)) {
      els.composerDfaSourceControl.open = false;
    }
  });
  els.stageRail.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      if (state.busy || !state.events.length) return;
      const indices = state.events
        .map((event, index) => event.stage === button.dataset.stage ? index : -1)
        .filter((index) => index >= 0);
      if (!indices.length) return;
      state.playToken += 1;
      state.eventIndex = indices[indices.length - 1];
      renderCurrentEvent();
      if (state.eventIndex === state.events.length - 1) finishRun();
    });
  });
}

initializeTimeRangeChoices();
updateThresholdPresetUi();
renderComposerDfaOptions();
bindEvents();
renderHistory();
autoResizeComposer();
renderPending();
renderRevisionThread();
updateComposerMode();
window.addEventListener("online", checkApi);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") checkApi();
});
checkApi();
