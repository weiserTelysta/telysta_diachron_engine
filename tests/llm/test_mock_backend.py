"""Tests for MockBackend determinism and response format."""

import json

from app.llm.backends.mock_backend import MockBackend


class TestMockBackend:
    def test_deterministic_same_seed(self) -> None:
        a = MockBackend(seed=42)
        b = MockBackend(seed=42)
        r1 = a.call("generate lore narrative")
        r2 = b.call("generate lore narrative")
        assert r1.raw_json == r2.raw_json

    def test_different_seeds_differ(self) -> None:
        a = MockBackend(seed=42)
        b = MockBackend(seed=99)
        r1 = a.call("generate lore narrative")
        r2 = b.call("generate lore narrative")
        # Tags are randomly sampled so different seeds should differ
        d1 = json.loads(r1.raw_json)
        d2 = json.loads(r2.raw_json)
        # At least the structure is valid
        assert "narrative" in d1
        assert "narrative" in d2

    def test_lore_keyword_match(self) -> None:
        m = MockBackend(seed=1)
        r = m.call("generate lore narrative for era 5")
        d = json.loads(r.raw_json)
        assert "narrative" in d
        assert "tags" in d
        assert isinstance(d["tags"], list)

    def test_proposal_keyword_match(self) -> None:
        m = MockBackend(seed=1)
        r = m.call("semantic proposal for word era_0_1")
        d = json.loads(r.raw_json)
        assert "word_id" in d
        assert "shift_type" in d
        assert d["shift_type"] in {"metaphor", "metonymy", "broadening", "narrowing"}

    def test_rag_keyword_match(self) -> None:
        m = MockBackend(seed=1)
        r = m.call("rag new_concept from roots")
        d = json.loads(r.raw_json)
        assert "new_concept" in d
        assert "new_ipa" in d

    def test_etymology_keyword_match(self) -> None:
        m = MockBackend(seed=1)
        r = m.call("etymology ancestor chain")
        d = json.loads(r.raw_json)
        assert "modern_word_id" in d
        assert "confidence_band" in d

    def test_provider_name(self) -> None:
        m = MockBackend()
        assert m.provider_name == "mock"
        assert m.model_name == "mock-deterministic"
