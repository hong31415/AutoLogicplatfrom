"""Offline induction of an evidence-condition-labeled writing DFA.

This module implements the offline half of AutoLogic over the FinLDP-Bench
CSV corpus.  The CSV section names are already aligned semantic writing
states, while non-empty sections in each historical report provide the
observed state sequence and transition context.
"""

from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


AUTOLOGIC_SCHEMA_VERSION = "autologic-condition-dfa/v1"
VIRTUAL_INITIAL_STATE = "S0"


EVIDENCE_SCHEMA: Sequence[Tuple[str, str, Sequence[str]]] = (
    ("market.price", "价格走势", ("价格", "金价", "银价", "铜价", "铝价", "指数", "期货", "现货", "涨", "跌")),
    ("market.liquidity", "市场流动性", ("成交", "资金流", "申购", "赎回", "持仓", "融资", "融券")),
    ("fundamentals.supply", "供给变化", ("供给", "供应", "产量", "产能", "进口", "出口", "减产", "停产", "开工")),
    ("fundamentals.demand", "需求变化", ("需求", "消费", "下游", "订单", "销量", "采购")),
    ("fundamentals.inventory", "库存变化", ("库存", "仓单", "去库", "累库")),
    ("macro.rates_fx", "利率与汇率", ("利率", "降息", "加息", "美元", "汇率", "美债", "流动性")),
    ("macro.growth", "宏观增长", ("GDP", "PMI", "工业", "地产", "内需", "外需", "就业", "通胀", "CPI", "PPI")),
    ("policy.event", "政策与事件", ("政策", "关税", "制裁", "地缘", "冲突", "监管", "会议")),
    ("risk.signal", "风险信号", ("风险", "不及预期", "波动", "不确定", "下行", "扰动")),
    ("strategy.signal", "策略信号", ("建议", "配置", "评级", "目标价", "增持", "买入", "谨慎")),
)


DIRECTION_RULES: Sequence[Tuple[str, str, str]] = (
    ("up", "走强/增加", r"上涨|上升|增加|增长|改善|回升|走强|扩张|去库|增持|买入"),
    ("down", "走弱/减少", r"下跌|下降|减少|回落|走弱|收缩|累库|减持|不及预期|下行"),
    ("volatile", "波动/不确定", r"波动|震荡|不确定|扰动|分化|风险"),
)


@dataclass
class HistoricalReport:
    report_id: str
    source_file: str
    states: List[Tuple[str, str]]


@dataclass
class StateAggregate:
    documents: int = 0
    total_length: int = 0
    positions: List[int] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    materials: Counter[str] = field(default_factory=Counter)


@dataclass
class TransitionAggregate:
    documents: int = 0
    contexts: List[str] = field(default_factory=list)
    events: Counter[str] = field(default_factory=Counter)


def _case_sort_key(path: Path) -> Tuple[int, str]:
    match = re.search(r"(\d+)", path.stem)
    return (int(match.group(1)) if match else math.inf, path.name)


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", str(label or "").strip())


def _compact_excerpt(text: str, limit: int = 260) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def iter_historical_reports(data_dir: str | Path, max_files: int = 500) -> Iterable[HistoricalReport]:
    directory = Path(data_dir)
    files = sorted(directory.glob("case_*.csv"), key=_case_sort_key)
    if max_files > 0:
        files = files[:max_files]

    for path in files:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row_number, row in enumerate(reader):
                states: List[Tuple[str, str]] = []
                for raw_label, raw_text in row.items():
                    if raw_label == "report_id":
                        continue
                    label = _normalize_label(raw_label)
                    text = str(raw_text or "").strip()
                    if label and text:
                        states.append((label, text))
                if not states:
                    continue
                report_id = str(row.get("report_id") or f"{path.stem}:{row_number}")
                yield HistoricalReport(report_id=report_id, source_file=path.name, states=states)


def discover_schema_order(data_dir: str | Path, max_files: int = 500) -> Dict[str, float]:
    """Recover the stable report-column order, including columns empty in a row."""
    directory = Path(data_dir)
    files = sorted(directory.glob("case_*.csv"), key=_case_sort_key)
    if max_files > 0:
        files = files[:max_files]
    positions: Dict[str, List[int]] = defaultdict(list)
    for path in files:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for position, raw_label in enumerate(reader.fieldnames or []):
                if raw_label == "report_id":
                    continue
                label = _normalize_label(raw_label)
                if label:
                    positions[label].append(position)
    return {label: sum(values) / len(values) for label, values in positions.items() if values}


def _direction(text: str) -> Tuple[str, str]:
    for key, label, pattern in DIRECTION_RULES:
        if re.search(pattern, text, flags=re.I):
            return key, label
    return "present", "出现"


def extract_evidence_events(text: str) -> Counter[str]:
    """Normalize aliases and relation synonyms into evidence predicates."""
    counts: Counter[str] = Counter()
    for sentence in re.split(r"[。！？!?；;\n]", str(text or "")):
        sentence = sentence.strip()
        if not sentence:
            continue
        direction, _ = _direction(sentence)
        for schema_key, _, aliases in EVIDENCE_SCHEMA:
            if any(alias.lower() in sentence.lower() for alias in aliases):
                normalized_direction = "volatile" if schema_key == "risk.signal" else direction
                counts[f"{schema_key}.{normalized_direction}"] += 1
    return counts


def infer_materials(label: str, text: str) -> List[str]:
    found: List[str] = []
    haystack = f"{label} {text[:900]}"
    for schema_key, display, aliases in EVIDENCE_SCHEMA:
        if any(alias.lower() in haystack.lower() for alias in aliases):
            found.append(f"{display} ({schema_key})")
    return found[:6] or [f"{label}相关事实与数据"]


def _condition_display(event: str) -> Tuple[str, str, List[str]]:
    parts = event.rsplit(".", 1)
    schema_key = parts[0]
    direction = parts[1] if len(parts) == 2 else "present"
    schema_label = next((label for key, label, _ in EVIDENCE_SCHEMA if key == schema_key), schema_key)
    direction_label = next((label for key, label, _ in DIRECTION_RULES if key == direction), "出现")
    return f"{schema_label}{direction_label}", f"{schema_key}.{direction}", [schema_key]


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper() or "CONDITION"


def _pick_discriminative_event(
    edge: Tuple[str, str],
    siblings: Sequence[Tuple[str, str]],
    aggregates: Dict[Tuple[str, str], TransitionAggregate],
) -> str:
    current = aggregates[edge]
    if not current.events:
        return ""
    best_event = ""
    best_score = float("-inf")
    for event, count in current.events.items():
        own_rate = count / max(1, current.documents)
        other_rate = max(
            (aggregates[item].events.get(event, 0) / max(1, aggregates[item].documents) for item in siblings if item != edge),
            default=0.0,
        )
        score = own_rate - other_rate + math.log1p(count) * 0.01
        if score > best_score:
            best_event = event
            best_score = score
    return best_event


def _state_guideline(label: str, aggregate: StateAggregate, domain: str) -> str:
    example = aggregate.examples[0] if aggregate.examples else ""
    base = f"围绕“{label}”完成{domain}报告中的独立语义写作任务，引用可核验的状态级证据。"
    return f"{base} 历史样例语义：{example}" if example else base


def induce_condition_labeled_dfa(
    *,
    data_dir: str | Path,
    domain: str,
    domain_key: str,
    frequency_threshold: float = 0.03,
    max_files: int = 500,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    reports = list(iter_historical_reports(data_dir, max_files=max_files))
    if not reports:
        raise ValueError(f"No non-empty historical reports found in {data_dir}.")

    schema_order = discover_schema_order(data_dir, max_files=max_files)

    state_stats: Dict[str, StateAggregate] = defaultdict(StateAggregate)
    for report in reports:
        seen: set[str] = set()
        for position, (label, text) in enumerate(report.states, start=1):
            aggregate = state_stats[label]
            if label not in seen:
                aggregate.documents += 1
                seen.add(label)
            aggregate.total_length += len(text)
            aggregate.positions.append(position)
            if len(aggregate.examples) < 3:
                aggregate.examples.append(_compact_excerpt(text))
            aggregate.materials.update(infer_materials(label, text))

    document_count = len(reports)
    retained_labels = {
        label
        for label, aggregate in state_stats.items()
        if aggregate.documents / document_count >= frequency_threshold
    }
    if not retained_labels:
        retained_labels = set(state_stats)

    transition_stats: Dict[Tuple[str, str], TransitionAggregate] = defaultdict(TransitionAggregate)
    start_counts: Counter[str] = Counter()
    final_counts: Counter[str] = Counter()
    observed_sequences: Counter[Tuple[str, ...]] = Counter()
    source_files: set[str] = set()

    for report in reports:
        source_files.add(report.source_file)
        filtered = [(label, text) for label, text in report.states if label in retained_labels]
        if not filtered:
            continue
        labels = tuple(label for label, _ in filtered)
        observed_sequences[labels] += 1
        start_counts[labels[0]] += 1
        final_counts[labels[-1]] += 1
        for (source, source_text), (target, target_text) in zip(filtered, filtered[1:]):
            aggregate = transition_stats[(source, target)]
            aggregate.documents += 1
            context = f"{source}: {_compact_excerpt(source_text, 420)}\n{target}: {_compact_excerpt(target_text, 420)}"
            if len(aggregate.contexts) < 36:
                aggregate.contexts.append(context)
            aggregate.events.update(extract_evidence_events(context))

    ordered_labels = sorted(
        retained_labels,
        key=lambda label: (
            schema_order.get(label, sum(state_stats[label].positions) / max(1, len(state_stats[label].positions))),
            label,
        ),
    )
    state_ids = {label: f"S{index}" for index, label in enumerate(ordered_labels, start=1)}

    nodes: List[Dict[str, Any]] = [
        {
            "node_id": VIRTUAL_INITIAL_STATE,
            "node_type": "root",
            "template_description": f"{domain}报告任务入口",
            "level": 0,
            "parent": None,
            "children": [state_ids[label] for label in ordered_labels],
            "content_guideline": "根据用户意图和可用证据选择第一个可执行写作状态。",
            "required_materials": [],
            "length": 0,
            "act": "route",
            "data": [],
            "index_exclude": True,
            "state_frequency": 1.0,
        }
    ]
    for order, label in enumerate(ordered_labels, start=1):
        aggregate = state_stats[label]
        materials = [item for item, _ in aggregate.materials.most_common(6)]
        nodes.append(
            {
                "node_id": state_ids[label],
                "node_type": "leaf",
                "template_description": label,
                "level": order,
                "parent": VIRTUAL_INITIAL_STATE,
                "children": [],
                "content_guideline": _state_guideline(label, aggregate, domain),
                "required_materials": materials,
                "length": round(aggregate.total_length / max(1, aggregate.documents)),
                "act": f"generate:{label}",
                "data": materials,
                "state_order": order,
                "state_frequency": round(aggregate.documents / document_count, 6),
                "support_documents": aggregate.documents,
            }
        )

    retained_edges = {
        edge: aggregate
        for edge, aggregate in transition_stats.items()
        if aggregate.documents / document_count >= frequency_threshold
    }
    for label, count in start_counts.items():
        if label in retained_labels and count / document_count >= frequency_threshold:
            retained_edges[(VIRTUAL_INITIAL_STATE, label)] = TransitionAggregate(documents=count)

    outgoing: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for source_label, target_label in retained_edges:
        source_id = VIRTUAL_INITIAL_STATE if source_label == VIRTUAL_INITIAL_STATE else state_ids[source_label]
        outgoing[source_id].append((source_label, target_label))

    transitions: List[Dict[str, Any]] = []
    alphabet_by_symbol: Dict[str, Dict[str, Any]] = {}
    for edge, aggregate in sorted(
        retained_edges.items(),
        key=lambda item: (
            -1 if item[0][0] == VIRTUAL_INITIAL_STATE else ordered_labels.index(item[0][0]),
            ordered_labels.index(item[0][1]),
        ),
    ):
        source_label, target_label = edge
        source_id = VIRTUAL_INITIAL_STATE if source_label == VIRTUAL_INITIAL_STATE else state_ids[source_label]
        target_id = state_ids[target_label]
        siblings = outgoing[source_id]
        priority_order = sorted(siblings, key=lambda item: retained_edges[item].documents, reverse=True)
        priority = priority_order.index(edge) + 1
        direct = len(siblings) == 1

        if direct:
            event = "direct"
            condition_label = "唯一稳定后继，直接转移"
            predicate = "TRUE"
            evidence_keys: List[str] = []
            mode = "direct"
        elif source_id == VIRTUAL_INITIAL_STATE:
            event = f"query.intent.{target_id.lower()}"
            condition_label = f"用户意图要求“{target_label}”"
            predicate = f"query.intent == '{target_label}'"
            evidence_keys = ["query.intent"]
            mode = "query-intent"
        else:
            historical_edge = (source_label, target_label)
            event = _pick_discriminative_event(historical_edge, siblings, transition_stats)
            if event:
                event_label, predicate, evidence_keys = _condition_display(event)
                condition_label = f"{event_label}，转入“{target_label}”"
                mode = "historical-evidence"
            else:
                event = f"evidence.section.{target_id.lower()}"
                condition_label = f"证据支持“{target_label}”写作任务"
                predicate = f"evidence.supports('{target_label}')"
                evidence_keys = ["section.evidence"]
                mode = "semantic-fallback"

        symbol = f"SIGMA_{source_id}_{target_id}_{_slug(event)}"
        condition = {
            "symbol": symbol,
            "label": condition_label,
            "predicate": predicate,
            "evidence_schema": evidence_keys,
            "mode": mode,
            "direct": direct,
            "priority": priority,
            "historical_support": aggregate.documents,
            "top_normalized_events": [item for item, _ in aggregate.events.most_common(5)],
        }
        alphabet_by_symbol[symbol] = condition
        transitions.append(
            {
                "id": f"T{len(transitions) + 1:03d}",
                "source": source_id,
                "target": target_id,
                "condition_symbol": symbol,
                "condition_label": condition_label,
                "condition": condition,
                "frequency": round(aggregate.documents / document_count, 6),
                "support_documents": aggregate.documents,
                "priority": priority,
                "direct": direct,
            }
        )

    deterministic_keys = [(edge["source"], edge["condition_symbol"]) for edge in transitions]
    if len(deterministic_keys) != len(set(deterministic_keys)):
        raise ValueError("Condition normalization produced a non-deterministic transition function.")

    outgoing_ids = {edge["source"] for edge in transitions}
    sink_states = {state_ids[label] for label in ordered_labels if state_ids[label] not in outgoing_ids}
    if not sink_states and final_counts:
        most_common_final = next((label for label, _ in final_counts.most_common() if label in state_ids), "")
        if most_common_final:
            sink_states.add(state_ids[most_common_final])
    final_states = sorted(sink_states, key=lambda item: int(item[1:]))

    template = {
        "template_id": f"{domain_key}_autologic_condition_dfa",
        "language": "zh",
        "template_description": f"{domain} condition-labeled writing DFA",
        "structure_pattern": {
            "reasoning_logic": "按历史稳定写作状态与证据条件动态选择后继状态。",
            "node_types": ["root", "leaf"],
            "transitions": transitions,
        },
        "node_template": {"nodes": nodes},
        "material_requirements_summary": sorted({item for node in nodes for item in node["required_materials"]}),
        "dfa": {
            "kind": "condition-labeled-semantic-dfa",
            "states": [node["node_id"] for node in nodes],
            "alphabet": list(alphabet_by_symbol.values()),
            "transition_function": [
                {"state": edge["source"], "condition": edge["condition_symbol"], "next_state": edge["target"]}
                for edge in transitions
            ],
            "initial_state": VIRTUAL_INITIAL_STATE,
            "final_states": final_states,
            "deterministic": True,
        },
        "usage_instruction": {
            "offline": "Reuse this cached DFA; rebuild only when the historical corpus or induction configuration changes.",
            "online": "Match the conversation to states, form a candidate subgraph, then select an evidence-supported path.",
        },
        "logicrag_metadata": {
            "schema_version": AUTOLOGIC_SCHEMA_VERSION,
            "method": "autologic-condition-dfa",
            "artifact_mode": "autologic-offline",
            "domain_key": domain_key,
            "historical_document_count": document_count,
            "historical_case_file_count": len(source_files),
            "frequency_threshold": frequency_threshold,
            "global_state_count": len(nodes),
            "semantic_state_count": len(nodes) - 1,
            "transition_count": len(transitions),
            "branching_state_count": sum(1 for edges in outgoing.values() if len(edges) > 1),
            "condition_induction": "normalized evidence events + sibling-contrast scoring",
            "state_alignment": "normalized FinLDP section semantics",
            "source_documents": sorted(source_files),
        },
    }
    summary = {
        "document_count": document_count,
        "case_file_count": len(source_files),
        "sequence_pattern_count": len(observed_sequences),
        "top_sequences": [
            {"states": list(sequence), "documents": count, "frequency": round(count / document_count, 6)}
            for sequence, count in observed_sequences.most_common(20)
        ],
        "state_frequencies": {
            label: round(state_stats[label].documents / document_count, 6) for label in ordered_labels
        },
        "transition_frequencies": {
            f"{source}->{target}": round(aggregate.documents / document_count, 6)
            for (source, target), aggregate in retained_edges.items()
        },
    }
    return template, summary
