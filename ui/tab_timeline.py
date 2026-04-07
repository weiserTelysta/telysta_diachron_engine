"""Timeline tab — per-era delta events and lore narratives."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

from app.core.config import configs

if TYPE_CHECKING:
    from app.engine.session import RunResult


def _load_deltas(era: int) -> list[dict]:
    path = configs.SNAPSHOT_DIR / "events" / f"delta_era_{era:04d}.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_lore(era: int) -> dict | None:
    path = configs.SNAPSHOT_DIR / "lore" / f"lore_era_{era:04d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_timeline(result: RunResult) -> None:
    if not result.era_log:
        st.info("No era data available.")
        return

    era = st.slider("Era", min_value=1, max_value=result.era_steps, value=1)

    era_record = next((r for r in result.era_log if r["era"] == era), None)

    # --- Era Summary ---
    if era_record:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sound Changes", era_record["changed_count"])
        c2.metric("Alive", era_record["alive_count"])
        c3.metric("Dead", era_record["dead_count"])
        c4.metric("Homophone Resolved", era_record["homophone_resolved"])

        st.markdown(f"**Active Operators:** {', '.join(era_record['active_ops'])}")
        st.markdown(f"**Morph Type:** {era_record['morph_type']} | **Word Order:** {era_record['word_order']}")

    # --- Lore ---
    lore = _load_lore(era)
    if lore:
        st.subheader("Era Lore")
        st.markdown(f"> {lore.get('narrative', '—')}")
        tags = lore.get("tags", [])
        if tags:
            st.markdown(f"**Tags:** {', '.join(tags)}")

    # --- Delta Events ---
    st.subheader("Delta Events")
    deltas = _load_deltas(era)
    if not deltas:
        st.info(f"No delta file found for Era {era}.")
        return

    sound_changes = [
        d for d in deltas
        if d.get("event_type") == "sound_change" and d.get("old_ipa") and d.get("new_ipa")
    ]

    if sound_changes:
        rows = [{
            "word_id": d["word_id"],
            "old_ipa": f"/{d['old_ipa']}/",
            "new_ipa": f"/{d['new_ipa']}/",
            "rule": d.get("rule_name", ""),
        } for d in sound_changes]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No sound change events in this era.")

    other = [d for d in deltas if d.get("event_type") != "sound_change" and d.get("event_type") != "era_advance"]
    if other:
        with st.expander(f"Other events ({len(other)})"):
            for d in other:
                st.json(d)
