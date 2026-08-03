"""
LogicRAG document learner.

This module implements the document-logic extraction stage described in the
LogicRAG paper:

1. Read two sample reports from the same CSV-style dataset format used by the
   original ReportAgent prototype.
2. Extract one state sequence from each report with the same node-style schema
   used by the old document_learner output.
3. Match states that appear in both reports by semantic similarity
   (theta=0.85 by default) and build a global state set.
4. Save a template-like JSON file and a JSON embedding index for later query
   matching.

The script intentionally does not hard-code API keys. Set DEEPSEEK_API_KEY or
OPENAI_API_KEY in the environment before running.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pandas as pd
except ModuleNotFoundError:  # Cached DFA query execution does not require pandas.
    pd = None


DEFAULT_CHAT_MODEL = os.environ.get("LOGICRAG_CHAT_MODEL", "deepseek-chat")
DEFAULT_CHAT_BASE_URL = os.environ.get("LOGICRAG_CHAT_BASE_URL", "https://api.deepseek.com")
DEFAULT_EMBEDDING_MODEL = os.environ.get("LOGICRAG_EMBEDDING_MODEL", "text-embedding-v4")
DEFAULT_EMBEDDING_BASE_URL = (
    os.environ.get("LOGICRAG_EMBEDDING_BASE_URL")
    or os.environ.get("DASHSCOPE_API_BASE")
    or "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
DEFAULT_EMBEDDING_BATCH_SIZE = int(os.environ.get("LOGICRAG_EMBEDDING_BATCH_SIZE", "10"))
DEFAULT_THETA = 0.5
LOCAL_EMBEDDING_DIM = 384


# ---------------------------------------------------------------------------
# Dataset loading: keep the original ReportAgent CSV-row input style.
# ---------------------------------------------------------------------------


def build_report_text_from_row(row: Dict[str, Any]) -> str:
    """Concatenate one CSV row into a report-like full text."""
    sections: List[str] = []
    for key, value in row.items():
        if key == "report_id":
            continue
        if isinstance(value, str) and value.strip():
            sections.append(f"{key}:\n{value.strip()}")
    return "\n\n".join(sections)


def read_report_from_csv(csv_file: str | Path, index: int) -> Tuple[str, str]:
    """Read one report row from a CSV file and return (report_id, full_text)."""
    if pd is None:
        raise RuntimeError("pandas is required to learn a DFA from CSV documents.")
    df = pd.read_csv(csv_file)
    if index < 0 or index >= len(df):
        raise IndexError(f"CSV has {len(df)} rows, cannot read row {index}.")

    row = df.iloc[index].to_dict()
    report_id = str(row.get("report_id", f"row_{index}"))
    return report_id, build_report_text_from_row(row)


def concat_sections(row: Dict[str, Any]) -> str:
    """Compatibility alias for older code."""
    return build_report_text_from_row(row)


# ---------------------------------------------------------------------------
# LLM JSON extraction.
# ---------------------------------------------------------------------------


def _get_openai_client(api_key_env: Sequence[str], base_url: Optional[str] = None):
    """Create an OpenAI-compatible client lazily."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is required for API calls: pip install openai") from exc

    api_key = None
    for name in api_key_env:
        api_key = os.environ.get(name)
        if api_key:
            break
    if not api_key:
        names = ", ".join(api_key_env)
        raise RuntimeError(f"Missing API key. Please set one of: {names}.")
    return OpenAI(api_key=api_key, base_url=base_url)


def extract_json_object(text: str) -> Dict[str, Any]:
    """Robustly parse one JSON object from an LLM response."""
    content = (text or "").strip()
    if not content:
        raise ValueError("Empty LLM response.")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    cleaned = re.sub(r"```json\s*", "", content, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM response.")

    depth = 0
    in_string = False
    escape = False
    for pos in range(start, len(cleaned)):
        ch = cleaned[pos]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start : pos + 1])

    raise ValueError("Could not locate a complete JSON object in LLM response.")


def build_state_sequence_prompt(report_id: str, report_text: str) -> str:
    """Build the single-report state sequence extraction prompt.

    The schema mirrors the original document_learner template:
    template_description is used as the state label, and content_guideline is
    used as the state description.
    """
    return f"""
You are an expert analyst of financial research report structure. Your task is to extract the state sequence of one report so that LogicRAG can later construct a global DFA from multiple reports.

Output requirements:
- Return exactly one valid JSON object.
- Do not include explanations, comments, Markdown code fences, or any extra text.
- The JSON must be directly parseable by Python json.loads().
- Use exactly the field names defined in the schema below.

Task instructions:
1. Read the full input report and identify its hierarchical writing structure.
2. Abstract each text segment with a stable semantic function into one state.
3. A leaf state should correspond to a concrete paragraph or the smallest functional discourse segment. A non-leaf state should summarize its child states.
4. Each state must include:
   - node_id: hierarchical identifier, such as "1", "1.1", or "1.1.1".
   - node_type: one of "root", "child", or "leaf".
   - template_description: the semantic label of the state, corresponding to label(s) in the paper.
   - level: hierarchy depth, with the root node at level 0.
   - parent: parent node_id; use null for the root node.
   - children: list of child node_id values.
   - content_guideline: the semantic function, writing requirement, or state description, corresponding to desc(s) in the paper.
   - required_materials: data types or information requirements needed to generate this state. Use abstract variable names or data requirements only; do not include concrete numerical values.
   - length: approximate character length of the source text corresponding to this state; for non-leaf states, use the sum of child-state lengths.
5. The state_sequence must follow the actual order in which states appear in the report.

Output JSON schema:
{{
  "document_id": "{report_id}",
  "language": "report language",
  "template_description": "brief description of the report topic and structure",
  "structure_pattern": {{
    "reasoning_logic": "the writing logic of the report, e.g., data/facts -> analysis -> conclusion",
    "node_types": ["root", "child", "leaf"]
  }},
  "state_sequence": [
    {{
      "node_id": "1",
      "node_type": "root",
      "template_description": "state label",
      "level": 0,
      "parent": null,
      "children": ["1.1"],
      "content_guideline": "state description",
      "required_materials": [],
      "length": 1000
    }}
  ],
  "material_requirements_summary": ["deduplicated list of data requirements"],
  "usage_instruction": {{
    "step1": "determine the writing logic according to state_sequence",
    "step2": "retrieve data according to required_materials",
    "step3": "generate text state by state following the state order",
    "step4": "concatenate all state outputs into a complete report"
  }}
}}

Input report:
{report_text}
""".strip()


class ChatJsonClient:
    """OpenAI-compatible chat client that returns parsed JSON."""

    def __init__(
        self,
        model: str = DEFAULT_CHAT_MODEL,
        base_url: str = DEFAULT_CHAT_BASE_URL,
        temperature: float = 0.2,
        max_tokens: int = 8000,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = _get_openai_client(
                api_key_env=("DEEPSEEK_API_KEY", "OPENAI_API_KEY"),
                base_url=self.base_url,
            )
        return self._client

    def complete_json(self, prompt: str) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise JSON-only generator. "
                        "Return only valid JSON, with no markdown or explanation."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=False,
        )
        content = response.choices[0].message.content or ""
        return extract_json_object(content)


# ---------------------------------------------------------------------------
# State normalization and matching.
# ---------------------------------------------------------------------------


def node_sort_key(node_id: str) -> List[Any]:
    parts = str(node_id).split(".")
    key: List[Any] = []
    for part in parts:
        key.append(int(part) if part.isdigit() else part)
    return key


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [value]


def normalize_state_sequence(data: Dict[str, Any], document_id: str) -> Dict[str, Any]:
    """Normalize possible LLM outputs into a stable state_sequence object."""
    nodes = data.get("state_sequence")
    if not nodes:
        nodes = data.get("node_template", {}).get("nodes")
    if not nodes:
        nodes = data.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError(f"No valid state_sequence found for document {document_id}.")

    normalized_nodes: List[Dict[str, Any]] = []
    for i, raw in enumerate(nodes, start=1):
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("node_id") or raw.get("id") or i)
        children = [str(c) for c in as_list(raw.get("children"))]
        parent = raw.get("parent")
        parent = None if parent in ("", "null", "None") else (str(parent) if parent is not None else None)

        required_materials = [
            str(item).strip()
            for item in as_list(raw.get("required_materials") or raw.get("data") or [])
            if str(item).strip()
        ]

        try:
            length = int(float(raw.get("length", 0) or 0))
        except (TypeError, ValueError):
            length = 0

        normalized_nodes.append(
            {
                "node_id": node_id,
                "node_type": str(raw.get("node_type") or infer_node_type(parent, children)),
                "template_description": str(raw.get("template_description") or raw.get("label") or "").strip(),
                "level": int(raw.get("level", node_id.count(".")) or 0),
                "parent": parent,
                "children": children,
                "content_guideline": str(raw.get("content_guideline") or raw.get("desc") or "").strip(),
                "required_materials": required_materials,
                "length": length,
            }
        )

    normalized_nodes.sort(key=lambda n: node_sort_key(n["node_id"]))
    materials = collect_materials(normalized_nodes)

    return {
        "document_id": document_id,
        "language": data.get("language", ""),
        "template_description": data.get("template_description", ""),
        "structure_pattern": data.get(
            "structure_pattern",
            {"reasoning_logic": "", "node_types": ["root", "child", "leaf"]},
        ),
        "state_sequence": normalized_nodes,
        "material_requirements_summary": materials,
        "usage_instruction": data.get("usage_instruction", {}),
    }


def infer_node_type(parent: Optional[str], children: Sequence[str]) -> str:
    if parent is None:
        return "root"
    if children:
        return "child"
    return "leaf"


def collect_materials(nodes: Sequence[Dict[str, Any]]) -> List[str]:
    seen = set()
    materials: List[str] = []
    for node in nodes:
        for item in as_list(node.get("required_materials")):
            key = str(item).strip()
            if key and key not in seen:
                seen.add(key)
                materials.append(key)
    return materials


def state_embedding_text(state: Dict[str, Any]) -> str:
    label = str(state.get("template_description", "")).strip()
    desc = str(state.get("content_guideline", "")).strip()
    return f"{label}\n{desc}".strip()


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class EmbeddingProvider:
    """Embedding provider with API-first and local fallback behavior."""

    def __init__(
        self,
        model: str = DEFAULT_EMBEDDING_MODEL,
        base_url: Optional[str] = DEFAULT_EMBEDDING_BASE_URL,
        local_dim: int = LOCAL_EMBEDDING_DIM,
        allow_api: bool = True,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    ) -> None:
        self.model = model
        self.base_url = base_url or DEFAULT_EMBEDDING_BASE_URL
        self.local_dim = local_dim
        self.allow_api = allow_api
        self.batch_size = max(1, batch_size)
        self.backend = "local-hash"
        self._client = None

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        clean_texts = [text if text.strip() else "empty state" for text in texts]
        if self.allow_api:
            try:
                vectors = self._embed_texts_api(clean_texts)
                self.backend = "api"
                return vectors
            except Exception as exc:
                print(f"[warn] API embedding failed, falling back to local hashing: {exc}")

        self.backend = "local-hash"
        return [self._embed_text_local(text) for text in clean_texts]

    def _embed_texts_api(self, texts: Sequence[str]) -> List[List[float]]:
        if self._client is None:
            self._client = _get_openai_client(
                api_key_env=("LOGICRAG_EMBEDDING_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY"),
                base_url=self.base_url,
            )
        vectors: List[List[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            response = self._client.embeddings.create(model=self.model, input=batch)
            vectors.extend(list(item.embedding) for item in response.data)
        return vectors

    def _embed_text_local(self, text: str) -> List[float]:
        """Deterministic local char/word n-gram hashing embedding.

        This fallback is designed to keep the pipeline runnable without an
        embedding API. Later modules can reuse the same method for query
        embeddings if no API embedding service is available.
        """
        features: List[str] = []
        compact = re.sub(r"\s+", "", text.lower())
        for n in (2, 3, 4):
            if len(compact) >= n:
                features.extend(compact[i : i + n] for i in range(len(compact) - n + 1))
        features.extend(re.findall(r"[\w\u4e00-\u9fff]+", text.lower()))

        vector = [0.0] * self.local_dim
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, byteorder="big", signed=False)
            idx = value % self.local_dim
            sign = 1.0 if (value >> 8) & 1 else -1.0
            vector[idx] += sign

        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0.0:
            return vector
        return [x / norm for x in vector]


@dataclass
class StateMatch:
    a_index: int
    b_index: int
    similarity: float


def match_common_states(
    states_a: Sequence[Dict[str, Any]],
    states_b: Sequence[Dict[str, Any]],
    embeddings_a: Sequence[Sequence[float]],
    embeddings_b: Sequence[Sequence[float]],
    theta: float,
) -> List[StateMatch]:

    candidates: List[StateMatch] = []
    for i, vec_a in enumerate(embeddings_a):
        for j, vec_b in enumerate(embeddings_b):
            sim = cosine_similarity(vec_a, vec_b)
            if sim >= theta:
                candidates.append(StateMatch(i, j, sim))
    candidates.sort(key=lambda m: m.similarity, reverse=True)
    used_a = set()
    used_b = set()
    matches: List[StateMatch] = []
    for match in candidates:
        if match.a_index in used_a or match.b_index in used_b:
            continue
        used_a.add(match.a_index)
        used_b.add(match.b_index)
        matches.append(match)

    matches.sort(key=lambda m: node_sort_key(states_a[m.a_index]["node_id"]))
    return matches


def merge_text_field(left: str, right: str) -> str:
    left = (left or "").strip()
    right = (right or "").strip()
    if not left:
        return right
    if not right or left == right:
        return left
    if right in left:
        return left
    if left in right:
        return right
    return f"{left}; {right}"


def merge_materials(left: Sequence[Any], right: Sequence[Any]) -> List[str]:
    seen = set()
    merged: List[str] = []
    for value in list(left or []) + list(right or []):
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            merged.append(item)
    return merged


def average_length(left: Any, right: Any) -> int:
    nums = []
    for value in (left, right):
        try:
            nums.append(int(float(value)))
        except (TypeError, ValueError):
            pass
    if not nums:
        return 0
    return int(round(sum(nums) / len(nums)))


def build_global_template(
    report_pair_id: str,
    seq_a: Dict[str, Any],
    seq_b: Dict[str, Any],
    matches: Sequence[StateMatch],
    theta: float,
) -> Dict[str, Any]:
    states_a = seq_a["state_sequence"]
    states_b = seq_b["state_sequence"]
    a_to_global: Dict[int, str] = {}
    b_to_global: Dict[int, str] = {}
    nodes: List[Dict[str, Any]] = []

    for match in matches:
        a = states_a[match.a_index]
        b = states_b[match.b_index]
        global_id = str(a["node_id"])
        a_to_global[match.a_index] = global_id
        b_to_global[match.b_index] = global_id

        node = {
            "node_id": global_id,
            "node_type": a.get("node_type") or b.get("node_type") or "leaf",
            "template_description": merge_text_field(
                a.get("template_description", ""),
                b.get("template_description", ""),
            ),
            "level": int(a.get("level", 0) or 0),
            "parent": None,
            "children": [],
            "content_guideline": merge_text_field(
                a.get("content_guideline", ""),
                b.get("content_guideline", ""),
            ),
            "required_materials": merge_materials(
                a.get("required_materials", []),
                b.get("required_materials", []),
            ),
            "length": average_length(a.get("length"), b.get("length")),
            "support": [
                {"document_id": seq_a["document_id"], "source_node_id": a.get("node_id")},
                {"document_id": seq_b["document_id"], "source_node_id": b.get("node_id")},
            ],
            "match_similarity": round(match.similarity, 6),
        }
        nodes.append(node)

    id_to_node = {node["node_id"]: node for node in nodes}
    source_id_to_global = {states_a[m.a_index]["node_id"]: states_a[m.a_index]["node_id"] for m in matches}

    # Reconstruct hierarchy using report A as the canonical order. Only retained
    # states are allowed to be parents/children in the global state set.
    for node in nodes:
        source_node = next((s for s in states_a if s["node_id"] == node["node_id"]), None)
        source_parent = source_node.get("parent") if source_node else None
        if source_parent in source_id_to_global and source_parent in id_to_node:
            node["parent"] = source_parent
            id_to_node[source_parent]["children"].append(node["node_id"])

    for node in nodes:
        node["children"] = sorted(set(node["children"]), key=node_sort_key)
        node["node_type"] = infer_node_type(node.get("parent"), node["children"])

    nodes.sort(key=lambda n: node_sort_key(n["node_id"]))
    transitions = build_global_transitions(seq_a, seq_b, matches)
    materials = collect_materials(nodes)

    language = seq_a.get("language") or seq_b.get("language") or ""
    description = merge_text_field(seq_a.get("template_description", ""), seq_b.get("template_description", ""))
    reasoning_logic = merge_text_field(
        seq_a.get("structure_pattern", {}).get("reasoning_logic", ""),
        seq_b.get("structure_pattern", {}).get("reasoning_logic", ""),
    )

    return {
        "template_id": f"{report_pair_id}_logicrag_template",
        "language": language,
        "template_description": description,
        "structure_pattern": {
            "reasoning_logic": reasoning_logic,
            "node_types": ["root", "child", "leaf"],
            "transitions": transitions,
        },
        "node_template": {"nodes": nodes},
        "material_requirements_summary": materials,
        "usage_instruction": {
            "step1": "Use the global state set and transitions as the reusable writing logic.",
            "step2": "Match a user query to relevant states with the state embedding index.",
            "step3": "Retrieve data according to each state's required_materials.",
            "step4": "Generate text state by state along the transition order.",
        },
        "logicrag_metadata": {
            "theta": theta,
            "source_documents": [seq_a["document_id"], seq_b["document_id"]],
            "source_state_counts": {
                seq_a["document_id"]: len(seq_a["state_sequence"]),
                seq_b["document_id"]: len(seq_b["state_sequence"]),
            },
            "global_state_count": len(nodes),
            "matching_rule": "A state is retained if it is semantically matched in both input reports with cosine similarity >= theta.",
        },
    }


def build_global_transitions(
    seq_a: Dict[str, Any],
    seq_b: Dict[str, Any],
    matches: Sequence[StateMatch],
) -> List[Dict[str, Any]]:
    """Build retained adjacent transitions appearing in both state sequences."""
    states_a = seq_a["state_sequence"]
    states_b = seq_b["state_sequence"]
    a_index_to_global = {m.a_index: states_a[m.a_index]["node_id"] for m in matches}
    b_index_to_global = {m.b_index: states_a[m.a_index]["node_id"] for m in matches}

    def collect(index_to_global: Dict[int, str]) -> List[Tuple[str, str]]:
        ordered = [(idx, gid) for idx, gid in index_to_global.items()]
        ordered.sort(key=lambda item: item[0])
        return [(ordered[i][1], ordered[i + 1][1]) for i in range(len(ordered) - 1)]

    counts: Dict[Tuple[str, str], int] = {}
    for edge in collect(a_index_to_global) + collect(b_index_to_global):
        counts[edge] = counts.get(edge, 0) + 1

    transitions = []
    for (src, dst), count in sorted(counts.items(), key=lambda item: node_sort_key(item[0][0])):
        transitions.append(
            {
                "source": src,
                "target": dst,
                "frequency": count,
                "support_documents": count,
            }
        )
    return transitions


def build_embedding_index(
    template: Dict[str, Any],
    embedder: EmbeddingProvider,
) -> Dict[str, Any]:
    nodes = [
        node
        for node in template.get("node_template", {}).get("nodes", [])
        if not node.get("index_exclude", False)
    ]
    texts = [state_embedding_text(node) for node in nodes]
    vectors = embedder.embed_texts(texts)

    states = []
    for node, text, vector in zip(nodes, texts, vectors):
        states.append(
            {
                "state_id": node["node_id"],
                "node_id": node["node_id"],
                "label": node.get("template_description", ""),
                "desc": node.get("content_guideline", ""),
                "embedding_text": text,
                "embedding": [round(float(x), 8) for x in vector],
                "metadata": {
                    "node_type": node.get("node_type"),
                    "level": node.get("level"),
                    "parent": node.get("parent"),
                    "children": node.get("children", []),
                    "required_materials": node.get("required_materials", []),
                    "support": node.get("support", []),
                    "match_similarity": node.get("match_similarity"),
                },
            }
        )

    dimension = len(vectors[0]) if vectors else 0
    return {
        "index_id": f"{template.get('template_id', 'logicrag')}_state_index",
        "template_id": template.get("template_id", ""),
        "embedding_backend": embedder.backend,
        "embedding_model": embedder.model if embedder.backend == "api" else "local-char-ngram-hash",
        "embedding_dimension": dimension,
        "state_count": len(states),
        "states": states,
    }


# ---------------------------------------------------------------------------
# End-to-end document learner.
# ---------------------------------------------------------------------------


class LogicRAGDocumentLearner:
    def __init__(
        self,
        theta: float = DEFAULT_THETA,
        chat_model: str = DEFAULT_CHAT_MODEL,
        chat_base_url: str = DEFAULT_CHAT_BASE_URL,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        embedding_base_url: Optional[str] = DEFAULT_EMBEDDING_BASE_URL,
        embedding_batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
        allow_api_embedding: bool = True,
    ) -> None:
        self.theta = theta
        self.chat = ChatJsonClient(model=chat_model, base_url=chat_base_url)
        self.embedder = EmbeddingProvider(
            model=embedding_model,
            base_url=embedding_base_url,
            batch_size=embedding_batch_size,
            allow_api=allow_api_embedding,
        )

    def extract_state_sequence(self, document_id: str, text: str) -> Dict[str, Any]:
        prompt = build_state_sequence_prompt(document_id, text)
        raw = self.chat.complete_json(prompt)
        return normalize_state_sequence(raw, document_id)

    def learn_from_texts(
        self,
        report_pair_id: str,
        document_a_id: str,
        text_a: str,
        document_b_id: str,
        text_b: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        print(f"[1/4] Extracting state sequence for {document_a_id} ...")
        seq_a = self.extract_state_sequence(document_a_id, text_a)

        print(f"[2/4] Extracting state sequence for {document_b_id} ...")
        seq_b = self.extract_state_sequence(document_b_id, text_b)

        print("[3/4] Matching states and building global state set ...")
        states_a = seq_a["state_sequence"]
        states_b = seq_b["state_sequence"]
        texts_a = [state_embedding_text(state) for state in states_a]
        texts_b = [state_embedding_text(state) for state in states_b]
        embeddings = self.embedder.embed_texts(texts_a + texts_b)
        embeddings_a = embeddings[: len(texts_a)]
        embeddings_b = embeddings[len(texts_a) :]
        matches = match_common_states(states_a, states_b, embeddings_a, embeddings_b, self.theta)
        template = build_global_template(report_pair_id, seq_a, seq_b, matches, self.theta)

        print("[4/4] Building global state embedding index ...")
        index = build_embedding_index(template, self.embedder)
        return seq_a, seq_b, template, index


def save_json(data: Dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def run_from_csv(args: argparse.Namespace) -> Dict[str, str]:
    csv_path = Path(args.csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc_a_id, text_a = read_report_from_csv(csv_path, args.row_a)
    doc_b_id, text_b = read_report_from_csv(csv_path, args.row_b)
    report_pair_id = args.report_pair_id or f"row_{args.row_a}_{args.row_b}"

    learner = LogicRAGDocumentLearner(
        theta=args.theta,
        chat_model=args.chat_model,
        chat_base_url=args.chat_base_url,
        embedding_model=args.embedding_model,
        embedding_base_url=args.embedding_base_url,
        embedding_batch_size=args.embedding_batch_size,
        allow_api_embedding=not args.local_embedding_only,
    )

    seq_a, seq_b, template, index = learner.learn_from_texts(
        report_pair_id=report_pair_id,
        document_a_id=doc_a_id,
        text_a=text_a,
        document_b_id=doc_b_id,
        text_b=text_b,
    )

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
            "csv": str(csv_path),
            "row_a": args.row_a,
            "row_b": args.row_b,
            "report_pair_id": report_pair_id,
            "theta": args.theta,
            "outputs": paths,
        },
        paths["manifest"],
    )

    return paths


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LogicRAG document learner")
    parser.add_argument("--csv", default="reports.csv", help="Input CSV file, same row-based format as ReportAgent.")
    parser.add_argument("--row-a", type=int, default=0, help="First sample report row index.")
    parser.add_argument("--row-b", type=int, default=1, help="Second sample report row index.")
    parser.add_argument("--theta", type=float, default=DEFAULT_THETA, help="State matching similarity threshold.")
    parser.add_argument("--report-pair-id", default="", help="Optional output template id prefix.")
    parser.add_argument("--output-dir", default="logicrag_outputs", help="Directory for generated JSON files.")
    parser.add_argument("--chat-model", default=DEFAULT_CHAT_MODEL, help="OpenAI-compatible chat model.")
    parser.add_argument("--chat-base-url", default=DEFAULT_CHAT_BASE_URL, help="OpenAI-compatible chat base URL.")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL, help="Embedding model name.")
    parser.add_argument("--embedding-base-url", default=DEFAULT_EMBEDDING_BASE_URL, help="Optional embedding API base URL.")
    parser.add_argument("--embedding-batch-size", type=int, default=DEFAULT_EMBEDDING_BATCH_SIZE, help="Embedding API batch size.")
    parser.add_argument(
        "--local-embedding-only",
        action="store_true",
        help="Skip embedding API calls and use deterministic local hash embeddings.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    paths = run_from_csv(args)
    print("LogicRAG document learning completed.")
    for name, path in paths.items():
        print(f"- {name}: {path}")


if __name__ == "__main__":
    main()
