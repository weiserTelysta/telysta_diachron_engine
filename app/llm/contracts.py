"""Phase 5 request/response data contracts.

Every field is type-annotated. ``to_dict`` / ``from_dict`` provide
serialization; ``json_schema`` exports a JSON Schema for provider
structured-output hints and sanitizer validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Requests (Engine -> LLM)
# ---------------------------------------------------------------------------

@dataclass
class EraLoreRequest:
    era: int
    active_rules: list[str]
    representative_changes: list[dict[str, str]]
    morph_type: str
    word_order: str
    alive_count: int
    dead_count: int
    branch_info: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticProposalRequest:
    era: int
    word_id: str
    concept: str
    current_primes: list[str]
    context_chain: list[str]
    allowed_shift_types: list[str] = field(
        default_factory=lambda: ["metaphor", "metonymy", "broadening", "narrowing"]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RagLexemeRequest:
    era: int
    anchor_concept: str
    anchor_pos: str
    candidate_roots: list[dict[str, str]]
    phonotactic_constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReverseEtymologyRequest:
    modern_word_id: str
    modern_ipa: str
    candidate_ancestors: list[dict[str, str]]
    dag_fragment: dict[str, list[str]] = field(default_factory=dict)
    max_tolerance_distance: float = 3.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Responses (LLM -> Engine)
# ---------------------------------------------------------------------------

@dataclass
class EraLoreResponse:
    narrative: str
    tags: list[str] = field(default_factory=list)
    era: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EraLoreResponse:
        return cls(
            narrative=d.get("narrative", ""),
            tags=d.get("tags", []),
            era=d.get("era", 0),
        )


@dataclass
class SemanticProposalResponse:
    word_id: str
    shift_type: str
    from_prime: str
    to_prime: str
    chain: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SemanticProposalResponse:
        return cls(
            word_id=d.get("word_id", ""),
            shift_type=d.get("shift_type", ""),
            from_prime=d.get("from_prime", ""),
            to_prime=d.get("to_prime", ""),
            chain=d.get("chain", []),
            confidence=d.get("confidence", 0.0),
            reasoning=d.get("reasoning", ""),
        )


@dataclass
class RagLexemeResponse:
    new_concept: str
    new_ipa: str
    root_ids_used: list[str] = field(default_factory=list)
    morpheme_breakdown: str = ""
    confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RagLexemeResponse:
        return cls(
            new_concept=d.get("new_concept", ""),
            new_ipa=d.get("new_ipa", ""),
            root_ids_used=d.get("root_ids_used", []),
            morpheme_breakdown=d.get("morpheme_breakdown", ""),
            confidence=d.get("confidence", 0.0),
            reasoning=d.get("reasoning", ""),
        )


@dataclass
class ReverseEtymologyResponse:
    modern_word_id: str
    accepted_chain: list[str] = field(default_factory=list)
    rejected_candidates: list[str] = field(default_factory=list)
    confidence_band: str = "unknown"   # "high" | "medium" | "low" | "unknown"
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReverseEtymologyResponse:
        return cls(
            modern_word_id=d.get("modern_word_id", ""),
            accepted_chain=d.get("accepted_chain", []),
            rejected_candidates=d.get("rejected_candidates", []),
            confidence_band=d.get("confidence_band", "unknown"),
            reasoning=d.get("reasoning", ""),
        )
