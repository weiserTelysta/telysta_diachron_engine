"""Feature matrix for legacy history replay.

Passing tests protect currently working scalar replay behavior.  Strict xfails
document known information loss that the Rust event/reducer core must close.
They must be removed only when the legacy behavior is deliberately repaired
or the equivalent Rust capability has a passing contract test.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from app.core.config import configs
from app.core.settings import GlobalSettings
from app.domain.lexicon.models import LexicalEntity
from app.domain.storage.canonical import canonical_legacy_state, semantic_hashes
from app.domain.storage.event_log import DeltaEvent, DeltaEventType, KeyframeManager
from app.domain.storage.history import HistoryRebuilder
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.typology import TypologyMatrix
from app.engine.epoch import EpochConfig, EpochManager
from app.engine.evolution import EvolutionEngine
from app.engine.vocabulary import DomainInjector


def _entity(word_id: str, concept: str, ipa: str) -> LexicalEntity:
    return LexicalEntity(
        id=word_id,
        concept=concept,
        pos="n.",
        ipa_current=ipa,
        ipa_history=[],
        frequency_weight=0.2,
        ipa_exemplars=[{"form": ipa, "weight": 1.0}],
    )


def _initial_state(*, protected: set[str] | None = None) -> EngineHotState:
    state = EngineHotState(current_era=0, swadesh_concepts=protected)
    state.load_entities([_entity("root_a", "fire", "taka"), _entity("root_b", "water", "mibo")])
    return state


def _typology() -> TypologyMatrix:
    return TypologyMatrix(
        word_order="SOV",
        tense_system="tenseless",
        morph_type="agglutinative",
        case_system="ergative_absolutive",
        agreement_features=["person"],
        morpheme_table={"ERG": "ka"},
    )


def _replay(
    tmp_path: Path,
    initial: EngineHotState,
    events: list[DeltaEvent],
    *,
    typology: TypologyMatrix | None = None,
) -> tuple[EngineHotState, EngineHotState, HistoryRebuilder]:
    manager = KeyframeManager(tmp_path, keyframe_interval=10)
    manager.write_keyframe(0, initial.snapshot(typology=typology))
    online = initial.clone()
    for event in events:
        online.apply_delta(event)
        manager.record(event)
    for era in sorted({event.era for event in events}):
        manager.flush_era(era)
    rebuilder = HistoryRebuilder(manager)
    return online, rebuilder.rebuild(max(event.era for event in events)), rebuilder


def _full_hash(state: EngineHotState, typology: TypologyMatrix | None = None) -> str:
    return semantic_hashes(canonical_legacy_state(state, typology))["full"]


def test_replay_preserves_sound_change_form_and_era(tmp_path: Path) -> None:
    online, rebuilt, _ = _replay(
        tmp_path,
        _initial_state(),
        [
            DeltaEvent(
                event_type=DeltaEventType.SOUND_CHANGE,
                era=1,
                word_id="root_a",
                old_ipa="taka",
                new_ipa="taga",
                rule_name="intervocalic_voicing",
            ),
            DeltaEvent(event_type=DeltaEventType.ERA_ADVANCE, era=1),
        ],
    )
    assert rebuilt.current_era == online.current_era == 1
    assert rebuilt.get("root_a").ipa_current == online.get("root_a").ipa_current == "taga"
    assert rebuilt.get("root_a").ipa_history == ["taka"]


def test_replay_preserves_injected_lexeme_body(tmp_path: Path) -> None:
    initial = _initial_state()
    injected = _entity("domain_wheat_1", "wheat", "kapi")
    online, rebuilt, _ = _replay(
        tmp_path,
        initial,
        [
            DeltaEvent(
                event_type=DeltaEventType.INJECT_WORD,
                era=1,
                word_id=injected.id,
                new_entity=injected,
            )
        ],
    )
    assert rebuilt.get(injected.id).ipa_current == online.get(injected.id).ipa_current
    assert rebuilt.get(injected.id).concept == "wheat"


def test_replay_preserves_soft_deletion(tmp_path: Path) -> None:
    online, rebuilt, _ = _replay(
        tmp_path,
        _initial_state(),
        [DeltaEvent(event_type=DeltaEventType.MARK_DEAD, era=1, word_id="root_a")],
    )
    assert rebuilt.get("root_a").is_dead is online.get("root_a").is_dead is True


@pytest.mark.xfail(
    strict=True,
    reason="HistoryRebuilder._load_snapshot ignores the persisted DAG, including base nodes.",
)
def test_replay_restores_full_state_after_sound_change(tmp_path: Path) -> None:
    typology = _typology()
    online, rebuilt, _ = _replay(
        tmp_path,
        _initial_state(),
        [
            DeltaEvent(
                event_type=DeltaEventType.SOUND_CHANGE,
                era=1,
                word_id="root_a",
                old_ipa="taka",
                new_ipa="taga",
            ),
            DeltaEvent(event_type=DeltaEventType.ERA_ADVANCE, era=1),
        ],
        typology=typology,
    )
    assert _full_hash(rebuilt, typology) == _full_hash(online, typology)


@pytest.mark.xfail(
    strict=True,
    reason="HistoryRebuilder._load_snapshot ignores EngineHotState.swadesh_concepts.",
)
def test_replay_restores_swadesh_protection_set(tmp_path: Path) -> None:
    protected = {"fire", "water"}
    _, rebuilt, _ = _replay(
        tmp_path,
        _initial_state(protected=protected),
        [DeltaEvent(event_type=DeltaEventType.ERA_ADVANCE, era=1)],
    )
    assert rebuilt.swadesh_concepts == protected


@pytest.mark.xfail(
    strict=True,
    reason="HistoryRebuilder has no typology read model and ignores snapshot['typology'].",
)
def test_replay_restores_typology_snapshot(tmp_path: Path) -> None:
    typology = _typology()
    _, rebuilt, _ = _replay(
        tmp_path,
        _initial_state(),
        [DeltaEvent(event_type=DeltaEventType.ERA_ADVANCE, era=1)],
        typology=typology,
    )
    assert rebuilt.typology.to_dict() == typology.to_dict()  # type: ignore[attr-defined]


@pytest.mark.xfail(
    strict=True,
    reason="_dict_to_event drops dag_parent_id, source_language, edge_type and concept.",
)
def test_event_decoder_preserves_all_replay_relevant_fields(tmp_path: Path) -> None:
    manager = KeyframeManager(tmp_path)
    event = DeltaEvent(
        event_type=DeltaEventType.BORROW_WORD,
        era=3,
        word_id="loan",
        dag_parent_id="source_root",
        source_language="South",
        edge_type="borrowing",
        concept="trade",
    )
    decoded = HistoryRebuilder(manager)._dict_to_event(event.to_dict())
    assert decoded.dag_parent_id == "source_root"
    assert decoded.source_language == "South"
    assert decoded.edge_type == "borrowing"
    assert decoded.concept == "trade"


@pytest.mark.parametrize(
    ("event_type", "edge_type"),
    [
        (DeltaEventType.BORROW_WORD, "borrowing"),
        (DeltaEventType.FOSSIL_SPAWN, "fossil_prefix"),
    ],
)
@pytest.mark.xfail(
    strict=True,
    reason="Event decoder loses dag_parent_id, so replay drops lexical lineage edges.",
)
def test_replay_restores_single_parent_lineage_events(
    tmp_path: Path,
    event_type: DeltaEventType,
    edge_type: str,
) -> None:
    initial = _initial_state()
    child = _entity("child", "loan", "kapi")
    online, rebuilt, _ = _replay(
        tmp_path,
        initial,
        [
            DeltaEvent(
                event_type=event_type,
                era=1,
                word_id=child.id,
                new_entity=child,
                dag_parent_id="root_a",
                edge_type=edge_type,
            )
        ],
    )
    assert rebuilt.dag.parents("child") == online.dag.parents("child") == ["root_a"]


@pytest.mark.xfail(
    strict=True,
    reason="Compound replay loses both parent references because its spawn and DAG-edge event fields are dropped.",
)
def test_replay_restores_compound_two_parent_lineage(tmp_path: Path) -> None:
    initial = _initial_state()
    compound = _entity("compound_fire_water", "fire_water", "tamibo")
    online, rebuilt, _ = _replay(
        tmp_path,
        initial,
        [
            DeltaEvent(
                event_type=DeltaEventType.COMPOUND_SPAWN,
                era=1,
                word_id=compound.id,
                new_entity=compound,
                dag_parent_id="root_a",
                edge_type="compound",
            ),
            DeltaEvent(
                event_type=DeltaEventType.DAG_EDGE_ADD,
                era=1,
                word_id=compound.id,
                dag_parent_id="root_b",
                edge_type="compound",
            ),
        ],
    )
    assert sorted(rebuilt.dag.parents(compound.id)) == sorted(online.dag.parents(compound.id))


@pytest.mark.xfail(
    strict=True,
    reason="Epoch DomainInjector mutates Hot State but its INJECT_WORD events are never recorded by KeyframeManager.",
)
def test_epoch_injection_is_present_in_persisted_event_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(configs, "SNAPSHOT_DIR", tmp_path)
    settings = GlobalSettings(seed=42, phoneme_preset="ipa_minimal")
    engine = EvolutionEngine(settings)
    state = _initial_state()
    manager = EpochManager(
        [EpochConfig("injection", 1, domain_inject="agriculture", compound_enabled=False)],
        domain_injector_factory=lambda domain: DomainInjector(domain, configs.DOMAIN_VOCAB_DIR),
        seed=42,
    )
    with redirect_stdout(io.StringIO()):
        _, _, results = manager.run(state, _typology(), engine, keyframe_interval=10)

    persisted_types = {
        event["event_type"]
        for event_file in (tmp_path / "events").glob("delta_era_*.json")
        for event in json.loads(event_file.read_text(encoding="utf-8"))
    }
    assert results[0].injected_words
    assert DeltaEventType.INJECT_WORD.value in persisted_types
