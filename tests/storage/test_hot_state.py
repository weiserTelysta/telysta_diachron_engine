import json
import tempfile
from pathlib import Path

import pytest

from app.domain.lexicon.models import LexicalEntity
from app.domain.storage.event_log import DeltaEvent, DeltaEventType, KeyframeManager
from app.domain.storage.history import HistoryRebuilder
from app.domain.storage.hot_state import EngineHotState


def make_entity(word_id: str, ipa: str = "taka") -> LexicalEntity:
    return LexicalEntity(
        id=word_id,
        concept="water",
        pos="n.",
        ipa_current=ipa,
        ipa_history=[ipa],
        frequency_weight=0.5,
    )


def test_hot_state_load_and_get():
    state = EngineHotState()
    e = make_entity("w1", "taka")
    state.load_entities([e])
    assert state.get("w1") is not None
    assert state.get("w1").ipa_current == "taka"


def test_hot_state_put_overwrites():
    state = EngineHotState()
    e = make_entity("w1", "taka")
    state.load_entities([e])
    e2 = make_entity("w1", "taga")
    state.put(e2)
    assert state.get("w1").ipa_current == "taga"


def test_hot_state_all_alive_filters_dead():
    state = EngineHotState()
    e1 = make_entity("w1")
    e2 = make_entity("w2")
    e2.is_dead = True
    state.load_entities([e1, e2])
    alive = state.all_alive()
    assert len(alive) == 1
    assert alive[0].id == "w1"


def test_hot_state_apply_delta_sound_change():
    state = EngineHotState()
    e = make_entity("w1", "taka")
    state.load_entities([e])
    event = DeltaEvent(
        event_type=DeltaEventType.SOUND_CHANGE,
        era=1,
        word_id="w1",
        old_ipa="taka",
        new_ipa="taga",
    )
    state.apply_delta(event)
    assert state.get("w1").ipa_current == "taga"
    assert "taka" in state.get("w1").ipa_history


def test_hot_state_apply_delta_mark_dead():
    state = EngineHotState()
    e = make_entity("w1")
    state.load_entities([e])
    event = DeltaEvent(
        event_type=DeltaEventType.MARK_DEAD,
        era=1,
        word_id="w1",
    )
    state.apply_delta(event)
    assert state.get("w1").is_dead is True


def test_hot_state_snapshot_round_trip():
    state = EngineHotState(current_era=3)
    e = make_entity("w1", "taka")
    state.load_entities([e])
    snap = state.snapshot()
    assert snap["era"] == 3
    assert "w1" in snap["lexicon"]


def test_hot_state_clone_is_independent():
    state = EngineHotState()
    e = make_entity("w1", "taka")
    state.load_entities([e])
    cloned = state.clone()
    cloned.get("w1").ipa_current = "modified"
    assert state.get("w1").ipa_current == "taka"


def test_keyframe_manager_write_and_load(tmp_path):
    km = KeyframeManager(base_dir=tmp_path, keyframe_interval=5)
    snapshot = {"era": 0, "lexicon": {"w1": {"id": "w1", "ipa_current": "taka"}}}
    km.write_keyframe(0, snapshot)
    loaded = km.load_keyframe(0)
    assert loaded is not None
    assert loaded["era"] == 0


def test_keyframe_manager_delta_record_and_load(tmp_path):
    km = KeyframeManager(base_dir=tmp_path)
    event = DeltaEvent(
        event_type=DeltaEventType.SOUND_CHANGE,
        era=1,
        word_id="w1",
        old_ipa="taka",
        new_ipa="taga",
    )
    km.record(event)
    km.flush_era(1)
    deltas = km.load_deltas_for_era(1)
    assert len(deltas) == 1
    assert deltas[0]["word_id"] == "w1"


def test_history_rebuilder(tmp_path):
    km = KeyframeManager(base_dir=tmp_path, keyframe_interval=10)
    e = make_entity("w1", "taka")
    state = EngineHotState(current_era=0)
    state.load_entities([e])
    km.write_keyframe(0, state.snapshot())

    delta = DeltaEvent(
        event_type=DeltaEventType.SOUND_CHANGE,
        era=1,
        word_id="w1",
        old_ipa="taka",
        new_ipa="taga",
    )
    km.record(delta)
    km.flush_era(1)

    rebuilder = HistoryRebuilder(km)
    rebuilt = rebuilder.rebuild(1)
    assert rebuilt.get("w1").ipa_current == "taga"
    assert rebuilt.current_era == 1
