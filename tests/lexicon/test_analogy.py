import random

import pytest

from app.domain.lexicon.analogy import AnalogyPropagator
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.syntax.typology import TypologyMatrix


def _inv() -> PhonemeInventory:
    return PhonemeInventory.from_preset("ipa_minimal")


def _entity(
    word_id: str,
    ipa: str,
    word_class: str = "content",
) -> LexicalEntity:
    return LexicalEntity(
        id=word_id,
        concept=f"word_{word_id}",
        pos="noun",
        ipa_current=ipa,
        ipa_history=[],
        frequency_weight=0.01,
        word_class=word_class,
    )


def _prop(spread_rate: float = 1.0, sim_threshold: float = 0.0) -> AnalogyPropagator:
    return AnalogyPropagator(_inv(), spread_rate=spread_rate, similarity_threshold=sim_threshold)


class TestFeatureProfile:
    def test_profile_non_empty_for_known_ipa(self):
        prop = _prop()
        profile = prop._feature_profile("ta")
        assert len(profile) >= 1

    def test_profile_empty_for_unrecognized_ipa(self):
        prop = _prop()
        profile = prop._feature_profile("")
        assert profile == []


class TestSimilarity:
    def test_identical_profiles_score_1(self):
        prop = _prop()
        p = prop._feature_profile("ta")
        assert prop._similarity(p, p) == pytest.approx(1.0)

    def test_both_empty_score_1(self):
        prop = _prop()
        assert prop._similarity([], []) == pytest.approx(1.0)

    def test_one_empty_score_0(self):
        prop = _prop()
        p = prop._feature_profile("ta")
        assert prop._similarity(p, []) == pytest.approx(0.0)

    def test_different_ipa_score_below_1(self):
        prop = _prop()
        p1 = prop._feature_profile("ta")
        p2 = prop._feature_profile("mi")
        assert prop._similarity(p1, p2) < 1.0


class TestPropagate:
    def test_source_excluded_from_result(self):
        prop = _prop(spread_rate=1.0, sim_threshold=0.0)
        source = _entity("s1", "ta")
        rng = random.Random(42)
        result = prop.propagate(source, [source], "PAST", "et", TypologyMatrix(), rng)
        assert "s1" not in result

    def test_dead_candidate_excluded(self):
        prop = _prop(spread_rate=1.0, sim_threshold=0.0)
        source = _entity("s1", "ta")
        dead = _entity("d1", "ta")
        dead.is_dead = True
        rng = random.Random(42)
        result = prop.propagate(source, [source, dead], "PAST", "et", TypologyMatrix(), rng)
        assert "d1" not in result

    def test_different_word_class_excluded(self):
        prop = _prop(spread_rate=1.0, sim_threshold=0.0)
        source = _entity("s1", "ta", word_class="content")
        function_word = _entity("f1", "ta", word_class="function")
        rng = random.Random(42)
        result = prop.propagate(source, [source, function_word], "PAST", "et", TypologyMatrix(), rng)
        assert "f1" not in result

    def test_spread_rate_zero_returns_empty(self):
        prop = _prop(spread_rate=0.0, sim_threshold=0.0)
        source = _entity("s1", "ta")
        candidate = _entity("c1", "ta")
        rng = random.Random(42)
        result = prop.propagate(source, [source, candidate], "PAST", "et", TypologyMatrix(), rng)
        assert result == []

    def test_spread_rate_one_returns_all_similar_candidates(self):
        prop = _prop(spread_rate=1.0, sim_threshold=0.0)
        source = _entity("s1", "ta")
        c1 = _entity("c1", "ta")
        c2 = _entity("c2", "ta")
        rng = random.Random(42)
        result = prop.propagate(source, [source, c1, c2], "PAST", "et", TypologyMatrix(), rng)
        assert set(result) == {"c1", "c2"}

    def test_high_similarity_threshold_reduces_matches(self):
        prop_low = _prop(spread_rate=1.0, sim_threshold=0.0)
        prop_high = _prop(spread_rate=1.0, sim_threshold=0.99)
        source = _entity("s1", "ta")
        dissimilar = _entity("c1", "mi")
        rng = random.Random(42)
        result_low = prop_low.propagate(source, [source, dissimilar], "PAST", "et", TypologyMatrix(), rng)
        result_high = prop_high.propagate(source, [source, dissimilar], "PAST", "et", TypologyMatrix(), rng)
        assert len(result_low) >= len(result_high)
