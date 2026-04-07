"""Sidebar controls — returns a config dict consumed by EngineSession."""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_sidebar() -> dict[str, Any] | None:
    """Draw sidebar widgets and return config when Run is clicked."""
    st.sidebar.header("Engine Parameters")

    seed = st.sidebar.number_input("Seed", min_value=0, max_value=2**32, value=888, step=1)
    preset = st.sidebar.selectbox(
        "Phoneme Preset",
        ["ipa_minimal", "elven_light", "orcish_heavy"],
        index=0,
    )
    is_llm = st.sidebar.checkbox("Enable LLM (MockBackend)", value=True)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Evolution Mode")
    use_epochs = st.sidebar.toggle("Epoch Mode", value=True, help="Multi-epoch evolution with vocabulary injection")

    if use_epochs:
        epoch_config = st.sidebar.selectbox(
            "Epoch Preset",
            ["default"],
            index=0,
            help="YAML preset from data/epoch_presets/",
        )
        era_steps = None
    else:
        era_steps = st.sidebar.slider("Era Steps", min_value=10, max_value=500, value=100, step=10)
        epoch_config = None

    run_clicked = st.sidebar.button("Run Evolution", type="primary", use_container_width=True)

    if run_clicked:
        return {
            "seed": int(seed),
            "phoneme_preset": preset,
            "era_steps": era_steps or 100,
            "is_llm": is_llm,
            "use_epochs": use_epochs,
            "epoch_config": epoch_config,
        }
    return None
