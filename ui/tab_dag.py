"""DAG etymology explorer — Graphviz DOT rendering via st.graphviz_chart."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from app.engine.session import RunResult


def _entity_label(result: "RunResult", word_id: str) -> str:
    entity = result.final_hot.get(str(word_id))
    if entity:
        status = " [DEAD]" if entity.is_dead else ""
        return f"{entity.concept}\\n/{entity.ipa_current}/{status}"
    return str(word_id)


def _build_subgraph_dot(
    result: "RunResult",
    center_id: str,
    mode: str,
) -> str:
    """Build DOT string for a word's ancestry/descendancy subgraph."""
    dag = result.final_hot.dag
    node_ids: set[str] = {center_id}
    edges: list[tuple[str, str, int, str]] = []

    if mode in ("ancestors", "both"):
        ancestors = dag.ancestors(center_id)
        node_ids.update(ancestors)
        for nid in [center_id] + ancestors:
            for parent_id in dag.parents(nid):
                for edge in dag.children(parent_id):
                    if edge.to_id == nid:
                        edges.append((parent_id, nid, edge.era, edge.edge_type))

    if mode in ("descendants", "both"):
        descendants = dag.descendants(center_id)
        node_ids.update(descendants)
        for nid in [center_id] + descendants:
            for edge in dag.children(nid):
                edges.append((nid, edge.to_id, edge.era, edge.edge_type))
                node_ids.add(edge.to_id)

    lines = ['digraph G {', '  rankdir=TB;', '  node [shape=box, style=rounded, fontsize=10];']

    for nid in node_ids:
        label = _entity_label(result, nid)
        color = "red" if nid == center_id else "black"
        lines.append(f'  "{nid}" [label="{label}", color="{color}", penwidth=2];')

    edge_colors = {
        "sound_change": "steelblue",
        "borrowing": "orange",
        "fossil_prefix": "gray",
        "grammaticalization": "purple",
        "analogy": "green",
        "compound": "brown",
    }
    for from_id, to_id, era, etype in edges:
        color = edge_colors.get(etype, "black")
        lines.append(f'  "{from_id}" -> "{to_id}" [label="E{era} {etype}", color="{color}", fontsize=8];')

    lines.append("}")
    return "\n".join(lines)


def _build_full_dag_dot(result: "RunResult", max_nodes: int = 100) -> str:
    dag = result.final_hot.dag
    dag_dict = dag.to_dict()
    nodes = dag_dict.get("nodes", [])[:max_nodes]
    node_set = set(nodes)
    edges = [e for e in dag_dict.get("edges", []) if e["from_id"] in node_set and e["to_id"] in node_set]

    lines = ['digraph G {', '  rankdir=TB;', '  node [shape=box, style=rounded, fontsize=9];']

    for nid in nodes:
        label = _entity_label(result, nid)
        lines.append(f'  "{nid}" [label="{label}"];')

    for e in edges:
        lines.append(f'  "{e["from_id"]}" -> "{e["to_id"]}" [label="E{e["era"]}", fontsize=7];')

    lines.append("}")
    return "\n".join(lines)


def render_dag(result: RunResult) -> None:
    dag = result.final_hot.dag
    dag_dict = dag.to_dict()
    total_nodes = len(dag_dict.get("nodes", []))
    total_edges = len(dag_dict.get("edges", []))

    st.caption(f"DAG: {total_nodes} nodes, {total_edges} edges")

    alive = [e for e in result.final_hot.all_alive() if e.ipa_history]
    if not alive:
        st.info("No words with evolution history to display.")
        return

    col_word, col_mode = st.columns([2, 1])
    with col_word:
        word_options = {f"{e.concept} /{e.ipa_current}/": e.id for e in alive}
        selected_label = st.selectbox("Select word", list(word_options.keys()))
        selected_id = word_options[selected_label] if selected_label else None
    with col_mode:
        mode = st.radio("View mode", ["both", "ancestors", "descendants", "full_dag"], horizontal=True)

    if mode == "full_dag":
        if total_nodes > 100:
            st.warning(f"Full DAG has {total_nodes} nodes — showing first 100.")
        dot = _build_full_dag_dot(result)
    elif selected_id:
        dot = _build_subgraph_dot(result, selected_id, mode)
    else:
        st.info("Select a word to view its etymology graph.")
        return

    st.graphviz_chart(dot, use_container_width=True)
