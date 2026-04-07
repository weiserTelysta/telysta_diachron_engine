from pathlib import Path

import pytest

from app.domain.lexicon.grammaticalization_operator import (
    GrammaticalizationOperator,
    GrammaticalResult,
)
from app.domain.lexicon.models import LexicalEntity
from app.domain.lexicon.pathways import load_pathways
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.typology import TypologyMatrix

_YAML = Path("data/grammaticalization_pathways.yaml")


def _make_entity(
    word_id: str,
    concept: str,
    ipa: str,
    *,
    pos: str = "verb",
    frequency_weight: float = 0.05,
    word_class: str = "content",
    grammaticalization_stage: int = 0,
    ipa_history: list[str] | None = None,
    stasis_counter: int = 0,
) -> LexicalEntity:
    return LexicalEntity(
        id=word_id,
        concept=concept,
        pos=pos,
        ipa_current=ipa,
        ipa_history=ipa_history or [],
        frequency_weight=frequency_weight,
        word_class=word_class,
        grammaticalization_stage=grammaticalization_stage,
        stasis_counter=stasis_counter,
    )


def _hot(entities: list[LexicalEntity]) -> EngineHotState:
    hs = EngineHotState(current_era=5)
    hs.load_entities(entities)
    return hs


def _op() -> GrammaticalizationOperator:
    inv = PhonemeInventory.from_preset("ipa_minimal")
    return GrammaticalizationOperator(load_pathways(_YAML), inv)


def _agglutinative() -> TypologyMatrix:
    return TypologyMatrix(morph_type="agglutinative")


def _isolating() -> TypologyMatrix:
    return TypologyMatrix(morph_type="isolating")


class TestYamlPathwayPath:
    def _come_entity(self, freq: float = 0.9, erosion: int = 3) -> LexicalEntity:
        # come_to_directional pathway: max_freq_rank=30, min_erosion=3
        history: list[str] = ["bam", "ba", "bɛ"][:erosion]
        return _make_entity(
            "e1", "come", "bɛ", pos="verb",
            frequency_weight=freq,
            word_class="content",
            ipa_history=history,
        )

    def test_pathway_fires_when_both_conditions_met(self):
        entity = self._come_entity()
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        hot = _hot([entity, host])
        op = _op()
        result = op.check(entity, hot, _agglutinative(), era=5)
        assert result is not None
        assert result.pathway_id == "come_to_directional"

    def test_pathway_sets_new_stage_3(self):
        entity = self._come_entity()
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(entity, _hot([entity, host]), _agglutinative(), era=5)
        assert result.new_stage == 3

    def test_pathway_product_type_agglutinative_is_suffix(self):
        entity = self._come_entity()
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(entity, _hot([entity, host]), _agglutinative(), era=5)
        assert result.product_type == "suffix"

    def test_pathway_product_type_isolating_is_free_particle(self):
        entity = self._come_entity()
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(entity, _hot([entity, host]), _isolating(), era=5)
        assert result.product_type == "free_particle"

    def test_pathway_fires_only_when_erosion_stage_sufficient(self):
        entity = self._come_entity(erosion=0)
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(entity, _hot([entity, host]), _agglutinative(), era=5)
        assert result is None

    def test_entity_word_class_updated_to_function(self):
        entity = self._come_entity()
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        op.check(entity, _hot([entity, host]), _agglutinative(), era=5)
        assert entity.word_class == "function"

    def test_entity_grammatical_function_set(self):
        entity = self._come_entity()
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        op.check(entity, _hot([entity, host]), _agglutinative(), era=5)
        assert entity.grammatical_function == "locative"

    def test_already_at_stage3_skipped(self):
        entity = self._come_entity()
        entity.grammaticalization_stage = 3
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        assert op.check(entity, _hot([entity, host]), _agglutinative(), era=5) is None

    def test_old_stage_reflects_entity_stage_before_mutation(self):
        entity = self._come_entity()
        entity.grammaticalization_stage = 1
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(entity, _hot([entity, host]), _agglutinative(), era=5)
        assert result is not None
        assert result.old_stage == 1
        assert result.new_stage == 3


class TestStasisPath:
    def _pronoun(self, counter: int = 3) -> LexicalEntity:
        return _make_entity(
            "p1", "I", "ʃu", pos="pron.",
            frequency_weight=0.05,
            word_class="function",
            stasis_counter=counter,
        )

    def test_stasis_promotes_when_threshold_reached(self):
        pronoun = self._pronoun(3)
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(pronoun, _hot([pronoun, host]), _agglutinative(), era=3)
        assert result is not None
        assert result.pathway_id == "stasis_promotion"

    def test_stasis_produces_prefix_for_agglutinative(self):
        pronoun = self._pronoun(3)
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(pronoun, _hot([pronoun, host]), _agglutinative(), era=3)
        assert result.product_type == "prefix"

    def test_stasis_produces_free_particle_for_isolating(self):
        pronoun = self._pronoun(3)
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(pronoun, _hot([pronoun, host]), _isolating(), era=3)
        assert result.product_type == "free_particle"

    def test_stasis_below_threshold_returns_none(self):
        pronoun = self._pronoun(2)
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        assert op.check(pronoun, _hot([pronoun, host]), _agglutinative(), era=3) is None

    def test_stasis_sets_stage_3(self):
        pronoun = self._pronoun(3)
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(pronoun, _hot([pronoun, host]), _agglutinative(), era=3)
        assert result.new_stage == 3

    def test_stasis_reduces_ipa_dropping_final_vowel(self):
        pronoun = self._pronoun(3)
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(pronoun, _hot([pronoun, host]), _agglutinative(), era=3)
        assert result.new_ipa == "ʃ"

    def test_stasis_resets_counter_on_entity(self):
        pronoun = self._pronoun(3)
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        op.check(pronoun, _hot([pronoun, host]), _agglutinative(), era=3)
        assert pronoun.stasis_counter == 0

    def test_note_blocked_increments_counter_for_candidate(self):
        pronoun = self._pronoun(0)
        op = _op()
        op.note_blocked(pronoun)
        assert pronoun.stasis_counter == 1

    def test_note_changed_resets_counter(self):
        pronoun = self._pronoun(2)
        op = _op()
        op.note_changed(pronoun)
        assert pronoun.stasis_counter == 0

    def test_stasis_old_stage_reflects_entity_stage_before_mutation(self):
        pronoun = _make_entity(
            "p1", "I", "ʃu", pos="pron.",
            frequency_weight=0.05,
            word_class="function",
            grammaticalization_stage=2,
            stasis_counter=3,
        )
        host = _make_entity("h1", "eat", "zɛga", pos="verb", frequency_weight=0.01)
        op = _op()
        result = op.check(pronoun, _hot([pronoun, host]), _agglutinative(), era=3)
        assert result is not None
        assert result.old_stage == 2
        assert result.new_stage == 3
