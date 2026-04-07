"""Tests for the LLM response sanitizer security layer."""

import json

from app.llm.sanitizer import sanitize


class TestJsonParseIsolation:
    def test_invalid_json_rejected(self) -> None:
        result = sanitize("not json at all", "EraLoreResponse")
        assert not result.ok
        assert "JSON parse" in result.errors[0]

    def test_non_object_rejected(self) -> None:
        result = sanitize('"just a string"', "EraLoreResponse")
        assert not result.ok
        assert "object" in result.errors[0]

    def test_unknown_type_rejected(self) -> None:
        result = sanitize('{"x": 1}', "NonExistentType")
        assert not result.ok


class TestFieldWhitelist:
    def test_extra_fields_stripped(self) -> None:
        payload = json.dumps({
            "narrative": "hello", "tags": ["myth"],
            "injected_field": "evil", "__proto__": "bad",
        })
        result = sanitize(payload, "EraLoreResponse")
        assert result.ok
        assert "injected_field" not in result.data  # type: ignore[operator]
        assert "__proto__" not in result.data  # type: ignore[operator]


class TestTypeCoercion:
    def test_wrong_type_rejected(self) -> None:
        payload = json.dumps({"narrative": 12345, "tags": ["myth"]})
        result = sanitize(payload, "EraLoreResponse")
        assert not result.ok

    def test_int_to_float_coercion(self) -> None:
        payload = json.dumps({
            "word_id": "w1", "shift_type": "metaphor",
            "from_prime": "SUN", "to_prime": "SOUL",
            "confidence": 1,
        })
        result = sanitize(payload, "SemanticProposalResponse")
        assert result.ok
        assert isinstance(result.data["confidence"], float)  # type: ignore[index]


class TestLengthTruncation:
    def test_long_narrative_truncated(self) -> None:
        payload = json.dumps({
            "narrative": "x" * 1000, "tags": ["myth"],
        })
        result = sanitize(payload, "EraLoreResponse")
        assert result.ok
        assert len(result.data["narrative"]) == 500  # type: ignore[index]

    def test_list_max_items(self) -> None:
        payload = json.dumps({
            "narrative": "ok", "tags": ["t"] * 20,
        })
        result = sanitize(payload, "EraLoreResponse")
        assert result.ok
        assert len(result.data["tags"]) == 10  # type: ignore[index]


class TestContentSanitization:
    def test_script_injection_rejected(self) -> None:
        payload = json.dumps({
            "narrative": '<script>alert("xss")</script>', "tags": ["myth"],
        })
        result = sanitize(payload, "EraLoreResponse")
        assert not result.ok
        assert "Injection" in result.errors[0]

    def test_prime_id_pattern_enforced(self) -> None:
        payload = json.dumps({
            "word_id": "w1", "shift_type": "metaphor",
            "from_prime": "invalid_lowercase", "to_prime": "SOUL",
        })
        result = sanitize(payload, "SemanticProposalResponse")
        assert not result.ok

    def test_valid_prime_ids_pass(self) -> None:
        payload = json.dumps({
            "word_id": "w1", "shift_type": "metaphor",
            "from_prime": "SUN", "to_prime": "SOUL",
            "confidence": 0.8,
        })
        result = sanitize(payload, "SemanticProposalResponse")
        assert result.ok

    def test_ipa_charset_stripping(self) -> None:
        payload = json.dumps({
            "new_concept": "test", "new_ipa": "kipo<script>rin",
        })
        result = sanitize(payload, "RagLexemeResponse")
        # The injection pattern check should catch <script> before IPA stripping
        assert not result.ok


class TestRateAnomaly:
    def test_proposal_rate_limit(self) -> None:
        counter: dict[int, int] = {}
        base = {"word_id": "w1", "shift_type": "metaphor",
                "from_prime": "SUN", "to_prime": "SOUL", "confidence": 0.5}

        for i in range(5):
            r = sanitize(
                json.dumps(base), "SemanticProposalResponse",
                max_proposals_per_era=5,
                _proposal_counter=counter, current_era=1,
            )
            assert r.ok, f"Call {i+1} should pass"

        r = sanitize(
            json.dumps(base), "SemanticProposalResponse",
            max_proposals_per_era=5,
            _proposal_counter=counter, current_era=1,
        )
        assert not r.ok
        assert "rate exceeded" in r.errors[0].lower()
