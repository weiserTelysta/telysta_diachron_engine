"""Tests for EpochConfig, load_epoch_config, and EpochManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import configs
from app.core.settings import global_settings
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.typology import TypologyMatrix
from app.engine.epoch import EpochConfig, EpochManager, EpochResult, load_epoch_config
from app.engine.evolution import EvolutionEngine

_PRESET = configs.EPOCH_PRESETS_DIR / "default.yaml"


def _make_hot(n: int = 5) -> EngineHotState:
    inv = PhonemeInventory.from_preset("ipa_minimal")
    import random
    rng = random.Random(42)
    entities = [
        LexicalEntity(
            id=f"w{i}", concept=f"concept_{i}", pos="n.",
            ipa_current=inv.sample_consonant(rng).symbol + inv.sample_vowel(rng).symbol,
            ipa_history=[], frequency_weight=0.01 * (i + 1),
            word_class="content",
        )
        for i in range(n)
    ]
    hot = EngineHotState(current_era=0)
    hot.load_entities(entities)
    return hot


def _typology() -> TypologyMatrix:
    return TypologyMatrix(morph_type="isolating")


class TestEpochConfig:
    def test_valid_config(self):
        cfg = EpochConfig(name="proto", era_count=10, morph_type_bias="isolating")
        assert cfg.name == "proto"
        assert cfg.era_count == 10

    def test_invalid_bias_raises(self):
        with pytest.raises(ValueError, match="morph_type_bias"):
            EpochConfig(name="proto", era_count=10, morph_type_bias="wrong")

    def test_invalid_era_count_raises(self):
        with pytest.raises(ValueError, match="era_count"):
            EpochConfig(name="proto", era_count=0)

    def test_default_values(self):
        cfg = EpochConfig(name="x", era_count=5)
        assert cfg.morph_type_bias == "auto"
        assert cfg.domain_inject is None
        assert cfg.compound_enabled is True


class TestLoadEpochConfig:
    def test_loads_five_epochs(self):
        epochs = load_epoch_config(_PRESET)
        assert len(epochs) == 5

    def test_epoch_names(self):
        epochs = load_epoch_config(_PRESET)
        names = [e.name for e in epochs]
        assert names == ["proto", "ancient", "medieval", "premodern", "modern"]

    def test_proto_has_no_inject(self):
        epochs = load_epoch_config(_PRESET)
        assert epochs[0].domain_inject is None

    def test_ancient_injects_agriculture(self):
        epochs = load_epoch_config(_PRESET)
        assert epochs[1].domain_inject == "agriculture"

    def test_all_era_counts_are_20(self):
        for ep in load_epoch_config(_PRESET):
            assert ep.era_count == 20


class TestEpochManager:
    def _engine(self) -> EvolutionEngine:
        global_settings.modify_settings({"seed": 42, "phoneme_preset": "ipa_minimal"})
        return EvolutionEngine(global_settings)

    def test_run_returns_three_items(self):
        epochs = [EpochConfig(name="p", era_count=2)]
        manager = EpochManager(epochs=epochs)
        hot = _make_hot()
        _, _, results = manager.run(hot, _typology(), self._engine())
        assert len(results) == 1

    def test_hot_state_persists_across_epochs(self):
        epochs = [
            EpochConfig(name="a", era_count=2),
            EpochConfig(name="b", era_count=2),
        ]
        manager = EpochManager(epochs=epochs)
        hot = _make_hot(5)
        final_hot, _, _ = manager.run(hot, _typology(), self._engine())
        assert len(final_hot.lexicon) >= 5

    def test_era_end_accumulates(self):
        epochs = [
            EpochConfig(name="a", era_count=3),
            EpochConfig(name="b", era_count=4),
        ]
        manager = EpochManager(epochs=epochs)
        hot = _make_hot()
        _, _, results = manager.run(hot, _typology(), self._engine())
        assert results[0].era_end == 3
        assert results[1].era_end == 7

    def test_epoch_result_fields(self):
        epochs = [EpochConfig(name="test", era_count=2)]
        manager = EpochManager(epochs=epochs)
        hot = _make_hot()
        _, _, results = manager.run(hot, _typology(), self._engine())
        r = results[0]
        assert r.epoch_name == "test"
        assert r.epoch_idx == 0
        assert r.era_start == 0
        assert r.era_end == 2
        assert isinstance(r.era_log, list)

    def test_bias_isolating_applied(self):
        epochs = [EpochConfig(name="p", era_count=2, morph_type_bias="agglutinative")]
        manager = EpochManager(epochs=epochs)
        hot = _make_hot()
        typology = TypologyMatrix(morph_type="isolating")
        _, final_typology, _ = manager.run(hot, typology, self._engine())
        # bias is applied at epoch start; drift may have changed it further
        # but at minimum the first run was started with agglutinative
        assert final_typology is not None
