import pytest

from app.domain.lexicon.models import LexicalEntity
from app.domain.lexicon.typology_drift import DriftStats, TypologyDriftEngine
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.typology import TypologyMatrix


def _entity(
    word_id: str,
    *,
    gram_stage: int = 0,
    grammatical_function: str = "",
) -> LexicalEntity:
    return LexicalEntity(
        id=word_id,
        concept=f"word_{word_id}",
        pos="noun",
        ipa_current="ta",
        ipa_history=[],
        frequency_weight=0.01,
        grammaticalization_stage=gram_stage,
        grammatical_function=grammatical_function,
    )


def _hot(entities: list[LexicalEntity]) -> EngineHotState:
    hs = EngineHotState(current_era=0)
    hs.load_entities(entities)
    return hs


class TestDriftStatsProperties:
    def test_gram_density_zero_when_empty(self):
        stats = DriftStats(0, 0, 0, False)
        assert stats.gram_density == 0.0

    def test_gram_density_correct(self):
        stats = DriftStats(total_alive=10, grammaticalized_count=2, case_marker_count=0, word_order_locked=False)
        assert stats.gram_density == pytest.approx(0.2)

    def test_case_density_correct(self):
        stats = DriftStats(total_alive=10, grammaticalized_count=0, case_marker_count=1, word_order_locked=False)
        assert stats.case_density == pytest.approx(0.1)


class TestObserve:
    def test_observe_counts_grammaticalized(self):
        entities = [
            _entity("1", gram_stage=0),
            _entity("2", gram_stage=2),
            _entity("3", gram_stage=3),
        ]
        engine = TypologyDriftEngine()
        stats = engine.observe(_hot(entities))
        assert stats.grammaticalized_count == 2
        assert stats.total_alive == 3

    def test_observe_counts_case_markers(self):
        entities = [
            _entity("1", gram_stage=2, grammatical_function="case_marker"),
            _entity("2", gram_stage=2, grammatical_function="tense_marker"),
            _entity("3", gram_stage=0),
        ]
        engine = TypologyDriftEngine()
        stats = engine.observe(_hot(entities))
        assert stats.case_marker_count == 1

    def test_observe_ignores_dead_entities(self):
        e = _entity("1", gram_stage=2)
        e.is_dead = True
        e2 = _entity("2", gram_stage=0)
        engine = TypologyDriftEngine()
        stats = engine.observe(_hot([e, e2]))
        assert stats.total_alive == 1
        assert stats.grammaticalized_count == 0


class TestMaybeDrift:
    def test_no_drift_below_threshold(self):
        engine = TypologyDriftEngine(gram_density_threshold=0.15)
        typ = TypologyMatrix(morph_type="isolating")
        stats = DriftStats(total_alive=100, grammaticalized_count=10, case_marker_count=5, word_order_locked=False)
        result = engine.maybe_drift(typ, stats)
        assert result.morph_type == "isolating"

    def test_isolating_drifts_to_agglutinative_when_threshold_exceeded(self):
        engine = TypologyDriftEngine(gram_density_threshold=0.15)
        typ = TypologyMatrix(morph_type="isolating")
        stats = DriftStats(total_alive=100, grammaticalized_count=20, case_marker_count=5, word_order_locked=False)
        result = engine.maybe_drift(typ, stats)
        assert result.morph_type == "agglutinative"

    def test_agglutinative_drifts_to_fusional(self):
        engine = TypologyDriftEngine(gram_density_threshold=0.15)
        typ = TypologyMatrix(morph_type="agglutinative")
        stats = DriftStats(total_alive=100, grammaticalized_count=20, case_marker_count=5, word_order_locked=False)
        result = engine.maybe_drift(typ, stats)
        assert result.morph_type == "fusional"

    def test_fusional_does_not_drift_further(self):
        engine = TypologyDriftEngine(gram_density_threshold=0.15)
        typ = TypologyMatrix(morph_type="fusional")
        stats = DriftStats(total_alive=100, grammaticalized_count=20, case_marker_count=5, word_order_locked=False)
        result = engine.maybe_drift(typ, stats)
        assert result.morph_type == "fusional"

    def test_word_order_locked_when_case_density_drops(self):
        engine = TypologyDriftEngine(case_loss_threshold=0.02)
        typ = TypologyMatrix(morph_type="agglutinative")
        stats = DriftStats(total_alive=100, grammaticalized_count=5, case_marker_count=1, word_order_locked=False)
        engine.maybe_drift(typ, stats)
        assert engine.word_order_locked is True

    def test_word_order_not_locked_when_case_density_sufficient(self):
        engine = TypologyDriftEngine(case_loss_threshold=0.02)
        typ = TypologyMatrix()
        stats = DriftStats(total_alive=100, grammaticalized_count=5, case_marker_count=5, word_order_locked=False)
        engine.maybe_drift(typ, stats)
        assert engine.word_order_locked is False

    def test_drift_returns_new_instance_not_same(self):
        engine = TypologyDriftEngine(gram_density_threshold=0.10)
        typ = TypologyMatrix(morph_type="isolating")
        stats = DriftStats(total_alive=10, grammaticalized_count=2, case_marker_count=0, word_order_locked=False)
        result = engine.maybe_drift(typ, stats)
        assert result is not typ
