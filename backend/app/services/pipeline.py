from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date as date_type, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.config import settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent


def configured_path(env_name: str, default: Path) -> Path:
    raw = os.environ.get(env_name, "").strip()
    path = Path(raw).expanduser() if raw else default
    return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


LOGICRAG_CODE_ROOT = configured_path("LOGICRAG_CODE_ROOT", BACKEND_ROOT / "logicrag_core")
FINLDP_ROOT = configured_path(
    "FINLDP_ROOT",
    PROJECT_ROOT / "data" / "FinLDP-Bench-6E26",
)
RUNTIME_ROOT = configured_path("SUBDFA_RUNTIME_ROOT", BACKEND_ROOT / "logicrag_runtime")
FULL_CORPUS_CASE_LIMIT = int(os.environ.get("AUTOLOGIC_MAX_CASE_FILES", "10000"))
FULL_CORPUS_PROFILE = "full-corpus-condition-dfa/v2"

if str(LOGICRAG_CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(LOGICRAG_CODE_ROOT))

from document_learner import (  # noqa: E402
    DEFAULT_EMBEDDING_BASE_URL,
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingProvider,
    StateMatch,
    build_embedding_index,
    build_global_template,
    node_sort_key,
    run_from_csv,
    save_json,
)
from autologic_learner import (  # noqa: E402
    AUTOLOGIC_SCHEMA_VERSION,
    induce_condition_labeled_dfa,
)
from query_processing import load_json, run_query_processing  # noqa: E402
from report_generator import get_template_nodes as get_report_nodes  # noqa: E402
from report_generator import is_executable_state  # noqa: E402
from ifind_data_plugin import run_data_plugin  # noqa: E402
from app.services.market_data import retrieve_market_materials  # noqa: E402


DOMAIN_SPECS: dict[str, dict[str, Any]] = {
    "precious_metals": {
        "dataset": "Precious_Metals",
        "domain": "Precious Metals",
        "title": "贵金属/有色金属",
        "match": r"precious|gold|silver|copper|aluminum|aluminium|metal|黄金|白银|贵金属|有色|铜|铝|工业金属|金属",
        "aliases": ["gold", "precious metals", "copper", "aluminum", "COMEX", "SHFE", "美元", "利率"],
    },
    "etf": {
        "dataset": "ETF",
        "domain": "ETF",
        "title": "ETF",
        "match": r"\bETF\b|fund|index|tracking|holding|基金|指数|宽基|行业ETF|资金流|持仓|跟踪误差|融资融券",
        "aliases": ["ETF", "fund flows", "index performance", "holdings", "valuation", "tracking error"],
    },
    "macro": {
        "dataset": "Macro",
        "domain": "Macro",
        "title": "宏观",
        "match": r"macro|GDP|CPI|PMI|inflation|employment|fiscal|monetary|宏观|经济|通胀|就业|财政|货币|社融|地产|内需|外需",
        "aliases": ["macro", "GDP", "CPI", "PMI", "inflation", "employment", "fiscal policy", "monetary policy"],
    },
    "cotton": {
        "dataset": "Cotton",
        "domain": "Cotton",
        "title": "棉花",
        "match": r"cotton|棉花|棉纱|纺织|郑棉",
        "aliases": ["cotton", "price", "supply", "demand", "strategy", "inventory"],
    },
    "agriculture": {
        "dataset": "Agriculture",
        "domain": "Agriculture",
        "title": "农产品/农业",
        "match": r"agriculture|corn|soybean|sugar|hog|农产品|农业|玉米|大豆|白糖|生猪|养殖|种植|饲料",
        "aliases": ["agriculture", "commodity", "price", "supply", "demand", "inventory", "weather"],
    },
}

GENERAL_SPEC = {
    "dataset": "",
    "domain": "General Research",
    "title": "通用研究",
    "match": r".*",
    "aliases": ["background", "facts", "metrics", "conclusion", "risk", "背景", "事实", "指标", "结论", "风险"],
}

SECTION_ALIASES: dict[str, list[str]] = {
    "投资建议": ["investment recommendation", "rating", "target price", "配置建议"],
    "行业观点": ["industry view", "sector view", "核心观点"],
    "行情回顾": ["market review", "performance review", "涨跌幅", "价格走势"],
    "行业跟踪": ["industry tracking", "copper", "aluminum", "gold", "供需", "库存"],
    "风险提示": ["risk warning", "downside risk", "不及预期"],
    "市场回顾": ["market review", "price performance"],
    "行业信息": ["industry information", "supply demand", "news"],
    "价格方面": ["price", "basis", "futures spot price"],
    "供给方面": ["supply", "production", "import", "weather"],
    "需求方面": ["demand", "consumption", "inventory"],
    "总结和策略": ["summary", "strategy", "outlook"],
    "二级市场概况": ["secondary market", "index performance", "turnover"],
    "ETF 产品概况": ["ETF products", "assets under management", "product overview"],
    "ETF 资金流情况": ["ETF fund flows", "subscription", "redemption"],
    "ETF 融资融券情况": ["margin trading", "securities lending"],
    "ETF 新发及上市情况": ["new ETF issuance", "listing"],
    "高频数据观察": ["high-frequency data", "macro tracking"],
    "工业": ["industrial production", "PMI", "manufacturing"],
    "地产": ["real estate", "property sales", "investment"],
    "内需": ["domestic demand", "consumption", "investment"],
    "外需": ["external demand", "export", "trade"],
    "价格": ["price", "CPI", "PPI", "inflation"],
    "背景回顾": ["background", "context"],
    "关键事实": ["facts", "evidence"],
    "指标分析": ["metrics", "indicator"],
    "结论判断": ["conclusion", "outlook"],
}

GENERAL_COLUMNS = ["背景回顾", "关键事实", "指标分析", "结论判断", "风险提示"]

ENGLISH_STATE_LABELS = {
    "报告任务入口": "Report Task Entry",
    "贵金属报告任务入口": "Precious Metals Report Task Entry",
    "Macro报告任务入口": "Macro Report Task Entry",
    "ETF报告任务入口": "ETF Report Task Entry",
    "棉花报告任务入口": "Cotton Report Task Entry",
    "农产品报告任务入口": "Agriculture Report Task Entry",
    "高频数据观察": "High-Frequency Indicators",
    "工业": "Industrial Activity",
    "地产": "Real Estate",
    "内需": "Domestic Demand",
    "外需": "External Demand",
    "价格": "Prices and Inflation",
    "风险提示": "Risk Factors",
    "政策跟踪": "Policy Tracking",
    "行情回顾": "Market Review",
    "市场回顾": "Market Review",
    "行业跟踪": "Industry Tracking",
    "行业信息": "Industry Information",
    "行业观点": "Industry View",
    "投资建议": "Investment Recommendations",
    "价格方面": "Price Trends",
    "供给方面": "Supply",
    "需求方面": "Demand",
    "总结和策略": "Summary and Strategy",
    "二级市场概况": "Secondary Market Overview",
    "ETF 产品概况": "ETF Product Overview",
    "ETF 资金流情况": "ETF Fund Flows",
    "ETF 融资融券情况": "ETF Margin Financing and Securities Lending",
    "ETF 新发及上市情况": "New ETF Issuance and Listings",
    "背景回顾": "Background",
    "关键事实": "Key Facts",
    "指标分析": "Indicator Analysis",
    "结论判断": "Conclusions",
}


@dataclass(frozen=True)
class RuntimeOptions:
    theta: float = 0.5
    preview_top_k: int = 8
    fallback_top_k: int = 3
    force_relearn: bool = False
    source_learning: bool = False
    use_ifind: bool = False
    ifind_dry_run: bool = False
    data_source: str = "auto"
    local_embedding_only: bool = True
    domain_override: str = ""
    language: str = "zh"


def bool_from_payload(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def options_from_payload(payload: dict[str, Any] | None = None) -> RuntimeOptions:
    payload = payload or {}
    remote_embedding_default = bool(settings.embedding_api_key)
    remote_embedding = bool_from_payload(payload.get("remote_embedding"), remote_embedding_default)
    selected_source = str(payload.get("data_source", settings.market_data_source or "auto")).strip().lower()
    if selected_source not in {"auto", "akshare", "tushare", "ifind", "demo", "none"}:
        selected_source = "auto"
    legacy_ifind = bool_from_payload(payload.get("use_ifind"), False)
    if "data_source" not in payload and legacy_ifind:
        selected_source = "ifind"
    return RuntimeOptions(
        theta=float(payload.get("theta", 0.5)),
        preview_top_k=int(payload.get("preview_top_k", 8)),
        fallback_top_k=int(payload.get("fallback_top_k", 3)),
        force_relearn=bool_from_payload(payload.get("force_relearn"), False),
        source_learning=bool_from_payload(payload.get("source_learning"), False),
        use_ifind=selected_source == "ifind" and settings.ifind_enabled,
        ifind_dry_run=bool_from_payload(payload.get("ifind_dry_run"), False),
        data_source=selected_source,
        local_embedding_only=not remote_embedding,
        domain_override=str(payload.get("domain", "")).strip(),
        language="en" if str(payload.get("language", "zh")).lower().startswith("en") else "zh",
    )


def embedding_runtime_config() -> dict[str, Any]:
    return {
        "model": settings.embedding_model or DEFAULT_EMBEDDING_MODEL,
        "base_url": settings.embedding_base_url or DEFAULT_EMBEDDING_BASE_URL,
        "batch_size": settings.embedding_batch_size or DEFAULT_EMBEDDING_BATCH_SIZE,
        "has_api_key": bool(settings.embedding_api_key),
    }


def desired_index_backend(options: RuntimeOptions) -> str:
    return "local-hash" if options.local_embedding_only else "api"


def make_embedding_provider(options: RuntimeOptions) -> EmbeddingProvider:
    embedding = embedding_runtime_config()
    return EmbeddingProvider(
        model=embedding["model"],
        base_url=embedding["base_url"],
        batch_size=embedding["batch_size"],
        allow_api=not options.local_embedding_only,
        local_dim=384,
    )


def _custom_dfa_text(value: Any, limit: int = 4000) -> str:
    return str(value or "").strip()[:limit]


def _custom_dfa_material_keys(materials: list[str]) -> list[str]:
    keys: list[str] = []
    for material in materials:
        match = re.search(r"\(([^()]+)\)\s*$", str(material))
        key = match.group(1).strip() if match else ""
        if key and key not in keys:
            keys.append(key)
    return keys or ["query.intent"]


def build_user_dfa_template(custom_dfa: dict[str, Any], domain_key: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Validate a browser-authored DFA and convert it to the executable LogicRAG schema."""
    raw_nodes = custom_dfa.get("nodes", [])
    raw_edges = custom_dfa.get("edges", [])
    if not isinstance(raw_nodes, list) or not 2 <= len(raw_nodes) <= 80:
        raise ValueError("用户写作图必须包含 2 至 80 个状态。")
    if not isinstance(raw_edges, list) or len(raw_edges) > 500:
        raise ValueError("用户写作图的状态转移不能超过 500 条。")

    node_ids: list[str] = []
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            raise ValueError("用户写作图节点格式无效。")
        node_id = _custom_dfa_text(raw_node.get("id"), 64)
        if not node_id or node_id in node_ids:
            raise ValueError("用户写作图节点 ID 不能为空且不能重复。")
        node_ids.append(node_id)

    root_candidates = [
        raw_node for raw_node in raw_nodes
        if str(raw_node.get("type", "")).lower() == "root" or int(raw_node.get("level") or 0) == 0
    ]
    if not root_candidates:
        raise ValueError("用户写作图缺少入口状态。")
    root_id = _custom_dfa_text(root_candidates[0].get("id"), 64)
    node_id_set = set(node_ids)
    nodes: list[dict[str, Any]] = []
    all_materials: set[str] = set()
    for index, raw_node in enumerate(raw_nodes):
        node_id = node_ids[index]
        is_root = node_id == root_id
        label = _custom_dfa_text(raw_node.get("label") or node_id, 120)
        materials = [
            _custom_dfa_text(item, 240)
            for item in (raw_node.get("materials", []) if isinstance(raw_node.get("materials", []), list) else [])
            if _custom_dfa_text(item, 240)
        ][:40]
        all_materials.update(materials)
        raw_children = raw_node.get("children", []) if isinstance(raw_node.get("children", []), list) else []
        children = [str(child) for child in raw_children if str(child) in node_id_set and str(child) != node_id]
        parent_value = raw_node.get("parent")
        parent = None if is_root else (str(parent_value) if str(parent_value) in node_id_set else root_id)
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "root" if is_root else "leaf",
                "template_description": label,
                "level": 0 if is_root else max(1, int(raw_node.get("level") or index)),
                "parent": parent,
                "children": children,
                "content_guideline": _custom_dfa_text(raw_node.get("guideline"), 8000)
                or f"围绕“{label}”生成独立报告段落，使用可核验材料并说明证据边界。",
                "required_materials": materials,
                "length": max(80, len(_custom_dfa_text(raw_node.get("guideline"), 8000))),
                "act": "route" if is_root else f"generate:{label}",
                "data": materials,
                "state_order": index,
                "state_frequency": max(0.0, min(1.0, float(raw_node.get("frequency") or 0.0))),
                "support_documents": max(0, int(raw_node.get("support_documents") or 0)),
                "index_exclude": is_root,
            }
        )

    transitions: list[dict[str, Any]] = []
    alphabet: list[dict[str, Any]] = []
    transition_function: list[dict[str, Any]] = []
    used_edge_ids: set[str] = set()
    for index, raw_edge in enumerate(raw_edges, start=1):
        if not isinstance(raw_edge, dict):
            continue
        source = _custom_dfa_text(raw_edge.get("source"), 64)
        target = _custom_dfa_text(raw_edge.get("target"), 64)
        if source not in node_id_set or target not in node_id_set or source == target:
            continue
        edge_id = _custom_dfa_text(raw_edge.get("id") or f"U{index:03d}", 64)
        if edge_id in used_edge_ids:
            edge_id = f"U{index:03d}"
        used_edge_ids.add(edge_id)
        label = _custom_dfa_text(raw_edge.get("condition_label") or "用户定义转移", 240)
        predicate = _custom_dfa_text(raw_edge.get("predicate") or "user.condition", 500)
        symbol_token = re.sub(r"[^A-Za-z0-9]+", "_", f"{source}_{target}_{index}").strip("_").upper()
        symbol = f"USER_{symbol_token or index}"
        target_materials = next((node["required_materials"] for node in nodes if node["node_id"] == target), [])
        evidence_schema = _custom_dfa_material_keys(target_materials)
        support = max(0, int(raw_edge.get("support_documents") or 0))
        frequency = max(0.000001, min(1.0, float(raw_edge.get("frequency") or 1.0)))
        condition = {
            "symbol": symbol,
            "label": label,
            "predicate": predicate,
            "evidence_schema": evidence_schema,
            "mode": "user-defined",
            "direct": predicate.upper() == "TRUE",
            "priority": index,
            "historical_support": support,
            "top_normalized_events": [],
        }
        transitions.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "condition_symbol": symbol,
                "condition_label": label,
                "condition": condition,
                "frequency": frequency,
                "support_documents": support,
                "priority": index,
                "direct": condition["direct"],
            }
        )
        alphabet.append(condition)
        transition_function.append({"source": source, "condition": symbol, "target": target})

    if not transitions:
        raise ValueError("用户写作图至少需要一条有效状态转移。")
    outgoing = {edge["source"] for edge in transitions}
    final_states = [node_id for node_id in node_ids if node_id not in outgoing and node_id != root_id]
    if not final_states:
        final_states = [node_ids[-1]]
    name = _custom_dfa_text(custom_dfa.get("name") or "我的写作图", 160)
    return {
        "template_id": f"user_{domain_key}_{hashlib.sha256(name.encode('utf-8')).hexdigest()[:12]}",
        "language": "zh",
        "template_description": f"{name} · 用户自定义写作图",
        "structure_pattern": {
            "reasoning_logic": "按用户自定义的段落状态、材料规则和状态转移动态构建查询执行图。",
            "node_types": ["root", "leaf"],
            "transitions": transitions,
        },
        "node_template": {"nodes": nodes},
        "material_requirements_summary": sorted(all_materials),
        "dfa": {
            "kind": "condition-labeled-semantic-dfa",
            "states": node_ids,
            "alphabet": alphabet,
            "transition_function": transition_function,
            "initial_state": root_id,
            "final_states": final_states,
            "deterministic": True,
        },
        "usage_instruction": {
            "offline": "用户在“我的写作图”中编辑并保存结构。",
            "online": "对当前问题匹配用户状态，并按用户转移构建确定性执行顺序。",
        },
        "logicrag_metadata": {
            "schema_version": "autologic-user-dfa/v1",
            "method": "user-authored-condition-dfa",
            "artifact_mode": "user-custom",
            "user_dfa_id": _custom_dfa_text(custom_dfa.get("id"), 160),
            "user_dfa_name": name,
            "base_domain": domain_key,
        },
    }


def ensure_user_dfa_artifacts(
    custom_dfa: dict[str, Any],
    domain_key: str,
    spec: dict[str, Any],
    options: RuntimeOptions,
) -> dict[str, Any]:
    canonical = json.dumps(custom_dfa, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    output_dir = RUNTIME_ROOT / "user_dfa" / digest[:24]
    template_path = output_dir / "global_template.json"
    index_path = output_dir / "state_index.json"
    rebuilt = not (template_path.exists() and index_path.exists())
    if rebuilt:
        template = build_user_dfa_template(custom_dfa, domain_key, spec)
        output_dir.mkdir(parents=True, exist_ok=True)
        save_json(template, template_path)
        save_json(build_embedding_index(template, make_embedding_provider(options)), index_path)
        save_json(
            {
                "artifact_mode": "user-custom",
                "domain_key": domain_key,
                "user_dfa_id": _custom_dfa_text(custom_dfa.get("id"), 160),
                "user_dfa_name": _custom_dfa_text(custom_dfa.get("name") or "我的写作图", 160),
                "content_hash": digest,
                "outputs": {"global_template": str(template_path), "state_index": str(index_path)},
            },
            output_dir / "run_manifest.json",
        )
    template = load_json(template_path)
    return {
        "output_dir": output_dir,
        "artifact_mode": "user-custom",
        "learning_error": "",
        "rebuilt": rebuilt,
        "health": template_health(template),
    }


def select_domain(query: str, override: str = "") -> tuple[str, dict[str, Any]]:
    override = override.strip().lower()
    if override and override in DOMAIN_SPECS:
        return override, DOMAIN_SPECS[override]
    for key in ("etf", "precious_metals", "cotton", "agriculture", "macro"):
        spec = DOMAIN_SPECS[key]
        if re.search(spec["match"], query, flags=re.I):
            return key, spec
    return "general", GENERAL_SPEC


def _valid_iso_date(year: int, month: int, day: int) -> str:
    try:
        return date_type(year, month, day).isoformat()
    except ValueError:
        return ""


def extract_date(query: str, today: date_type | None = None) -> str:
    """Return the evidence cutoff date represented by a query.

    Date ranges use their end date because market-data retrieval is cutoff based.
    The original range remains in the query for the report-generation prompt.
    """
    anchor = today or date_type.today()

    numeric_range = re.search(
        r"(?P<sy>20\d{2})[-/.](?P<sm>\d{1,2})[-/.](?P<sd>\d{1,2})\s*"
        r"(?:至|到|—|–|~|～|-)\s*"
        r"(?:(?P<ey>20\d{2})[-/.])?(?P<em>\d{1,2})[-/.](?P<ed>\d{1,2})",
        query,
    )
    if numeric_range:
        start_year = int(numeric_range.group("sy"))
        start_month = int(numeric_range.group("sm"))
        end_month = int(numeric_range.group("em"))
        end_year = int(numeric_range.group("ey") or start_year)
        if not numeric_range.group("ey") and end_month < start_month:
            end_year += 1
        value = _valid_iso_date(end_year, end_month, int(numeric_range.group("ed")))
        if value:
            return value

    chinese_range = re.search(
        r"(?P<sy>20\d{2})\s*年\s*(?P<sm>\d{1,2})\s*月\s*(?P<sd>\d{1,2})\s*(?:日|号)?\s*"
        r"(?:至|到|—|–|~|～|-)\s*"
        r"(?:(?P<ey>20\d{2})\s*年\s*)?(?:(?P<em>\d{1,2})\s*月\s*)?(?P<ed>\d{1,2})\s*(?:日|号)?",
        query,
    )
    if chinese_range:
        start_year = int(chinese_range.group("sy"))
        start_month = int(chinese_range.group("sm"))
        end_month = int(chinese_range.group("em") or start_month)
        end_year = int(chinese_range.group("ey") or start_year)
        if not chinese_range.group("ey") and end_month < start_month:
            end_year += 1
        value = _valid_iso_date(end_year, end_month, int(chinese_range.group("ed")))
        if value:
            return value

    iso_matches = re.findall(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", query)
    for year, month, day in reversed(iso_matches):
        value = _valid_iso_date(int(year), int(month), int(day))
        if value:
            return value

    chinese_matches = re.findall(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*(?:日|号)?", query)
    for year, month, day in reversed(chinese_matches):
        value = _valid_iso_date(int(year), int(month), int(day))
        if value:
            return value

    english_matches = re.findall(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(20\d{2})",
        query,
        flags=re.I,
    )
    months = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    for month_name, day, year in reversed(english_matches):
        value = _valid_iso_date(int(year), months[month_name.lower()], int(day))
        if value:
            return value

    quarter_match = re.search(r"\b(20\d{2})\s*[-/]?\s*[Qq]([1-4])\b", query)
    if quarter_match:
        year = int(quarter_match.group(1))
        quarter = int(quarter_match.group(2))
        quarter_end_month = quarter * 3
        next_month = date_type(year + (quarter_end_month == 12), quarter_end_month % 12 + 1, 1)
        return (next_month - timedelta(days=1)).isoformat()

    chinese_quarter_match = re.search(r"(20\d{2})\s*年?\s*第?\s*([一二三四1-4])\s*季度", query)
    if chinese_quarter_match:
        quarter_map = {"一": 1, "二": 2, "三": 3, "四": 4}
        year = int(chinese_quarter_match.group(1))
        quarter_text = chinese_quarter_match.group(2)
        quarter = quarter_map.get(quarter_text, int(quarter_text) if quarter_text.isdigit() else 1)
        quarter_end_month = quarter * 3
        next_month = date_type(year + (quarter_end_month == 12), quarter_end_month % 12 + 1, 1)
        return (next_month - timedelta(days=1)).isoformat()

    numeric_month_match = re.search(r"\b(20\d{2})[-/.](\d{1,2})(?![-/.]\d)", query)
    if numeric_month_match:
        year = int(numeric_month_match.group(1))
        month = int(numeric_month_match.group(2))
        if 1 <= month <= 12:
            next_month = date_type(year + (month == 12), month % 12 + 1, 1)
            return (next_month - timedelta(days=1)).isoformat()

    chinese_month_match = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月(?!\s*\d)", query)
    if chinese_month_match:
        year = int(chinese_month_match.group(1))
        month = int(chinese_month_match.group(2))
        if 1 <= month <= 12:
            next_month = date_type(year + (month == 12), month % 12 + 1, 1)
            return (next_month - timedelta(days=1)).isoformat()

    current_week_start = anchor - timedelta(days=anchor.weekday())
    if re.search(r"上上周|前一个完整周", query):
        return (current_week_start - timedelta(days=8)).isoformat()
    if re.search(r"上一完整(?:数据|自然)?周|上个完整(?:数据|自然)?周|上周", query):
        return (current_week_start - timedelta(days=1)).isoformat()
    if re.search(r"上个月|上月", query):
        return (anchor.replace(day=1) - timedelta(days=1)).isoformat()
    return anchor.isoformat()


def safe_query_id(query: str) -> str:
    digest = hashlib.sha1(query.encode("utf-8")).hexdigest()[:12]
    return f"query_{digest}"


def domain_runtime_dir(domain_key: str) -> Path:
    return RUNTIME_ROOT / domain_key


def find_case_file(dataset: str) -> Path | None:
    if not dataset:
        return None
    data_dir = FINLDP_ROOT / dataset / "data"
    if not data_dir.exists():
        return None
    preferred = data_dir / "case_1.csv"
    if preferred.exists():
        return preferred
    files = sorted(data_dir.glob("case_*.csv"), key=lambda path: path.name)
    return files[0] if files else None


def find_dataset_dir(dataset: str) -> Path | None:
    if not dataset:
        return None
    data_dir = FINLDP_ROOT / dataset / "data"
    return data_dir if data_dir.exists() else None


def read_case_rows(path: Path | None) -> tuple[list[str], list[dict[str, str]]]:
    if path is None:
        return GENERAL_COLUMNS, []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = [{key: str(value or "") for key, value in row.items()} for row in reader]
        columns = [name for name in (reader.fieldnames or []) if name and name != "report_id"]
    return columns or GENERAL_COLUMNS, rows[:2]


def excerpt_for_column(rows: list[dict[str, str]], column: str) -> str:
    for row in rows:
        value = re.sub(r"\s+", " ", row.get(column, "")).strip()
        if value:
            return value[:220]
    return ""


def material_names(label: str, spec: dict[str, Any]) -> list[str]:
    values = [label, *SECTION_ALIASES.get(label, []), *spec.get("aliases", [])[:5]]
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def sequence_from_csv_schema(document_id: str, columns: list[str], rows: list[dict[str, str]], spec: dict[str, Any]) -> dict[str, Any]:
    children = [f"1.{index}" for index in range(1, len(columns) + 1)]
    states: list[dict[str, Any]] = [
        {
            "node_id": "1",
            "node_type": "root",
            "template_description": f"{spec['title']}报告结构",
            "level": 0,
            "parent": None,
            "children": children,
            "content_guideline": f"组织 {spec['domain']} 报告的整体写作逻辑。",
            "required_materials": [],
            "length": 0,
        }
    ]
    for index, column in enumerate(columns, start=1):
        excerpt = excerpt_for_column(rows, column)
        states.append(
            {
                "node_id": f"1.{index}",
                "node_type": "leaf",
                "template_description": column,
                "level": 1,
                "parent": "1",
                "children": [],
                "content_guideline": (
                    f"围绕“{column}”生成 {spec['domain']} 报告段落。"
                    f"可使用的状态别名和材料要求包括：{', '.join(material_names(column, spec))}。"
                    + (f" 历史样例片段：{excerpt}" if excerpt else "")
                ),
                "required_materials": material_names(column, spec),
                "length": max(80, len(excerpt)),
            }
        )
    return {
        "document_id": document_id,
        "language": "zh",
        "template_description": f"{spec['title']}报告",
        "structure_pattern": {
            "reasoning_logic": "按照历史报告栏目顺序组织：事实/数据 -> 分析 -> 判断/风险。",
            "node_types": ["root", "child", "leaf"],
        },
        "state_sequence": states,
        "material_requirements_summary": sorted({item for node in states for item in node["required_materials"]}),
        "usage_instruction": {},
    }


def bootstrap_artifacts(
    output_dir: Path,
    domain_key: str,
    spec: dict[str, Any],
    reason: str,
    options: RuntimeOptions | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    options = options or RuntimeOptions()
    csv_path = find_case_file(spec.get("dataset", ""))
    columns, rows = read_case_rows(csv_path)
    seq_a = sequence_from_csv_schema("schema_row_0", columns, rows[:1], spec)
    seq_b = sequence_from_csv_schema("schema_row_1", columns, rows[1:2] or rows[:1], spec)
    matches = [StateMatch(index, index, 1.0) for index in range(len(seq_a["state_sequence"]))]
    template = build_global_template(
        report_pair_id=f"{domain_key}_bootstrap",
        seq_a=seq_a,
        seq_b=seq_b,
        matches=matches,
        theta=1.0,
    )
    template.setdefault("logicrag_metadata", {})
    template["logicrag_metadata"].update(
        {
            "artifact_mode": "bootstrap",
            "bootstrap_reason": reason,
            "source_csv": str(csv_path) if csv_path else "",
            "note": "This cache uses LogicRAG document_learner builders but skips LLM state extraction because source learning was unavailable.",
        }
    )
    embedder = make_embedding_provider(options)
    index = build_embedding_index(template, embedder)
    paths = {
        "document_a_state_sequence": str(output_dir / "document_a_state_sequence.json"),
        "document_b_state_sequence": str(output_dir / "document_b_state_sequence.json"),
        "global_template": str(output_dir / "global_template.json"),
        "state_index": str(output_dir / "state_index.json"),
        "manifest": str(output_dir / "run_manifest.json"),
    }
    save_json(seq_a, paths["document_a_state_sequence"])
    save_json(seq_b, paths["document_b_state_sequence"])
    save_json(template, paths["global_template"])
    save_json(index, paths["state_index"])
    save_json(
        {
            "artifact_mode": "bootstrap",
            "domain_key": domain_key,
            "csv": str(csv_path) if csv_path else "",
            "fallback_reason": reason,
            "embedding_backend": index.get("embedding_backend", ""),
            "embedding_model": index.get("embedding_model", ""),
            "outputs": paths,
        },
        paths["manifest"],
    )
    return paths


def build_autologic_artifacts(
    output_dir: Path,
    domain_key: str,
    spec: dict[str, Any],
    options: RuntimeOptions,
    *,
    rebuild_reason: str,
) -> dict[str, str]:
    data_dir = find_dataset_dir(spec.get("dataset", ""))
    if data_dir is None:
        raise ValueError(f"No historical corpus found for {spec['domain']}.")

    frequency_threshold = float(os.environ.get("AUTOLOGIC_FREQUENCY_THRESHOLD", "0.03"))
    max_files = FULL_CORPUS_CASE_LIMIT
    template, induction_summary = induce_condition_labeled_dfa(
        data_dir=data_dir,
        domain=spec["domain"],
        domain_key=domain_key,
        frequency_threshold=frequency_threshold,
        max_files=max_files,
    )
    template.setdefault("logicrag_metadata", {})
    template["logicrag_metadata"].update(
        {
            "artifact_mode": "autologic-offline",
            "induction_profile": FULL_CORPUS_PROFILE,
            "case_file_limit": max_files,
            "rebuild_reason": rebuild_reason,
            "source_code": str(LOGICRAG_CODE_ROOT / "autologic_learner.py"),
        }
    )
    index = build_embedding_index(template, make_embedding_provider(options))
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "global_template": str(output_dir / "global_template.json"),
        "state_index": str(output_dir / "state_index.json"),
        "induction_summary": str(output_dir / "induction_summary.json"),
        "manifest": str(output_dir / "run_manifest.json"),
    }
    save_json(template, paths["global_template"])
    save_json(index, paths["state_index"])
    save_json(induction_summary, paths["induction_summary"])
    save_json(
        {
            "artifact_mode": "autologic-offline",
            "schema_version": AUTOLOGIC_SCHEMA_VERSION,
            "induction_profile": FULL_CORPUS_PROFILE,
            "case_file_limit": max_files,
            "domain_key": domain_key,
            "historical_corpus": str(data_dir),
            "historical_document_count": induction_summary["document_count"],
            "historical_case_file_count": induction_summary["case_file_count"],
            "sequence_pattern_count": induction_summary["sequence_pattern_count"],
            "frequency_threshold": frequency_threshold,
            "embedding_backend": index.get("embedding_backend", ""),
            "embedding_model": index.get("embedding_model", ""),
            "rebuild_reason": rebuild_reason,
            "outputs": paths,
        },
        paths["manifest"],
    )
    return paths


def rebuild_state_index(output_dir: Path, template: dict[str, Any], options: RuntimeOptions, reason: str) -> dict[str, Any]:
    index = build_embedding_index(template, make_embedding_provider(options))
    save_json(index, output_dir / "state_index.json")
    manifest_path = output_dir / "run_manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    manifest["embedding_backend"] = index.get("embedding_backend", "")
    manifest["embedding_model"] = index.get("embedding_model", "")
    manifest["embedding_rebuilt_reason"] = reason
    save_json(manifest, manifest_path)
    return index


def index_backend(output_dir: Path) -> str:
    index_path = output_dir / "state_index.json"
    if not index_path.exists():
        return ""
    try:
        return str(load_json(index_path).get("embedding_backend", ""))
    except Exception:  # noqa: BLE001 - corrupt cache should be rebuilt by the caller.
        return ""


def artifact_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "template": output_dir / "global_template.json",
        "index": output_dir / "state_index.json",
        "manifest": output_dir / "run_manifest.json",
    }


def artifacts_ready(output_dir: Path) -> bool:
    paths = artifact_paths(output_dir)
    return paths["template"].exists() and paths["index"].exists()


def template_health(template: dict[str, Any]) -> dict[str, Any]:
    nodes = template.get("node_template", {}).get("nodes", [])
    edges = template.get("structure_pattern", {}).get("transitions", [])
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(edges, list):
        edges = []
    roots = [node for node in nodes if node.get("parent") is None]
    roots_with_children = [node for node in roots if node.get("children")]
    labels = [node_label(node) for node in nodes]
    dfa = template.get("dfa", {}) if isinstance(template.get("dfa", {}), dict) else {}
    is_condition_dfa = dfa.get("kind") == "condition-labeled-semantic-dfa"
    outgoing_counts: dict[str, int] = {}
    for edge in edges:
        source = str(edge.get("source", ""))
        outgoing_counts[source] = outgoing_counts.get(source, 0) + 1
    branching_states = [state for state, count in outgoing_counts.items() if count > 1]
    issues = []
    if len(nodes) < 3:
        issues.append(f"only {len(nodes)} state(s)")
    if not edges:
        issues.append("no transitions")
    if not roots_with_children:
        issues.append("no root state with children")
    if is_condition_dfa:
        if not dfa.get("deterministic"):
            issues.append("DFA is not marked deterministic")
        if not dfa.get("initial_state"):
            issues.append("missing initial state")
        if not dfa.get("final_states"):
            issues.append("missing final states")
        if any(not edge.get("condition_symbol") for edge in edges):
            issues.append("transition without normalized condition")
        transition_keys = [(str(edge.get("source")), str(edge.get("condition_symbol"))) for edge in edges]
        if len(transition_keys) != len(set(transition_keys)):
            issues.append("non-deterministic state-condition pair")
    return {
        "ok": not issues,
        "state_count": len(nodes),
        "transition_count": len(edges),
        "root_count": len(roots),
        "branching_state_count": len(branching_states),
        "condition_count": len(dfa.get("alphabet", [])) if is_condition_dfa else 0,
        "schema_version": template.get("logicrag_metadata", {}).get("schema_version", ""),
        "method": template.get("logicrag_metadata", {}).get("method", ""),
        "deterministic": bool(dfa.get("deterministic")) if is_condition_dfa else False,
        "labels": labels,
        "issues": issues,
    }


def repair_with_bootstrap(
    output_dir: Path,
    domain_key: str,
    spec: dict[str, Any],
    reason: str,
    *,
    options: RuntimeOptions | None = None,
    source_template: dict[str, Any] | None = None,
    source_index: dict[str, Any] | None = None,
) -> None:
    if source_template:
        save_json(source_template, output_dir / "global_template.source_degenerate.json")
    if source_index:
        save_json(source_index, output_dir / "state_index.source_degenerate.json")

    paths = bootstrap_artifacts(output_dir, domain_key, spec, reason, options=options)
    template = load_json(paths["global_template"])
    template.setdefault("logicrag_metadata", {})
    template["logicrag_metadata"]["artifact_mode"] = "source-repaired"
    template["logicrag_metadata"]["source_repair_reason"] = reason
    save_json(template, paths["global_template"])

    manifest = load_json(paths["manifest"])
    manifest["artifact_mode"] = "source-repaired"
    manifest["fallback_reason"] = reason
    manifest["source_repaired"] = True
    save_json(manifest, paths["manifest"])


def ensure_artifacts(domain_key: str, spec: dict[str, Any], options: RuntimeOptions) -> dict[str, Any]:
    output_dir = domain_runtime_dir(domain_key)
    dataset_available = find_dataset_dir(spec.get("dataset", "")) is not None
    rebuild_requested = options.force_relearn or options.source_learning

    if artifacts_ready(output_dir) and not rebuild_requested:
        manifest = load_json(output_dir / "run_manifest.json") if (output_dir / "run_manifest.json").exists() else {}
        template = load_json(output_dir / "global_template.json")
        metadata = template.get("logicrag_metadata", {})
        schema_current = metadata.get("schema_version") == AUTOLOGIC_SCHEMA_VERSION
        health = template_health(template)

        profile_current = metadata.get("induction_profile") == FULL_CORPUS_PROFILE
        corpus_complete = int(manifest.get("historical_case_file_count") or 0) >= FULL_CORPUS_CASE_LIMIT
        if dataset_available and (not schema_current or not health["ok"] or not profile_current or not corpus_complete):
            legacy_path = output_dir / "global_template.legacy.json"
            if not legacy_path.exists():
                save_json(template, legacy_path)
            reasons = []
            if not schema_current:
                reasons.append(f"cached schema is {metadata.get('schema_version') or 'legacy'}")
            if not health["ok"]:
                reasons.append(", ".join(health["issues"]))
            if not profile_current:
                reasons.append("cached DFA uses the sampled induction profile")
            if not corpus_complete:
                reasons.append(
                    f"cached DFA covers {manifest.get('historical_case_file_count') or 0} case files, expected {FULL_CORPUS_CASE_LIMIT}"
                )
            reason = "AutoLogic cache migration: " + "; ".join(reasons)
            build_autologic_artifacts(output_dir, domain_key, spec, options, rebuild_reason=reason)
            rebuilt_template = load_json(output_dir / "global_template.json")
            return {
                "output_dir": output_dir,
                "artifact_mode": "autologic-offline",
                "learning_error": "",
                "rebuilt": True,
                "health": template_health(rebuilt_template),
            }

        desired_backend = desired_index_backend(options)
        current_backend = index_backend(output_dir)
        if current_backend != desired_backend:
            reason = f"Cached state_index embedding backend is {current_backend or 'missing'}, expected {desired_backend}."
            rebuilt_index = rebuild_state_index(output_dir, template, options, reason)
            return {
                "output_dir": output_dir,
                "artifact_mode": metadata.get("artifact_mode") or manifest.get("artifact_mode") or "cache",
                "learning_error": reason if rebuilt_index.get("embedding_backend") != desired_backend else "",
                "rebuilt": True,
                "health": health,
            }
        return {
            "output_dir": output_dir,
            "artifact_mode": metadata.get("artifact_mode") or manifest.get("artifact_mode") or "cache",
            "learning_error": "",
            "rebuilt": False,
            "health": health,
        }

    if dataset_available:
        reason = "User requested offline DFA re-induction." if rebuild_requested else "No current AutoLogic DFA cache was found."
        build_autologic_artifacts(output_dir, domain_key, spec, options, rebuild_reason=reason)
        template = load_json(output_dir / "global_template.json")
        return {
            "output_dir": output_dir,
            "artifact_mode": "autologic-offline",
            "learning_error": "",
            "rebuilt": True,
            "health": template_health(template),
        }

    reason = "No historical corpus is available for the general domain; using the generic compatibility DFA."
    bootstrap_artifacts(output_dir, domain_key, spec, reason, options=options)
    return {
        "output_dir": output_dir,
        "artifact_mode": "generic-compatibility",
        "learning_error": reason,
        "rebuilt": True,
        "health": template_health(load_json(output_dir / "global_template.json")),
    }


def query_for_language(query: str, options: RuntimeOptions) -> str:
    if options.language != "en":
        return query
    lowered = query.lower()
    matched_labels = [
        chinese for chinese, english in ENGLISH_STATE_LABELS.items()
        if any(token in lowered for token in re.findall(r"[a-z]{4,}", english.lower()))
    ]
    return query if not matched_labels else f"{query}\nSemantic state aliases: {'、'.join(matched_labels)}"


def run_query_stage(query: str, tau: float, output_dir: Path, options: RuntimeOptions) -> dict[str, Any]:
    output_path = output_dir / f"{safe_query_id(query)}_query_subtree.json"
    embedding = embedding_runtime_config()
    stage_args = SimpleNamespace(
        query=query_for_language(query, options),
        tau=tau,
        template=str(output_dir / "global_template.json"),
        index=str(output_dir / "state_index.json"),
        output=str(output_path),
        preview_top_k=options.preview_top_k,
        fallback_top_k=options.fallback_top_k,
        embedding_model=embedding["model"],
        embedding_base_url=embedding["base_url"],
        embedding_batch_size=embedding["batch_size"],
        local_embedding_only=options.local_embedding_only,
    )
    try:
        return run_query_processing(stage_args)
    except ValueError:
        if options.fallback_top_k > 0:
            raise
        stage_args.fallback_top_k = 1
        return run_query_processing(stage_args)


def english_label(value: str) -> str:
    output = str(value)
    label_phrases = {
        **ENGLISH_STATE_LABELS,
        "有色金属": "Base Metals",
        "贵金属": "Precious Metals",
        "农产品": "Agriculture",
        "棉花": "Cotton",
        "宏观": "Macro",
    }
    for chinese, english in sorted(label_phrases.items(), key=lambda item: len(item[0]), reverse=True):
        output = output.replace(chinese, english)
    return re.sub(r"(?<=[A-Za-z])(?=Report Task Entry)", " ", output)


def english_condition(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    output = value
    phrases = {
        "用户意图要求": "User intent requests ",
        "供给变化走弱/减少，转入": "Supply conditions weaken or decline; transition to ",
        "供给变化走强/增加，转入": "Supply conditions strengthen or increase; transition to ",
        "价格走势出现，转入": "A price trend emerges; transition to ",
        "价格走势走强/增加，转入": "Prices strengthen or increase; transition to ",
        "价格走势走弱/减少，转入": "Prices weaken or decline; transition to ",
        "Price Trend出现，转入": "A price trend emerges; transition to ",
        "Macro Growth出现，转入": "Macro growth is present; transition to ",
        "Strategy Signal走强/增加，转入": "Strategy signal strengthens; transition to ",
        "Market Liquidity走强/增加，转入": "Market liquidity strengthens; transition to ",
        "Supply Change出现，转入": "A supply change is present; transition to ",
        "宏观增长出现，转入": "Macro growth is present; transition to ",
        "Macro增长出现，转入": "Macro growth is present; transition to ",
        "策略信号走强/增加，转入": "Strategy signal strengthens; transition to ",
        "市场流动性走强/增加，转入": "Market liquidity strengthens; transition to ",
        "供给变化出现，转入": "A supply change is present; transition to ",
        "风险信号波动/不确定，转入": "Risk signals fluctuate or remain uncertain; transition to ",
        "需求变化走弱/减少，转入": "Demand conditions weaken or decline; transition to ",
        "需求变化走强/增加，转入": "Demand conditions strengthen or increase; transition to ",
        "稳定转移": "Stable transition",
        "唯一稳定后继，直接转移": "Only stable successor; direct transition",
        "用户定义转移": "User-defined transition",
    }
    for chinese, english in sorted(phrases.items(), key=lambda item: len(item[0]), reverse=True):
        output = output.replace(chinese, english)
    for chinese, english in sorted(ENGLISH_STATE_LABELS.items(), key=lambda item: len(item[0]), reverse=True):
        output = output.replace(chinese, english)
    return output


def english_internal_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    output = value
    phrases = {
        "需求变化走强/增加，转入": "Demand conditions strengthen or increase; transition to ",
        "需求变化走弱/减少，转入": "Demand conditions weaken or decline; transition to ",
        "供给变化走强/增加，转入": "Supply conditions strengthen or increase; transition to ",
        "供给变化走弱/减少，转入": "Supply conditions weaken or decline; transition to ",
        "价格走势走强/增加，转入": "Prices strengthen or increase; transition to ",
        "价格走势走弱/减少，转入": "Prices weaken or decline; transition to ",
        "价格走势出现，转入": "A price trend emerges; transition to ",
        "宏观增长出现，转入": "Macro growth is present; transition to ",
        "策略信号走强/增加，转入": "Strategy signal strengthens; transition to ",
        "市场流动性走强/增加，转入": "Market liquidity strengthens; transition to ",
        "供给变化出现，转入": "A supply change is present; transition to ",
        "风险信号波动/不确定，转入": "Risk signals fluctuate or remain uncertain; transition to ",
        "证据汇合与完整性校验": "Evidence Aggregation and Completeness Validation",
        "段落输出与摘要传递": "Section Output and Summary Handoff",
        "接收": "Receive ",
        "的上游摘要、用户约束和运行参数": " upstream summaries, user constraints, and runtime parameters",
        "合并状态材料，检查来源、截止日期、缺失值和记录完整性": "Merge state materials and validate sources, cutoff dates, missing values, and record completeness",
        "按照状态写作规则组织事实、判断和边界说明": "Organize facts, judgments, and limitations according to the state writing rules",
        "复核数字、来源、时间口径及相互冲突的证据": "Validate figures, sources, time conventions, and conflicting evidence",
        "输出完整段落，只向后继状态传递结论和证据边界": "Output the complete section and pass only conclusions and evidence limitations to successor states",
        "状态入口": "State Entry",
        "证据校验": "Evidence Validation",
        "摘要传递": "Summary Handoff",
        "需求变化": "Demand Change",
        "策略信号": "Strategy Signal",
        "供给变化": "Supply Change",
        "宏观增长": "Macro Growth",
        "利率与汇率": "Rates and FX",
        "价格走势": "Price Trend",
        "风险信号": "Risk Signal",
        "市场流动性": "Market Liquidity",
        "相关事实与数据": " Supporting Facts and Data",
        "政策与事件": "Policy and Events",
        "库存变化": "Inventory Change",
        "出现 / 被提及": "Present / Mentioned",
        "走强 / 增加": "Strengthening / Increasing",
        "走弱 / 减少": "Weakening / Decreasing",
        "波动 / 不确定": "Volatile / Uncertain",
        "进入条件": "Entry Condition",
        "离开条件": "Exit Condition",
        "生成": "Generate ",
        "引用与冲突复核": "Citation and Conflict Review",
    }
    for chinese, english in sorted(phrases.items(), key=lambda item: len(item[0]), reverse=True):
        output = output.replace(chinese, english)
    return english_condition(output).replace("。", ".")


def localize_frontend_template(template: dict[str, Any], language: str) -> dict[str, Any]:
    if language != "en":
        return template
    for node in template.get("nodes", []):
        node["label"] = english_label(str(node.get("label", "")))
        node["guideline"] = (
            f"Write a standalone {node['label']} section using verifiable state-level evidence. "
            "Follow the semantic pattern learned from the source corpus; source-language examples remain preserved in the training cache."
        )
        if isinstance(node.get("materials"), list):
            node["materials"] = [english_internal_text(item) for item in node["materials"]]
        internal_dfa = node.get("internal_dfa")
        if isinstance(internal_dfa, dict):
            for internal_state in internal_dfa.get("states", []) if isinstance(internal_dfa.get("states"), list) else []:
                internal_state["label"] = english_internal_text(internal_state.get("label", ""))
                internal_state["detail"] = english_internal_text(internal_state.get("detail", ""))
            for transition in internal_dfa.get("transitions", []) if isinstance(internal_dfa.get("transitions"), list) else []:
                transition["condition"] = english_internal_text(transition.get("condition", ""))
            for pattern in internal_dfa.get("sequence_patterns", []) if isinstance(internal_dfa.get("sequence_patterns"), list) else []:
                if isinstance(pattern.get("states"), list):
                    pattern["states"] = [english_label(str(item)) for item in pattern["states"]]
    transition_sets = [
        template.get("structure_pattern", {}).get("transitions", []),
        template.get("edges", []),
    ]
    seen_transition_ids: set[int] = set()
    for edge in [item for transition_set in transition_sets if isinstance(transition_set, list) for item in transition_set]:
        if id(edge) in seen_transition_ids:
            continue
        seen_transition_ids.add(id(edge))
        for key in ("condition_label", "label", "predicate"):
            if key in edge:
                edge[key] = english_condition(edge.get(key))
        condition = edge.get("condition")
        if isinstance(condition, dict):
            for key in ("label", "predicate"):
                if key in condition:
                    condition[key] = english_condition(condition.get(key))
            if isinstance(condition.get("top_normalized_events"), list):
                condition["top_normalized_events"] = [english_condition(item) for item in condition["top_normalized_events"]]
    return template


def node_label(node: dict[str, Any]) -> str:
    return str(node.get("template_description") or node.get("label") or node.get("node_id") or "")


def logicrag_edges(template: dict[str, Any]) -> list[dict[str, Any]]:
    edges = template.get("structure_pattern", {}).get("transitions", [])
    return edges if isinstance(edges, list) else []


def edge_id(edge: dict[str, Any], index: int) -> str:
    return str(edge.get("id") or f"E{index}")


def internal_event_label(event: str) -> str:
    parts = str(event).split(".")
    subject_key = ".".join(parts[:-1]) if len(parts) > 1 else str(event)
    signal_key = parts[-1] if parts else "present"
    subjects = {
        "market.price": "价格走势",
        "fundamentals.demand": "需求变化",
        "fundamentals.supply": "供给变化",
        "macro.rates_fx": "利率与汇率",
        "macro.growth": "宏观增长",
        "risk.signal": "风险信号",
        "strategy.signal": "策略信号",
        "query.intent": "用户意图",
    }
    signals = {
        "up": "走强 / 增加",
        "down": "走弱 / 减少",
        "volatile": "波动 / 不确定",
        "present": "出现 / 被提及",
        "stable": "稳定",
    }
    return f"{subjects.get(subject_key, subject_key)} · {signals.get(signal_key, signal_key)}"


def build_internal_dfa(
    node: dict[str, Any],
    edges: list[dict[str, Any]],
    induction_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node_id = str(node.get("node_id", ""))
    node_name = node_label(node)
    node_support = int(node.get("support_documents") or 0)
    adjacent_edges = [
        edge for edge in edges
        if str(edge.get("source", "")) == node_id or str(edge.get("target", "")) == node_id
    ]
    states: list[dict[str, Any]] = [
        {
            "id": "I00",
            "stage": "entry",
            "label": "状态入口",
            "detail": f"接收“{node_name}”的上游摘要、用户约束和运行参数。",
            "support_documents": node_support,
        }
    ]
    transitions: list[dict[str, Any]] = []

    materials = list(node.get("required_materials", []) or [])
    if not materials and (node.get("node_type") == "root" or int(node.get("level") or 0) == 0):
        materials = ["用户意图 (query.intent)", "需求范围 (query.scope)", "时间范围 (query.time_range)", "阈值配置 (runtime.thresholds)"]
    material_ids: list[str] = []
    for index, material in enumerate(materials, start=1):
        state_id = f"M{index:02d}"
        material_ids.append(state_id)
        states.append(
            {
                "id": state_id,
                "stage": "material",
                "label": str(material).split(" (")[0],
                "detail": str(material),
                "support_documents": node_support,
            }
        )
        transitions.append({"source": "I00", "target": state_id, "condition": "required binding", "support_documents": node_support})

    states.append(
        {
            "id": "V00",
            "stage": "evidence",
            "label": "证据汇合与完整性校验",
            "detail": "合并状态材料，检查来源、截止日期、缺失值和记录完整性。",
            "support_documents": node_support,
        }
    )
    if material_ids:
        transitions.extend(
            {"source": state_id, "target": "V00", "condition": "binding ready", "support_documents": node_support}
            for state_id in material_ids
        )
    else:
        transitions.append({"source": "I00", "target": "V00", "condition": "context ready", "support_documents": node_support})

    event_support: dict[str, int] = {}
    for edge in adjacent_edges:
        condition = edge.get("condition", {}) if isinstance(edge.get("condition", {}), dict) else {}
        support = int(edge.get("support_documents") or condition.get("historical_support") or 0)
        for event in condition.get("top_normalized_events", []) or []:
            event_name = str(event)
            event_support[event_name] = max(event_support.get(event_name, 0), support)

    event_ids: list[str] = []
    for index, (event, support) in enumerate(event_support.items(), start=1):
        state_id = f"E{index:02d}"
        event_ids.append(state_id)
        states.append(
            {
                "id": state_id,
                "stage": "event",
                "label": internal_event_label(event),
                "detail": event,
                "support_documents": support,
            }
        )
        transitions.append({"source": "V00", "target": state_id, "condition": event, "support_documents": support})

    condition_ids: list[str] = []
    for index, edge in enumerate(adjacent_edges, start=1):
        condition = edge.get("condition", {}) if isinstance(edge.get("condition", {}), dict) else {}
        state_id = f"C{index:02d}"
        condition_ids.append(state_id)
        support = int(edge.get("support_documents") or condition.get("historical_support") or 0)
        direction = "进入" if str(edge.get("target", "")) == node_id else "离开"
        states.append(
            {
                "id": state_id,
                "stage": "condition",
                "label": f"{direction}条件 · {edge.get('condition_label') or condition.get('label') or '稳定转移'}",
                "detail": condition.get("predicate") or ("TRUE" if edge.get("direct") else condition.get("mode", "historical condition")),
                "support_documents": support,
            }
        )
        transitions.append({"source": "V00", "target": state_id, "condition": condition.get("predicate") or "TRUE", "support_documents": support})

    states.extend(
        [
            {
                "id": "G00",
                "stage": "generation",
                "label": f"生成“{node_name}”",
                "detail": "按照状态写作规则组织事实、判断和边界说明。",
                "support_documents": node_support,
            },
            {
                "id": "Q00",
                "stage": "validation",
                "label": "引用与冲突复核",
                "detail": "复核数字、来源、时间口径及相互冲突的证据。",
                "support_documents": node_support,
            },
            {
                "id": "O00",
                "stage": "output",
                "label": "段落输出与摘要传递",
                "detail": "输出完整段落，只向后继状态传递结论和证据边界。",
                "support_documents": node_support,
            },
        ]
    )
    branch_ids = event_ids + condition_ids
    if branch_ids:
        transitions.extend(
            {"source": state_id, "target": "G00", "condition": "branch accepted", "support_documents": next((int(item.get("support_documents") or 0) for item in states if item["id"] == state_id), 0)}
            for state_id in branch_ids
        )
    else:
        transitions.append({"source": "V00", "target": "G00", "condition": "evidence ready", "support_documents": node_support})
    transitions.extend(
        [
            {"source": "G00", "target": "Q00", "condition": "draft ready", "support_documents": node_support},
            {"source": "Q00", "target": "O00", "condition": "validation passed", "support_documents": node_support},
        ]
    )

    induction_summary = induction_summary or {}
    related_sequences = [
        sequence for sequence in induction_summary.get("top_sequences", []) or []
        if node_name in (sequence.get("states", []) or [])
    ]
    return {
        "states": states,
        "transitions": transitions,
        "sequence_patterns": related_sequences,
        "source_case_files": int(induction_summary.get("case_file_count") or 0),
        "source_documents": int(induction_summary.get("document_count") or 0),
    }


def graph_positions(nodes: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    sorted_nodes = sorted(nodes, key=lambda node: node_sort_key(str(node.get("node_id", ""))))
    levels: dict[int, list[dict[str, Any]]] = {}
    for node in sorted_nodes:
        level = int(node.get("level") or str(node.get("node_id", "")).count("."))
        levels.setdefault(level, []).append(node)

    positions: dict[str, tuple[int, int]] = {}
    x_gap = 230
    y_gap = 112
    for level, level_nodes in sorted(levels.items()):
        total = len(level_nodes)
        start_y = max(48, 280 - ((total - 1) * y_gap) // 2)
        for index, node in enumerate(level_nodes):
            node_id = str(node["node_id"])
            positions[node_id] = (60 + level * x_gap, start_y + index * y_gap)
    return positions


def template_to_frontend(template: dict[str, Any], induction_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    nodes = get_report_nodes(template)
    source_edges = logicrag_edges(template)
    positions = graph_positions(nodes)
    frontend_nodes = []
    for node in nodes:
        node_id = str(node["node_id"])
        x, y = positions.get(node_id, (80, 80))
        frontend_nodes.append(
            {
                "id": node_id,
                "label": node_label(node),
                "type": node.get("node_type", ""),
                "x": x,
                "y": y,
                "guideline": node.get("content_guideline", ""),
                "materials": node.get("required_materials", []),
                "children": [str(child) for child in node.get("children", [])],
                "parent": str(node["parent"]) if node.get("parent") is not None else None,
                "level": node.get("level", 0),
                "support": node.get("support", []),
                "frequency": node.get("state_frequency"),
                "support_documents": node.get("support_documents"),
                "internal_dfa": build_internal_dfa(node, source_edges, induction_summary),
            }
        )

    frontend_edges = []
    for index, edge in enumerate(source_edges):
        condition = edge.get("condition", {}) if isinstance(edge.get("condition", {}), dict) else {}
        frontend_edges.append(
            {
                "id": edge_id(edge, index),
                "source": str(edge.get("source", "")),
                "target": str(edge.get("target", "")),
                "label": edge.get("condition_label") or condition.get("label") or f"{edge.get('source')} -> {edge.get('target')}",
                "condition_symbol": edge.get("condition_symbol") or condition.get("symbol"),
                "condition_label": edge.get("condition_label") or condition.get("label"),
                "predicate": condition.get("predicate"),
                "condition_mode": condition.get("mode"),
                "direct": bool(edge.get("direct") or condition.get("direct")),
                "priority": edge.get("priority") or condition.get("priority"),
                "frequency": edge.get("frequency"),
                "support_documents": edge.get("support_documents"),
                "evidence_schema": condition.get("evidence_schema", []),
                "top_normalized_events": condition.get("top_normalized_events", []),
            }
        )
    max_x = max((node["x"] for node in frontend_nodes), default=900) + 210
    max_y = max((node["y"] for node in frontend_nodes), default=500) + 120
    induction_summary = induction_summary or {}
    return {
        "nodes": frontend_nodes,
        "edges": frontend_edges,
        "viewport": [0, 0, max(980, max_x), max(560, max_y)],
        "induction": {
            "document_count": int(induction_summary.get("document_count") or 0),
            "case_file_count": int(induction_summary.get("case_file_count") or 0),
            "sequence_pattern_count": int(induction_summary.get("sequence_pattern_count") or 0),
            "top_sequences": induction_summary.get("top_sequences", []) or [],
        },
    }


def edge_lookup(template: dict[str, Any]) -> dict[tuple[str, str], str]:
    return {
        (str(edge.get("source", "")), str(edge.get("target", ""))): edge_id(edge, index)
        for index, edge in enumerate(logicrag_edges(template))
    }


def node_maps(template: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    nodes = get_report_nodes(template)
    by_id = {str(node["node_id"]): node for node in nodes}
    children = {node_id: [str(child) for child in node.get("children", [])] for node_id, node in by_id.items()}
    for node_id, node in by_id.items():
        parent = node.get("parent")
        if parent is not None and str(parent) in children and node_id not in children[str(parent)]:
            children[str(parent)].append(node_id)
    return by_id, children


def ancestor_closure(template: dict[str, Any], raw_node_ids: list[str]) -> list[str]:
    by_id, _ = node_maps(template)
    included: set[str] = set()
    for node_id in raw_node_ids:
        current = node_id
        while current and current in by_id and current not in included:
            included.add(current)
            parent = by_id[current].get("parent")
            current = str(parent) if parent is not None else ""
    ordered = [str(node["node_id"]) for node in get_report_nodes(template) if str(node["node_id"]) in included]
    return ordered or raw_node_ids


def subtree_node_ids(subtree: dict[str, Any]) -> list[str]:
    return [str(node["node_id"]) for node in get_report_nodes(subtree)]


def edge_ids_for_nodes(template: dict[str, Any], node_ids: list[str]) -> list[str]:
    included = set(node_ids)
    ids = []
    for index, edge in enumerate(logicrag_edges(template)):
        if str(edge.get("source", "")) in included and str(edge.get("target", "")) in included:
            ids.append(edge_id(edge, index))
    return ids


def raw_subtree_edge_ids(template: dict[str, Any], subtree: dict[str, Any]) -> list[str]:
    lookup = edge_lookup(template)
    ids = []
    for edge in logicrag_edges(subtree):
        found = lookup.get((str(edge.get("source", "")), str(edge.get("target", ""))))
        if found:
            ids.append(found)
    return ids


def ranked_to_frontend(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in ranked:
        score = float(item.get("similarity", 0.0))
        result.append(
            {
                "id": str(item.get("node_id")),
                "node_id": str(item.get("node_id")),
                "label": item.get("label", ""),
                "desc": item.get("desc", ""),
                "similarity": round(score, 6),
                "score": round(max(0.0, min(1.0, score)), 6),
            }
        )
    return result


def execution_order(subtree: dict[str, Any]) -> list[str]:
    nodes = get_report_nodes(subtree)
    requested_order = subtree.get("query_processing_metadata", {}).get("execution_order", [])
    if isinstance(requested_order, list) and requested_order:
        node_by_id = {str(node["node_id"]): node for node in nodes}
        ordered = [
            str(node_id)
            for node_id in requested_order
            if str(node_id) in node_by_id and is_executable_state(node_by_id[str(node_id)], generate_internal=False)
        ]
        if ordered:
            return ordered
    executable = [str(node["node_id"]) for node in nodes if is_executable_state(node, generate_internal=False)]
    return executable or [str(node["node_id"]) for node in nodes]


def materials_for(node_id: str, frontend_node: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    materials = frontend_node.get("materials", [])
    return {
        "node_id": node_id,
        "label": frontend_node["label"],
        "required_materials": materials,
        "retrieved_facts": [
            f"状态来源：{runtime['artifact_mode']} artifact / {runtime['domain']}",
            f"状态材料要求：{', '.join(materials) if materials else '无显式材料要求'}",
            "当前阶段展示写作图与状态级绑定；接入 iFinD 后可替换为真实检索数据。",
        ],
    }


def sanitize_error(message: Any) -> str:
    text = str(message or "")
    for secret in (
        settings.ifind_username,
        settings.ifind_password,
        settings.tushare_token,
        settings.deepseek_api_key,
        settings.embedding_api_key,
    ):
        if secret:
            text = text.replace(secret, "***")
    return text


def valid_ifind_date(date: str) -> str:
    return date if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(date or "")) else ""


def summarize_ifind_bindings(bindings: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    found = 0
    for binding in bindings:
        status = str(binding.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
        if status == "found":
            found += 1
    return {"total": len(bindings), "found": found, "status_counts": counts}


def retrieve_ifind_materials(
    *,
    query: str,
    date: str,
    query_subtree_path: Path,
    output_dir: Path,
    options: RuntimeOptions,
) -> dict[str, Any]:
    config = {
        "enabled": options.use_ifind,
        "requested": options.use_ifind,
        "used": False,
        "has_credentials": bool(settings.ifind_username and settings.ifind_password),
        "mode": "iFinDPy",
        "dictionary": str(LOGICRAG_CODE_ROOT / "domain_dictionary.csv"),
    }
    empty_summary = {"total": 0, "found": 0, "status_counts": {}}
    if not options.use_ifind:
        return {**config, "status": "disabled", "bindings_by_node": {}, "summary": empty_summary}
    if not config["has_credentials"]:
        return {
            **config,
            "status": "not_configured",
            "error": "IFIND_USERNAME/IFIND_PASSWORD are not configured.",
            "bindings_by_node": {},
            "summary": empty_summary,
        }

    materials_dir = output_dir / "ifind_materials" / safe_query_id(query)
    args = SimpleNamespace(
        query=query,
        query_subtree=str(query_subtree_path),
        dictionary=str(LOGICRAG_CODE_ROOT / "domain_dictionary.csv"),
        output_dir=str(materials_dir),
        date=valid_ifind_date(date),
        asset_name="",
        username=settings.ifind_username,
        password=settings.ifind_password,
        dry_run=options.ifind_dry_run,
    )
    try:
        result = run_data_plugin(args)
    except Exception as exc:  # noqa: BLE001 - data retrieval should not block visualization.
        return {
            **config,
            "status": "error",
            "error": sanitize_error(exc),
            "bindings_by_node": {},
            "summary": {"total": 0, "found": 0, "status_counts": {"error": 1}},
            "output_dir": str(materials_dir),
        }

    bindings = list(result.get("bindings", []))
    for binding in bindings:
        if binding.get("error"):
            binding["error"] = sanitize_error(binding["error"])
    by_node: dict[str, list[dict[str, Any]]] = {}
    for binding in bindings:
        by_node.setdefault(str(binding.get("node_id", "")), []).append(binding)
    summary = summarize_ifind_bindings(bindings)
    status = "found" if summary["found"] else ("planned" if options.ifind_dry_run else "no_data")
    if summary["status_counts"].get("error") and not summary["found"]:
        status = "error"
    elif summary["status_counts"].get("unresolved") and not summary["found"]:
        status = "unresolved"
    first_error = next((sanitize_error(binding.get("error")) for binding in bindings if binding.get("error")), "")
    return {
        **config,
        "status": status,
        "used": summary["found"] > 0,
        "dry_run": options.ifind_dry_run,
        "summary": summary,
        "error": first_error,
        "query_date": result.get("query_date", date),
        "output_dir": str(materials_dir),
        "outputs": result.get("outputs", {}),
        "bindings_by_node": by_node,
    }


def historical_demo_text(node: dict[str, Any]) -> str:
    guideline = str(node.get("guideline", "")).strip()
    marker = "历史样例语义："
    if marker in guideline:
        sample = guideline.split(marker, 1)[1].strip()
    else:
        sample = guideline
    sample = re.sub(r"\s+", " ", sample).strip()
    if sample:
        return f"离线历史样例（仅用于演示流程，不代表实时市场）：{sample[:1400]}"
    return f"离线演示证据：已完成“{node.get('label', '写作状态')}”的状态级材料绑定；该内容不代表实时市场。"


def build_demo_materials(
    *,
    date: str,
    order: list[str],
    frontend_node_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_node: dict[str, list[dict[str, Any]]] = {}
    for node_id in order:
        node = frontend_node_by_id.get(node_id)
        if not node:
            continue
        by_node[node_id] = [
            {
                "node_id": node_id,
                "state_label": node.get("label", ""),
                "required_material": "cached historical demonstration evidence",
                "date": date,
                "provider": "demo",
                "status": "found",
                "error": "",
                "records": [],
                "raw_text": historical_demo_text(node),
            }
        ]
    count = len(by_node)
    return {
        "enabled": True,
        "requested": True,
        "used": bool(count),
        "has_credentials": False,
        "mode": "demo-snapshot",
        "status": "found" if count else "no_data",
        "summary": {"total": count, "found": count, "status_counts": {"found": count} if count else {}},
        "query_date": date,
        "bindings_by_node": by_node,
        "demo_notice": "Historical cached examples for interface demonstration; not live market data.",
    }


def first_record_value(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def numeric_value(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def display_number(value: Any, decimals: int = 2) -> str:
    number = numeric_value(value)
    if number is None:
        return str(value or "")
    if abs(number) >= 10000:
        return f"{number:,.0f}"
    rendered = f"{number:.{decimals}f}"
    return rendered.rstrip("0").rstrip(".")


def display_date(value: Any) -> str:
    text = str(value or "").strip()
    match = re.fullmatch(r"(20\d{2})-(\d{2})-(\d{2})", text)
    if match:
        return f"{match.group(1)}年{int(match.group(2))}月{int(match.group(3))}日"
    return text


def change_description(metric: str, period: str, value: Any, growth_word: str = "上涨") -> str:
    number = numeric_value(value)
    if number is None:
        return f"{metric}{period}{display_number(value)}%"
    if number > 0:
        direction = growth_word
    elif number < 0:
        direction = "下降"
    else:
        direction = "持平"
    amount = "" if number == 0 else f"{abs(number):g}%"
    return f"{metric}{period}{direction}{amount}"


def market_binding_fact(binding: dict[str, Any], records: list[dict[str, Any]]) -> str:
    latest = records[-1]
    previous = records[-2] if len(records) > 1 else {}
    instrument = str(binding.get("instrument", "相关标的"))
    date = display_date(first_record_value(latest, "date", "trade_date", "日期", "月份"))
    close = first_record_value(latest, "close", "收盘")
    previous_close = first_record_value(previous, "close", "收盘")
    high = first_record_value(latest, "high", "最高")
    low = first_record_value(latest, "low", "最低")
    volume = first_record_value(latest, "volume", "vol", "成交量")
    hold = first_record_value(latest, "hold", "oi", "持仓量")
    parts = [f"{instrument}{f'在{date}' if date else ''}收盘价为{display_number(close)}"]
    close_number = numeric_value(close)
    previous_number = numeric_value(previous_close)
    if close_number is not None and previous_number not in (None, 0):
        change = (close_number / previous_number - 1) * 100
        direction = "上涨" if change > 0 else "下跌" if change < 0 else "持平"
        parts.append(f"较上一期{direction}{abs(change):.2f}%")
    if high is not None and low is not None:
        parts.append(f"期内高低点为{display_number(high)}和{display_number(low)}")
    if volume is not None:
        parts.append(f"成交量{display_number(volume, 0)}")
    if hold is not None:
        parts.append(f"持仓量{display_number(hold, 0)}")
    return "，".join(parts)


def macro_binding_fact(binding: dict[str, Any], records: list[dict[str, Any]]) -> str:
    latest = records[-1]
    endpoint = str(binding.get("endpoint", "")).lower()
    instrument = str(binding.get("instrument", "宏观指标"))
    date = display_date(first_record_value(latest, "月份", "季度", "month", "quarter", "date", "trade_date"))
    prefix = f"{date}，" if date else ""
    if "cpi" in endpoint:
        yoy = first_record_value(latest, "全国-同比增长", "nt_yoy", "cpi_yoy")
        mom = first_record_value(latest, "全国-环比增长", "nt_mom", "cpi_mom")
        index = first_record_value(latest, "全国-当月", "nt_val")
        parts = [change_description("全国CPI", "同比", yoy) if yoy is not None else f"全国CPI指数为{display_number(index)}"]
        if mom is not None:
            parts.append(change_description("", "环比", mom))
        return prefix + "，".join(parts)
    if "ppi" in endpoint:
        yoy = first_record_value(latest, "当月同比增长", "ppi_yoy")
        index = first_record_value(latest, "当月", "ppi")
        return prefix + (change_description("PPI", "同比", yoy) if yoy is not None else f"PPI指数为{display_number(index)}")
    if "pmi" in endpoint:
        manufacturing = first_record_value(latest, "制造业-指数", "pmi010000", "manufacturing_pmi")
        non_manufacturing = first_record_value(latest, "非制造业-指数", "pmi020000", "non_manufacturing_pmi")
        parts = []
        if manufacturing is not None:
            level = "扩张" if (numeric_value(manufacturing) or 0) >= 50 else "收缩"
            parts.append(f"制造业PMI为{display_number(manufacturing)}，处于{level}区间")
        if non_manufacturing is not None:
            level = "扩张" if (numeric_value(non_manufacturing) or 0) >= 50 else "收缩"
            parts.append(f"非制造业PMI为{display_number(non_manufacturing)}，处于{level}区间")
        return prefix + ("，".join(parts) if parts else f"{instrument}已取得最新观测值")
    if "gdp" in endpoint:
        yoy = first_record_value(latest, "国内生产总值-同比增长", "gdp_yoy")
        secondary = first_record_value(latest, "第二产业-同比增长", "si_yoy")
        tertiary = first_record_value(latest, "第三产业-同比增长", "ti_yoy")
        parts = [change_description("GDP", "同比", yoy, "增长") if yoy is not None else "GDP已取得最新观测值"]
        if secondary is not None:
            parts.append(change_description("第二产业", "同比", secondary, "增长"))
        if tertiary is not None:
            parts.append(change_description("第三产业", "同比", tertiary, "增长"))
        return prefix + "，".join(parts)

    ignored = {"date", "trade_date", "日期", "月份", "季度", "ts_code", "code"}
    metrics = [(key, value) for key, value in latest.items() if key not in ignored and numeric_value(value) is not None][:4]
    detail = "，".join(f"{key}为{display_number(value)}" for key, value in metrics)
    return prefix + (f"{instrument}{detail}" if detail else f"{instrument}已取得最新观测值")


def binding_to_fact(binding: dict[str, Any]) -> str:
    if binding.get("provider") == "demo":
        return str(binding.get("raw_text", "")).strip()[:1200]
    records = [record for record in binding.get("records", []) if isinstance(record, dict)]
    if records:
        category = str(binding.get("endpoint", "")).lower()
        if any(token in category for token in ("macro", "cpi", "ppi", "pmi", "gdp", "cn_")):
            return macro_binding_fact(binding, records)
        return market_binding_fact(binding, records)
    raw_text = re.sub(r"\s+", " ", str(binding.get("raw_text", "")).strip())
    if raw_text and not raw_text.startswith(("{", "[")):
        return raw_text[:900]
    return f"{binding.get('instrument') or binding.get('provider') or '数据源'}已返回可核验记录"


def section_bindings(label: str, bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    endpoint_rules = {
        "工业": ("pmi", "ppi", "gdp"),
        "地产": ("gdp", "ppi", "pmi"),
        "内需": ("cpi", "gdp", "pmi"),
        "外需": ("pmi", "gdp"),
        "价格": ("cpi", "ppi"),
    }
    tokens = endpoint_rules.get(label)
    if not tokens:
        return bindings[:4]
    selected = [binding for binding in bindings if any(token in str(binding.get("endpoint", "")).lower() for token in tokens)]
    return (selected or bindings)[:3]


def section_closing(label: str) -> str:
    closings = {
        "高频数据观察": "这些指标共同刻画了当前增长、景气与价格环境，后续判断仍需结合更新频率更高的需求和金融条件数据。",
        "工业": "现有证据能够反映工业景气和价格环境，但尚不足以替代产量、库存及订单等行业数据。",
        "地产": "现有宏观指标只能提供间接参照，房地产销售、投资与开工数据仍需单独核验。",
        "内需": "物价、景气和增长指标可用于观察内需方向，但消费与投资的结构性差异仍需进一步拆分。",
        "外需": "当前证据未直接覆盖进出口和海外订单，因此对外需仅作审慎判断。",
        "价格": "CPI与PPI分别反映消费端和生产端价格变化，可作为通胀与工业品定价环境的主要观察依据。",
        "风险提示": "数据修订、政策变化和外部冲击均可能使后续走势偏离当前观测。",
    }
    return closings.get(label, "以上数据构成本节的量化依据，未覆盖部分仍需补充专项数据后再作判断。")


def materials_for(
    node_id: str,
    frontend_node: dict[str, Any],
    runtime: dict[str, Any],
    evidence_bindings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    materials = frontend_node.get("materials", [])
    evidence_bindings = evidence_bindings or []
    facts = [
        f"State source: {runtime['artifact_mode']} artifact / {runtime['domain']}",
        f"Required materials: {', '.join(materials) if materials else 'none'}",
    ]
    if evidence_bindings:
        facts.extend(binding_to_fact(binding) for binding in evidence_bindings)
    elif runtime.get("evidence", {}).get("enabled"):
        facts.append(f"Evidence retrieval produced no binding for this state; status={runtime.get('evidence', {}).get('status')}.")
    else:
        facts.append("Writing-graph state-level material binding is active, but no external evidence source is enabled.")
    return {
        "node_id": node_id,
        "label": frontend_node["label"],
        "required_materials": materials,
        "retrieved_facts": facts,
        "evidence_bindings": evidence_bindings,
        "ifind_bindings": evidence_bindings,
    }


def draft_section(
    node_id: str,
    order: int,
    date: str,
    node: dict[str, Any],
    material: dict[str, Any],
    language: str = "zh",
) -> dict[str, Any]:
    verified_bindings = [
        binding
        for binding in material.get("evidence_bindings", material.get("ifind_bindings", []))
        if isinstance(binding, dict)
        and binding.get("status") == "found"
        and not binding.get("error")
        and str(binding.get("raw_text", "")).strip()
    ]
    selected_bindings = section_bindings(str(node.get("label", "")), verified_bindings)
    facts = [binding_to_fact(binding).rstrip("。；") for binding in selected_bindings]
    if facts:
        demo_evidence = any(binding.get("provider") == "demo" for binding in verified_bindings)
        if language == "en":
            content = (
                f"As of {date}, provider-bound evidence for {node['label']} includes: "
                + "; ".join(facts)
                + ". The signals should be interpreted within the stated data cutoff and evidence coverage."
            )
        elif demo_evidence:
            content = f"{node['label']}（离线演示）：" + "；".join(facts)
        else:
            content = f"截至 {date}，可核验数据显示：" + "；".join(facts) + "。" + section_closing(str(node.get("label", "")))
    elif language == "en":
        content = (
            f"As of {date}, the available evidence is insufficient to form a reliable quantitative conclusion for “{node['label']}”. "
            "This section remains pending until the required market data and verifiable facts are available."
        )
    else:
        content = (
            f"截至 {date}，当前可用证据尚不足以对“{node['label']}”形成可靠的量化判断。"
            "本节保留为待补充项，发布前需补充对应市场数据与可核验事实。"
        )
    return {
        "node_id": node_id,
        "label": node["label"],
        "order": order,
        "content": content,
        "evidence_verified": bool(verified_bindings),
        "evidence_status": (
            "demo"
            if any(binding.get("provider") == "demo" for binding in verified_bindings)
            else "verified" if verified_bindings else "missing"
        ),
    }


def incoming_edge(node_id: str, edges: list[dict[str, Any]], included: set[str]) -> str | None:
    for edge in edges:
        if edge["target"] == node_id and edge["source"] in included:
            return edge["id"]
    return None


def build_steps(analysis: dict[str, Any], report_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked_preview = [
        {"node_id": item["id"], "label": item["label"], "similarity": item["similarity"]}
        for item in analysis["ranked"][: analysis["runtime"]["preview_top_k"]]
    ]
    matched_states = [
        {"node_id": item["id"], "label": item["label"], "similarity": item["similarity"]}
        for item in analysis["matched"]
    ]
    subdfa = analysis["subdfa"]
    edges = analysis["template"]["edges"]
    using_user_dfa = analysis.get("runtime", {}).get("dfa_source") == "user"
    user_dfa_name = analysis.get("runtime", {}).get("user_dfa", {}).get("name", "我的写作图") if using_user_dfa else ""
    steps = [
        {
            "title": "接收 Query",
            "description": "解析用户输入、领域、阈值和运行参数。",
            "active_nodes": [],
            "active_edges": [],
            "detail": {"query": analysis["query"], "constraints": analysis["constraints"]},
        },
        {
            "title": "读取我的写作图" if using_user_dfa else "AutoLogic 离线诱导",
            "description": (
                f"读取用户保存的“{user_dfa_name}”，使用其段落状态、材料要求与转移结构构建本次查询执行图。"
                if using_user_dfa
                else "从同领域历史报告对齐语义状态、统计稳定转移并诱导归一化证据条件，生成或读取全局写作图。"
            ),
            "active_nodes": [node["id"] for node in analysis["template"]["nodes"]],
            "active_edges": [edge["id"] for edge in edges],
            "detail": {
                "artifact_mode": analysis["runtime"]["artifact_mode"],
                "rebuilt": analysis["runtime"]["rebuilt"],
                "learning_error": analysis["runtime"]["learning_error"],
                "dfa_health": analysis["runtime"].get("dfa_health", {}),
                "global_template": analysis["runtime"]["global_template"],
                "state_index": analysis["runtime"]["state_index"],
                "dfa_source": analysis["runtime"].get("dfa_source", "system"),
                "user_dfa": analysis["runtime"].get("user_dfa"),
            },
        },
        {
            "title": "Query Processing",
            "description": "调用 LogicRAG 源码的 run_query_processing，对 query embedding 与 state index 做相似度排序。",
            "active_nodes": [item["node_id"] for item in ranked_preview],
            "active_edges": [],
            "detail": {"top_ranked_preview": ranked_preview},
        },
        {
            "title": "Matched States",
            "description": "应用 select_matched_states，保留 similarity > tau 的状态；必要时使用源码支持的 fallback_top_k。",
            "active_nodes": [item["node_id"] for item in matched_states],
            "active_edges": [],
            "detail": {"tau": analysis["tau"], "fallback_top_k": analysis["runtime"]["fallback_top_k"], "matched_states": matched_states},
        },
        {
            "title": "候选执行图",
            "description": "从初始状态到各命中状态寻找历史支持度最高的路径，并合并为候选子图。",
            "active_nodes": analysis["raw_subdfa"]["node_ids"],
            "active_edges": analysis["raw_subdfa"]["edge_ids"],
            "detail": {
                "subtree_root": analysis["subtree_root"],
                "raw_subtree_nodes": analysis["raw_subdfa"]["node_ids"],
                "raw_subtree_edges": analysis["raw_subdfa"]["edge_ids"],
            },
        },
        {
            "title": "Query-Specific Execution Graph",
            "description": "根据当前对话和条件优先级，从候选子图中选择确定性的可执行路径。",
            "active_nodes": subdfa["node_ids"],
            "active_edges": subdfa["edge_ids"],
            "detail": {"visual_nodes": subdfa["node_ids"], "visual_edges": subdfa["edge_ids"]},
        },
        {
            "title": "Material Binding",
            "description": "按 report_generator 的可执行状态顺序绑定 required_materials。",
            "active_nodes": analysis["execution_order"],
            "active_edges": subdfa["edge_ids"],
            "materials_ready": True,
            "detail": {"data_retrieval": analysis["runtime"].get("evidence", {}), "materials_index": list(analysis["materials"].values())},
        },
    ]
    included = set(subdfa["node_ids"])
    for index, section in enumerate(report_sections):
        edge = incoming_edge(section["node_id"], edges, included)
        steps.append(
            {
                "title": f"生成片段 {index + 1}: {section['label']}",
                "description": "按照查询执行图的确定性顺序逐状态生成，并只向下一状态传递摘要。",
                "active_nodes": [section["node_id"]],
                "active_edges": [edge] if edge else [],
                "generated_until": index + 1,
                "detail": {"section": section, "materials": analysis["materials"].get(section["node_id"])},
            }
        )
    steps.append(
        {
            "title": "Report Trace 完成",
            "description": "输出 query_subtree、状态材料、生成顺序和最终报告片段。",
            "active_nodes": subdfa["node_ids"],
            "active_edges": subdfa["edge_ids"],
            "generated_until": len(report_sections),
            "detail": {"report_sections": report_sections, "query_subtree": analysis["runtime"]["query_subtree"]},
        }
    )
    return steps


def build_analysis(query: str, tau: float = 0.5, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    options = options_from_payload(payload)
    domain_key, spec = select_domain(query, options.domain_override)
    custom_dfa = payload.get("custom_dfa") if payload.get("dfa_source") == "user" else None
    if custom_dfa is not None and not isinstance(custom_dfa, dict):
        raise ValueError("custom_dfa must be an object when dfa_source is user.")
    artifacts = (
        ensure_user_dfa_artifacts(custom_dfa, domain_key, spec, options)
        if isinstance(custom_dfa, dict)
        else ensure_artifacts(domain_key, spec, options)
    )
    output_dir = Path(artifacts["output_dir"])
    template = load_json(output_dir / "global_template.json")
    induction_summary_path = output_dir / "induction_summary.json"
    induction_summary = load_json(induction_summary_path) if induction_summary_path.exists() else {}
    subtree = run_query_stage(query, tau, output_dir, options)
    frontend_template = localize_frontend_template(template_to_frontend(template, induction_summary), options.language)
    frontend_node_by_id = {node["id"]: node for node in frontend_template["nodes"]}

    metadata = subtree.get("query_processing_metadata", {})
    ranked = ranked_to_frontend(metadata.get("top_ranked_preview", []))
    matched = ranked_to_frontend(metadata.get("matched_states", []))
    selected_node_ids = metadata.get("selected_node_ids") or subtree_node_ids(subtree)
    selected_edge_ids = metadata.get("selected_edge_ids") or raw_subtree_edge_ids(template, subtree)
    raw_node_ids = metadata.get("candidate_node_ids") or selected_node_ids
    raw_edge_ids = metadata.get("candidate_edge_ids") or selected_edge_ids
    visual_node_ids = [str(node_id) for node_id in selected_node_ids]
    visual_edge_ids = [str(edge_id_value) for edge_id_value in selected_edge_ids]
    order = execution_order(subtree)
    date = extract_date(query)
    runtime = {
        "embedding": {
            **embedding_runtime_config(),
            "mode": "local-hash" if options.local_embedding_only else "semantic-api",
            "remote_embedding": not options.local_embedding_only,
            "state_index_backend": index_backend(output_dir),
        },
        "domain_key": domain_key,
        "domain": spec["domain"],
        "language": options.language,
        "artifact_mode": artifacts["artifact_mode"],
        "dfa_source": "user" if isinstance(custom_dfa, dict) else "system",
        "user_dfa": {
            "id": _custom_dfa_text(custom_dfa.get("id"), 160),
            "name": _custom_dfa_text(custom_dfa.get("name") or "我的写作图", 160),
            "base_domain": _custom_dfa_text(custom_dfa.get("baseDomain") or domain_key, 80),
        } if isinstance(custom_dfa, dict) else None,
        "rebuilt": artifacts["rebuilt"],
        "learning_error": artifacts["learning_error"],
        "theta": options.theta,
        "tau": tau,
        "preview_top_k": options.preview_top_k,
        "fallback_top_k": options.fallback_top_k,
        "source_learning": options.source_learning,
        "force_relearn": options.force_relearn,
        "local_embedding_only": options.local_embedding_only,
        "dfa_health": artifacts.get("health", {}),
        "logicrag_code_root": str(LOGICRAG_CODE_ROOT),
        "document_learner": str(LOGICRAG_CODE_ROOT / "autologic_learner.py"),
        "query_processing": str(LOGICRAG_CODE_ROOT / "query_processing.py"),
        "global_template": str(output_dir / "global_template.json"),
        "state_index": str(output_dir / "state_index.json"),
        "query_subtree": str(output_dir / f"{safe_query_id(query)}_query_subtree.json"),
    }
    manifest_path = output_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        runtime["induction"] = {
            "profile": manifest.get("induction_profile", "sampled-legacy"),
            "documents": manifest.get("historical_document_count", 0),
            "case_files": manifest.get("historical_case_file_count", 0),
            "frequency_threshold": manifest.get("frequency_threshold"),
            "sequence_patterns": manifest.get("sequence_pattern_count", 0),
        }
    if options.data_source == "ifind":
        evidence_result = retrieve_ifind_materials(
            query=query,
            date=date,
            query_subtree_path=Path(runtime["query_subtree"]),
            output_dir=output_dir,
            options=options,
        )
        evidence_result["source"] = "ifind"
        evidence_result["providers_used"] = ["iFinD"] if evidence_result.get("summary", {}).get("found") else []
    elif options.data_source == "demo":
        evidence_result = build_demo_materials(
            date=date,
            order=order,
            frontend_node_by_id=frontend_node_by_id,
        )
    elif options.data_source == "none":
        evidence_result = {
            "enabled": False,
            "requested": False,
            "used": False,
            "mode": "disabled",
            "source": "none",
            "status": "disabled",
            "providers_used": [],
            "summary": {"total": 0, "found": 0, "status_counts": {}},
            "bindings_by_node": {},
        }
    else:
        evidence_result = retrieve_market_materials(
            source=options.data_source,
            domain_key=domain_key,
            query_date=date,
            order=order,
            frontend_node_by_id=frontend_node_by_id,
        )
    if settings.demo_mode and not evidence_result.get("summary", {}).get("found"):
        evidence_result = build_demo_materials(
            date=date,
            order=order,
            frontend_node_by_id=frontend_node_by_id,
        )
    runtime["data_source"] = options.data_source
    runtime["evidence"] = {key: value for key, value in evidence_result.items() if key != "bindings_by_node"}
    runtime["ifind"] = runtime["evidence"]
    evidence_by_node = evidence_result.get("bindings_by_node", {})
    materials = {
        node_id: materials_for(node_id, frontend_node_by_id[node_id], runtime, evidence_by_node.get(node_id, []))
        for node_id in order
        if node_id in frontend_node_by_id
    }
    report_sections = [
        draft_section(node_id, index + 1, date, frontend_node_by_id[node_id], materials[node_id], options.language)
        for index, node_id in enumerate(order)
        if node_id in frontend_node_by_id
    ]
    verified_sections = sum(1 for section in report_sections if section.get("evidence_verified"))
    providers_used = evidence_result.get("providers_used", [])
    if evidence_result.get("mode") == "demo-snapshot":
        providers_used = ["demo"]
    evidence_summary = {
        "provider": " + ".join(providers_used) if providers_used else options.data_source,
        "providers": providers_used,
        "requested": options.data_source != "none" or settings.demo_mode,
        "status": evidence_result.get("status", "unknown"),
        "total_bindings": evidence_result.get("summary", {}).get("total", 0),
        "found_bindings": evidence_result.get("summary", {}).get("found", 0),
        "sections_total": len(report_sections),
        "sections_verified": verified_sections,
        "error": sanitize_error(evidence_result.get("error", "")),
    }
    analysis = {
        "query": query,
        "tau": tau,
        "date": date,
        "domain": spec["domain"],
        "runtime": runtime,
        "logicrag_source": {
            "document_learner": runtime["document_learner"],
            "query_processing": runtime["query_processing"],
            "algorithm": "historical state alignment -> frequency filtering -> condition induction -> candidate paths -> deterministic execution order",
        },
        "constraints": {
            "date": date,
            "report_type": "query-specific report",
            "domain": spec["domain"],
            "artifact_mode": artifacts["artifact_mode"],
            "output": "state-by-state report",
        },
        "template": frontend_template,
        "raw_subtree": subtree,
        "raw_subdfa": {"node_ids": raw_node_ids, "edge_ids": raw_edge_ids},
        "subtree_root": str(metadata.get("subtree_root", "")),
        "ranked": ranked,
        "matched": matched,
        "subdfa": {"node_ids": visual_node_ids, "edge_ids": visual_edge_ids},
        "execution_order": order,
        "materials": materials,
        "report_sections": report_sections,
        "report_status": "ready" if verified_sections else "blocked",
        "evidence_summary": evidence_summary,
    }
    analysis["steps"] = build_steps(analysis, report_sections)
    return analysis


def enrich_analysis_internal_dfa(analysis: dict[str, Any]) -> dict[str, Any]:
    """Attach the current full internal DFA to stored runs created by older UI versions."""
    nodes = analysis.get("template", {}).get("nodes", []) if isinstance(analysis.get("template", {}), dict) else []
    if nodes and all(node.get("internal_dfa", {}).get("states") for node in nodes):
        return analysis
    template_path_value = analysis.get("runtime", {}).get("global_template", "")
    if not template_path_value:
        return analysis
    template_path = Path(str(template_path_value))
    if not template_path.exists():
        return analysis
    induction_path = template_path.parent / "induction_summary.json"
    induction_summary = load_json(induction_path) if induction_path.exists() else {}
    analysis["template"] = template_to_frontend(load_json(template_path), induction_summary)
    return analysis
