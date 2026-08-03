"""
LogicRAG report generator.

Inputs:
  1. query_subtree.json produced by query_processing.py
  2. logicrag_outputs/retrieved_materials produced by ifind_data_plugin.py

Generation follows the query-specific state tree in order.  After each state is
generated, the system produces a short summary and passes only that summary to
the next state as local context, avoiding unbounded accumulation of the full
historical output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


DEFAULT_QUERY_SUBTREE = "logicrag_outputs/query_subtree.json"
DEFAULT_MATERIALS_DIR = "logicrag_outputs/retrieved_materials"
DEFAULT_OUTPUT_MD = "logicrag_outputs/generated_report.md"
DEFAULT_NODE_OUTPUTS = "logicrag_outputs/generated_node_outputs.json"
DEFAULT_TRACE = "logicrag_outputs/generation_trace.json"
DEFAULT_CHAT_MODEL = os.environ.get("LOGICRAG_CHAT_MODEL", "deepseek-chat")
DEFAULT_CHAT_BASE_URL = os.environ.get("LOGICRAG_CHAT_BASE_URL", "https://api.deepseek.com")


def load_json(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: Dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def node_sort_key(node: Dict[str, Any]) -> List[Any]:
    parts = str(node.get("node_id", "")).split(".")
    key: List[Any] = []
    for part in parts:
        key.append(int(part) if part.isdigit() else part)
    return key


def clean_markdown(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```[^\n]*\n?", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_template_nodes(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes = template.get("node_template", {}).get("nodes", [])
    if not nodes:
        nodes = template.get("nodes", [])
    if not isinstance(nodes, list):
        raise ValueError("query_subtree.json does not contain node_template.nodes.")
    return sorted(nodes, key=node_sort_key)


def is_executable_state(node: Dict[str, Any], generate_internal: bool = False) -> bool:
    if generate_internal:
        return True
    children = node.get("children") or []
    return not children


def format_materials_text(materials_payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    extraction_results = materials_payload.get("extraction_results", {})
    if not extraction_results:
        return "No retrieved material is available for this state.", extraction_results

    blocks: List[str] = []
    for material_name, result in extraction_results.items():
        if not isinstance(result, dict):
            continue
        status = result.get("status", "")
        found = result.get("found", False)
        raw_text = str(result.get("raw_text", "") or "").strip()
        query_meta = result.get("query", {})
        codes = ", ".join(query_meta.get("codes", []) or [])
        indicators = ", ".join(query_meta.get("indicators", []) or [])
        header = f"Material: {material_name}"
        meta = f"status={status or found}; codes={codes}; indicators={indicators}"
        content = raw_text if raw_text else "No data was retrieved for this material."
        blocks.append(f"{header}\n{meta}\n{content}")

    return "\n\n".join(blocks) if blocks else "No retrieved material is available for this state.", extraction_results


class ChatClient:
    def __init__(
        self,
        model: str = DEFAULT_CHAT_MODEL,
        base_url: str = DEFAULT_CHAT_BASE_URL,
        temperature: float = 0.2,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("The openai package is required: pip install openai") from exc

            api_key = (
                os.environ.get("DEEPSEEK_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
                or os.environ.get("LOGICRAG_CHAT_API_KEY")
            )
            if not api_key:
                raise RuntimeError("Missing chat API key. Set DEEPSEEK_API_KEY or OPENAI_API_KEY.")
            self._client = OpenAI(api_key=api_key, base_url=self.base_url)
        return self._client

    def complete(self, system: str, user: str, max_tokens: int = 1200) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        return response.choices[0].message.content or ""


@dataclass
class GeneratedState:
    node_id: str
    label: str
    content: str
    summary: str
    materials_file: str


class LogicRAGReportGenerator:
    def __init__(
        self,
        query_subtree_path: str | Path,
        materials_dir: str | Path,
        chat_client: Optional[ChatClient] = None,
        dry_run: bool = False,
        generate_internal: bool = False,
    ) -> None:
        self.query_subtree_path = Path(query_subtree_path)
        self.materials_dir = Path(materials_dir)
        self.chat_client = chat_client or ChatClient()
        self.dry_run = dry_run
        self.generate_internal = generate_internal

        self.template: Dict[str, Any] = {}
        self.nodes: List[Dict[str, Any]] = []
        self.materials_index: Dict[str, Any] = {}
        self.node_outputs: Dict[str, GeneratedState] = {}
        self.prev_summary = ""

    def load_data(self) -> None:
        self.template = load_json(self.query_subtree_path)
        self.nodes = get_template_nodes(self.template)

        index_path = self.materials_dir / "materials_index.json"
        self.materials_index = load_json(index_path) if index_path.exists() else {"node_files": {}}

        self.language = self.template.get("language", "Chinese")
        self.template_description = self.template.get("template_description", "")
        self.reasoning_logic = self.template.get("structure_pattern", {}).get("reasoning_logic", "")
        self.query = self.template.get("query_processing_metadata", {}).get("query", "")

    def _materials_path_for_node(self, node_id: str) -> Path:
        node_files = self.materials_index.get("node_files", {})
        indexed = node_files.get(node_id)
        if indexed:
            return Path(indexed)
        return self.materials_dir / f"materials_{node_id.replace('.', '_')}.json"

    def _load_node_materials(self, node_id: str) -> Tuple[str, Dict[str, Any], str]:
        path = self._materials_path_for_node(node_id)
        if not path.exists():
            return "No retrieved material file is available for this state.", {}, str(path)
        payload = load_json(path)
        materials_text, extraction_results = format_materials_text(payload)
        return materials_text, extraction_results, str(path)

    def _build_state_prompt(
        self,
        node: Dict[str, Any],
        materials_text: str,
        prev_summary: str,
    ) -> str:
        required_materials = node.get("required_materials") or []
        required_block = "\n".join(f"- {item}" for item in required_materials) or "- No explicit required_materials."

        return f"""
You are a professional financial research report writer. Generate the text segment for the current LogicRAG state.

Global information:
- User query: {self.query}
- Report topic: {self.template_description}
- Language: {self.language}
- Reasoning logic: {self.reasoning_logic}

Current state:
- node_id: {node.get('node_id', '')}
- label: {node.get('template_description', '')}
- description: {node.get('content_guideline', '')}
- target length: {node.get('length', '')}
- required_materials:
{required_block}

Local context from the immediately previous state:
{prev_summary or "None."}

Use the previous-state summary only to maintain local coherence and smooth transitions.
Do not restate, summarize, or copy the previous state's content in the current output.

Retrieved data bound to the current state:
{materials_text}

Writing requirements:
1. Use only the retrieved data and the local context above.
2. Accurately include all relevant numerical values from the retrieved data.
3. Do not invent missing data. If key data is missing, state the absence briefly and conservatively.
4. Focus only on the current state; do not generate content for other states.
5. Output plain report text only. Do not output node_id, titles, bullet lists, Markdown, or explanations.
6. Do not repeat content that has already appeared in the previous state.
""".strip()

    def _generate_state_content(self, node: Dict[str, Any], materials_text: str) -> str:
        if self.dry_run:
            label = node.get("template_description", "")
            return f"[DRY RUN] Generated segment for {label}. Materials used: {materials_text[:300]}"

        system = (
            "You write concise, factual financial research report paragraphs. "
            "Return only plain text, with no Markdown and no metadata."
        )
        prompt = self._build_state_prompt(node, materials_text, self.prev_summary)
        content = self.chat_client.complete(system=system, user=prompt, max_tokens=1400)
        return clean_markdown(content) or "No content generated."

    def _generate_summary(self, content: str) -> str:
        if self.dry_run:
            return clean_markdown(content[:220])

        system = "You summarize report paragraphs for local continuity. Return only a brief plain-text summary."
        prompt = f"""
Summarize the following generated state text in 1-3 short sentences.
The summary will be used only as local context for the next state.
Do not add new facts.

Generated state text:
{content}
""".strip()
        summary = self.chat_client.complete(system=system, user=prompt, max_tokens=300)
        return clean_markdown(summary)

    def generate(self) -> List[GeneratedState]:
        if not self.template:
            self.load_data()

        generated: List[GeneratedState] = []
        for node in self.nodes:
            if not is_executable_state(node, self.generate_internal):
                continue

            node_id = str(node.get("node_id", ""))
            label = str(node.get("template_description", ""))
            materials_text, _materials, materials_file = self._load_node_materials(node_id)
            content = self._generate_state_content(node, materials_text)
            summary = self._generate_summary(content)
            self.prev_summary = summary

            state = GeneratedState(
                node_id=node_id,
                label=label,
                content=content,
                summary=summary,
                materials_file=materials_file,
            )
            self.node_outputs[node_id] = state
            generated.append(state)
            print(f"Generated state {node_id}: {label}")

        return generated

    def assemble_report(self) -> str:
        parts: List[str] = []
        for node in self.nodes:
            node_id = str(node.get("node_id", ""))
            state = self.node_outputs.get(node_id)
            if not state:
                continue
            parts.append(state.content)
        return "\n\n".join(parts).strip()

    def save_outputs(
        self,
        output_md: str | Path = DEFAULT_OUTPUT_MD,
        node_outputs_path: str | Path = DEFAULT_NODE_OUTPUTS,
        trace_path: str | Path = DEFAULT_TRACE,
    ) -> Dict[str, str]:
        report_text = self.assemble_report()
        output_md = Path(output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(report_text, encoding="utf-8")

        node_payload = {
            node_id: {
                "node_id": state.node_id,
                "label": state.label,
                "content": state.content,
                "summary_for_next_state": state.summary,
                "materials_file": state.materials_file,
            }
            for node_id, state in self.node_outputs.items()
        }
        save_json(node_payload, node_outputs_path)

        save_json(
            {
                "query_subtree": str(self.query_subtree_path),
                "materials_dir": str(self.materials_dir),
                "query": self.query,
                "generated_state_count": len(self.node_outputs),
                "state_order": list(self.node_outputs.keys()),
                "output_md": str(output_md),
                "node_outputs": str(node_outputs_path),
            },
            trace_path,
        )

        return {
            "report": str(output_md),
            "node_outputs": str(node_outputs_path),
            "trace": str(trace_path),
        }


def quick_generate(
    query_subtree: str = DEFAULT_QUERY_SUBTREE,
    materials_dir: str = DEFAULT_MATERIALS_DIR,
    output_md: str = DEFAULT_OUTPUT_MD,
    output_json: str = DEFAULT_NODE_OUTPUTS,
    trace_json: str = DEFAULT_TRACE,
    dry_run: bool = False,
) -> str:
    generator = LogicRAGReportGenerator(
        query_subtree_path=query_subtree,
        materials_dir=materials_dir,
        dry_run=dry_run,
    )
    generator.load_data()
    generator.generate()
    generator.save_outputs(output_md, output_json, trace_json)
    return generator.assemble_report()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LogicRAG report generator")
    parser.add_argument("--query-subtree", default=DEFAULT_QUERY_SUBTREE, help="query_subtree.json path.")
    parser.add_argument("--materials-dir", default=DEFAULT_MATERIALS_DIR, help="Directory from ifind_data_plugin.py.")
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD, help="Generated report Markdown/text path.")
    parser.add_argument("--output-json", default=DEFAULT_NODE_OUTPUTS, help="Generated node outputs JSON path.")
    parser.add_argument("--trace-json", default=DEFAULT_TRACE, help="Generation trace JSON path.")
    parser.add_argument("--chat-model", default=DEFAULT_CHAT_MODEL, help="OpenAI-compatible chat model.")
    parser.add_argument("--chat-base-url", default=DEFAULT_CHAT_BASE_URL, help="OpenAI-compatible chat base URL.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Generation temperature.")
    parser.add_argument("--dry-run", action="store_true", help="Do not call LLM; generate placeholder text.")
    parser.add_argument(
        "--generate-internal",
        action="store_true",
        help="Generate text for internal tree nodes as well as leaf/material states.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    chat_client = ChatClient(
        model=args.chat_model,
        base_url=args.chat_base_url,
        temperature=args.temperature,
    )
    generator = LogicRAGReportGenerator(
        query_subtree_path=args.query_subtree,
        materials_dir=args.materials_dir,
        chat_client=chat_client,
        dry_run=args.dry_run,
        generate_internal=args.generate_internal,
    )
    generator.load_data()
    generator.generate()
    outputs = generator.save_outputs(args.output_md, args.output_json, args.trace_json)

    print("LogicRAG report generation completed.")
    print(f"- generated states: {len(generator.node_outputs)}")
    print(f"- report: {outputs['report']}")
    print(f"- node outputs: {outputs['node_outputs']}")
    print(f"- trace: {outputs['trace']}")
    if args.dry_run:
        print("- dry_run: LLM API was not called")


if __name__ == "__main__":
    main()
