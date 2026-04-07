"""Tests for the LLM response sanitizer security layer."""

import json

import pytest

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


class TestRequiredFields:
    def test_missing_required_narrative_rejected(self) -> None:
        payload = json.dumps({"tags": ["myth"]})
        result = sanitize(payload, "EraLoreResponse")
        assert not result.ok
        assert any("narrative" in e for e in result.errors)

    def test_missing_required_tags_rejected(self) -> None:
        payload = json.dumps({"narrative": "ok"})
        result = sanitize(payload, "EraLoreResponse")
        assert not result.ok
        assert any("tags" in e for e in result.errors)

    def test_missing_required_proposal_fields_rejected(self) -> None:
        payload = json.dumps({
            "word_id": "w1", "shift_type": "metaphor",
            "from_prime": "SUN",
            # to_prime missing
        })
        result = sanitize(payload, "SemanticProposalResponse")
        assert not result.ok
        assert any("to_prime" in e for e in result.errors)

    def test_missing_modern_word_id_rejected(self) -> None:
        payload = json.dumps({"confidence_band": "high"})
        result = sanitize(payload, "ReverseEtymologyResponse")
        assert not result.ok
        assert any("modern_word_id" in e for e in result.errors)


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

    def test_bool_not_accepted_as_int(self) -> None:
        payload = json.dumps({"narrative": "ok", "tags": ["myth"], "era": True})
        result = sanitize(payload, "EraLoreResponse")
        assert not result.ok


class TestEnumValidation:
    def test_invalid_shift_type_rejected(self) -> None:
        payload = json.dumps({
            "word_id": "w1", "shift_type": "EVIL_INJECTION",
            "from_prime": "SUN", "to_prime": "SOUL",
        })
        result = sanitize(payload, "SemanticProposalResponse")
        assert not result.ok
        assert any("enum" in e.lower() for e in result.errors)

    def test_invalid_confidence_band_rejected(self) -> None:
        payload = json.dumps({
            "modern_word_id": "w1",
            "confidence_band": "definitely_certain",
        })
        result = sanitize(payload, "ReverseEtymologyResponse")
        assert not result.ok
        assert any("enum" in e.lower() for e in result.errors)

    def test_valid_confidence_band_passes(self) -> None:
        for band in ("high", "medium", "low", "unknown"):
            result = sanitize(
                json.dumps({"modern_word_id": "w1", "confidence_band": band}),
                "ReverseEtymologyResponse",
            )
            assert result.ok, f"band={band} should pass"


class TestNumericRange:
    def test_confidence_above_max_rejected(self) -> None:
        payload = json.dumps({
            "word_id": "w1", "shift_type": "metaphor",
            "from_prime": "SUN", "to_prime": "SOUL",
            "confidence": 1.5,
        })
        result = sanitize(payload, "SemanticProposalResponse")
        assert not result.ok
        assert any("above maximum" in e for e in result.errors)

    def test_confidence_below_min_rejected(self) -> None:
        payload = json.dumps({
            "word_id": "w1", "shift_type": "metaphor",
            "from_prime": "SUN", "to_prime": "SOUL",
            "confidence": -0.1,
        })
        result = sanitize(payload, "SemanticProposalResponse")
        assert not result.ok
        assert any("below minimum" in e for e in result.errors)

    def test_confidence_boundary_values_pass(self) -> None:
        for conf in (0.0, 1.0):
            result = sanitize(
                json.dumps({
                    "word_id": "w1", "shift_type": "metaphor",
                    "from_prime": "SUN", "to_prime": "SOUL",
                    "confidence": conf,
                }),
                "SemanticProposalResponse",
            )
            assert result.ok, f"confidence={conf} should pass"


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

    def test_list_item_too_long_truncated(self) -> None:
        payload = json.dumps({
            "narrative": "ok", "tags": ["x" * 100],
        })
        result = sanitize(payload, "EraLoreResponse")
        assert result.ok
        assert len(result.data["tags"][0]) == 32  # type: ignore[index]


class TestContentSanitization:
    def test_script_injection_rejected(self) -> None:
        payload = json.dumps({
            "narrative": '<script>alert("xss")</script>', "tags": ["myth"],
        })
        result = sanitize(payload, "EraLoreResponse")
        assert not result.ok
        assert "Injection" in result.errors[0]

    def test_backtick_injection_rejected(self) -> None:
        payload = json.dumps({
            "narrative": "`rm -rf /`", "tags": ["myth"],
        })
        result = sanitize(payload, "EraLoreResponse")
        assert not result.ok

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
        assert not result.ok

    def test_list_item_injection_rejected(self) -> None:
        payload = json.dumps({
            "modern_word_id": "w1",
            "accepted_chain": ["ok_root", "<script>bad</script>"],
        })
        result = sanitize(payload, "ReverseEtymologyResponse")
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


class TestFullValidLorePasses:
    def test_minimal_valid_lore(self) -> None:
        result = sanitize(
            json.dumps({"narrative": "A great change.", "tags": ["myth"]}),
            "EraLoreResponse",
        )
        assert result.ok
        assert result.data["narrative"] == "A great change."

    def test_full_valid_proposal(self) -> None:
        result = sanitize(
            json.dumps({
                "word_id": "era_0_5", "shift_type": "broadening",
                "from_prime": "WATER", "to_prime": "LIFE",
                "chain": ["WATER", "LIQUID", "LIFE"],
                "confidence": 0.75,
                "reasoning": "Water is the source of life.",
            }),
            "SemanticProposalResponse",
        )
        assert result.ok

    def test_full_valid_rag(self) -> None:
        result = sanitize(
            json.dumps({
                "new_concept": "compass",
                "new_ipa": "porak",
                "root_ids_used": ["era_0_12"],
                "confidence": 0.6,
            }),
            "RagLexemeResponse",
        )
        assert result.ok
