"""Branch comparison tab — side-by-side dialectal evolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from app.engine.demo import DEMO_CSGS, build_csg, run_branch_comparison

if TYPE_CHECKING:
    from app.engine.session import RunResult


def render_branches(result: RunResult) -> None:
    col_cfg, col_csg = st.columns([1, 1])

    with col_cfg:
        st.subheader("Branch Config")
        branch_a_name = st.text_input("Branch A name", "北方方言 (SVO)")
        branch_b_name = st.text_input("Branch B name", "南方方言 (SOV)")
        branch_eras = st.slider("Branch evolution eras", 1, 10, 5)

    with col_csg:
        st.subheader("Test Sentence")
        csg_name = st.selectbox("CSG Preset", list(DEMO_CSGS.keys()), key="branch_csg")

    if not csg_name:
        return

    run_btn = st.button("Run Branch Comparison", type="primary")
    if not run_btn:
        st.info("Click 'Run Branch Comparison' to execute.")
        return

    csg = build_csg(csg_name)

    try:
        result_a, result_b = run_branch_comparison(
            result.era0_hot,
            result.engine.registry,
            result.engine.inventory,
            csg,
            branch_a_name=branch_a_name,
            branch_b_name=branch_b_name,
            branch_eras=branch_eras,
            seed=result.seed,
        )
    except Exception as exc:
        st.error(f"Branch comparison error: {exc}")
        return

    st.subheader("Results")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"### {branch_a_name}")
        st.markdown(f"**Era:** {result_a.era}")
        st.code(f"/{result_a.sentence}/", language=None)
        st.markdown("**Lexmap:**")
        for k, v in result_a.lexmap_used.items():
            st.markdown(f"- `{k}` → /{v or '?'}/")

    with col_b:
        st.markdown(f"### {branch_b_name}")
        st.markdown(f"**Era:** {result_b.era}")
        st.code(f"/{result_b.sentence}/", language=None)
        st.markdown("**Lexmap:**")
        for k, v in result_b.lexmap_used.items():
            st.markdown(f"- `{k}` → /{v or '?'}/")
