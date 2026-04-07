"""Dashboard tab — overview metrics and evolution charts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

if TYPE_CHECKING:
    from app.engine.session import RunResult


def render_dashboard(result: RunResult) -> None:
    hot = result.final_hot

    alive = [e for e in hot.lexicon.values() if not e.is_dead]
    dead = [e for e in hot.lexicon.values() if e.is_dead]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Words", len(hot.lexicon))
    c2.metric("Alive", len(alive))
    c3.metric("Dead", len(dead))
    c4.metric("Morph Type", result.final_typology.morph_type)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Word Order", result.final_typology.word_order)
    c6.metric("Case System", result.final_typology.case_system)
    c7.metric("Tense System", result.final_typology.tense_system)
    c8.metric("Seed", result.seed)

    if not result.era_log:
        return

    st.subheader("Evolution Over Time")

    df = pd.DataFrame(result.era_log)

    col_left, col_right = st.columns(2)

    with col_left:
        st.caption("Sound Changes per Era")
        st.bar_chart(df.set_index("era")["changed_count"])

    with col_right:
        st.caption("Alive / Dead Words")
        chart_df = df.set_index("era")[["alive_count", "dead_count"]]
        st.area_chart(chart_df)

    st.subheader("Morpheme Table (Final)")
    mt = result.final_typology.morpheme_table
    if mt:
        mt_df = pd.DataFrame(
            [{"Function": k, "IPA Affix": f"/{v}/"} for k, v in sorted(mt.items())]
        )
        st.dataframe(mt_df, use_container_width=True, hide_index=True)
    else:
        st.info("No morphemes generated (isolating type).")
