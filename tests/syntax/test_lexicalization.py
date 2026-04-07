import pytest

from app.domain.lexicon.models import LexicalEntity
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.lexicalization import LexicalizationLayer
from app.domain.syntax.semantic_graph import SemanticGraph, SemanticPrime


def _entity(concept: str, is_dead: bool = False) -> LexicalEntity:
    return LexicalEntity(
        id=concept.lower(),
        concept=concept,
        pos="n",
        ipa_current=f"/{concept.lower()}/",
        ipa_history=[],
        frequency_weight=0.5,
        is_dead=is_dead,
    )


def _prime_graph() -> SemanticGraph:
    g = SemanticGraph()
    g.add_prime(SemanticPrime(id="SOMEONE", label_en="someone", category="substantives", relations=()))
    g.add_prime(SemanticPrime(id="PEOPLE",  label_en="people",  category="substantives", relations=("SOMEONE",)))
    g.add_prime(SemanticPrime(id="DO",      label_en="do",      category="actions",      relations=()))
    g.add_prime(SemanticPrime(id="MOVE",    label_en="move",    category="actions",      relations=("DO",)))
    g.add_prime(SemanticPrime(id="KNOW",    label_en="know",    category="mental",       relations=()))
    return g


class TestLexicalizationLayerExactMatch:
    def test_exact_hit(self):
        layer = LexicalizationLayer(_prime_graph())
        hs = EngineHotState(lexicon={"e1": _entity("SOMEONE")})
        result = layer.lexicalize_one("SOMEONE", hs)
        assert result is not None
        assert result.concept == "SOMEONE"

    def test_dead_entity_ignored(self):
        layer = LexicalizationLayer(_prime_graph())
        hs = EngineHotState(lexicon={"e1": _entity("SOMEONE", is_dead=True)})
        result = layer.lexicalize_one("SOMEONE", hs)
        assert result is None

    def test_concept_case_insensitive(self):
        layer = LexicalizationLayer(_prime_graph())
        e = _entity("someone")  # lowercase concept
        hs = EngineHotState(lexicon={"e1": e})
        result = layer.lexicalize_one("SOMEONE", hs)
        assert result is not None


class TestLexicalizationLayerAncestorFallback:
    def test_ancestor_fallback(self):
        """PEOPLE → relations=(SOMEONE,); lexicon has SOMEONE but not PEOPLE."""
        layer = LexicalizationLayer(_prime_graph())
        hs = EngineHotState(lexicon={"e1": _entity("SOMEONE")})
        result = layer.lexicalize_one("PEOPLE", hs)
        assert result is not None
        assert result.concept == "SOMEONE"

    def test_deep_ancestor_fallback(self):
        """MOVE → relations=(DO,); lexicon has DO but not MOVE."""
        layer = LexicalizationLayer(_prime_graph())
        hs = EngineHotState(lexicon={"e1": _entity("DO")})
        result = layer.lexicalize_one("MOVE", hs)
        assert result is not None
        assert result.concept == "DO"

    def test_no_match_returns_none(self):
        layer = LexicalizationLayer(_prime_graph())
        hs = EngineHotState(lexicon={"e1": _entity("FIRE")})
        result = layer.lexicalize_one("KNOW", hs)
        assert result is None


class TestLexicalizationLayerFull:
    def test_lexicalize_all_primes(self):
        layer = LexicalizationLayer(_prime_graph())
        hs = EngineHotState(
            lexicon={
                "e1": _entity("SOMEONE"),
                "e2": _entity("DO"),
                "e3": _entity("KNOW"),
            }
        )
        mapping = layer.lexicalize(hs)
        assert mapping["SOMEONE"].concept == "SOMEONE"
        assert mapping["PEOPLE"].concept == "SOMEONE"  # ancestor fallback
        assert mapping["DO"].concept == "DO"
        assert mapping["MOVE"].concept == "DO"          # ancestor fallback
        assert mapping["KNOW"].concept == "KNOW"

    def test_empty_lexicon_all_none(self):
        layer = LexicalizationLayer(_prime_graph())
        hs = EngineHotState()
        mapping = layer.lexicalize(hs)
        assert all(v is None for v in mapping.values())
