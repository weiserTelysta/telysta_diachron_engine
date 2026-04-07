"""Epoch overview tab — vocabulary growth, typology timeline, injections."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from app.engine.session import RunResult


def render_epochs(result: "RunResult") -> None:
    if not result.epoch_results:
        st.info("No epoch data available. Run with Epoch Mode enabled.")
        return

    epochs = result.epoch_results

    # ------------------------------------------------------------------
    # Summary cards
    # ------------------------------------------------------------------
    total_injected = sum(len(ep.injected_words) for ep in epochs)
    total_compounds = sum(len(ep.compound_words) for ep in epochs)
    total_renewed = sum(len(ep.replaced_concepts) for ep in epochs)
    final_alive = result.final_hot.all_alive()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Lexicon", len(final_alive))
    c2.metric("Domain Injections", total_injected)
    c3.metric("Compounds Generated", total_compounds)
    c4.metric("Concept Renewals", total_renewed)

    st.markdown("---")

    # ------------------------------------------------------------------
    # Vocabulary growth per epoch
    # ------------------------------------------------------------------
    st.subheader("Vocabulary Growth by Epoch")

    import pandas as pd

    rows = []
    for ep in epochs:
        rows.append({
            "Epoch": ep.epoch_name.capitalize(),
            "Era End": ep.era_end,
            "Alive Words": ep.lexicon_size_at_end,
            "Injected": len(ep.injected_words),
            "Compounds": len(ep.compound_words),
            "Morph Type": ep.typology_at_end_morph,
            "Word Order": ep.typology_at_end_order,
        })
    df = pd.DataFrame(rows)

    st.bar_chart(df.set_index("Epoch")["Alive Words"])

    # ------------------------------------------------------------------
    # Epoch detail table
    # ------------------------------------------------------------------
    st.subheader("Epoch Summary Table")
    st.dataframe(df, use_container_width=True)

    # ------------------------------------------------------------------
    # Typology timeline
    # ------------------------------------------------------------------
    st.subheader("Typology Timeline")
    typology_rows = []
    for ep in epochs:
        typology_rows.append({
            "Epoch": ep.epoch_name.capitalize(),
            "Era End": ep.era_end,
            "Morph Type": ep.typology_at_end_morph,
            "Word Order": ep.typology_at_end_order,
        })
    st.dataframe(pd.DataFrame(typology_rows), use_container_width=True)

    # ------------------------------------------------------------------
    # Per-epoch detail expanders
    # ------------------------------------------------------------------
    st.subheader("Per-Epoch Detail")
    for ep in epochs:
        with st.expander(
            f"[{ep.epoch_name.upper()}] Era {ep.era_start}–{ep.era_end} "
            f"| {ep.typology_at_end_morph} | {ep.lexicon_size_at_end} words"
        ):
            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("**Injected Words**")
                if ep.injected_words:
                    inj_data = [
                        {"Concept": w.concept, "IPA": f"/{w.ipa_current}/", "POS": w.pos}
                        for w in ep.injected_words
                    ]
                    st.dataframe(pd.DataFrame(inj_data), use_container_width=True)
                else:
                    st.caption("None")

            with col_b:
                st.markdown("**Compound Words**")
                if ep.compound_words:
                    cmp_data = [
                        {"Concept": w.concept, "IPA": f"/{w.ipa_current}/", "POS": w.pos}
                        for w in ep.compound_words
                    ]
                    st.dataframe(pd.DataFrame(cmp_data), use_container_width=True)
                else:
                    st.caption("None")

            if ep.replaced_concepts:
                st.markdown("**Renewed Concepts** (Swadesh vacuum filled)")
                st.write(", ".join(ep.replaced_concepts))

            if ep.era_log:
                st.markdown("**Era Log (last 5)**")
                last5 = ep.era_log[-5:]
                era_rows = []
                for e in last5:
                    era_rows.append({
                        "Era": e.get("era"),
                        "Changed": e.get("changed_count"),
                        "Alive": e.get("alive_count"),
                        "Dead": e.get("dead_count"),
                        "Morph": e.get("morph_type"),
                    })
                st.dataframe(pd.DataFrame(era_rows), use_container_width=True)
