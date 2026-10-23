from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings
from app.services.report_length import report_length_config


def clean_json_text(text: str) -> str:
    text = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    return fenced.group(1).strip() if fenced else text


def parse_model_payload(content: str) -> dict[str, Any]:
    cleaned = clean_json_text(content)
    candidates = [cleaned]
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(cleaned[first_brace : last_brace + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"sections": parsed}
        except json.JSONDecodeError:
            continue

    # Some compatible endpoints return nearly-valid JSON with unescaped quotes
    # inside Chinese paragraphs. Recover fields by their stable schema markers.
    node_markers = list(re.finditer(r'["“]node_id["”]\s*:', cleaned))
    recovered: list[dict[str, str]] = []
    for index, marker in enumerate(node_markers):
        end = node_markers[index + 1].start() if index + 1 < len(node_markers) else len(cleaned)
        block = cleaned[marker.start() : end]
        node_match = re.search(r'["“]node_id["”]\s*:\s*["“]([^"”]+)', block)
        content_match = re.search(
            r'["“]content["”]\s*:\s*["“](.*?)(?=["”]\s*,\s*["“]summary["”]\s*:)',
            block,
            flags=re.DOTALL,
        )
        summary_match = re.search(
            r'["“]summary["”]\s*:\s*["“](.*?)(?=["”]\s*[,}]|\}\s*$)',
            block,
            flags=re.DOTALL,
        )
        if not node_match or not content_match:
            continue
        recovered.append(
            {
                "node_id": node_match.group(1).strip(),
                "content": content_match.group(1).replace('\\n', '\n').replace('\\"', '"').strip(),
                "summary": summary_match.group(1).replace('\\n', ' ').strip() if summary_match else "",
            }
        )

    if recovered:
        return {"sections": recovered}
    raise RuntimeError("Model response could not be parsed into report sections.")


def build_prompt(
    query: str,
    date: str,
    sections: list[dict[str, Any]],
    materials: dict[str, Any],
    language: str = "zh",
    report_length: dict[str, Any] | str | None = None,
) -> str:
    english = str(language).lower().startswith("en")
    target_language = "English" if english else "Chinese"
    length_key = report_length.get("key") if isinstance(report_length, dict) else report_length
    length_config = report_length_config(length_key, language)
    section_count = max(1, len(sections))
    per_section_min = max(1, round(int(length_config["min"]) / section_count))
    per_section_max = max(per_section_min, round(int(length_config["max"]) / section_count))
    compact_sections = []
    evidence_catalog: list[dict[str, Any]] = []
    evidence_ids: dict[str, str] = {}
    for section in sections:
        material = materials.get(section["node_id"], {})
        refs = []
        for binding in material.get("evidence_bindings", material.get("ifind_bindings", [])):
            if not isinstance(binding, dict) or binding.get("status") != "found" or binding.get("error"):
                continue
            compact_binding = {
                "provider": binding.get("provider", ""),
                "endpoint": binding.get("endpoint", ""),
                "instrument": binding.get("instrument", ""),
                "start_date": binding.get("start_date", ""),
                "end_date": binding.get("end_date", binding.get("date", date)),
                "query_date": binding.get("date", date),
                # Preserve complete weekly/monthly evidence windows while
                # keeping unusually long requests within a bounded payload.
                "records": binding.get("records", [])[-40:],
                "pre_period_context": binding.get("context_records", [])[-10:],
                "weighting": binding.get("weighting", {
                    "in_range_weight": 1.0,
                    "pre_period_role": "baseline_only",
                }),
            }
            fingerprint = json.dumps(compact_binding, ensure_ascii=False, sort_keys=True, default=str)
            evidence_id = evidence_ids.get(fingerprint)
            if not evidence_id:
                evidence_id = f"E{len(evidence_catalog) + 1}"
                evidence_ids[fingerprint] = evidence_id
                evidence_catalog.append({"evidence_id": evidence_id, **compact_binding})
            refs.append(evidence_id)
        compact_sections.append(
            {
                "node_id": section["node_id"],
                "label": section["label"],
                "order": section["order"],
                "safe_local_draft": section["content"],
                "required_materials": material.get("required_materials", []),
                "evidence_refs": refs,
            }
        )

    payload = {
        "task": f"Execute an AutoLogic condition-labeled writing DFA and generate a {target_language} financial research report state by state.",
        "query": query,
        "date": date,
        "length_control": {
            **length_config,
            "section_count": section_count,
            "average_per_section_min": per_section_min,
            "average_per_section_max": per_section_max,
        },
        "evidence_catalog": evidence_catalog,
        "sections": compact_sections,
        "output_schema": {
            "sections": [
                {
                    "node_id": "same node_id as input",
                    "label": f"concise {target_language} section heading",
                    "content": f"plain {target_language} report paragraph, no markdown title",
                    "summary": f"1 short {target_language} sentence for next-state continuity",
                }
            ]
        },
        "requirements": [
            "Return valid JSON only.",
            "Keep the same section order and node_id values.",
            "Use only state-level retrieved evidence as factual grounding.",
            "Treat in-range records as primary evidence with weight 1.0. Use pre-period context only as a lower-weight baseline for measuring change and trend; never present it as a current-period observation.",
            f"Translate structured evidence into natural {target_language} analysis; never copy JSON, field paths, endpoint names, provider names, or raw key-value syntax into the report.",
            "Treat each input section as a semantic writing state on the executed DFA path.",
            "Do not mention DFA, AutoLogic, APIs, caches, node IDs, retrieval systems, prompts, or implementation details in report content.",
            "Do not invent missing numerical values.",
            "When evidence is insufficient, state the uncertainty in professional report language instead of describing the software workflow.",
            f"Write polished professional {target_language}. Do not mix languages except for established market abbreviations and proper nouns.",
            f"Target {length_config['min']}-{length_config['max']} {length_config['unit']} across all section content, excluding headings and summaries.",
            f"With {section_count} sections, use about {per_section_min}-{per_section_max} {length_config['unit']} per section on average; allocate more space to evidence-rich or decision-critical states and less to supporting states.",
            "Meet the length target through substantive evidence interpretation, comparisons, implications, and uncertainty analysis. Never repeat points or invent facts merely to reach the target.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def publishable_content(value: Any) -> bool:
    text = str(value or "").strip()
    if len(text) < 30:
        return False
    forbidden = (
        "akshare evidence",
        "tushare evidence",
        "ifind real data",
        "接口=",
        "记录=[",
        "required materials",
        "retrieved_facts",
        "macro.growth",
        "market.price",
        "market.liquidity",
        "fundamentals.",
        "risk.signal",
        "autologic",
        "subdfa",
        "node_id",
    )
    lowered = text.lower()
    if any(marker in lowered for marker in forbidden):
        return False
    if text.count("{") + text.count("[") + text.count('"') >= 4:
        return False
    return True


def generate_sections(
    *,
    settings: Settings,
    query: str,
    date: str,
    draft_sections: list[dict[str, Any]],
    materials: dict[str, Any],
    language: str = "zh",
    report_length: dict[str, Any] | str | None = None,
) -> list[dict[str, Any]]:
    profile = settings.active_generation_profile()
    if not profile["api_key"]:
        raise RuntimeError(f"{profile['provider']} generation API Key is not configured.")

    english = str(language).lower().startswith("en")
    body = {
        "model": profile["model"],
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You write publication-ready {'English' if english else 'Chinese'} financial research reports grounded only in supplied evidence. "
                    "Never expose APIs, providers, schemas, field paths, JSON, prompts, or internal workflow. Output valid JSON only."
                ),
            },
            {"role": "user", "content": build_prompt(query, date, draft_sections, materials, language, report_length)},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    request = Request(
        f"{profile['base_url']}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {profile['api_key']}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=settings.request_timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{profile['provider']} HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach {profile['provider']} API: {exc.reason}") from exc

    data = json.loads(raw)
    content = data["choices"][0]["message"]["content"]
    parsed = parse_model_payload(content)
    sections = parsed.get("sections")
    if not isinstance(sections, list):
        raise RuntimeError(f"{profile['provider']} response does not contain a sections list.")

    by_node = {section.get("node_id"): section for section in sections}
    merged = []
    for draft in draft_sections:
        generated = by_node.get(draft["node_id"], {})
        material = materials.get(draft["node_id"], {})
        bindings = material.get("evidence_bindings", material.get("ifind_bindings", []))
        has_verified_evidence = any(
            isinstance(binding, dict)
            and not binding.get("error")
            and binding.get("status") == "found"
            and str(binding.get("raw_text", "")).strip()
            for binding in bindings
        )
        merged.append(
            {
                **draft,
                "label": str(generated.get("label") or draft.get("label", "")).strip(),
                "content": (
                    str(generated.get("content", "")).strip()
                    if has_verified_evidence and publishable_content(generated.get("content"))
                    else draft["content"]
                ),
                "summary": generated.get("summary", ""),
                "evidence_verified": has_verified_evidence,
                "generation_quality": (
                    "ai"
                    if has_verified_evidence and publishable_content(generated.get("content"))
                    else "safe_fallback"
                ),
            }
        )
    return merged


def refine_sections(
    *,
    settings: Settings,
    query: str,
    date: str,
    sections: list[dict[str, Any]],
    materials: dict[str, Any],
    instruction: str,
    language: str = "zh",
    report_length: dict[str, Any] | str | None = None,
) -> list[dict[str, Any]]:
    """Rewrites report prose while keeping the existing evidence-backed section contract."""
    profile = settings.active_generation_profile()
    if not profile["api_key"]:
        raise RuntimeError(f"{profile['provider']} generation API Key is not configured.")
    english = str(language).lower().startswith("en")
    target_language = "English" if english else "Chinese"
    length_key = report_length.get("key") if isinstance(report_length, dict) else report_length
    length_config = report_length_config(length_key, language)
    payload = {
        "task": f"Revise a {target_language} financial research report according to the user's instruction.",
        "original_request": query,
        "report_date": date,
        "revision_instruction": instruction,
        "length_control": length_config,
        "sections": [{"node_id": section.get("node_id"), "label": section.get("label"), "order": section.get("order"), "content": section.get("content", "")} for section in sections],
        "requirements": [
            "Return valid JSON only in the shape {\\\"sections\\\":[{\\\"node_id\\\":...,\\\"content\\\":...}]}",
            "Return the desired final section list in its intended order. You may omit an existing section only when the revision instruction explicitly asks to remove or merge it.",
            "Use only existing node_id values. Preserve a section's evidence boundary even when changing its heading or prose.",
            "Do not invent facts, numbers, sources, or dates beyond the original report.",
            "Do not mention prompts, APIs, DFA, tools, or the revision process.",
            f"Use polished professional {target_language}; do not mix languages except for established abbreviations and proper nouns.",
            f"Unless the revision instruction explicitly requests a shorter or longer result, keep total section content within {length_config['min']}-{length_config['max']} {length_config['unit']}.",
            "If the revision instruction explicitly changes length, follow that instruction instead of the inherited length preset.",
        ],
    }
    body = {
        "model": profile["model"],
        "messages": [
            {"role": "system", "content": f"You are a senior {target_language} financial research editor. Return valid JSON only."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0.25,
        "stream": False,
    }
    request = Request(
        f"{profile['base_url']}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {profile['api_key']}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.request_timeout_seconds) as response:
            content = json.loads(response.read().decode("utf-8"))["choices"][0]["message"]["content"]
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{profile['provider']} HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach {profile['provider']} API: {exc.reason}") from exc
    parsed = parse_model_payload(content)
    revisions = parsed.get("sections")
    if not isinstance(revisions, list):
        raise RuntimeError(f"{profile['provider']} response does not contain revised sections.")
    original_by_id = {str(section.get("node_id")): section for section in sections}
    refined = []
    for revision in revisions:
        if not isinstance(revision, dict):
            continue
        section = original_by_id.get(str(revision.get("node_id")))
        if not section:
            continue
        content = str(revision.get("content", "")).strip()
        if content and publishable_content(content):
            refined.append({
                **section,
                "label": str(revision.get("label") or section.get("label", "")).strip(),
                "order": len(refined) + 1,
                "content": content,
                "generation_quality": "ai_refined",
            })
        else:
            refined.append({**section, "order": len(refined) + 1})
    return refined or sections
