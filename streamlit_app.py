"""Telysta legacy research lab — Streamlit demonstration.

Launch:  streamlit run streamlit_app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Telysta — Legacy Research Lab",
    page_icon="🗣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Telysta · Legacy Research Lab")
st.caption("Python research prototype · not the Rust desktop product")
st.warning(
    "此界面仅供旧引擎研究与迁移对照，尚有已知的历史回放信息损失。"
    "输出不是正式 Rust 项目，也不代表已生成完整可用的语言。"
)

# --- Sidebar ---
from ui.sidebar import render_sidebar

params = render_sidebar()

if params is not None:
    with st.spinner("Running evolution engine..."):
        from app.engine.session import EngineSession

        session = EngineSession(
            seed=params["seed"],
            phoneme_preset=params["phoneme_preset"],
            era_steps=params["era_steps"],
            is_llm=params["is_llm"],
            use_epochs=params.get("use_epochs", True),
            epoch_config=params.get("epoch_config"),
        )
        st.session_state.result = session.run()

    result = st.session_state.result
    mode_label = "epoch mode" if params.get("use_epochs") else "flat mode"
    alive_count = len(result.final_hot.all_alive())
    st.success(
        f"Evolution complete — {mode_label}, seed {params['seed']}, "
        f"{result.era_steps} eras, "
        f"{result.final_typology.morph_type} / {result.final_typology.word_order}, "
        f"{alive_count} alive words"
    )

# --- Main content ---
if "result" not in st.session_state:
    st.info("Configure parameters in the sidebar and click **Run Evolution** to begin.")
    st.stop()

result = st.session_state.result

tab_dashboard, tab_epochs, tab_lexicon, tab_timeline, tab_dag, tab_csg, tab_branches = st.tabs(
    ["Dashboard", "Epochs", "Lexicon", "Timeline", "Etymology DAG", "CSG Demo", "Branches"]
)

with tab_dashboard:
    from ui.tab_dashboard import render_dashboard

    render_dashboard(result)

with tab_epochs:
    from ui.tab_epochs import render_epochs

    render_epochs(result)

with tab_lexicon:
    from ui.tab_lexicon import render_lexicon

    render_lexicon(result)

with tab_timeline:
    from ui.tab_timeline import render_timeline

    render_timeline(result)

with tab_dag:
    from ui.tab_dag import render_dag

    render_dag(result)

with tab_csg:
    from ui.tab_csg import render_csg

    render_csg(result)

with tab_branches:
    from ui.tab_branches import render_branches

    render_branches(result)
