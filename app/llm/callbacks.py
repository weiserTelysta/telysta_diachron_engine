"""Semantic proposal callback — three-stage validation pipeline.

Stage 1: ResponseSchemaValidation  — fields present, types correct, enums legal
Stage 2: SymbolicValidation        — semantic chain nodes exist, no cycles,
                                      hop count bounded, domain shift bounded
Stage 3: CommitPolicy              — accepted → write to LexicalEntity;
                                      over-limit → lore_only;
                                      hard-fail → rejected + audit trail
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.llm.base import LLMBackend
from app.llm.contracts import SemanticProposalRequest, SemanticProposalResponse
from app.llm.sanitizer import SanitizeResult, sanitize
from app.llm.schema import SEMANTIC_PROPOSAL_RESPONSE_SCHEMA

logger = get_logger(__name__)

_VALID_SHIFT_TYPES = frozenset({"metaphor", "metonymy", "broadening", "narrowing"})
_MAX_CHAIN_HOPS = 8


@dataclass
class CallbackVerdict:
    status: str  # "accepted" | "rejected" | "lore_only"
    proposal: SemanticProposalResponse | None = None
    reason: str = ""


def _build_proposal_prompt(req: SemanticProposalRequest) -> str:
    return "\n".join([
        "You are a diachronic semantics engine. Propose ONE semantic shift for this word.",
        "",
        f"Era: {req.era}",
        f"Word ID: {req.word_id}",
        f"Concept: {req.concept}",
        f"Current semantic primes: {', '.join(req.current_primes) or 'none'}",
        f"Context chain: {' -> '.join(req.context_chain) or 'none'}",
        f"Allowed shift types: {', '.join(req.allowed_shift_types)}",
        "",
        "Reply ONLY with a JSON object:",
        '{"word_id": "...", "shift_type": "...", "from_prime": "...", "to_prime": "...", '
        '"chain": [...], "confidence": 0.0-1.0, "reasoning": "..."}',
    ])


def _symbolic_validate(
    proposal: SemanticProposalResponse,
    known_primes: set[str],
    existing_chain: list[str],
) -> list[str]:
    """Stage 2: validate proposal against symbolic constraints."""
    errors: list[str] = []

    if proposal.shift_type not in _VALID_SHIFT_TYPES:
        errors.append(f"Invalid shift_type: {proposal.shift_type}")

    if known_primes and proposal.from_prime not in known_primes:
        errors.append(f"from_prime '{proposal.from_prime}' not in known primes")

    if len(proposal.chain) > _MAX_CHAIN_HOPS:
        errors.append(f"Chain too long: {len(proposal.chain)} > {_MAX_CHAIN_HOPS}")

    if proposal.chain:
        seen: set[str] = set()
        for node in proposal.chain:
            if node in seen:
                errors.append(f"Cycle detected in chain at '{node}'")
                break
            seen.add(node)

    return errors


def generate_and_validate_proposal(
    backend: LLMBackend,
    req: SemanticProposalRequest,
    known_primes: set[str],
    *,
    max_proposals_per_era: int = 5,
    proposal_counter: dict[int, int] | None = None,
) -> CallbackVerdict:
    """Full three-stage callback pipeline for a single proposal."""
    prompt = _build_proposal_prompt(req)
    result = backend.call(prompt, schema_hint=SEMANTIC_PROPOSAL_RESPONSE_SCHEMA)

    # Stage 1: Schema sanitization
    san: SanitizeResult = sanitize(
        result.raw_json,
        "SemanticProposalResponse",
        max_proposals_per_era=max_proposals_per_era,
        _proposal_counter=proposal_counter,
        current_era=req.era,
    )
    if not san.ok:
        logger.warning("Proposal schema rejected for era %d: %s", req.era, san.errors)
        return CallbackVerdict(status="rejected", reason="; ".join(san.errors))

    proposal = SemanticProposalResponse.from_dict(san.data)  # type: ignore[arg-type]

    # Stage 2: Symbolic validation
    sym_errors = _symbolic_validate(proposal, known_primes, req.context_chain)
    if sym_errors:
        logger.warning("Proposal symbolic rejected: %s", sym_errors)
        return CallbackVerdict(
            status="lore_only",
            proposal=proposal,
            reason="; ".join(sym_errors),
        )

    # Stage 3: Commit policy
    if proposal.confidence < 0.2:
        return CallbackVerdict(
            status="lore_only",
            proposal=proposal,
            reason=f"Low confidence: {proposal.confidence}",
        )

    return CallbackVerdict(status="accepted", proposal=proposal)
