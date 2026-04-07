"""Integration test: evolve() with is_llm on and off.

Ensures the symbolic evolution path is unaffected by the LLM flag.
"""

from app.core.settings import GlobalSettings, global_settings
from app.domain.lexicon.factory import create_basic_lexicon_generator
from app.domain.storage.hot_state import EngineHotState


def _evolve_with_flag(is_llm: bool, seed: int = 888) -> EngineHotState:
    """Run a minimal evolve with the given LLM flag and return the final state."""
    from main import evolve

    settings_dict = {"seed": seed, "is_llm": is_llm}
    global_settings.modify_settings(settings_dict)

    engine = create_basic_lexicon_generator(global_settings)
    words = engine.generate()
    swadesh = {e.concept for e in words}

    phase5_orch = None
    if is_llm:
        from app.core.config import configs
        from app.llm.factory import create_backend
        from app.llm.lore import LoreSidecar
        from app.llm.orchestrator import Phase5Orchestrator

        backend = create_backend(global_settings)
        lore_sc = LoreSidecar(configs.SNAPSHOT_DIR / "lore_test")
        phase5_orch = Phase5Orchestrator(backend, global_settings, lore_sc)

    hot, _ = evolve(
        words, era_steps=3, swadesh_concepts=swadesh,
        phase5_orchestrator=phase5_orch,
    )
    return hot


class TestEvolveLLMFlag:
    def test_llm_off_deterministic(self) -> None:
        h1 = _evolve_with_flag(is_llm=False, seed=888)
        h2 = _evolve_with_flag(is_llm=False, seed=888)
        ipas1 = sorted(e.ipa_current for e in h1.all_alive())
        ipas2 = sorted(e.ipa_current for e in h2.all_alive())
        assert ipas1 == ipas2

    def test_llm_on_runs_without_error(self) -> None:
        hot = _evolve_with_flag(is_llm=True, seed=888)
        assert len(hot) > 0

    def test_llm_off_no_semantic_changes(self) -> None:
        hot = _evolve_with_flag(is_llm=False, seed=888)
        for e in hot.all_alive():
            assert len(e.semantic_era_log) == 0

    def test_llm_on_has_semantic_changes(self) -> None:
        hot = _evolve_with_flag(is_llm=True, seed=888)
        total_entries = sum(len(e.semantic_era_log) for e in hot.all_alive())
        assert total_entries > 0
