"""CSG pipeline demo tab — cross-era sentence generation comparison."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from app.engine.demo import DEMO_CSGS, build_csg, compare_eras_for_csg

if TYPE_CHECKING:
    from app.engine.session import RunResult


def render_csg(result: RunResult) -> None:
    csg_name = st.selectbox("CSG Preset", list(DEMO_CSGS.keys()))
    if not csg_name:
        return

    spec = DEMO_CSGS[csg_name]
    with st.expander("CSG Structure", expanded=False):
        st.json(spec)

    csg = build_csg(csg_name)

    try:
        era_results = compare_eras_for_csg(
            csg,
            result.era0_hot,
            result.final_hot,
            result.engine.registry,
            result.engine.inventory,
        )
    except Exception as exc:
        st.error(f"CSG pipeline error: {exc}")
        return

    st.subheader("Cross-Era Comparison")

    if len(era_results) >= 2:
        col_a, col_b = st.columns(2)
        r0, rN = era_results[0], era_results[-1]

        with col_a:
            st.markdown(f"### Era {r0.era}")
            st.code(f"/{r0.sentence}/", language=None)
            st.markdown("**Lexmap:**")
            for k, v in r0.lexmap_used.items():
                st.markdown(f"- `{k}` → /{v or '?'}/")
            if r0.warnings:
                for w in r0.warnings:
                    st.warning(w)

        with col_b:
            st.markdown(f"### Era {rN.era}")
            st.code(f"/{rN.sentence}/", language=None)
            st.markdown("**Lexmap:**")
            for k, v in rN.lexmap_used.items():
                st.markdown(f"- `{k}` → /{v or '?'}/")
            if rN.warnings:
                for w in rN.warnings:
                    st.warning(w)
    else:
        for r in era_results:
            st.markdown(f"**Era {r.era}:** `/{r.sentence}/`")
