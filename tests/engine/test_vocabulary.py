"""Tests for DomainInjector, CompoundingEngine, VocabularyRenewalEngine."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from app.core.config import configs
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.storage.hot_state import EngineHotState
from app.domain.storage.event_log import DeltaEventType
from app.engine.vocabulary import (
    CompoundingEngine,
    DomainInjector,
    VocabularyRenewalEngine,
)

_INV = PhonemeInventory.from_preset("ipa_minimal")
_RNG = random.Random(99)

_COMPOUNDS_FILE = configs.DATA_DIR / "semantic_compounds.json"
_DOMAIN_DIR = configs.DOMAIN_VOCAB_DIR


def _hot_with(concepts: list[str]) -> EngineHotState:
    rng = random.Random(7)
    entities = [
        LexicalEntity(
            id=f"w_{c}", concept=c, pos="n.",
            ipa_current=_INV.sample_consonant(rng).symbol + _INV.sample_vowel(rng).symbol,
            ipa_history=[], frequency_weight=0.01,
            word_class="content",
        )
        for c in concepts
    ]
    hot = EngineHotState(current_era=0)
    hot.load_entities(entities)
    return hot


class TestDomainInjector:
    def test_injects_words_from_file(self):
        injector = DomainInjector("agriculture", _DOMAIN_DIR)
        hot = _hot_with([])
        words = injector.inject(hot, era=1, inv=_INV, rng=random.Random(1))
        assert len(words) > 0

    def test_skips_existing_concept(self):
        injector = DomainInjector("agriculture", _DOMAIN_DIR)
        hot = _hot_with(["plow", "harvest"])
        words = injector.inject(hot, era=1, inv=_INV, rng=random.Random(1))
        injected_concepts = [w.concept for w in words]
        assert "plow" not in injected_concepts
        assert "harvest" not in injected_concepts

    def test_injected_words_are_alive_in_hot(self):
        injector = DomainInjector("agriculture", _DOMAIN_DIR)
        hot = _hot_with([])
        words = injector.inject(hot, era=1, inv=_INV, rng=random.Random(2))
        for w in words:
            assert w.id in hot.lexicon
            assert not hot.lexicon[w.id].is_dead

    def test_era_born_set(self):
        injector = DomainInjector("agriculture", _DOMAIN_DIR)
        hot = _hot_with([])
        words = injector.inject(hot, era=5, inv=_INV, rng=random.Random(3))
        for w in words:
            assert w.era_born == 5

    def test_missing_file_returns_empty(self):
        injector = DomainInjector("nonexistent", _DOMAIN_DIR)
        hot = _hot_with([])
        result = injector.inject(hot, era=1, inv=_INV, rng=random.Random(4))
        assert result == []


class TestCompoundingEngine:
    def test_generates_compound_when_both_alive(self):
        engine = CompoundingEngine(_COMPOUNDS_FILE)
        # fire + mountain → volcano (epoch_min=1)
        hot = _hot_with(["fire", "mountain"])
        result = engine.generate(hot, era=1, rng=random.Random(5), epoch_idx=1)
        concepts = [w.concept for w in result]
        assert "volcano" in concepts

    def test_no_compound_when_component_missing(self):
        engine = CompoundingEngine(_COMPOUNDS_FILE)
        hot = _hot_with(["fire"])  # mountain is missing
        result = engine.generate(hot, era=1, rng=random.Random(6), epoch_idx=1)
        concepts = [w.concept for w in result]
        assert "volcano" not in concepts

    def test_no_duplicate_if_concept_exists(self):
        engine = CompoundingEngine(_COMPOUNDS_FILE)
        hot = _hot_with(["fire", "mountain", "volcano"])
        result = engine.generate(hot, era=1, rng=random.Random(7), epoch_idx=1)
        concepts = [w.concept for w in result]
        assert concepts.count("volcano") == 0

    def test_compound_ipa_non_empty(self):
        engine = CompoundingEngine(_COMPOUNDS_FILE)
        hot = _hot_with(["fire", "mountain"])
        result = engine.generate(hot, era=1, rng=random.Random(8))
        for w in result:
            assert len(w.ipa_current) >= 1

    def test_epoch_min_filter(self):
        engine = CompoundingEngine(_COMPOUNDS_FILE)
        # stardust requires epoch_min=3; pass epoch_idx=0
        hot = _hot_with(["star", "ash"])
        result = engine.generate(hot, era=1, rng=random.Random(9), epoch_idx=0)
        concepts = [w.concept for w in result]
        assert "stardust" not in concepts

    def test_epoch_min_passes_at_correct_epoch(self):
        engine = CompoundingEngine(_COMPOUNDS_FILE)
        hot = _hot_with(["star", "ash"])
        result = engine.generate(hot, era=1, rng=random.Random(10), epoch_idx=3)
        concepts = [w.concept for w in result]
        assert "stardust" in concepts


class TestVocabularyRenewalEngine:
    def test_renews_vacant_swadesh_concept(self):
        from app.engine.vocabulary import DomainInjector
        injector = DomainInjector("agriculture", _DOMAIN_DIR)
        engine = VocabularyRenewalEngine(injector)

        # Create hot state where "water" is fully grammaticalized (stage 4)
        rng = random.Random(11)
        water = LexicalEntity(
            id="w_water", concept="water", pos="n.",
            ipa_current="ba",
            ipa_history=["bala"], frequency_weight=0.05,
            word_class="function",
            grammaticalization_stage=4,
        )
        hot = EngineHotState(current_era=0)
        hot.load_entities([water])

        swadesh = {"water"}
        renewed = engine.renew(hot, era=5, swadesh_concepts=swadesh, inv=_INV, rng=rng)
        assert "water" in renewed

    def test_no_renewal_when_concept_alive(self):
        from app.engine.vocabulary import DomainInjector
        injector = DomainInjector("agriculture", _DOMAIN_DIR)
        engine = VocabularyRenewalEngine(injector)

        rng = random.Random(12)
        water = LexicalEntity(
            id="w_water", concept="water", pos="n.",
            ipa_current="ba", ipa_history=[], frequency_weight=0.05,
            word_class="content", grammaticalization_stage=0,
        )
        hot = EngineHotState(current_era=0)
        hot.load_entities([water])

        swadesh = {"water"}
        renewed = engine.renew(hot, era=5, swadesh_concepts=swadesh, inv=_INV, rng=rng)
        assert renewed == []

    def test_replacement_word_added_to_hot(self):
        from app.engine.vocabulary import DomainInjector
        injector = DomainInjector("agriculture", _DOMAIN_DIR)
        engine = VocabularyRenewalEngine(injector)

        rng = random.Random(13)
        water = LexicalEntity(
            id="w_water", concept="water", pos="n.",
            ipa_current="ba", ipa_history=[], frequency_weight=0.05,
            word_class="function", grammaticalization_stage=4,
        )
        hot = EngineHotState(current_era=0)
        hot.load_entities([water])

        engine.renew(hot, era=5, swadesh_concepts={"water"}, inv=_INV, rng=rng)
        alive_concepts = {e.concept for e in hot.all_alive()}
        assert "water" in alive_concepts
