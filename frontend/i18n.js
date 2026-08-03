(() => {
  const STORAGE_KEY = "autologic-language-v1";
  const language = localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "zh";
  const exact = new Map(Object.entries({
    "新建任务": "New Task",
    "切换国际版": "Switch Language",
    "查看离线 DFA": "View Offline DFA",
    "我的 DFA": "My DFA",
    "最近任务": "Recent Tasks",
    "运行配置": "Runtime Settings",
    "报告领域": "Report Domain",
    "自动识别": "Auto Detect",
    "贵金属 / 有色": "Precious & Base Metals",
    "宏观": "Macro",
    "棉花": "Cotton",
    "农产品": "Agriculture",
    "写作模式频率阈值 θ": "Writing-pattern frequency θ",
    "高级参数": "Advanced Parameters",
    "状态匹配阈值 τ": "State match threshold τ",
    "市场证据源": "Market Evidence Source",
    "自动选择（AkShare + Tushare）": "Auto Select (AkShare + Tushare)",
    "离线演示": "Offline Demo",
    "语义 Embedding": "Semantic Embedding",
    "重新诱导写作 DFA": "Re-induce Writing DFA",
    "忽略本地 DFA 缓存": "Ignore Local DFA Cache",
    "正在检查服务": "Checking Services",
    "服务已连接": "Services Connected",
    "写作 DFA": "Writing DFA",
    "证据源": "Evidence Source",
    "本地材料": "Local Materials",
    "等待任务": "Waiting for Task",
    "证据驱动报告工作台": "Evidence-Driven Report Workspace",
    "连接中": "Connecting",
    "让证据决定报告的下一步": "Let Evidence Determine the Next Step",
    "全局 DFA": "Global DFA",
    "对话解析": "Query Parsing",
    "状态匹配": "State Matching",
    "SubDFA 构建": "SubDFA Construction",
    "数据证据": "Data Evidence",
    "数据与证据": "Data & Evidence",
    "报告生成": "Report Generation",
    "黄金周报": "Gold Weekly",
    "有色金属跟踪": "Base Metals Tracker",
    "宏观专题": "Macro Research",
    "需求范围": "Research Scope",
    "时间范围": "Time Range",
    "选择示例": "Select Example",
    "证据驱动": "Evidence Driven",
    "系统 DFA": "System DFA",
    "我的 DFA · 宏观研究 · 自定义 DFA": "My DFA · Macro Research · Custom DFA",
    "按垂类自动选择": "Auto-select by domain",
    "结构": "Structure",
    "均衡": "Balanced",
    "核心": "Core",
    "全面": "Comprehensive",
    "输入报告主题、目标读者和关注重点": "Enter the report topic, target audience, and key focus",
    "发送并生成报告": "Send and Generate Report",
    "Enter 发送 · Shift+Enter 换行": "Enter to send · Shift+Enter for a new line",
    "选择生成报告使用的 DFA": "Choose the DFA used to generate the report",
    "设置 DFA 信息范围": "Configure DFA Information Scope",
    "本次生成使用的 DFA": "DFA Used for This Run",
    "DFA 来源": "DFA Source",
    "系统 DFA · 按垂类自动选择": "System DFA · Auto-select by domain",
    "管理 / 构建我的 DFA": "Manage / Build My DFA",
    "DFA 信息范围": "DFA Information Scope",
    "频率阈值 θ": "Frequency Threshold θ",
    "匹配阈值 τ": "Match Threshold τ",
    "关闭": "Close",
    "离线全局 DFA": "Offline Global DFA",
    "读取本地已诱导的写作结构。": "Load the locally induced writing structure.",
    "报告领域": "Report Domain",
    "切换结构": "Switch Structure",
    "我的垂类结构": "My Domain Structures",
    "导入系统垂类": "Import a System Domain",
    "导入为我的 DFA": "Import as My DFA",
    "导入创建独立副本，不修改系统训练模板。": "Importing creates an independent copy and does not modify the system template.",
    "还没有用户 DFA": "No User DFA Yet",
    "从左侧选择一个系统垂类导入，即可开始构建自己的段落状态机。": "Import a system domain from the left to start building your own paragraph state machine.",
    "DFA 名称": "DFA Name",
    "＋ 添加段落": "+ Add Section",
    "保存结构": "Save Structure",
    "删除": "Delete",
    "基础垂类": "Base Domain",
    "段落状态": "Section States",
    "状态转移": "State Transitions",
    "材料规则": "Material Rules",
    "节点名称": "Node Name",
    "写作规则": "Writing Rules",
    "材料要求": "Material Requirements",
    "每行一项": "One per line",
    "删除该段落节点": "Delete This Section Node",
    "添加转移": "Add Transition",
    "关闭我的 DFA": "Close My DFA",
    "用户 DFA 保存在当前浏览器本机存储中；系统原始 DFA 始终保持只读并可重新导入。": "User DFAs are stored locally in this browser. Original system DFAs remain read-only and can always be re-imported.",
    "你的问题": "Your Request",
    "正在启动 AutoLogic": "Starting AutoLogic",
    "运行中": "Running",
    "跳到结果": "Skip to Result",
    "Primary Output": "Primary Output",
    "生成报告": "Generated Report",
    "等待生成": "Waiting to Generate",
    "复制报告": "Copy Report",
    "下载 Markdown 报告": "Download Markdown Report",
    "SubDFA 构建与执行轨迹": "SubDFA Construction & Execution Trace",
    "动态构建": "Dynamic Construction",
    "完整 DFA": "Full DFA",
    "放大查看 SubDFA": "Expand SubDFA",
    "等待 SubDFA 构建": "Waiting for SubDFA Construction",
    "当前构建对象": "Current Construction Target",
    "初始化全局 DFA": "Initialize Global DFA",
    "构建依据": "Construction Basis",
    "当前产出": "Current Output",
    "等待解析用户对话": "Waiting to Parse the User Request",
    "等待构建本次 SubDFA": "Waiting to Build This SubDFA",
    "运行明细与数据来源": "Runtime Details & Data Sources",
    "继续调整报告": "Refine Report",
    "发送修改要求": "Send Revision Request",
    "完整报告": "Full Report",
    "报告组装完成": "Report Assembly Complete",
    "已完成": "Complete",
    "回看": "Review",
    "执行中": "Executing",
    "正在执行": "Executing",
    "等待执行": "Waiting",
    "已完成": "Complete",
    "读取我的 DFA": "Load My DFA",
    "读取系统全局 DFA": "Load System Global DFA",
    "解析当前对话": "Parse Current Query",
    "计算 Query 与状态的语义匹配": "Match Query Semantics to States",
    "筛选命中状态": "Filter Matched States",
    "合并候选状态路径": "Merge Candidate State Paths",
    "应用条件约束选择路径": "Apply Conditions and Select Path",
    "本次对话 SubDFA 构建完成": "SubDFA Construction Complete",
    "本次 SubDFA 已构建完成": "SubDFA Ready",
    "SubDFA 构建过程": "SubDFA Construction Process",
    "报告生成过程": "Report Generation Process",
    "当前写作状态": "Current Writing State",
    "当前证据状态": "Current Evidence State",
    "状态级证据": "State-Level Evidence",
    "数据处理": "Data Processing",
    "报告产出": "Report Output",
    "最终报告": "Final Report",
    "报告组装受阻": "Report Assembly Blocked",
    "报告未生成": "Report Not Generated",
    "证据受阻": "Evidence Blocked",
    "数据获取与证据血缘": "Data Retrieval & Evidence Lineage",
    "数据源连接": "Data Source Connections",
    "已获取数据": "Retrieved Data",
    "连接数据源": "Connected Sources",
    "已验证数据集": "Verified Datasets",
    "时点记录": "Point-in-Time Records",
    "最新数据期": "Latest Data Period",
    "接口级去重": "Endpoint-Level Deduplication",
    "纳入证据缓存": "Included in Evidence Cache",
    "发布日校验通过": "Release-Date Validation Passed",
    "来源 / 标的": "Source / Instrument",
    "接口 / 关键信号": "Endpoint / Key Signal",
    "数据期": "Data Period",
    "覆盖状态": "Covered State",
    "质量": "Quality",
    "状态绑定": "State Binding",
    "已验证": "Verified",
    "报告正文未生成": "Report Body Was Not Generated",
    "可验证证据": "Verified Evidence",
    "计划章节": "Planned Sections",
    "查看内部 DFA": "View Internal DFA",
    "收起内部 DFA": "Collapse Internal DFA",
    "入口状态": "Entry State",
    "材料绑定": "Material Binding",
    "证据汇合": "Evidence Aggregation",
    "证据事件": "Evidence Event",
    "条件决策": "Condition Decision",
    "段落生成": "Section Generation",
    "引用校验": "Citation Validation",
    "段落输出": "Section Output",
    "高频数据观察": "High-Frequency Indicators",
    "工业": "Industrial Activity",
    "地产": "Real Estate",
    "内需": "Domestic Demand",
    "外需": "External Demand",
    "价格": "Prices and Inflation",
    "风险提示": "Risk Factors",
    "政策跟踪": "Policy Tracking",
    "行情回顾": "Market Review",
    "行业跟踪": "Industry Tracking",
    "行业观点": "Industry View",
    "投资建议": "Investment Recommendations"
    ,"模型": "Model"
    ,"未配置": "Not Configured"
    ,"AutoLogic 方法流程": "AutoLogic Workflow"
    ,"金融研究工作台": "Financial Research Workspace"
    ,"AutoLogic 自动化与业务增长工作台": "AutoLogic Automation and Business Growth Workspace"
    ,"多状态 · 深度周报": "Multi-state · In-depth Weekly"
    ,"多状态 · 铜铝供需": "Multi-state · Copper & Aluminum Supply-Demand"
    ,"全链路 · 宏观专题": "Full Pipeline · Macro Research"
    ,"如：黄金现货、COMEX 与国内市场": "e.g. spot gold, COMEX, and the domestic market"
    ,"如：2025-06-02 至 2025-06-08": "e.g. 2025-06-02 to 2025-06-08"
    ,"选择时间示例": "Select a Time Example"
    ,"推荐 · 2025-06-02 至 2025-06-08": "Recommended · 2025-06-02 to 2025-06-08"
    ,"2025年12月1日至12月7日": "Dec 1–7, 2025"
    ,"2026年1月": "January 2026"
    ,"2026年第一季度": "Q1 2026"
    ,"截至 2026-03-31": "As of 2026-03-31"
    ,"宏观研究": "Macro Research"
    ,"宏观研究 · 自定义 DFA": "Macro Research · Custom DFA"
    ,"自定义 DFA": "Custom DFA"
    ,"iFinD（未配置）": "iFinD (Not Configured)"
    ,"当前运行模式": "Current Runtime Mode"
    ,"执行视图": "Execution View"
    ,"写作 DFA 执行图": "Writing DFA Execution Graph"
    ,"尚未检索证据": "No evidence retrieved yet"
    ,"等待条件判定": "Waiting for condition evaluation"
    ,"正在准备 AutoLogic": "Preparing AutoLogic"
    ,"正在载入离线全局 DFA": "Loading the offline global DFA"
    ,"跳到最终结果": "Skip to Final Result"
    ,"继续调整报告，例如：缩短结论，并加强风险提示": "Refine the report, e.g. shorten the conclusion and strengthen risk factors"
    ,"生成过的报告会保留在这里。": "Generated reports will be saved here."
    ,"自动识别": "Auto Detect"
    ,"失败": "Failed"
    ,"刚刚": "Just now"
    ,"你": "You"
    ,"自定义": "Custom"
    ,"状态": "states"
    ,"截止": "As of"
    ,"已校验": "Validated"
    ,"已连接": "Connected"
    ,"接口返回": "endpoints returned"
    ,"解析对话并匹配语义状态": "Parsing the query and matching semantic states"
    ,"等待条件标注写作 DFA": "Waiting to annotate the Writing DFA conditions"
    ,"沿已执行路径组装": "Assembled along the executed path:"
    ,"到达终止状态 F，按执行顺序组装文档": "Reached terminal state F and assembled the document in execution order"
    ,"完成截止日、发布日与记录完整性校验": "Cutoff date, release date, and record completeness validated"
    ,"中国CPI": "China CPI"
    ,"中国PPI": "China PPI"
    ,"中国PMI": "China PMI"
    ,"中国GDP": "China GDP"
    ,"CPI同比": "CPI YoY"
    ,"CPI环比": "CPI MoM"
    ,"PPI同比": "PPI YoY"
    ,"当月": "Current month"
    ,"制造业PMI": "Manufacturing PMI"
    ,"非制造业PMI": "Non-manufacturing PMI"
    ,"GDP同比": "GDP YoY"
    ,"国内生产总值-绝对值": "GDP (absolute value)"
    ,"2026年6月1日，全国CPI同比上涨1%，环比下降0.3%；2026年6月1日，PPI同比上涨4.1%": "On June 1, 2026, China CPI rose 1% YoY and fell 0.3% MoM; PPI rose 4.1% YoY."
    ,"供给变化走弱/减少，转入": "Supply conditions weaken or decline; transition to "
    ,"价格走势出现，转入": "A price trend emerges; transition to "
    ,"供给变化走强/增加，转入": "Supply conditions strengthen or increase; transition to "
    ,"风险信号波动/不确定，转入": "Risk signals fluctuate or remain uncertain; transition to "
    ,"来自": "From"
    ,"第一产业-绝对值": "Primary industry (absolute value)"
    ,"生成报告片段": "Generate Report Section"
    ,"该图来自本机缓存的全局写作 DFA；本窗口不会调用市场数据或生成报告。": "This graph comes from the locally cached global Writing DFA. This window does not call market-data services or generate a report."
    ,"离线全局 DFA 结构图": "Offline Global DFA Structure Graph"
  }));

  const replacements = [
    ["正在根据全局 DFA 与当前对话构建 SubDFA。", "Building a SubDFA from the global DFA and the current query."],
    ["当前只展示结构推导，不提前显示报告正文。", "Only structural reasoning is shown at this stage; report prose remains hidden."],
    ["结构已锁定，下一步开始逐状态检索证据；完整正文将在全部状态生成后统一展示。", "The structure is locked. Evidence retrieval now runs state by state; the full report will appear only after every state is complete."],
    ["所有状态片段完成并按 SubDFA 顺序组装后，再统一显示最终文章。", "The final report will appear only after all state sections are completed and assembled in SubDFA order."],
    ["系统结构或你保存的自定义结构，将用于构建本次 SubDFA。", "Choose a system structure or a saved custom structure for this SubDFA."],
    ["当前将使用系统训练得到的全局 DFA。", "The system-trained global DFA will be used."],
    ["本次将使用", "This run will use "],
    ["构建 SubDFA", "to build the SubDFA"],
    ["个可执行写作状态", " executable writing states"],
    ["个写作状态", " writing states"],
    ["个状态片段", " state sections"],
    ["个状态", " states"],
    ["条稳定转移", " stable transitions"],
    ["条候选转移", " candidate transitions"],
    ["条可执行转移", " executable transitions"],
    ["条转移", " transitions"],
    ["个数据源", " data sources"],
    ["个数据集", " datasets"],
    ["条时点记录", " point-in-time records"],
    ["条记录", " records"],
    ["第 ", "Step "],
    ["步骤 ", "Step "],
    ["状态片段已生成", "State section generated"],
    ["正在生成", "Generating"],
    ["等待前序状态", "Waiting for previous state"],
    ["用户副本", "User Copy"],
    ["自定义结构", "Custom Structure"],
    ["我的 DFA", "My DFA"],
    ["系统 DFA", "System DFA"],
    ["用户意图要求该段落", "User intent requests this section"],
    ["用户意图要求", "User intent requests"],
    ["执行顺序", "Execution order"],
    ["当前子图", "Current subgraph"],
    ["当前", "Current"],
    ["报告片段", "report section"],
    ["生成", "Generate"],
    ["获取数据与证据", "Retrieve Data & Evidence"],
    ["组装路径判定", "Assembly Path Decision"],
    ["报告组装", "Report Assembly"],
    ["复用缓存", "Cache Reused"],
    ["本次重建", "Rebuilt for This Run"],
    ["正在调用模型生成报告", "Generating Report with the Model"],
    ["报告生成中", "Generating Report"],
    ["生成完成", "Generation Complete"],
    ["运行失败", "Run Failed"],
    ["请先输入报告需求", "Please enter a report request first"]
  ];

  function translateText(value) {
    if (language !== "en" || !value || !/[\u3400-\u9fff]/.test(value)) return value;
    const trimmed = value.trim();
    if (exact.has(trimmed)) return value.replace(trimmed, exact.get(trimmed));
    let output = value;
    const phrases = [...replacements, ...exact.entries()].sort((left, right) => right[0].length - left[0].length);
    for (const [zh, en] of phrases) output = output.split(zh).join(en);
    output = output.replace(/(\d+)\s*段/g, "$1 sections");
    output = output.replace(/(\d+)\s*个State section generated/g, "$1 state sections generated");
    output = output.replaceAll("、", ", ").replaceAll("：", ": ");
    return output;
  }

  function isProtectedNode(node) {
    const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
    return Boolean(element?.closest?.(".history-query, .history-report-query, .history-report-sections"));
  }

  function translateElement(element) {
    if (!(element instanceof Element) || element.closest("script, style") || isProtectedNode(element)) return;
    for (const attribute of ["placeholder", "title", "aria-label", "alt"]) {
      if (element.hasAttribute(attribute)) {
        const value = element.getAttribute(attribute);
        const translated = translateText(value);
        if (translated !== value) element.setAttribute(attribute, translated);
      }
    }
  }

  function translateTree(root) {
    if (language !== "en" || !root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      if (isProtectedNode(root)) return;
      const translated = translateText(root.nodeValue);
      if (translated !== root.nodeValue) root.nodeValue = translated;
      return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return;
    if (root.nodeType === Node.ELEMENT_NODE) translateElement(root);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      if (node.nodeType === Node.TEXT_NODE) {
        if (isProtectedNode(node)) {
          node = walker.nextNode();
          continue;
        }
        const translated = translateText(node.nodeValue);
        if (translated !== node.nodeValue) node.nodeValue = translated;
      } else {
        translateElement(node);
      }
      node = walker.nextNode();
    }
  }

  document.documentElement.lang = language === "en" ? "en" : "zh-CN";
  window.AutoLogicI18n = { language, translateText, translateTree };
  translateTree(document.body);
  if (language === "en") {
    new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        mutation.addedNodes.forEach(translateTree);
        if (mutation.type === "characterData") translateTree(mutation.target);
        if (mutation.type === "attributes") translateElement(mutation.target);
      }
    }).observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["placeholder", "title", "aria-label", "alt"]
    });
  }

  const button = document.getElementById("languageToggleButton");
  if (button) {
    button.querySelector("strong").textContent = language === "en" ? "中文版" : "International";
    button.querySelector("small").textContent = language === "en" ? "切换中文" : "English";
    button.addEventListener("click", () => {
      localStorage.setItem(STORAGE_KEY, language === "en" ? "zh" : "en");
      window.location.reload();
    });
  }
})();
