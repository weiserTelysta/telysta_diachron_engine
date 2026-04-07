"""Integration test: EvolutionEngine.run() with is_llm on and off.

Ensures the symbolic evolution path is unaffected by the LLM flag,
and that Phase 5 orchestrator receives real era delta events.
"""

from app.core.settings import GlobalSettings, global_settings
from app.domain.lexicon.factory import create_basic_lexicon_generator
from app.domain.storage.hot_state import EngineHotState
from app.engine.evolution import EvolutionEngine


def _evolve_with_flag(is_llm: bool, seed: int = 888) -> EngineHotState:
    settings_dict = {"seed": seed, "is_llm": is_llm}
    global_settings.modify_settings(settings_dict)

    engine = EvolutionEngine(global_settings)
    words = create_basic_lexicon_generator(global_settings).generate()
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

    hot, _ = engine.run(
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

    def test_lore_files_created_with_llm_on(self) -> None:
        """Era lore sidecar files must be written when lore is enabled."""
        from app.core.config import configs
        from app.llm.lore import LoreSidecar

        _evolve_with_flag(is_llm=True, seed=888)

        sidecar = LoreSidecar(configs.SNAPSHOT_DIR / "lore_test")
        lore_entries = sidecar.load_all()
        assert len(lore_entries) > 0, "Expected lore files to be written"

    def test_era_deltas_not_empty_for_lore(self) -> None:
        """Smoke test: orchestrator receives non-trivial delta lists by era 3."""
        captured_deltas: list[list] = []

        from app.core.config import configs
        from app.core.settings import global_settings
        from app.domain.lexicon.factory import create_basic_lexicon_generator
        from app.engine.evolution import EvolutionEngine
        from app.llm.backends.mock_backend import MockBackend
        from app.llm.lore import LoreSidecar
        from app.llm.orchestrator import Phase5Orchestrator

        global_settings.modify_settings({"seed": 42, "is_llm": True})

        class SpyOrchestrator(Phase5Orchestrator):
            def on_era_end(self, era, hot_state, active_ops, delta_events, typology, **kw):
                captured_deltas.append(list(delta_events))
                return super().on_era_end(era, hot_state, active_ops, delta_events, typology, **kw)

        backend = MockBackend(seed=42)
        orch = SpyOrchestrator(backend, global_settings, LoreSidecar(configs.SNAPSHOT_DIR / "lore_test"))

        engine = EvolutionEngine(global_settings)
        words = create_basic_lexicon_generator(global_settings).generate()
        engine.run(words, era_steps=3, swadesh_concepts={e.concept for e in words}, phase5_orchestrator=orch)

        total_deltas = sum(len(d) for d in captured_deltas)
        assert total_deltas > 0, "Expected non-empty delta events passed to orchestrator"
