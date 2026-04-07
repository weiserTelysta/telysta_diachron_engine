"""Tests for Phase 5 request/response contracts."""

from app.llm.contracts import (
    EraLoreRequest,
    EraLoreResponse,
    RagLexemeRequest,
    RagLexemeResponse,
    ReverseEtymologyRequest,
    ReverseEtymologyResponse,
    SemanticProposalRequest,
    SemanticProposalResponse,
)


class TestEraLoreContracts:
    def test_request_roundtrip(self) -> None:
        req = EraLoreRequest(
            era=3, active_rules=["final_vowel_drop"], representative_changes=[],
            morph_type="isolating", word_order="SVO", alive_count=200, dead_count=7,
        )
        d = req.to_dict()
        assert d["era"] == 3
        assert d["active_rules"] == ["final_vowel_drop"]

    def test_response_from_dict(self) -> None:
        resp = EraLoreResponse.from_dict({
            "narrative": "The age of change.",
            "tags": ["myth", "war"],
            "era": 5,
        })
        assert resp.narrative == "The age of change."
        assert resp.era == 5
        assert len(resp.tags) == 2


class TestSemanticProposalContracts:
    def test_response_roundtrip(self) -> None:
        resp = SemanticProposalResponse(
            word_id="era_0_1", shift_type="metaphor",
            from_prime="SUN", to_prime="SOUL",
            chain=["SUN", "LIGHT", "SOUL"], confidence=0.7,
        )
        d = resp.to_dict()
        reconstructed = SemanticProposalResponse.from_dict(d)
        assert reconstructed.word_id == "era_0_1"
        assert reconstructed.chain == ["SUN", "LIGHT", "SOUL"]


class TestRagContracts:
    def test_response_from_dict(self) -> None:
        resp = RagLexemeResponse.from_dict({
            "new_concept": "telescope",
            "new_ipa": "kiporin",
            "root_ids_used": ["a", "b"],
        })
        assert resp.new_concept == "telescope"
        assert resp.new_ipa == "kiporin"


class TestEtymologyContracts:
    def test_response_unknown_band(self) -> None:
        resp = ReverseEtymologyResponse.from_dict({
            "modern_word_id": "w1",
            "confidence_band": "unknown",
        })
        assert resp.confidence_band == "unknown"
        assert resp.accepted_chain == []
