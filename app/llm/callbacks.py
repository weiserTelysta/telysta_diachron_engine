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

from app.core.event_bus import get_event_bus
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

    # Stage 1: Schema sanitization — structural error → hard reject
    san: SanitizeResult = sanitize(
        result.raw_json,
        "SemanticProposalResponse",
        max_proposals_per_era=max_proposals_per_era,
        _proposal_counter=proposal_counter,
        current_era=req.era,
    )
    if not san.ok:
        reason = "; ".join(san.errors)
        logger.warning("Proposal rejected (era=%d, stage=schema): %s", req.era, reason)
        get_event_bus().emit(
            "llm", "PROPOSAL_REJ",
            era=req.era, word_id=req.word_id, stage="schema", reason=reason[:80],
        )
        return CallbackVerdict(status="rejected", reason=reason)

    try:
        proposal = SemanticProposalResponse.from_dict(san.data)  # type: ignore[arg-type]
    except KeyError as exc:
        logger.error("Proposal contract deserialization failed: %s", exc)
        return CallbackVerdict(status="rejected", reason=f"Deserialization error: {exc}")

    # Stage 2: Symbolic validation — domain mismatch → lore_only (not commit)
    sym_errors = _symbolic_validate(proposal, known_primes, req.context_chain)
    if sym_errors:
        reason = "; ".join(sym_errors)
        logger.warning("Proposal lore_only (era=%d, stage=symbolic): %s", req.era, reason)
        get_event_bus().emit(
            "llm", "PROPOSAL_LORE",
            era=req.era, word_id=req.word_id, stage="symbolic", reason=reason[:80],
        )
        return CallbackVerdict(status="lore_only", proposal=proposal, reason=reason)

    # Stage 3: Commit policy — low-confidence proposals are lore-only
    if proposal.confidence < 0.2:
        reason = f"Low confidence: {proposal.confidence:.2f}"
        logger.info("Proposal lore_only (era=%d, stage=commit): %s", req.era, reason)
        get_event_bus().emit(
            "llm", "PROPOSAL_LORE",
            era=req.era, word_id=req.word_id, stage="commit", reason=reason,
        )
        return CallbackVerdict(status="lore_only", proposal=proposal, reason=reason)

    logger.info(
        "Proposal accepted (era=%d): %s %s→%s conf=%.2f",
        req.era, proposal.word_id, proposal.from_prime,
        proposal.to_prime, proposal.confidence,
    )
    get_event_bus().emit(
        "llm", "PROPOSAL_ACC",
        era=req.era, word_id=proposal.word_id,
        from_prime=proposal.from_prime, to_prime=proposal.to_prime,
        conf=f"{proposal.confidence:.2f}",
    )
    return CallbackVerdict(status="accepted", proposal=proposal)
