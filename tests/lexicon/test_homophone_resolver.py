import random

import pytest

from app.domain.lexicon.homophone_resolver import HomophoneResolver
from app.domain.lexicon.models import LexicalEntity
from app.domain.storage.event_log import DeltaEventType


def make_entity(
    wid: str,
    ipa: str,
    freq: float = 0.01,
    is_dead: bool = False,
    era_born: int = 0,
) -> LexicalEntity:
    return LexicalEntity(
        id=wid,
        concept=wid,
        pos="noun",
        ipa_current=ipa,
        ipa_history=[],
        frequency_weight=freq,
        is_dead=is_dead,
        era_born=era_born,
    )


@pytest.fixture
def resolver() -> HomophoneResolver:
    return HomophoneResolver()


# ------------------------------------------------------------------
# detect
# ------------------------------------------------------------------

def test_no_homophones(resolver: HomophoneResolver) -> None:
    lexicon = {
        "a": make_entity("a", "ta"),
        "b": make_entity("b", "ka"),
    }
    assert resolver.detect(lexicon) == []


def test_detects_pair(resolver: HomophoneResolver) -> None:
    lexicon = {
        "a": make_entity("a", "ta"),
        "b": make_entity("b", "ta"),
    }
    pairs = resolver.detect(lexicon)
    assert len(pairs) == 1


def test_ignores_dead_words(resolver: HomophoneResolver) -> None:
    lexicon = {
        "a": make_entity("a", "ta"),
        "b": make_entity("b", "ta", is_dead=True),
    }
    assert resolver.detect(lexicon) == []


def test_triple_collision_produces_three_pairs(resolver: HomophoneResolver) -> None:
    lexicon = {
        "a": make_entity("a", "ta"),
        "b": make_entity("b", "ta"),
        "c": make_entity("c", "ta"),
    }
    pairs = resolver.detect(lexicon)
    assert len(pairs) == 3


# ------------------------------------------------------------------
# resolve — reduplication
# ------------------------------------------------------------------

def test_reduplication_doubles_form(resolver: HomophoneResolver) -> None:
    high = make_entity("a", "ta", freq=0.05)
    low  = make_entity("b", "ta", freq=0.01)
    rng = random.Random(0)
    events = resolver.resolve((high, low), era=1, rng=rng, morphological_type="agglutinative")
    assert events
    change_events = [e for e in events if e.event_type == DeltaEventType.SOUND_CHANGE]
    assert change_events
    assert change_events[0].new_ipa is not None


# ------------------------------------------------------------------
# resolve — lexical_death
# ------------------------------------------------------------------

def test_lexical_death_marks_low_freq(resolver: HomophoneResolver) -> None:
    high = make_entity("a", "ta", freq=0.05)
    low  = make_entity("b", "ta", freq=0.001)
    rng = random.Random(0)
    events = resolver.resolve((high, low), era=1, rng=rng, morphological_type="fusional")
    dead_events = [e for e in events if e.event_type == DeltaEventType.MARK_DEAD]
    assert dead_events
    assert dead_events[0].word_id == "b"


# ------------------------------------------------------------------
# resolve — agglutinative prefers affixation over reduplication
# ------------------------------------------------------------------

def test_agglutinative_prefers_affixation(resolver: HomophoneResolver) -> None:
    high = make_entity("a", "ta", freq=0.05)
    low  = make_entity("b", "ta", freq=0.01)
    rng = random.Random(0)
    events = resolver.resolve((high, low), era=1, rng=rng, morphological_type="agglutinative")
    assert events
    e = events[0]
    assert e.event_type == DeltaEventType.SOUND_CHANGE
    assert e.rule_name == "homophone_affixation"
    assert e.word_id == "b"  # low-freq word gets suffix


# ------------------------------------------------------------------
# resolve — empty result when no strategy applies (borrowing stub)
# ------------------------------------------------------------------

def test_only_borrowing_stub_returns_empty() -> None:
    """Borrowing strategy (stub) alone produces no events."""

    class BorrowingOnlyResolver(HomophoneResolver):
        @staticmethod
        def _strategy_order(_: str) -> list[str]:  # type: ignore[override]
            return ["borrowing"]

    resolver = BorrowingOnlyResolver()
    high = make_entity("a", "ta", freq=0.05)
    low  = make_entity("b", "ta", freq=0.01)
    rng = random.Random(0)
    events = resolver.resolve((high, low), era=1, rng=rng)
    assert events == []


# ------------------------------------------------------------------
# resolve — seniority protection
# ------------------------------------------------------------------

def test_seniority_protects_older_word() -> None:
    """An old low-freq word should outweigh a young higher-freq newcomer."""
    resolver = HomophoneResolver()
    # "ancient" word: born at era 0, freq=0.001; at era 100 it has +0.05 bonus
    ancient = make_entity("ancient", "zu", freq=0.001, era_born=0)
    # "newcomer" word: born at era 99, freq=0.002; almost no seniority bonus
    newcomer = make_entity("newcomer", "zu", freq=0.002, era_born=99)
    rng = random.Random(0)
    # fusional favours semantic_shift / lexical_death on the loser
    events = resolver.resolve((ancient, newcomer), era=100, rng=rng, morphological_type="fusional")
    dead_events = [e for e in events if e.event_type == DeltaEventType.MARK_DEAD]
    assert dead_events, "expected at least one MARK_DEAD event"
    # newcomer should be the one that dies, not the ancient word
    assert dead_events[0].word_id == "newcomer"
