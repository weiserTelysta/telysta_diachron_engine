from __future__ import annotations

from copy import deepcopy

import pytest

from app.core.config import configs
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.phonology.validator import WellFormednessValidator
from app.domain.storage.canonical import (
    LEGACY_CANONICAL_SCHEMA,
    build_baseline_report,
    canonical_id,
    canonical_json_bytes,
    canonical_legacy_state,
    semantic_hashes,
)
from app.domain.storage.event_log import DeltaEvent, DeltaEventType
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.typology import TypologyMatrix


def _entity(word_id: str, concept: str, ipa: str, *, dead: bool = False) -> LexicalEntity:
    return LexicalEntity(
        id=word_id,
        concept=concept,
        pos="n.",
        ipa_current=ipa,
        ipa_history=[],
        frequency_weight=0.1,
        is_dead=dead,
        ipa_exemplars=[{"form": ipa, "weight": 1.0}],
    )


def _state(reverse: bool = False) -> tuple[EngineHotState, TypologyMatrix]:
    entities = [_entity("w1", "fire", "taka"), _entity("w2", "water", "mibo")]
    if reverse:
        entities.reverse()
    hot = EngineHotState(current_era=3, swadesh_concepts={"water", "fire"})
    hot.load_entities(entities)
    hot.dag.add_edge("w1", "w2", 2, "compound")
    typology = TypologyMatrix(
        word_order="SOV",
        morph_type="agglutinative",
        morpheme_table={"ACC": "m", "PAST": "ta"},
    )
    return hot, typology


def test_canonical_id_migrates_integer_and_strips_string() -> None:
    assert canonical_id(7) == "7"
    assert canonical_id("  word-7  ") == "word-7"


@pytest.mark.parametrize("value", [None, "", "   ", True])
def test_canonical_id_rejects_ambiguous_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        canonical_id(value)


def test_insertion_order_does_not_change_canonical_bytes_or_hashes() -> None:
    hot_a, typology_a = _state(reverse=False)
    hot_b, typology_b = _state(reverse=True)
    state_a = canonical_legacy_state(hot_a, typology_a)
    state_b = canonical_legacy_state(hot_b, typology_b)
    assert canonical_json_bytes(state_a) == canonical_json_bytes(state_b)
    assert semantic_hashes(state_a) == semantic_hashes(state_b)


def test_schema_and_hash_domains_are_explicit() -> None:
    hot, typology = _state()
    hashes = semantic_hashes(canonical_legacy_state(hot, typology))
    assert hashes["schema"] == LEGACY_CANONICAL_SCHEMA
    assert hashes["algorithm"] == "sha256"
    assert set(hashes["domains"]) == {"lexicon", "dag", "typology", "events"}
    assert len(hashes["full"]) == 64


def test_event_timestamp_is_not_semantic() -> None:
    hot, typology = _state()
    first = DeltaEvent(
        event_type=DeltaEventType.SOUND_CHANGE,
        era=1,
        word_id="w1",
        old_ipa="taka",
        new_ipa="taga",
        timestamp="2020-01-01T00:00:00Z",
    )
    second = deepcopy(first)
    second.timestamp = "2030-01-01T00:00:00Z"
    hashes_a = semantic_hashes(canonical_legacy_state(hot, typology, [first]))
    hashes_b = semantic_hashes(canonical_legacy_state(hot, typology, [second]))
    assert hashes_a == hashes_b


def test_lexical_change_only_changes_lexicon_domain_and_full_hash() -> None:
    hot, typology = _state()
    before = semantic_hashes(canonical_legacy_state(hot, typology))
    hot.lexicon["w1"].ipa_current = "taga"
    after = semantic_hashes(canonical_legacy_state(hot, typology))
    assert before["domains"]["lexicon"] != after["domains"]["lexicon"]
    assert before["domains"]["dag"] == after["domains"]["dag"]
    assert before["domains"]["typology"] == after["domains"]["typology"]
    assert before["domains"]["events"] == after["domains"]["events"]
    assert before["full"] != after["full"]


def test_lexicon_key_must_match_entity_id() -> None:
    hot, typology = _state()
    hot.lexicon["wrong"] = hot.lexicon.pop("w1")
    with pytest.raises(ValueError, match="does not match"):
        canonical_legacy_state(hot, typology)


def test_baseline_report_contains_metrics_and_hard_errors() -> None:
    hot, typology = _state()
    inventory = PhonemeInventory.from_preset("ipa_minimal")
    validator = WellFormednessValidator.from_config(
        inventory,
        configs.DATA_DIR / "phonotactics" / "default_phonotactics.json",
    )
    report = build_baseline_report(
        hot,
        typology,
        inventory=inventory,
        validator=validator,
    ).to_dict()
    assert report["counts"]["alive_words"] == 2
    assert report["graph"] == {"connected_components": 1, "edges": 1, "nodes": 2}
    assert report["phonology"]["average_segments"] > 0
    assert report["hashes"]["full"]


def test_non_finite_float_is_rejected() -> None:
    hot, typology = _state()
    hot.lexicon["w1"].frequency_weight = float("nan")
    with pytest.raises(ValueError, match="NaN"):
        canonical_legacy_state(hot, typology)


def test_mapping_keys_cannot_collide_after_id_normalisation() -> None:
    with pytest.raises(ValueError, match="Duplicate canonical mapping key"):
        canonical_json_bytes({1: "integer", "1": "string"})
