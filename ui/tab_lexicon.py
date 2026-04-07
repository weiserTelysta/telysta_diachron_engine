"""Lexicon explorer tab — searchable, filterable word table with detail expanders."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

if TYPE_CHECKING:
    from app.engine.session import RunResult


def render_lexicon(result: RunResult) -> None:
    hot = result.final_hot
    entities = list(hot.lexicon.values())

    # --- Filters ---
    col_search, col_status, col_wc = st.columns([2, 1, 1])
    with col_search:
        query = st.text_input("Search (concept or IPA)", "")
    with col_status:
        status_filter = st.selectbox("Status", ["all", "alive", "dead"])
    with col_wc:
        wc_filter = st.selectbox("Word Class", ["all", "content", "function"])

    filtered = entities
    if query:
        q = query.lower()
        filtered = [e for e in filtered if q in e.concept.lower() or q in e.ipa_current.lower()]
    if status_filter == "alive":
        filtered = [e for e in filtered if not e.is_dead]
    elif status_filter == "dead":
        filtered = [e for e in filtered if e.is_dead]
    if wc_filter != "all":
        filtered = [e for e in filtered if e.word_class == wc_filter]

    st.caption(f"{len(filtered)} / {len(entities)} words")

    # --- Table ---
    rows = []
    for e in filtered:
        rows.append({
            "concept": e.concept,
            "POS": e.pos,
            "IPA": f"/{e.ipa_current}/",
            "freq": round(e.frequency_weight, 4),
            "class": e.word_class,
            "era_born": e.era_born,
            "dead": e.is_dead,
            "gram_stage": e.grammaticalization_stage,
            "gram_func": e.grammatical_function or "—",
            "changes": len(e.ipa_history),
        })

    if not rows:
        st.warning("No words match the current filters.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "freq": st.column_config.NumberColumn(format="%.4f"),
            "dead": st.column_config.CheckboxColumn("Dead"),
        },
    )

    # --- Detail expander ---
    st.subheader("Word Detail")
    concepts = [e.concept for e in filtered]
    selected = st.selectbox("Select word", concepts, index=0) if concepts else None
    if selected:
        entity = next(e for e in filtered if e.concept == selected)
        with st.expander(f"**{entity.concept}** /{entity.ipa_current}/", expanded=True):
            if entity.ipa_history:
                chain = " → ".join(f"/{h}/" for h in entity.ipa_history) + f" → **/{entity.ipa_current}/**"
                st.markdown(f"**IPA History:** {chain}")
            else:
                st.markdown(f"**IPA:** /{entity.ipa_current}/ (unchanged)")

            detail_cols = st.columns(3)
            detail_cols[0].markdown(f"**POS:** {entity.pos}")
            detail_cols[1].markdown(f"**Frequency:** {entity.frequency_weight:.4f}")
            detail_cols[2].markdown(f"**Morpheme Type:** {entity.morpheme_type}")

            if entity.scar_log:
                st.markdown(f"**Irregular Scars:** {', '.join(entity.scar_log)}")
            if entity.semantic_primes:
                st.markdown(f"**Semantic Primes:** {', '.join(entity.semantic_primes)}")
            if entity.semantic_era_log:
                st.markdown("**Semantic Era Log:**")
                for entry in entity.semantic_era_log:
                    st.markdown(
                        f"- Era {entry.era}: {entry.proposal_type} "
                        f"`{entry.from_prime}` → `{entry.to_prime}` "
                        f"[{entry.validator_status}]"
                    )
            if entity.dag_parent_ids:
                st.markdown(f"**DAG Parents:** {', '.join(str(p) for p in entity.dag_parent_ids)}")
