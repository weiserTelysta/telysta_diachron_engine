"""EngineSession — full pipeline orchestration for CLI and UI consumers.

Wraps bootstrap → lexicon generation → evolution → result collection
into a single ``run()`` call that returns a ``RunResult``.

Two execution modes:
  use_epochs=True  (default) — EpochManager drives multi-epoch evolution
  use_epochs=False           — flat era loop via EvolutionEngine.run()
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import app.core.console as console
from app.core.config import configs
from app.core.logging import configure_root, get_logger, setup_run_logger
from app.core.settings import GlobalSettings, global_settings
from app.domain.lexicon.factory import create_basic_lexicon_generator
from app.domain.storage.hot_state import EngineHotState
from app.engine.evolution import EvolutionEngine

if TYPE_CHECKING:
    from app.domain.lexicon.models import LexicalEntity
    from app.domain.syntax.typology import TypologyMatrix
    from app.engine.epoch import EpochResult

logger = get_logger(__name__)


@dataclass
class RunResult:
    """Structured output of a complete engine run."""

    seed: int
    phoneme_preset: str
    era_steps: int
    era0_hot: EngineHotState
    final_hot: EngineHotState
    final_typology: "TypologyMatrix"
    era_log: list[dict]
    generated_words: list["LexicalEntity"]
    swadesh_concepts: set[str]
    engine: EvolutionEngine = field(repr=False)
    epoch_results: list["EpochResult"] = field(default_factory=list)


class EngineSession:
    """One-shot pipeline: configure → generate → evolve → collect.

    Usage::

        session = EngineSession(seed=888, use_epochs=True)
        result = session.run()
    """

    def __init__(
        self,
        seed: int = 888,
        phoneme_preset: str = "ipa_minimal",
        era_steps: int = 100,
        is_llm: bool = True,
        llm_provider: str = "mock",
        keyframe_interval: int = 10,
        use_epochs: bool = True,
        epoch_config: str | None = None,
    ) -> None:
        self.seed = seed
        self.phoneme_preset = phoneme_preset
        self.era_steps = era_steps
        self.is_llm = is_llm
        self.llm_provider = llm_provider
        self.keyframe_interval = keyframe_interval
        self.use_epochs = use_epochs
        self.epoch_config = epoch_config

    def run(self) -> RunResult:
        self._bootstrap()
        setup_run_logger(self.seed)
        console.session_start(self.seed, self.phoneme_preset)

        engine = EvolutionEngine(global_settings)

        words = create_basic_lexicon_generator(global_settings).generate()
        logger.debug("创世完成，共生成 %d 个核心词汇。", len(words))

        self._verify_grammar_embryo(words)
        swadesh_concepts = self._load_swadesh_100()

        era0_hot = EngineHotState(current_era=0)
        era0_hot.load_entities(words)
        era0_snapshot = era0_hot.clone()

        phase5_orch = self._build_phase5() if self.is_llm else None

        if self.use_epochs:
            hot, final_typology, epoch_results, era_log = self._run_epochs(
                engine, words, swadesh_concepts, phase5_orch
            )
            total_eras = sum(ep.era_end - ep.era_start for ep in epoch_results) if epoch_results else 0
        else:
            era_log: list[dict] = []
            hot, final_typology = engine.run(
                words,
                era_steps=self.era_steps,
                keyframe_interval=self.keyframe_interval,
                swadesh_concepts=swadesh_concepts,
                phase5_orchestrator=phase5_orch,
                era_log=era_log,
            )
            epoch_results = []
            total_eras = self.era_steps

        logger.debug(
            "演化完成: %d 时代, 最终类型学 %s / %s, 词库 %d 词",
            total_eras, final_typology.morph_type, final_typology.word_order,
            len(hot.all_alive()),
        )
        alive_n = len(hot.all_alive())
        _sample_words = list(hot.all_alive())[:3]
        _sample_parts = []
        for w in _sample_words:
            hist = " → ".join(w.ipa_history[-1:] + [w.ipa_current]) if w.ipa_history else w.ipa_current
            _sample_parts.append(f"[{w.concept}] {hist}")
        console.session_end(
            total_eras=total_eras,
            alive=alive_n,
            dead=len(hot.lexicon) - alive_n,
            morph=final_typology.morph_type,
            order=final_typology.word_order,
            sample=" | ".join(_sample_parts),
        )

        return RunResult(
            seed=self.seed,
            phoneme_preset=self.phoneme_preset,
            era_steps=total_eras,
            era0_hot=era0_snapshot,
            final_hot=hot,
            final_typology=final_typology,
            era_log=era_log,
            generated_words=words,
            swadesh_concepts=swadesh_concepts,
            engine=engine,
            epoch_results=epoch_results,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_epochs(
        self,
        engine: EvolutionEngine,
        words: list["LexicalEntity"],
        swadesh_concepts: set[str],
        phase5_orch: object,
    ) -> tuple["EngineHotState", "TypologyMatrix", list["EpochResult"], list[dict]]:
        from app.engine.epoch import EpochManager, load_epoch_config
        from app.engine.vocabulary import (
            CompoundingEngine,
            DomainInjector,
            VocabularyRenewalEngine,
        )
        from app.domain.syntax.typology import TypologyMatrix

        epoch_name = self.epoch_config or "default"
        if not epoch_name.endswith(".yaml"):
            epoch_name += ".yaml"
        preset_path = configs.EPOCH_PRESETS_DIR / epoch_name
        epoch_configs = load_epoch_config(preset_path)

        compounding = CompoundingEngine(configs.DATA_DIR / "semantic_compounds.json")

        def domain_injector_factory(domain: str) -> DomainInjector:
            return DomainInjector(domain, configs.DOMAIN_VOCAB_DIR)

        base_injector = DomainInjector("agriculture", configs.DOMAIN_VOCAB_DIR)
        renewal = VocabularyRenewalEngine(base_injector)

        initial_hot = EngineHotState(current_era=0, swadesh_concepts=swadesh_concepts)
        initial_hot.load_entities(words)

        initial_typology = TypologyMatrix(
            word_order="SVO",
            tense_system="inflectional",
            morph_type="isolating",
            case_system="nominative_accusative",
            morpheme_table={},
        )

        manager = EpochManager(
            epochs=epoch_configs,
            domain_injector_factory=domain_injector_factory,
            compounding_engine=compounding,
            renewal_engine=renewal,
            seed=self.seed,
        )

        final_hot, final_typology, epoch_results = manager.run(
            hot=initial_hot,
            typology=initial_typology,
            engine=engine,
            swadesh_concepts=swadesh_concepts,
            phase5_orchestrator=phase5_orch,
            keyframe_interval=self.keyframe_interval,
        )

        combined_era_log: list[dict] = []
        for ep in epoch_results:
            combined_era_log.extend(ep.era_log)

        return final_hot, final_typology, epoch_results, combined_era_log

    @staticmethod
    def _verify_grammar_embryo(words: list["LexicalEntity"]) -> None:
        """Ensure the initial lexicon contains sufficient functional seeds.

        Grammaticalization pathways require source material: pronouns,
        core verbs (be/have/go), demonstratives, and negation markers.
        Without these, the engine cannot produce case markers, tense
        affixes, or definiteness clitics through natural evolution.
        """
        required_pos = {"pron.", "v."}
        found_pos = {w.pos for w in words}
        missing = required_pos - found_pos
        if missing:
            logger.warning(
                "Grammar embryo check: missing POS categories %s. "
                "Grammaticalization pathways may be starved.",
                missing,
            )

        concepts_lower = {w.concept.lower() for w in words}
        core_concepts = {"i", "you", "this", "that", "not", "be", "go", "give"}
        found_core = core_concepts & concepts_lower
        if len(found_core) < 3:
            logger.warning(
                "Grammar embryo check: only %d/%d core functional concepts "
                "found (%s). Consider enriching the seed lexicon.",
                len(found_core), len(core_concepts), found_core,
            )

    def _bootstrap(self) -> None:
        settings_dict = {
            "seed": self.seed,
            "is_llm": self.is_llm,
            "phoneme_preset": self.phoneme_preset,
            "llm_provider": self.llm_provider,
        }
        global_settings.modify_settings(settings_dict)
        configure_root(
            global_settings.log_level,
            verbose=global_settings.log_verbose,
            force=True,
        )
        logger.debug("系统引导完成，配置已就绪。")

    @staticmethod
    def _load_swadesh_100() -> set[str]:
        """Load the Swadesh 100-word concept names from the data file."""
        path = configs.DATA_DIR / "lexicolist" / "swadesh_100.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        items = list(data.values())[0]
        return {item["en"] for item in items}

    def _build_phase5(self) -> object:
        from app.llm.factory import create_backend
        from app.llm.lore import LoreSidecar
        from app.llm.orchestrator import Phase5Orchestrator

        llm_backend = create_backend(global_settings)
        lore_sidecar = LoreSidecar(configs.SNAPSHOT_DIR / "lore")
        orch = Phase5Orchestrator(llm_backend, global_settings, lore_sidecar)
        logger.debug("Phase5 orchestrator initialized (provider=%s)", llm_backend.provider_name)
        return orch
