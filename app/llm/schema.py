"""JSON Schema definitions for Phase 5 contracts.

Used by:
  - Provider structured-output hints (``schema_hint`` in ``LLMBackend.call``)
  - Sanitizer validation layer
"""

from __future__ import annotations

from typing import Any

ERA_LORE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "narrative": {"type": "string", "maxLength": 500},
        "tags": {
            "type": "array",
            "items": {"type": "string", "maxLength": 32},
            "maxItems": 10,
        },
        "era": {"type": "integer"},
    },
    "required": ["narrative", "tags"],
    "additionalProperties": False,
}

SEMANTIC_PROPOSAL_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "word_id": {"type": "string", "maxLength": 64},
        "shift_type": {
            "type": "string",
            "enum": ["metaphor", "metonymy", "broadening", "narrowing"],
        },
        "from_prime": {"type": "string", "maxLength": 64, "pattern": "^[A-Z_][A-Z0-9_]*$"},
        "to_prime": {"type": "string", "maxLength": 64, "pattern": "^[A-Z_][A-Z0-9_]*$"},
        "chain": {
            "type": "array",
            "items": {"type": "string", "maxLength": 64},
            "maxItems": 20,
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reasoning": {"type": "string", "maxLength": 300},
    },
    "required": ["word_id", "shift_type", "from_prime", "to_prime"],
    "additionalProperties": False,
}

RAG_LEXEME_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "new_concept": {"type": "string", "maxLength": 64},
        "new_ipa": {"type": "string", "maxLength": 64},
        "root_ids_used": {
            "type": "array",
            "items": {"type": "string", "maxLength": 64},
            "maxItems": 10,
        },
        "morpheme_breakdown": {"type": "string", "maxLength": 128},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reasoning": {"type": "string", "maxLength": 300},
    },
    "required": ["new_concept", "new_ipa"],
    "additionalProperties": False,
}

REVERSE_ETYMOLOGY_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "modern_word_id": {"type": "string", "maxLength": 64},
        "accepted_chain": {
            "type": "array",
            "items": {"type": "string", "maxLength": 64},
            "maxItems": 20,
        },
        "rejected_candidates": {
            "type": "array",
            "items": {"type": "string", "maxLength": 64},
            "maxItems": 20,
        },
        "confidence_band": {
            "type": "string",
            "enum": ["high", "medium", "low", "unknown"],
        },
        "reasoning": {"type": "string", "maxLength": 300},
    },
    "required": ["modern_word_id"],
    "additionalProperties": False,
}

SCHEMA_REGISTRY: dict[str, dict[str, Any]] = {
    "EraLoreResponse": ERA_LORE_RESPONSE_SCHEMA,
    "SemanticProposalResponse": SEMANTIC_PROPOSAL_RESPONSE_SCHEMA,
    "RagLexemeResponse": RAG_LEXEME_RESPONSE_SCHEMA,
    "ReverseEtymologyResponse": REVERSE_ETYMOLOGY_RESPONSE_SCHEMA,
}


def get_schema(response_class_name: str) -> dict[str, Any]:
    schema = SCHEMA_REGISTRY.get(response_class_name)
    if schema is None:
        raise KeyError(f"No schema registered for {response_class_name!r}")
    return schema
