"""
LogicRAG query processing.

Given a user query q, this module embeds the query in the same vector space as
the state index produced by document_learner.py, selects states satisfying
sim(I(q), e(s_j)) > tau, and extracts a complete subtree from the global
template JSON so that all matched states are covered.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from document_learner import (
    DEFAULT_EMBEDDING_BASE_URL,
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingProvider,
    collect_materials,
    cosine_similarity,
    infer_node_type,
    node_sort_key,
    save_json,
)


DEFAULT_TAU = 0.5


def load_json(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def get_template_nodes(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes = template.get("node_template", {}).get("nodes", [])
    if not nodes:
        nodes = template.get("nodes", [])
    if not isinstance(nodes, list):
        raise ValueError("Template JSON does not contain node_template.nodes.")
    return nodes


def get_index_states(index: Dict[str, Any]) -> List[Dict[str, Any]]:
    states = index.get("states", [])
    if not isinstance(states, list):
        raise ValueError("State index JSON does not contain a valid states list.")
    return states


def make_query_embedder(index: Dict[str, Any], args: argparse.Namespace) -> EmbeddingProvider:
    backend = index.get("embedding_backend", "")
    dimension = int(index.get("embedding_dimension") or 0)

    if backend == "local-hash" or args.local_embedding_only:
        return EmbeddingProvider(
            model=args.embedding_model,
            base_url=args.embedding_base_url,
            local_dim=dimension or 384,
            allow_api=False,
            batch_size=args.embedding_batch_size,
        )

    return EmbeddingProvider(
        model=args.embedding_model,
        base_url=args.embedding_base_url,
        allow_api=True,
        batch_size=args.embedding_batch_size,
    )


def embed_query(query: str, index: Dict[str, Any], args: argparse.Namespace) -> List[float]:
    embedder = make_query_embedder(index, args)
    vector = embedder.embed_texts([query])[0]
    expected_dim = int(index.get("embedding_dimension") or 0)
    if expected_dim and len(vector) != expected_dim:
        raise ValueError(
            f"Query embedding dimension {len(vector)} does not match state index dimension {expected_dim}."
        )
    return vector


def rank_states_by_similarity(
    query_vector: Sequence[float],
    index: Dict[str, Any],
) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for state in get_index_states(index):
        state_vector = state.get("embedding", [])
        sim = cosine_similarity(query_vector, state_vector)
        ranked.append(
            {
                "state_id": state.get("state_id") or state.get("node_id"),
                "node_id": state.get("node_id") or state.get("state_id"),
                "label": state.get("label", ""),
                "desc": state.get("desc", ""),
                "similarity": sim,
            }
        )
    ranked.sort(key=lambda item: item["similarity"], reverse=True)
    return ranked


def apply_query_label_boost(query: str, ranked_states: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Preserve explicit section requests even when a fallback embedding is weak."""
    compact_query = "".join(str(query or "").lower().split())
    boosted: List[Dict[str, Any]] = []
    for item in ranked_states:
        copied = dict(item)
        compact_label = "".join(str(item.get("label", "")).lower().split())
        label_variants = {compact_label}
        if compact_label.startswith("etf") and len(compact_label) > 5:
            label_variants.add(compact_label[3:])
        if any(len(variant) >= 2 and variant in compact_query for variant in label_variants):
            copied["similarity"] = max(float(copied.get("similarity", 0.0)), 0.92)
            copied["match_reason"] = "explicit-label"
        boosted.append(copied)
    boosted.sort(key=lambda item: item["similarity"], reverse=True)
    return boosted


def select_matched_states(
    ranked_states: Sequence[Dict[str, Any]],
    tau: float,
    fallback_top_k: int = 0,
) -> List[Dict[str, Any]]:
    matched = [state for state in ranked_states if state["similarity"] > tau]
    if matched or fallback_top_k <= 0:
        return matched
    return list(ranked_states[:fallback_top_k])


def build_node_maps(nodes: Sequence[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    node_by_id = {str(node["node_id"]): node for node in nodes}
    children_by_id: Dict[str, List[str]] = {node_id: [] for node_id in node_by_id}

    for node in nodes:
        node_id = str(node["node_id"])
        children = [str(child) for child in node.get("children", []) if str(child) in node_by_id]
        children_by_id[node_id].extend(children)

    for node in nodes:
        node_id = str(node["node_id"])
        parent = node.get("parent")
        if parent is not None and str(parent) in node_by_id:
            parent_id = str(parent)
            if node_id not in children_by_id[parent_id]:
                children_by_id[parent_id].append(node_id)

    for node_id in children_by_id:
        children_by_id[node_id] = sorted(set(children_by_id[node_id]), key=node_sort_key)
    return node_by_id, children_by_id


def ancestor_chain(node_id: str, node_by_id: Dict[str, Dict[str, Any]]) -> List[str]:
    chain: List[str] = []
    current: Optional[str] = node_id
    visited = set()
    while current and current in node_by_id and current not in visited:
        visited.add(current)
        chain.append(current)
        parent = node_by_id[current].get("parent")
        current = str(parent) if parent is not None else None
    return chain


def lowest_common_ancestor(node_ids: Sequence[str], node_by_id: Dict[str, Dict[str, Any]]) -> str:
    valid_node_ids = [node_id for node_id in node_ids if node_id in node_by_id]
    if not valid_node_ids:
        raise ValueError("None of the matched states exist in the global template tree.")

    chains = [ancestor_chain(node_id, node_by_id) for node_id in valid_node_ids]
    common = set(chains[0])
    for chain in chains[1:]:
        common &= set(chain)

    if not common:
        raise ValueError("Matched states do not share a common ancestor in the template tree.")

    def depth(node_id: str) -> int:
        return len(ancestor_chain(node_id, node_by_id))

    return max(common, key=depth)


def collect_subtree_ids(root_id: str, children_by_id: Dict[str, List[str]]) -> List[str]:
    ordered: List[str] = []

    def visit(node_id: str) -> None:
        ordered.append(node_id)
        for child_id in children_by_id.get(node_id, []):
            visit(child_id)

    visit(root_id)
    return ordered


def subset_transitions(template: Dict[str, Any], subtree_ids: Sequence[str]) -> List[Dict[str, Any]]:
    subtree_set = set(subtree_ids)
    transitions = template.get("structure_pattern", {}).get("transitions", [])
    if not isinstance(transitions, list):
        return []

    kept = []
    for edge in transitions:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in subtree_set and target in subtree_set:
            kept.append(deepcopy(edge))
    return kept


def is_condition_labeled_dfa(template: Dict[str, Any]) -> bool:
    dfa = template.get("dfa", {})
    return isinstance(dfa, dict) and dfa.get("kind") == "condition-labeled-semantic-dfa"


def transition_id(edge: Dict[str, Any], index: int) -> str:
    return str(edge.get("id") or f"T{index + 1:03d}")


def most_supported_path(
    start_id: str,
    target_id: str,
    adjacency: Dict[str, List[Tuple[Dict[str, Any], str]]],
) -> Tuple[List[str], List[str]]:
    """Find a historically supported path using -log(frequency) as cost."""
    queue: List[Tuple[float, str, List[str], List[str]]] = [(0.0, start_id, [start_id], [])]
    best_cost: Dict[str, float] = {}
    while queue:
        cost, node_id, path_nodes, path_edges = heapq.heappop(queue)
        if node_id == target_id:
            return path_nodes, path_edges
        if cost >= best_cost.get(node_id, float("inf")):
            continue
        best_cost[node_id] = cost
        for edge, edge_id in adjacency.get(node_id, []):
            next_id = str(edge.get("target", ""))
            if not next_id or next_id in path_nodes:
                continue
            frequency = max(1e-6, min(1.0, float(edge.get("frequency") or 0.0)))
            edge_cost = -math.log(frequency) + 0.01
            heapq.heappush(queue, (cost + edge_cost, next_id, path_nodes + [next_id], path_edges + [edge_id]))
    return [], []


def select_execution_path(
    start_id: str,
    candidate_node_ids: Sequence[str],
    candidate_edge_ids: Sequence[str],
    transitions: Sequence[Dict[str, Any]],
    matched_states: Sequence[Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """Select one deterministic path maximizing covered query-matched states."""
    candidate_nodes = set(candidate_node_ids)
    candidate_edges = set(candidate_edge_ids)
    matched_scores = {str(item["node_id"]): float(item.get("similarity", 0.0)) for item in matched_states}
    adjacency: Dict[str, List[Tuple[Dict[str, Any], str]]] = {}
    for index, edge in enumerate(transitions):
        edge_id = transition_id(edge, index)
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if edge_id in candidate_edges and source in candidate_nodes and target in candidate_nodes:
            adjacency.setdefault(source, []).append((edge, edge_id))

    memo: Dict[str, Tuple[float, List[str], List[str]]] = {}

    def solve(node_id: str, visiting: set[str]) -> Tuple[float, List[str], List[str]]:
        if node_id in memo:
            return memo[node_id]
        if node_id in visiting:
            return float("-inf"), [node_id], []
        reward = (10.0 + max(-1.0, matched_scores[node_id])) if node_id in matched_scores else 0.0
        best: Tuple[float, List[str], List[str]] = (reward, [node_id], [])
        next_visiting = set(visiting)
        next_visiting.add(node_id)
        for edge, edge_id in adjacency.get(node_id, []):
            target = str(edge.get("target", ""))
            child_score, child_nodes, child_edges = solve(target, next_visiting)
            frequency = max(1e-6, min(1.0, float(edge.get("frequency") or 0.0)))
            score = reward + child_score + 0.04 * math.log(frequency)
            if score > best[0]:
                best = (score, [node_id, *child_nodes], [edge_id, *child_edges])
        memo[node_id] = best
        return best

    _, path_nodes, path_edges = solve(start_id, set())
    return path_nodes, path_edges


def extract_query_subdfa(
    template: Dict[str, Any],
    matched_states: Sequence[Dict[str, Any]],
    query: str,
    tau: float,
    ranked_preview: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    nodes = get_template_nodes(template)
    node_by_id = {str(node["node_id"]): node for node in nodes}
    transitions = template.get("structure_pattern", {}).get("transitions", [])
    transitions = transitions if isinstance(transitions, list) else []
    dfa = template.get("dfa", {})
    start_id = str(dfa.get("initial_state") or "")
    if start_id not in node_by_id:
        raise ValueError("The condition-labeled DFA has no valid initial state.")

    edge_by_id: Dict[str, Dict[str, Any]] = {}
    adjacency: Dict[str, List[Tuple[Dict[str, Any], str]]] = {}
    for index, edge in enumerate(transitions):
        edge_id = transition_id(edge, index)
        edge_by_id[edge_id] = edge
        adjacency.setdefault(str(edge.get("source", "")), []).append((edge, edge_id))

    matched_node_ids = [str(item["node_id"]) for item in matched_states if str(item["node_id"]) in node_by_id]
    candidate_nodes = {start_id}
    candidate_edges: set[str] = set()
    unreachable: List[str] = []
    for target_id in matched_node_ids:
        path_nodes, path_edges = most_supported_path(start_id, target_id, adjacency)
        if not path_nodes:
            unreachable.append(target_id)
            continue
        candidate_nodes.update(path_nodes)
        candidate_edges.update(path_edges)

    if len(candidate_nodes) == 1 and matched_node_ids:
        candidate_nodes.update(matched_node_ids)

    # Once supported connector nodes are known, retain every stable transition
    # among them. This lets the final path cover several matched states instead
    # of forcing each match to keep only its individually shortest path.
    for index, edge in enumerate(transitions):
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in candidate_nodes and target in candidate_nodes:
            candidate_edges.add(transition_id(edge, index))

    state_order = {
        str(node["node_id"]): int(node.get("state_order") or node.get("level") or 0)
        for node in nodes
    }
    ordered_candidate_nodes = sorted(candidate_nodes, key=lambda item: (state_order.get(item, 0), item))
    ordered_candidate_edges = [
        transition_id(edge, index)
        for index, edge in enumerate(transitions)
        if transition_id(edge, index) in candidate_edges
    ]
    selected_nodes, selected_edges = select_execution_path(
        start_id,
        ordered_candidate_nodes,
        ordered_candidate_edges,
        transitions,
        matched_states,
    )
    if not selected_nodes:
        selected_nodes = ordered_candidate_nodes

    selected_node_set = set(selected_nodes)
    selected_edge_set = set(selected_edges)
    subtree_nodes: List[Dict[str, Any]] = []
    for node_id in selected_nodes:
        node = deepcopy(node_by_id[node_id])
        node["children"] = [child for child in node.get("children", []) if str(child) in selected_node_set]
        subtree_nodes.append(node)

    subtree_transitions: List[Dict[str, Any]] = []
    for index, edge in enumerate(transitions):
        edge_id = transition_id(edge, index)
        if edge_id not in selected_edge_set:
            continue
        copied = deepcopy(edge)
        copied["id"] = edge_id
        target_score = next(
            (float(item.get("similarity", 0.0)) for item in matched_states if str(item["node_id"]) == str(edge.get("target"))),
            0.0,
        )
        copied["runtime_condition_score"] = round(max(0.0, min(1.0, (target_score + 1.0) / 2.0)), 6)
        copied["runtime_selected"] = True
        subtree_transitions.append(copied)

    execution_order = [
        node_id
        for node_id in selected_nodes
        if not node_by_id[node_id].get("index_exclude", False)
    ]
    selected_symbols = {edge.get("condition_symbol") for edge in subtree_transitions}
    result = deepcopy(template)
    result["template_id"] = f"{template.get('template_id', 'autologic')}_query_subdfa"
    result["node_template"] = {"nodes": subtree_nodes}
    result["material_requirements_summary"] = collect_materials(subtree_nodes)
    result.setdefault("structure_pattern", {})
    result["structure_pattern"]["transitions"] = subtree_transitions
    result["dfa"] = {
        **deepcopy(dfa),
        "states": selected_nodes,
        "alphabet": [item for item in dfa.get("alphabet", []) if item.get("symbol") in selected_symbols],
        "transition_function": [
            item for item in dfa.get("transition_function", []) if item.get("condition") in selected_symbols
        ],
        "final_states": [selected_nodes[-1]] if selected_nodes else [],
    }
    result["query_processing_metadata"] = {
        "method": "condition-constrained-path-subdfa",
        "query": query,
        "tau": tau,
        "matched_state_count": len(matched_states),
        "matched_states": [
            {
                "node_id": state["node_id"],
                "label": state.get("label", ""),
                "similarity": round(float(state["similarity"]), 6),
            }
            for state in matched_states
        ],
        "subtree_root": start_id,
        "candidate_node_ids": ordered_candidate_nodes,
        "candidate_edge_ids": ordered_candidate_edges,
        "selected_node_ids": selected_nodes,
        "selected_edge_ids": selected_edges,
        "execution_order": execution_order,
        "unreachable_matched_states": unreachable,
        "subtree_state_count": len(subtree_nodes),
        "top_ranked_preview": [
            {
                "node_id": state["node_id"],
                "label": state.get("label", ""),
                "similarity": round(float(state["similarity"]), 6),
            }
            for state in ranked_preview
        ],
    }
    return result


def extract_query_subtree(
    template: Dict[str, Any],
    matched_states: Sequence[Dict[str, Any]],
    query: str,
    tau: float,
    ranked_preview: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if is_condition_labeled_dfa(template):
        return extract_query_subdfa(template, matched_states, query, tau, ranked_preview)

    nodes = get_template_nodes(template)
    node_by_id, children_by_id = build_node_maps(nodes)
    matched_node_ids = [str(state["node_id"]) for state in matched_states]
    root_id = lowest_common_ancestor(matched_node_ids, node_by_id)
    subtree_ids = collect_subtree_ids(root_id, children_by_id)
    subtree_set = set(subtree_ids)

    subtree_nodes: List[Dict[str, Any]] = []
    for node_id in subtree_ids:
        node = deepcopy(node_by_id[node_id])
        node["children"] = [child for child in children_by_id.get(node_id, []) if child in subtree_set]
        if node_id == root_id:
            node["parent"] = None
        elif node.get("parent") is not None:
            node["parent"] = str(node["parent"])
        node["node_type"] = infer_node_type(node.get("parent"), node["children"])
        subtree_nodes.append(node)

    subtree_nodes.sort(key=lambda node: node_sort_key(str(node["node_id"])))
    transitions = subset_transitions(template, subtree_ids)

    result = deepcopy(template)
    result["template_id"] = f"{template.get('template_id', 'logicrag')}_query_subtree"
    result["node_template"] = {"nodes": subtree_nodes}
    result["material_requirements_summary"] = collect_materials(subtree_nodes)
    result.setdefault("structure_pattern", {})
    result["structure_pattern"]["transitions"] = transitions
    result["query_processing_metadata"] = {
        "query": query,
        "tau": tau,
        "matched_state_count": len(matched_states),
        "matched_states": [
            {
                "node_id": state["node_id"],
                "label": state.get("label", ""),
                "similarity": round(float(state["similarity"]), 6),
            }
            for state in matched_states
        ],
        "subtree_root": root_id,
        "subtree_state_count": len(subtree_nodes),
        "top_ranked_preview": [
            {
                "node_id": state["node_id"],
                "label": state.get("label", ""),
                "similarity": round(float(state["similarity"]), 6),
            }
            for state in ranked_preview
        ],
    }
    return result


def run_query_processing(args: argparse.Namespace) -> Dict[str, Any]:
    template = load_json(args.template)
    index = load_json(args.index)

    query_vector = embed_query(args.query, index, args)
    ranked = apply_query_label_boost(args.query, rank_states_by_similarity(query_vector, index))
    explicit_matches = [state for state in ranked if state.get("match_reason") == "explicit-label"]
    matched = explicit_matches or select_matched_states(ranked, args.tau, args.fallback_top_k)

    if not matched:
        preview = "\n".join(
            f"- {item['node_id']} sim={item['similarity']:.4f} label={item.get('label', '')}"
            for item in ranked[:5]
        )
        raise ValueError(
            f"No state satisfies sim(I(q), e(s_j)) > {args.tau}. "
            f"Top candidates are:\n{preview}"
        )

    subtree = extract_query_subtree(
        template=template,
        matched_states=matched,
        query=args.query,
        tau=args.tau,
        ranked_preview=ranked[: args.preview_top_k],
    )
    save_json(subtree, args.output)
    return subtree


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LogicRAG query processing")
    parser.add_argument("--query", required=True, help="User query q.")
    parser.add_argument("--tau", type=float, default=DEFAULT_TAU, help="Similarity threshold.")
    parser.add_argument("--template", default="logicrag_outputs/global_template.json", help="Global template JSON.")
    parser.add_argument("--index", default="logicrag_outputs/state_index.json", help="State embedding index JSON.")
    parser.add_argument("--output", default="logicrag_outputs/query_subtree.json", help="Output query-specific subtree JSON.")
    parser.add_argument("--preview-top-k", type=int, default=5, help="Number of ranked states saved in metadata.")
    parser.add_argument(
        "--fallback-top-k",
        type=int,
        default=0,
        help="Optional fallback when no state exceeds tau. Keep 0 for strict threshold behavior.",
    )
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL, help="Embedding model name.")
    parser.add_argument("--embedding-base-url", default=DEFAULT_EMBEDDING_BASE_URL, help="Embedding API base URL.")
    parser.add_argument("--embedding-batch-size", type=int, default=DEFAULT_EMBEDDING_BATCH_SIZE, help="Embedding API batch size.")
    parser.add_argument(
        "--local-embedding-only",
        action="store_true",
        help="Use local hash embeddings instead of the embedding API.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    subtree = run_query_processing(args)
    meta = subtree["query_processing_metadata"]
    print("LogicRAG query processing completed.")
    print(f"- query: {meta['query']}")
    print(f"- matched states: {meta['matched_state_count']}")
    print(f"- subtree root: {meta['subtree_root']}")
    print(f"- subtree states: {meta['subtree_state_count']}")
    print(f"- output: {args.output}")


if __name__ == "__main__":
    main()
