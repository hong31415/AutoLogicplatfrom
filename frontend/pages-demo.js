(() => {
  const DB_NAME = "autologic-pages-demo-v1";
  const DB_VERSION = 1;
  const STORES = ["templateDfas", "jobs", "runs"];
  const DOMAIN_DEFINITIONS = {
    precious_metals: {
      domain: "Precious Metals",
      labels: ["投资建议", "行业观点", "行情回顾", "行业跟踪", "风险提示"],
      materials: ["价格走势", "利率与汇率", "供给变化", "需求变化", "库存变化", "风险信号"]
    },
    etf: {
      domain: "ETF",
      labels: ["市场概览", "资金流向", "行业配置", "产品筛选", "风险提示"],
      materials: ["指数表现", "成交额", "资金净流入", "估值水平", "跟踪误差", "风险信号"]
    },
    macro: {
      domain: "Macro",
      labels: ["制造业与工业", "房地产", "消费与投资", "出口外需", "价格与政策", "风险提示"],
      materials: ["制造业 PMI", "工业增加值", "房地产销售", "社会消费品零售", "出口", "CPI / PPI"]
    },
    cotton: {
      domain: "Cotton",
      labels: ["行情回顾", "供给分析", "需求分析", "库存与基差", "策略建议", "风险提示"],
      materials: ["期现价格", "种植面积", "产量", "纺织开工", "商业库存", "基差"]
    },
    agriculture: {
      domain: "Agriculture",
      labels: ["市场综述", "供给跟踪", "需求跟踪", "库存与贸易", "策略建议", "风险提示"],
      materials: ["现货价格", "产量", "消费", "库存", "进出口", "天气与政策"]
    }
  };

  function openDatabase() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        STORES.forEach((name) => {
          if (!request.result.objectStoreNames.contains(name)) request.result.createObjectStore(name, { keyPath: "id" });
        });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("浏览器数据库初始化失败"));
    });
  }

  async function transact(storeName, mode, action) {
    const database = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction(storeName, mode);
      const store = transaction.objectStore(storeName);
      const request = action(store);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("浏览器数据库操作失败"));
      transaction.oncomplete = () => database.close();
      transaction.onerror = () => reject(transaction.error || new Error("浏览器数据库事务失败"));
    });
  }

  const dbPut = (store, value) => transact(store, "readwrite", (target) => target.put(value));
  const dbGet = (store, id) => transact(store, "readonly", (target) => target.get(id));
  const dbGetAll = (store) => transact(store, "readonly", (target) => target.getAll());

  function domainKey(payload = {}) {
    const requested = String(payload.custom_dfa?.baseDomain || payload.domain || "").toLowerCase();
    if (DOMAIN_DEFINITIONS[requested]) return requested;
    const query = String(payload.query || "");
    if (/ETF|基金|指数/i.test(query)) return "etf";
    if (/棉花|棉纺|棉纱/.test(query)) return "cotton";
    if (/农产品|大豆|玉米|生猪|粮食/.test(query)) return "agriculture";
    if (/宏观|制造业|房地产|CPI|PPI|出口/.test(query)) return "macro";
    return "precious_metals";
  }

  function internalDfa(label, materials, support) {
    const states = [
      { id: "I00", stage: "entry", label: "状态入口", detail: `接收“${label}”的用户约束与上游摘要。`, support_documents: support },
      ...materials.slice(0, 4).map((material, index) => ({ id: `M0${index + 1}`, stage: "material", label: material, detail: `绑定演示材料：${material}`, support_documents: support })),
      { id: "V00", stage: "evidence", label: "证据汇合", detail: "检查数据期、来源和字段完整性。", support_documents: support },
      { id: "C01", stage: "condition", label: `进入条件 · 用户要求“${label}”`, detail: `query.intent == '${label}'`, support_documents: support },
      { id: "G00", stage: "generation", label: `生成“${label}”`, detail: "按状态规则组织演示事实与判断。", support_documents: support },
      { id: "Q00", stage: "validation", label: "引用与冲突复核", detail: "标记演示证据，不作为真实投资依据。", support_documents: support },
      { id: "O00", stage: "output", label: "段落输出", detail: "输出段落并传递状态摘要。", support_documents: support }
    ];
    const materialIds = states.filter((state) => state.stage === "material").map((state) => state.id);
    const transitions = [
      ...materialIds.map((id) => ({ source: "I00", target: id, condition: "required binding", support_documents: support })),
      ...materialIds.map((id) => ({ source: id, target: "V00", condition: "binding ready", support_documents: support })),
      { source: "V00", target: "C01", condition: `query.intent == '${label}'`, support_documents: support },
      { source: "C01", target: "G00", condition: "branch accepted", support_documents: support },
      { source: "G00", target: "Q00", condition: "draft ready", support_documents: support },
      { source: "Q00", target: "O00", condition: "validation passed", support_documents: support }
    ];
    return { states, transitions, sequence_patterns: [], source_case_files: 24, source_documents: 48 };
  }

  function buildTemplate(payload = {}) {
    if (payload.custom_dfa?.nodes?.length) {
      const custom = structuredClone(payload.custom_dfa);
      custom.nodes = custom.nodes.map((node, index) => ({
        ...node,
        x: Number(node.x ?? (index === 0 ? 50 : 310 + ((index - 1) % 3) * 260)),
        y: Number(node.y ?? (index === 0 ? 240 : 80 + Math.floor((index - 1) / 3) * 170)),
        internal_dfa: node.internal_dfa || internalDfa(node.label || node.id, node.materials || [], 24)
      }));
      custom.viewport = custom.viewport || [0, 0, 1100, 600];
      return custom;
    }
    const key = domainKey(payload);
    const definition = DOMAIN_DEFINITIONS[key];
    const nodes = [{
      id: "S0", label: `${definition.domain} 报告任务入口`, type: "root", x: 50, y: 245,
      guideline: "根据用户意图选择可执行写作状态。", materials: [], parent: null, level: 0,
      support_documents: null, internal_dfa: internalDfa("报告任务入口", ["用户意图", "需求范围", "时间范围", "阈值配置"], 48)
    }];
    definition.labels.forEach((label, index) => {
      const column = Math.floor(index / 2);
      const row = index % 2;
      const support = 4200 - index * 370;
      nodes.push({
        id: `S${index + 1}`, label, type: "leaf", x: 310 + column * 270, y: 95 + row * 300,
        guideline: `围绕“${label}”组织可核验事实、判断与风险边界。`,
        materials: definition.materials.slice(index % 2, index % 2 + 4), parent: "S0", level: 1,
        support_documents: support, frequency: Number((0.72 - index * 0.06).toFixed(2)),
        internal_dfa: internalDfa(label, definition.materials.slice(index % 2, index % 2 + 4), support)
      });
    });
    const edges = [];
    definition.labels.forEach((label, index) => {
      edges.push({ id: `T${String(edges.length + 1).padStart(3, "0")}`, source: "S0", target: `S${index + 1}`, condition_label: `用户意图要求“${label}”`, support_documents: 4200 - index * 370 });
      if (index > 0) edges.push({ id: `T${String(edges.length + 1).padStart(3, "0")}`, source: `S${index}`, target: `S${index + 1}`, condition_label: "稳定后继", direct: true, support_documents: 2600 - index * 210 });
    });
    return { nodes, edges, viewport: [0, 0, 1120, 600] };
  }

  function selectStates(payload, template) {
    const query = String(payload.query || "");
    const leaves = template.nodes.filter((node) => node.type !== "root");
    const scores = leaves.map((node, index) => {
      const direct = query.includes(node.label);
      const risk = /风险/.test(query) && /风险/.test(node.label);
      const score = direct || risk ? 0.94 : Math.max(0.31, 0.78 - index * 0.08);
      return { id: node.id, label: node.label, score, similarity: score };
    }).sort((left, right) => right.score - left.score);
    const comprehensive = /同时|完整|全部|全链路|深度|周报/.test(query);
    const requestedCount = comprehensive ? Math.min(5, leaves.length) : Math.min(Math.max(3, Number(payload.fallback_top_k || 3)), leaves.length);
    const chosen = scores.slice(0, requestedCount).sort((left, right) => leaves.findIndex((node) => node.id === left.id) - leaves.findIndex((node) => node.id === right.id));
    return { ranked: scores, matched: chosen };
  }

  function routeFor(template, matched) {
    const ids = matched.map((item) => item.id);
    const edgeIds = [];
    let source = "S0";
    ids.forEach((target) => {
      const direct = template.edges.find((edge) => edge.source === source && edge.target === target)
        || template.edges.find((edge) => edge.source === "S0" && edge.target === target);
      if (direct) edgeIds.push(direct.id);
      source = target;
    });
    return { node_ids: ["S0", ...ids], edge_ids: edgeIds };
  }

  function demoSection(label, query, date, index, language) {
    if (language === "en") {
      return `Demo result for “${label}”: AutoLogic matched this section to the request, bound a built-in point-in-time sample dated ${date}, and assembled it as step ${index + 1}. This content demonstrates the DFA workflow only; deploy the Python API for live market data and model-generated conclusions.`;
    }
    const statements = {
      投资建议: "演示路径建议先确认实际利率与美元方向，再结合价格趋势分层配置；在真实运行中，系统会用最新市场数据替换此示例。",
      行业观点: "演示状态显示价格、宏观与供需信息需要联合判断，当前仅用于展示证据绑定和状态转移方式。",
      行情回顾: "演示数据记录了价格、涨跌幅与成交变化，并按查询时间范围进行时点校验；这里不代表实时行情。",
      行业跟踪: "演示流程将库存、供给、需求及政策事件绑定到同一写作状态，再向后继状态传递摘要。",
      风险提示: "需关注利率、汇率、价格波动、流动性及数据滞后风险；正式结论必须使用可核验的实时来源。"
    };
    return `${statements[label] || `系统已将“${label}”匹配到当前查询，并完成演示证据绑定与段落组装。`} 本段生成于 ${date}，输入主题为“${query.slice(0, 60)}${query.length > 60 ? "…" : ""}”。`;
  }

  function buildAnalysis(payload = {}) {
    const key = domainKey(payload);
    const definition = DOMAIN_DEFINITIONS[key];
    const template = buildTemplate(payload);
    const selection = selectStates(payload, template);
    const route = routeFor(template, selection.matched);
    const date = new Date().toISOString().slice(0, 10);
    const language = payload.language === "en" ? "en" : "zh";
    const order = selection.matched.map((item) => item.id);
    const materials = {};
    const sections = order.map((nodeId, index) => {
      const node = template.nodes.find((item) => item.id === nodeId);
      const record = { date, close: Number((2380 + index * 37.6).toFixed(2)), pct_chg: Number((0.8 - index * 0.17).toFixed(2)), volume: 128400 + index * 11300 };
      materials[nodeId] = {
        node_id: nodeId, label: node.label, required_materials: node.materials || [],
        retrieved_facts: [`内置演示数据已绑定到“${node.label}”`, `数据日期：${date}`],
        ifind_bindings: [{ status: "found", provider: "Built-in Demo Dataset", endpoint: `${key}.sample`, instrument: node.label, state_label: node.label, date, records: [record] }]
      };
      return { node_id: nodeId, label: node.label, order: index + 1, content: demoSection(node.label, String(payload.query || "演示查询"), date, index, language), evidence_verified: true, evidence_status: "demo" };
    });
    return {
      query: String(payload.query || "AutoLogic 在线演示"), tau: Number(payload.tau || 0.2), theta: Number(payload.theta || 0.5), date,
      domain: definition.domain, constraints: { date, domain: definition.domain, report_type: "query-specific demo report" },
      template, ranked: selection.ranked, matched: selection.matched,
      subtree_root: "S0", raw_subdfa: route, subdfa: route, execution_order: order, materials,
      report_sections: sections, report_status: "complete",
      evidence_summary: { total_bindings: sections.length, found_bindings: sections.length, provider: "Built-in Demo Dataset" },
      runtime: {
        domain_key: key, domain: definition.domain, language, artifact_mode: "browser-demo", dfa_source: payload.custom_dfa ? "user" : "system",
        user_dfa: payload.custom_dfa ? { name: payload.custom_dfa.name || "用户写作图" } : null,
        rebuilt: false, fallback_top_k: Number(payload.fallback_top_k || 3),
        induction: { documents: 48, case_files: 24, frequency_threshold: 0.3, sequence_patterns: 6 },
        evidence: { enabled: true, requested: true, used: true, mode: "demo-snapshot", source: "browser", status: "found", providers_used: ["Built-in Demo Dataset"], summary: { total: sections.length, found: sections.length }, providers: { "Built-in Demo Dataset": { status: "found", calls: sections.length, found: sections.length, errors: [] } } }
      }
    };
  }

  function decodeTextFile(file) {
    try {
      const extension = String(file.name || "").split(".").pop().toLowerCase();
      if (!["txt", "md", "csv", "json", "html", "htm"].includes(extension)) return "";
      const binary = atob(String(file.content_base64 || ""));
      const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
      return new TextDecoder("utf-8", { fatal: false }).decode(bytes).slice(0, 250000);
    } catch (_error) {
      return "";
    }
  }

  function extractHeadings(files, fallbackLabels) {
    const headings = [];
    files.forEach((file) => {
      const text = decodeTextFile(file);
      text.split(/\r?\n/).forEach((line) => {
        const cleaned = line.trim().replace(/^#{1,6}\s*/, "").replace(/^[一二三四五六七八九十0-9]+[、.．]\s*/, "").trim();
        if (cleaned.length >= 2 && cleaned.length <= 28 && (/^#{1,6}\s/.test(line.trim()) || /^[一二三四五六七八九十0-9]+[、.．]/.test(line.trim()))) headings.push(cleaned);
      });
      fallbackLabels.forEach((label) => { if (text.includes(label)) headings.push(label); });
    });
    return [...new Set(headings)].slice(0, 8);
  }

  async function createTemplateJob(payload) {
    const key = DOMAIN_DEFINITIONS[payload.domain] ? payload.domain : domainKey({ query: `${payload.name || ""} ${payload.category || ""}` });
    const definition = DOMAIN_DEFINITIONS[key];
    const labels = extractHeadings(payload.files || [], definition.labels);
    const selectedLabels = labels.length >= 2 ? labels : definition.labels.slice(0, Math.max(3, Math.min(6, (payload.files || []).length + 2)));
    const id = `browser-dfa-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const nodes = [{ id: "S0", label: `${payload.name || "上传模板"}入口`, type: "root", materials: [], parent: null, level: 0 }];
    selectedLabels.forEach((label, index) => nodes.push({ id: `S${index + 1}`, label, type: "leaf", materials: definition.materials.slice(index % 2, index % 2 + 4), parent: "S0", level: 1, guideline: `根据上传模板归纳“${label}”的写作要求。`, support_documents: (payload.files || []).length }));
    const edges = selectedLabels.map((_label, index) => ({ id: `T${String(index + 1).padStart(3, "0")}`, source: index === 0 ? "S0" : `S${index}`, target: `S${index + 1}`, condition_label: index === 0 ? "用户意图匹配" : "模板稳定顺序", direct: index > 0 }));
    const files = (payload.files || []).map((file) => ({ name: file.name, type: file.type, size: file.size }));
    const quality = { document_count: files.length, state_count: selectedLabels.length, transition_count: edges.length, frequency_threshold: Number(payload.frequency_threshold || 0.3), confidence: files.length >= 3 ? "high" : "medium", file_errors: [] };
    const graph = { id, name: payload.name || `${definition.domain} · 浏览器模板写作图`, baseDomain: key, category: payload.category || "未分类模板", nodes, edges, files, quality, origin: "browser-template-demo", createdAt: new Date().toISOString() };
    await dbPut("templateDfas", { id, name: graph.name, domain: key, category: graph.category, graph, files, quality, archived: false });
    const jobId = `browser-job-${Date.now()}`;
    const now = new Date().toLocaleTimeString();
    const job = { id: jobId, job_id: jobId, status: "complete", stage: "complete", progress: 100, message: "浏览器端模板解析与 DFA 归纳已完成。", result_dfa_id: id, quality, logs: [
      { time: now, message: `读取 ${files.length} 个模板文件` },
      { time: now, message: `抽取并对齐 ${selectedLabels.length} 个写作状态` },
      { time: now, message: `归纳 ${edges.length} 条稳定转移` },
      { time: now, message: "已保存到当前浏览器数据库" }
    ] };
    await dbPut("jobs", job);
    return { ...job, status: "running", stage: "extracting", progress: 12, message: "正在浏览器中解析模板。" };
  }

  async function apiPost(path, payload = {}) {
    if (path === "/pipeline/preview") return { analysis: buildAnalysis(payload), run_id: null, ai_used: false, model: "Browser Demo Engine" };
    if (path === "/reports/generate") {
      const analysis = buildAnalysis(payload);
      const runId = `browser-run-${Date.now()}`;
      const result = { id: runId, run_id: runId, analysis, report_sections: analysis.report_sections, ai_used: false, model: "Browser Demo Engine", status: "complete" };
      await dbPut("runs", result);
      return result;
    }
    if (path === "/reports/refine") {
      const instruction = String(payload.instruction || "").trim();
      const sections = (payload.sections || []).map((section) => ({ ...section, content: `${section.content}\n\n演示调整：已根据“${instruction}”重新组织本节表达。` }));
      return { report_sections: sections, ai_used: false, model: "Browser Demo Engine" };
    }
    if (path === "/template-dfa-jobs") return createTemplateJob(payload);
    if (path === "/template-dfas/archive") {
      const item = await dbGet("templateDfas", String(payload.id || ""));
      if (item) await dbPut("templateDfas", { ...item, archived: true });
      return { ok: true };
    }
    throw new Error(`在线演示暂不支持：${path}`);
  }

  async function apiGet(path) {
    if (path === "/template-dfas") {
      const items = (await dbGetAll("templateDfas")).filter((item) => !item.archived);
      return { items };
    }
    if (path.startsWith("/template-dfa-jobs/")) return dbGet("jobs", decodeURIComponent(path.split("/").pop()));
    if (path.startsWith("/template-dfas/")) return dbGet("templateDfas", decodeURIComponent(path.split("/").pop()));
    if (path.startsWith("/runs/")) return dbGet("runs", decodeURIComponent(path.split("/").pop()));
    throw new Error(`在线演示暂不支持：${path}`);
  }

  window.AutoLogicPagesDemo = { apiPost, apiGet, buildAnalysis, databaseName: DB_NAME };
})();
