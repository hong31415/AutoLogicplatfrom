from __future__ import annotations

import base64
import csv
import html
import io
import json
import re
import threading
import time
import uuid
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree

from app.config import BACKEND_ROOT
from app.database import archive_template_dfa as archive_template_dfa_db
from app.database import get_template_dfa, list_template_dfas, save_template_dfa


UPLOAD_ROOT = BACKEND_ROOT / "data" / "template_uploads"
MAX_FILE_COUNT = 20
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 40 * 1024 * 1024
MAX_EXTRACTED_BYTES = 25 * 1024 * 1024
MAX_EXTRACTED_CHARACTERS = 2_000_000
SUPPORTED_SUFFIXES = {".txt", ".md", ".csv", ".json", ".html", ".htm", ".docx", ".pptx", ".xlsx", ".pdf"}

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "precious_metals": ("黄金", "白银", "贵金属", "有色", "铜", "铝", "金价", "银价", "gold", "silver", "copper", "aluminum"),
    "etf": ("etf", "基金", "申购", "赎回", "份额", "净值", "指数基金"),
    "macro": ("宏观", "gdp", "pmi", "cpi", "ppi", "通胀", "利率", "汇率", "财政", "货币政策", "房地产"),
    "cotton": ("棉花", "棉纱", "纺织", "郑棉", "cotton"),
    "agriculture": ("农产品", "玉米", "大豆", "豆粕", "白糖", "生猪", "小麦", "agriculture"),
}
DOMAIN_ANCHORS: dict[str, tuple[str, ...]] = {
    "precious_metals": ("黄金", "白银", "贵金属", "有色", "gold", "silver", "copper", "aluminum"),
    "etf": ("etf", "指数基金", "基金份额"),
    "macro": ("宏观报告", "gdp", "pmi", "cpi", "ppi"),
    "cotton": ("棉花", "棉纱", "郑棉", "cotton"),
    "agriculture": ("农产品", "玉米", "大豆", "豆粕", "白糖", "生猪", "小麦"),
}

STATE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("投资建议", ("投资建议", "配置建议", "操作建议", "策略建议", "investment", "recommendation", "strategy")),
    ("行业观点", ("行业观点", "核心观点", "市场观点", "观点", "view", "outlook")),
    ("行情回顾", ("行情回顾", "市场回顾", "价格回顾", "市场表现", "本周走势", "行情", "market review", "performance")),
    ("宏观与政策", ("宏观", "利率", "汇率", "美元", "通胀", "政策", "macro", "interest rate", "policy", "inflation")),
    ("供给分析", ("供给", "供应", "产量", "产能", "进口", "矿端", "supply", "production", "import")),
    ("需求分析", ("需求", "消费", "下游", "采购", "订单", "demand", "consumption")),
    ("库存分析", ("库存", "仓单", "去库", "累库", "inventory", "stock")),
    ("行业跟踪", ("行业跟踪", "产业跟踪", "基本面", "产业链", "industry tracking", "fundamentals")),
    ("风险提示", ("风险", "不确定", "下行", "波动", "risk", "uncertainty")),
    ("结论与展望", ("结论", "总结", "展望", "后市", "conclusion", "summary")),
)

MATERIAL_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("价格走势", "market.price", ("价格", "行情", "涨跌", "结算价", "收盘", "price", "return")),
    ("成交与持仓", "market.liquidity", ("成交", "持仓", "资金流", "申购", "赎回", "volume", "liquidity")),
    ("供给变化", "fundamentals.supply", ("供给", "供应", "产量", "进口", "产能", "supply")),
    ("需求变化", "fundamentals.demand", ("需求", "消费", "下游", "订单", "demand")),
    ("库存变化", "fundamentals.inventory", ("库存", "仓单", "去库", "累库", "inventory")),
    ("利率与汇率", "macro.rates_fx", ("利率", "汇率", "美元", "美债", "rates", "fx")),
    ("宏观增长", "macro.growth", ("gdp", "pmi", "cpi", "ppi", "增长", "通胀", "制造业", "macro")),
    ("政策事件", "policy.event", ("政策", "监管", "财政", "货币", "制裁", "policy")),
    ("风险信号", "risk.signal", ("风险", "波动", "不确定", "下行", "risk")),
    ("策略信号", "strategy.signal", ("建议", "配置", "评级", "目标价", "策略", "recommendation")),
)


@dataclass
class ParsedDocument:
    name: str
    suffix: str
    text: str
    sections: list[tuple[str, str]]
    warnings: list[str] = field(default_factory=list)


_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def _record_file(job_dir: Path) -> Path:
    return job_dir / "dfa_record.json"


def _save_file_record(
    job_dir: Path,
    graph: dict[str, Any],
    quality: dict[str, Any],
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    record = {
        "id": str(graph.get("id") or ""),
        "name": str(graph.get("name") or "上传模板 DFA"),
        "domain": str(graph.get("baseDomain") or "macro"),
        "category": str(graph.get("category") or "未分类模板"),
        "origin": "uploaded-template",
        "graph": graph,
        "quality": quality,
        "files": files,
        "storage_path": str(job_dir.resolve()),
        "archived": False,
        "created_at": now,
        "updated_at": now,
    }
    _record_file(job_dir).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def _file_records(*, include_archived: bool = False) -> list[dict[str, Any]]:
    if not UPLOAD_ROOT.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in UPLOAD_ROOT.glob("*/dfa_record.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(item, dict) and (include_archived or not item.get("archived")):
                records.append(item)
        except (OSError, json.JSONDecodeError):
            continue
    records.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return records


def _safe_name(value: str) -> str:
    name = Path(str(value or "template")).name
    name = re.sub(r"[^\w.\-()（）\u4e00-\u9fff ]+", "_", name, flags=re.UNICODE).strip(" ._")
    return name[:160] or "template.txt"


def _clean_text(value: str) -> str:
    value = html.unescape(str(value or "")).replace("\x00", "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "big5"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _xml_text(data: bytes, paragraph_tags: tuple[str, ...]) -> str:
    root = ElementTree.fromstring(data)
    blocks: list[str] = []
    for element in root.iter():
        if not any(element.tag.endswith(tag) for tag in paragraph_tags):
            continue
        texts = [child.text or "" for child in element.iter() if child.tag.endswith(("}t", "}v"))]
        line = "".join(texts).strip()
        if line:
            blocks.append(line)
    return "\n\n".join(blocks)


def _checked_zip_names(archive: zipfile.ZipFile, names: list[str]) -> list[str]:
    info_by_name = {item.filename: item for item in archive.infolist()}
    selected = [name for name in names if name in info_by_name]
    expanded_size = sum(info_by_name[name].file_size for name in selected)
    if expanded_size > MAX_EXTRACTED_BYTES:
        raise ValueError("压缩模板展开后超过 25 MB 安全限制")
    return selected


def _extract_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = _checked_zip_names(archive, ["word/document.xml"])
        if not names:
            raise ValueError("DOCX 中没有找到正文内容")
        return _xml_text(archive.read(names[0]), ("}p",))


def _extract_pptx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = sorted(name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
        names = _checked_zip_names(archive, names)
        return "\n\n".join(_xml_text(archive.read(name), ("}p",)) for name in names)


def _extract_xlsx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names_to_read = [name for name in archive.namelist() if name == "xl/sharedStrings.xml" or re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)]
        allowed_names = set(_checked_zip_names(archive, names_to_read))
        shared: list[str] = []
        if "xl/sharedStrings.xml" in allowed_names:
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root:
                shared.append("".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")))
        rows: list[str] = []
        sheet_names = sorted(name for name in allowed_names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
        for name in sheet_names:
            root = ElementTree.fromstring(archive.read(name))
            for row in (node for node in root.iter() if node.tag.endswith("}row")):
                values: list[str] = []
                for cell in (node for node in row if node.tag.endswith("}c")):
                    value_node = next((node for node in cell.iter() if node.tag.endswith("}v")), None)
                    value = value_node.text if value_node is not None and value_node.text else ""
                    if cell.attrib.get("t") == "s" and value.isdigit() and int(value) < len(shared):
                        value = shared[int(value)]
                    if value.strip():
                        values.append(value.strip())
                if values:
                    rows.append(" | ".join(values))
        return "\n".join(rows)


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise ValueError("PDF 解析组件尚未安装，请安装 requirements.txt 后重试。") from exc
    reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) > 300:
        raise ValueError("PDF 超过 300 页安全限制，请拆分后上传")
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_raw_text(name: str, data: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        return _decode_text(data)
    if suffix in {".html", ".htm"}:
        source = _decode_text(data)
        source = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", source, flags=re.I | re.S)
        return re.sub(r"<[^>]+>", "\n", source)
    if suffix == ".docx":
        return _extract_docx(data)
    if suffix == ".pptx":
        return _extract_pptx(data)
    if suffix == ".xlsx":
        return _extract_xlsx(data)
    if suffix == ".pdf":
        return _extract_pdf(data)
    raise ValueError(f"不支持的文件格式：{suffix or '未知'}")


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip().strip("#* ")
    if not stripped or len(stripped) > 70:
        return False
    if re.match(r"^(#{1,6}\s+|第[一二三四五六七八九十百\d]+[章节部分]|[一二三四五六七八九十]+[、.]|\d+(?:\.\d+)*[、.．)）\s])", line.strip(), re.I):
        return True
    if stripped.endswith(("：", ":")) and len(stripped) <= 36:
        return True
    if stripped.endswith(("。", "！", "？", ".", "!", "?", "；", ";")):
        return False
    compact = re.sub(r"\s+", "", stripped)
    return len(compact) <= 18 and any(keyword in compact.lower() for _, aliases in STATE_RULES for keyword in aliases)


def _sectionize(name: str, text: str) -> list[tuple[str, str]]:
    suffix = Path(name).suffix.lower()
    if suffix == ".json":
        try:
            value = json.loads(text)
            candidates = value.get("sections") if isinstance(value, dict) and isinstance(value.get("sections"), list) else value
            sections: list[tuple[str, str]] = []
            if isinstance(candidates, list):
                for index, item in enumerate(candidates, start=1):
                    if isinstance(item, dict):
                        title = next((str(item.get(key) or "").strip() for key in ("title", "name", "label", "section") if item.get(key)), f"内容单元 {index}")
                        content = next((item.get(key) for key in ("content", "text", "body", "value") if item.get(key) is not None), item)
                    else:
                        title, content = f"内容单元 {index}", item
                    rendered = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)
                    if rendered.strip():
                        sections.append((title[:80], rendered.strip()[:8000]))
            elif isinstance(candidates, dict):
                for key, item in candidates.items():
                    rendered = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, default=str)
                    if rendered.strip():
                        sections.append((str(key)[:80], rendered.strip()[:8000]))
            if len(sections) >= 2:
                return sections[:30]
        except json.JSONDecodeError:
            pass

    if suffix == ".csv":
        reader = csv.DictReader(io.StringIO(text))
        fields = [field.strip() for field in (reader.fieldnames or []) if field and field.strip().lower() not in {"report_id", "id"}]
        rows = list(reader)
        sections = []
        for field in fields:
            content = "\n".join(str(row.get(field) or "").strip() for row in rows if str(row.get(field) or "").strip())
            if content:
                sections.append((field, content[:8000]))
        if sections:
            return sections

    if suffix == ".xlsx":
        rows = [[cell.strip() for cell in line.split("|")] for line in text.splitlines() if line.strip()]
        rows = [row for row in rows if any(row)]
        if len(rows) >= 2 and len(rows[0]) >= 2:
            width = max(len(row) for row in rows)
            sections = []
            for column in range(width):
                title = rows[0][column] if column < len(rows[0]) and rows[0][column] else f"字段 {column + 1}"
                content = "\n".join(row[column] for row in rows[1:] if column < len(row) and row[column])
                if content:
                    sections.append((title[:80], content[:8000]))
            if len(sections) >= 2:
                return sections[:30]
        row_sections = [(row[0][:80], " | ".join(row[1:])[:8000]) for row in rows if len(row) >= 2 and row[0] and any(row[1:])]
        if len(row_sections) >= 2:
            return row_sections[:30]

    lines = [line.strip() for line in text.splitlines()]
    sections: list[tuple[str, str]] = []
    current_title = ""
    buffer: list[str] = []
    for line in lines:
        if _looks_like_heading(line):
            if current_title and any(item.strip() for item in buffer):
                sections.append((current_title, "\n".join(buffer).strip()))
            current_title = re.sub(r"^(#{1,6}\s+|第[一二三四五六七八九十百\d]+[章节部分]\s*|[一二三四五六七八九十]+[、.]\s*|\d+(?:\.\d+)*[、.．)）\s]*)", "", line).strip(" ：:")
            buffer = []
        elif line:
            buffer.append(line)
    if current_title and buffer:
        sections.append((current_title, "\n".join(buffer).strip()))
    if len(sections) >= 2:
        return sections[:30]

    paragraphs = [item.strip() for item in re.split(r"\n\s*\n|(?<=[。！？.!?])\s*\n", text) if len(item.strip()) >= 16]
    if not paragraphs:
        paragraphs = [text]
    chunk_size = max(1, (len(paragraphs) + 7) // 8)
    fallback: list[tuple[str, str]] = []
    for index in range(0, len(paragraphs), chunk_size):
        chunk = "\n".join(paragraphs[index:index + chunk_size]).strip()
        first = re.split(r"[。！？.!?\n]", chunk)[0].strip()
        fallback.append((first[:28] or f"内容单元 {len(fallback) + 1}", chunk[:8000]))
    return fallback[:10]


def _canonical_label(label: str, content: str) -> str:
    haystack = f"{label} {content[:600]}".lower()
    for canonical, aliases in STATE_RULES:
        if any(alias.lower() in haystack for alias in aliases):
            return canonical
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "", label, flags=re.UNICODE)
    cleaned = re.sub(r"^(第?[一二三四五六七八九十百\d]+)(章节部分)?", "", cleaned)
    return (cleaned[:24] or "内容分析").strip()


def _merge_label(label: str, existing: list[str]) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", label.lower())
    for candidate in existing:
        other = re.sub(r"[^\w\u4e00-\u9fff]+", "", candidate.lower())
        if normalized == other or SequenceMatcher(None, normalized, other).ratio() >= 0.86:
            return candidate
    return label


def _infer_materials(label: str, content: str) -> list[str]:
    haystack = f"{label} {content[:1600]}".lower()
    found = [f"{title} ({key})" for title, key, aliases in MATERIAL_RULES if any(alias.lower() in haystack for alias in aliases)]
    return found[:6] or [f"{label}相关事实与数据"]


def _classify_domain(documents: list[ParsedDocument], hint: str) -> tuple[str, dict[str, int]]:
    if hint in DOMAIN_KEYWORDS:
        return hint, {hint: 100}
    text = " ".join(f"{doc.name} {doc.text[:8000]}" for doc in documents).lower()
    scores = {
        domain: sum(text.count(keyword.lower()) for keyword in keywords)
        + 3 * sum(text.count(keyword.lower()) for keyword in DOMAIN_ANCHORS.get(domain, ()))
        for domain, keywords in DOMAIN_KEYWORDS.items()
    }
    domain = max(scores, key=scores.get) if any(scores.values()) else "macro"
    return domain, scores


def _parse_uploaded_file(file_item: dict[str, Any], job_dir: Path) -> ParsedDocument:
    name = _safe_name(str(file_item.get("name") or "template.txt"))
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"{name}：暂不支持 {suffix or '未知'} 格式")
    try:
        data = base64.b64decode(str(file_item.get("content_base64") or ""), validate=True)
    except ValueError as exc:
        raise ValueError(f"{name}：文件内容编码无效") from exc
    if not data:
        raise ValueError(f"{name}：文件为空")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"{name}：文件超过 10 MB 限制")
    stored_name = f"{uuid.uuid4().hex[:10]}-{name}"
    (job_dir / stored_name).write_bytes(data)
    text = _clean_text(_extract_raw_text(name, data))
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise ValueError(f"{name}：提取文本超过 200 万字符，请拆分后上传")
    if len(text) < 20:
        raise ValueError(f"{name}：没有提取到足够的可读文本")
    return ParsedDocument(name=name, suffix=suffix, text=text, sections=_sectionize(name, text))


def _build_graph(documents: list[ParsedDocument], name: str, domain: str, category: str, threshold: float) -> tuple[dict[str, Any], dict[str, Any]]:
    sequences: list[list[str]] = []
    state_docs: Counter[str] = Counter()
    state_examples: dict[str, list[str]] = defaultdict(list)
    state_materials: dict[str, Counter[str]] = defaultdict(Counter)
    state_positions: dict[str, list[int]] = defaultdict(list)
    known_labels: list[str] = []

    for document in documents:
        sequence: list[str] = []
        seen: set[str] = set()
        for position, (raw_label, content) in enumerate(document.sections, start=1):
            canonical = _merge_label(_canonical_label(raw_label, content), known_labels)
            if canonical not in known_labels:
                known_labels.append(canonical)
            if sequence and sequence[-1] == canonical:
                continue
            sequence.append(canonical)
            state_positions[canonical].append(position)
            if len(state_examples[canonical]) < 3:
                state_examples[canonical].append(content[:320])
            state_materials[canonical].update(_infer_materials(canonical, content))
            if canonical not in seen:
                state_docs[canonical] += 1
                seen.add(canonical)
        if sequence:
            sequences.append(sequence)

    document_count = len(sequences)
    if not document_count:
        raise ValueError("上传文件中没有识别出可用的写作状态序列")
    retained = [label for label in known_labels if state_docs[label] / document_count >= threshold]
    if len(retained) < 2:
        retained = sorted(known_labels, key=lambda item: (-state_docs[item], sum(state_positions[item]) / len(state_positions[item])))[:max(2, min(8, len(known_labels)))]
    retained_set = set(retained)
    ordered = sorted(retained, key=lambda item: (sum(state_positions[item]) / max(1, len(state_positions[item])), -state_docs[item], item))
    state_ids = {label: f"S{index:02d}" for index, label in enumerate(ordered, start=1)}

    transition_counts: Counter[tuple[str, str]] = Counter()
    start_counts: Counter[str] = Counter()
    for sequence in sequences:
        filtered = [label for label in sequence if label in retained_set]
        if not filtered:
            continue
        start_counts[filtered[0]] += 1
        transition_counts.update(zip(filtered, filtered[1:]))

    nodes: list[dict[str, Any]] = [{
        "id": "S0", "label": "任务入口", "type": "root", "level": 0, "parent": None,
        "children": [], "guideline": "根据用户意图和上传模板归纳的结构选择第一个写作状态。",
        "materials": [], "support_documents": document_count, "frequency": 1.0,
    }]
    for index, label in enumerate(ordered, start=1):
        materials = [item for item, _ in state_materials[label].most_common(6)]
        examples = state_examples[label]
        nodes.append({
            "id": state_ids[label], "label": label, "type": "leaf", "level": index, "parent": "S0", "children": [],
            "guideline": f"按照上传模板中“{label}”的稳定语义功能完成该段落。" + (f" 参考表达：{examples[0][:180]}" if examples else ""),
            "materials": materials, "support_documents": state_docs[label],
            "frequency": round(state_docs[label] / document_count, 6),
        })

    edge_specs: list[tuple[str, str, int]] = []
    for label, count in start_counts.items():
        if label in retained_set:
            edge_specs.append(("S0", state_ids[label], count))
    for (source, target), count in transition_counts.items():
        if source in retained_set and target in retained_set and count / document_count >= threshold:
            edge_specs.append((state_ids[source], state_ids[target], count))

    reachable = {"S0"}
    changed = True
    while changed:
        changed = False
        for source, target, _ in edge_specs:
            if source in reachable and target not in reachable:
                reachable.add(target)
                changed = True
    for label in ordered:
        node_id = state_ids[label]
        if node_id not in reachable:
            edge_specs.append(("S0", node_id, state_docs[label]))
            reachable.add(node_id)

    outgoing: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for spec in edge_specs:
        outgoing[spec[0]].append(spec)
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    label_by_id = {node["id"]: node["label"] for node in nodes}
    for source, target, count in edge_specs:
        if (source, target) in seen_edges:
            continue
        seen_edges.add((source, target))
        branching = len({item[1] for item in outgoing[source]}) > 1
        target_label = label_by_id[target]
        condition_label = f"用户意图或模板证据需要“{target_label}”" if branching or source == "S0" else "唯一稳定后继，直接转移"
        predicate = f"evidence.supports('{target_label}')" if branching or source == "S0" else "TRUE"
        edges.append({
            "id": f"T{len(edges) + 1:03d}", "source": source, "target": target,
            "condition_label": condition_label, "predicate": predicate,
            "support_documents": count, "frequency": round(count / document_count, 6), "origin": "uploaded-template",
        })
    root = nodes[0]
    root["children"] = [edge["target"] for edge in edges if edge["source"] == "S0"]
    for node in nodes[1:]:
        node["children"] = [edge["target"] for edge in edges if edge["source"] == node["id"]]

    graph_id = f"upload-{uuid.uuid4().hex[:20]}"
    graph = {
        "id": graph_id,
        "name": name,
        "baseDomain": domain,
        "category": category or "未分类模板",
        "origin": "uploaded-template",
        "nodes": nodes,
        "edges": edges,
        "sourceFiles": [document.name for document in documents],
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    state_coverage = sum(state_docs[label] for label in retained) / max(1, document_count * len(retained))
    quality = {
        "document_count": document_count,
        "recognized_section_count": sum(len(document.sections) for document in documents),
        "state_count": len(nodes) - 1,
        "transition_count": len(edges),
        "frequency_threshold": threshold,
        "average_state_coverage": round(state_coverage, 4),
        "confidence": "high" if document_count >= 3 and state_coverage >= 0.6 else "medium" if len(nodes) >= 3 else "low",
        "warnings": [warning for document in documents for warning in document.warnings],
    }
    return graph, quality


def _update_job(job_id: str, **updates: Any) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        if "message" in updates:
            job.setdefault("logs", []).append({"time": datetime.now().strftime("%H:%M:%S"), "message": updates["message"]})
        job.update(updates)
        job["updated_at"] = datetime.now().isoformat(timespec="seconds")


def _run_build(job_id: str, payload: dict[str, Any]) -> None:
    try:
        files = payload.get("files") or []
        job_dir = UPLOAD_ROOT / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        _update_job(job_id, status="running", progress=8, stage="validating", message="已验证上传清单，开始读取模板文件。")
        time.sleep(0.15)

        documents: list[ParsedDocument] = []
        errors: list[str] = []
        _update_job(job_id, progress=18, stage="extracting", message=f"正在解析 {len(files)} 个模板文件。")
        for index, file_item in enumerate(files, start=1):
            try:
                document = _parse_uploaded_file(file_item, job_dir)
                documents.append(document)
                _update_job(job_id, progress=min(42, 18 + round(index / len(files) * 24)), message=f"已解析 {document.name}，识别 {len(document.sections)} 个内容单元。")
            except Exception as exc:  # noqa: BLE001 - report individual file failures without losing valid files.
                errors.append(str(exc))
                _update_job(job_id, message=f"跳过文件：{exc}")
        if not documents:
            raise ValueError("所有文件均解析失败：" + "；".join(errors[:5]))

        _update_job(job_id, progress=50, stage="classifying", message="正在识别报告领域和模板类别。")
        domain, domain_scores = _classify_domain(documents, str(payload.get("domain") or "auto"))
        time.sleep(0.15)
        _update_job(job_id, progress=62, stage="aligning", message="正在对齐不同文件中的同义写作状态。")
        time.sleep(0.15)
        _update_job(job_id, progress=74, stage="inducing", message="正在统计状态频率和相邻转移，归纳稳定结构。")
        graph, quality = _build_graph(
            documents,
            str(payload.get("name") or "上传模板 DFA").strip()[:120] or "上传模板 DFA",
            domain,
            str(payload.get("category") or "未分类模板").strip()[:80],
            max(0.05, min(0.95, float(payload.get("frequency_threshold") or 0.3))),
        )
        quality["domain_scores"] = domain_scores
        quality["file_errors"] = errors
        _update_job(job_id, progress=88, stage="validating_graph", message="正在检查入口、可达性、转移唯一性和材料规则。")
        if not graph["nodes"] or not graph["edges"]:
            raise ValueError("构建结果缺少可执行状态或转移")
        time.sleep(0.15)
        _update_job(job_id, progress=95, stage="saving", message="结构检查通过，正在按领域与类别归档。")
        file_summaries = [
            {"name": document.name, "suffix": document.suffix, "section_count": len(document.sections), "text_length": len(document.text)}
            for document in documents
        ]
        _save_file_record(job_dir, graph, quality, file_summaries)
        try:
            saved_id = save_template_dfa(
                graph=graph,
                quality=quality,
                files=file_summaries,
                storage_path=str(job_dir.resolve()),
            )
        except Exception as exc:  # noqa: BLE001 - local file archive remains available if the database is offline.
            saved_id = None
            quality.setdefault("warnings", []).append(f"数据库归档暂不可用，已保存到本地文件：{exc}")
            _save_file_record(job_dir, graph, quality, file_summaries)
            _update_job(job_id, message="数据库归档暂不可用，已自动切换到本地文件保存。")
        if saved_id:
            graph["serverId"] = saved_id
        _update_job(
            job_id,
            status="complete",
            progress=100,
            stage="complete",
            message=f"构建完成：{len(graph['nodes']) - 1} 个写作状态、{len(graph['edges'])} 条转移。",
            result_dfa_id=saved_id or graph["id"],
            result=graph,
            quality=quality,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the progress UI.
        _update_job(job_id, status="error", stage="error", error=str(exc), message=f"构建失败：{exc}")


def create_template_dfa_job(payload: dict[str, Any]) -> dict[str, Any]:
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("请至少上传一个模板文件")
    if len(files) > MAX_FILE_COUNT:
        raise ValueError(f"一次最多上传 {MAX_FILE_COUNT} 个文件")
    estimated_total = sum(max(0, len(str(item.get("content_base64") or "")) * 3 // 4) for item in files if isinstance(item, dict))
    if estimated_total > MAX_TOTAL_BYTES:
        raise ValueError("本次上传内容超过 40 MB 限制")
    job_id = uuid.uuid4().hex
    now = datetime.now().isoformat(timespec="seconds")
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": 2,
            "stage": "queued",
            "name": str(payload.get("name") or "上传模板 DFA")[:120],
            "logs": [{"time": datetime.now().strftime("%H:%M:%S"), "message": "构建任务已创建，等待处理。"}],
            "created_at": now,
            "updated_at": now,
        }
    threading.Thread(target=_run_build, args=(job_id, payload), name=f"template-dfa-{job_id[:8]}", daemon=True).start()
    return get_template_dfa_job(job_id) or {}


def get_template_dfa_job(job_id: str) -> dict[str, Any] | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        return json.loads(json.dumps(job, ensure_ascii=False, default=str)) if job else None


def template_dfa_library() -> list[dict[str, Any]]:
    try:
        database_items = list_template_dfas()
    except Exception:  # noqa: BLE001 - use durable local records while the database is unavailable.
        database_items = []
    items_by_id = {str(item.get("id") or ""): item for item in _file_records()}
    for item in database_items:
        items_by_id[str(item.get("id") or "")] = item
    return sorted(
        (item for key, item in items_by_id.items() if key),
        key=lambda item: (str(item.get("domain") or ""), str(item.get("category") or ""), str(item.get("updated_at") or "")),
        reverse=True,
    )


def template_dfa_detail(dfa_id: str) -> dict[str, Any] | None:
    try:
        item = get_template_dfa(dfa_id)
    except Exception:  # noqa: BLE001 - local records are the availability fallback.
        item = None
    if item:
        return item
    return next((record for record in _file_records() if str(record.get("id") or "") == dfa_id), None)


def archive_template_dfa_record(dfa_id: str) -> bool:
    archived = False
    try:
        archived = archive_template_dfa_db(dfa_id)
    except Exception:  # noqa: BLE001 - the file record is independently archivable.
        archived = False
    for record in _file_records(include_archived=True):
        if str(record.get("id") or "") != dfa_id or record.get("archived"):
            continue
        record["archived"] = True
        record["updated_at"] = datetime.now().isoformat(timespec="seconds")
        Path(str(record.get("storage_path") or ""), "dfa_record.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        archived = True
        break
    return archived
