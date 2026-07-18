"""Executable golden scenarios for the legacy Python migration baseline."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from app.core.config import configs
from app.core.rng import RNG_TREE_VERSION
from app.core.settings import GlobalSettings
from app.domain.language.branch import BranchConfig, BranchLanguage
from app.domain.lexicon.factory import create_basic_lexicon_generator
from app.domain.phonology.validator import WellFormednessValidator
from app.domain.storage.canonical import LEGACY_CANONICAL_SCHEMA, build_baseline_report
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.semantic_graph import SemanticGraph
from app.domain.syntax.typology import TypologyMatrix
from app.engine.epoch import EpochConfig, EpochManager
from app.engine.evolution import EvolutionEngine
from app.engine.vocabulary import CompoundingEngine, DomainInjector, VocabularyRenewalEngine
from app.llm.backends.mock_backend import MockBackend
from app.llm.lore import LoreSidecar
from app.llm.orchestrator import Phase5Orchestrator


GOLDEN_SCENARIO_VERSION = "legacy-golden-v1"
GOLDEN_SCENARIOS = ("genesis", "flat_10", "epoch_injection", "branch", "mock_llm")


@contextmanager
def _snapshot_workspace(path: Path) -> Iterator[None]:
    old_snapshot_dir = configs.SNAPSHOT_DIR
    configs.SNAPSHOT_DIR = path
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield
    finally:
        configs.SNAPSHOT_DIR = old_snapshot_dir


def _settings(seed: int) -> GlobalSettings:
    return GlobalSettings(
        seed=seed,
        is_llm=False,
        phoneme_preset="ipa_minimal",
    )


def _typology() -> TypologyMatrix:
    return TypologyMatrix(
        word_order="SVO",
        tense_system="inflectional",
        morph_type="isolating",
        case_system="nominative_accusative",
        morpheme_table={},
    )


def _genesis(settings: GlobalSettings) -> tuple[list[Any], set[str]]:
    words = create_basic_lexicon_generator(settings).generate()
    swadesh_path = configs.DATA_DIR / "lexicolist" / "swadesh_100.json"
    raw = json.loads(swadesh_path.read_text(encoding="utf-8"))
    swadesh = {item["en"] for item in list(raw.values())[0]}
    return words, swadesh


def _events(path: Path) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    events_dir = path / "events"
    for event_file in sorted(events_dir.glob("delta_era_*.json")):
        result.extend(json.loads(event_file.read_text(encoding="utf-8")))
    return result


def _result(
    *,
    name: str,
    seed: int,
    hot: EngineHotState,
    typology: TypologyMatrix,
    events: list[Mapping[str, Any]],
    settings: GlobalSettings,
    inputs: Mapping[str, Any],
    known_limitations: list[str] | None = None,
) -> dict[str, Any]:
    validator = WellFormednessValidator.from_config(
        settings.inventory,
        configs.DATA_DIR / "phonotactics" / "default_phonotactics.json",
    )
    report = build_baseline_report(
        hot,
        typology,
        events,
        inventory=settings.inventory,
        validator=validator,
    )
    return {
        "scenario_version": GOLDEN_SCENARIO_VERSION,
        "canonical_schema": LEGACY_CANONICAL_SCHEMA,
        "rng_version": RNG_TREE_VERSION,
        "name": name,
        "seed": seed,
        "inputs": dict(inputs),
        "report": report.to_dict(),
        "known_limitations": known_limitations or [],
    }


def run_legacy_golden_scenario(name: str, seed: int, workspace: str | Path) -> dict[str, Any]:
    """Run one named scenario in an isolated snapshot workspace."""
    if name not in GOLDEN_SCENARIOS:
        raise ValueError(f"Unknown golden scenario {name!r}; expected one of {GOLDEN_SCENARIOS}")

    root = Path(workspace)
    settings = _settings(seed)
    with _snapshot_workspace(root):
        words, swadesh = _genesis(settings)
        typology = _typology()

        if name == "genesis":
            hot = EngineHotState(current_era=0, swadesh_concepts=swadesh)
            hot.load_entities(words)
            return _result(
                name=name,
                seed=seed,
                hot=hot,
                typology=typology,
                events=[],
                settings=settings,
                inputs={"phoneme_preset": settings.phoneme_preset, "era_steps": 0},
            )

        engine = EvolutionEngine(settings)

        if name == "flat_10":
            hot, typology = engine.run(
                words,
                era_steps=10,
                keyframe_interval=5,
                swadesh_concepts=swadesh,
                typology=typology,
            )
            return _result(
                name=name,
                seed=seed,
                hot=hot,
                typology=typology,
                events=_events(root),
                settings=settings,
                inputs={"phoneme_preset": settings.phoneme_preset, "era_steps": 10},
            )

        if name == "epoch_injection":
            hot = EngineHotState(current_era=0, swadesh_concepts=swadesh)
            hot.load_entities(words)
            epochs = [
                EpochConfig("proto", 2, "isolating", None, False),
                EpochConfig("ancient", 2, "auto", "agriculture", True),
            ]

            def injector_factory(domain: str) -> DomainInjector:
                return DomainInjector(domain, configs.DOMAIN_VOCAB_DIR)

            manager = EpochManager(
                epochs,
                domain_injector_factory=injector_factory,
                compounding_engine=CompoundingEngine(configs.DATA_DIR / "semantic_compounds.json"),
                renewal_engine=VocabularyRenewalEngine(
                    DomainInjector("agriculture", configs.DOMAIN_VOCAB_DIR)
                ),
                seed=seed,
            )
            hot, typology, _ = manager.run(
                hot,
                typology,
                engine,
                swadesh_concepts=swadesh,
                keyframe_interval=2,
            )
            return _result(
                name=name,
                seed=seed,
                hot=hot,
                typology=typology,
                events=_events(root),
                settings=settings,
                inputs={"epochs": ["proto:2", "ancient:2+agriculture+compound"]},
                known_limitations=[
                    "Epoch boundary injection and compound events are not fully persisted by the legacy engine."
                ],
            )

        if name == "branch":
            parent = EngineHotState(current_era=0, swadesh_concepts=swadesh)
            parent.load_entities(words)
            branch = BranchLanguage(
                BranchConfig(name="north", fork_era=0, seed=seed),
                parent,
                typology,
                SemanticGraph(),
                engine.registry,
                settings.inventory,
            )
            for _ in range(3):
                branch.evolve_one_era()
            return _result(
                name=name,
                seed=seed,
                hot=branch.hot_state,
                typology=branch.typology,
                events=[],
                settings=settings,
                inputs={"branch": "north", "era_steps": 3},
                known_limitations=[
                    "BranchLanguage does not yet expose its applied events; state hashes remain authoritative."
                ],
            )

        backend = MockBackend(seed=seed)
        orchestrator = Phase5Orchestrator(
            backend,
            settings,
            LoreSidecar(root / "lore"),
        )
        hot, typology = engine.run(
            words,
            era_steps=3,
            keyframe_interval=3,
            swadesh_concepts=swadesh,
            typology=typology,
            phase5_orchestrator=orchestrator,
        )
        return _result(
            name=name,
            seed=seed,
            hot=hot,
            typology=typology,
            events=_events(root),
            settings=settings,
            inputs={"llm_provider": "mock", "era_steps": 3},
        )
