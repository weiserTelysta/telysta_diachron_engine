"""Reverse etymology engine.

Given a modern-era word, attempts to reconstruct its ancestral
derivation chain by consulting the DAG, IPA history, and LLM
reasoning.  If no confident chain can be established, returns
``etymology_unknown`` rather than fabricating a path.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.llm.base import LLMBackend
from app.llm.contracts import ReverseEtymologyRequest, ReverseEtymologyResponse
from app.llm.sanitizer import SanitizeResult, sanitize
from app.llm.schema import REVERSE_ETYMOLOGY_RESPONSE_SCHEMA

logger = get_logger(__name__)

_DEFAULT_TOLERANCE = 3.0


def _build_etymology_prompt(req: ReverseEtymologyRequest) -> str:
    ancestors_desc = "\n".join(
        f"  - {a.get('id', '?')}: /{a.get('ipa', '?')}/ ({a.get('concept', '?')})"
        for a in req.candidate_ancestors[:10]
    )
    return "\n".join([
        "You are a historical linguist. For the given modern word, determine the "
        "most likely ancestral derivation chain from the candidates below.",
        "",
        f"Modern word: {req.modern_word_id} /{req.modern_ipa}/",
        f"Max tolerance distance: {req.max_tolerance_distance}",
        f"Candidate ancestors:\n{ancestors_desc}",
        "",
        "If no confident chain exists, set confidence_band to 'unknown'.",
        "",
        "Reply ONLY with a JSON object:",
        '{"modern_word_id": "...", "accepted_chain": [...], "rejected_candidates": [...], '
        '"confidence_band": "high|medium|low|unknown", "reasoning": "..."}',
    ])


def collect_candidate_ancestors(
    word_id: str,
    lexicon: dict[str, Any],
    dag: Any,
    *,
    max_candidates: int = 10,
) -> list[dict[str, str]]:
    """Gather candidate ancestor words from DAG ancestry and IPA similarity."""
    candidates: list[dict[str, str]] = []

    # DAG-based ancestors
    ancestors: set[str] = set()
    if hasattr(dag, "ancestors"):
        ancestors = dag.ancestors(word_id)
    for aid in list(ancestors)[:max_candidates]:
        entity = lexicon.get(aid)
        if entity is None:
            continue
        candidates.append({
            "id": aid,
            "ipa": entity.ipa_current,
            "concept": entity.concept,
        })

    if len(candidates) < max_candidates:
        target = lexicon.get(word_id)
        if target and target.ipa_history:
            for hist_ipa in target.ipa_history[:5]:
                for wid, e in lexicon.items():
                    if wid == word_id or wid in ancestors:
                        continue
                    if e.ipa_current == hist_ipa or hist_ipa in e.ipa_history:
                        candidates.append({
                            "id": wid,
                            "ipa": e.ipa_current,
                            "concept": e.concept,
                        })
                    if len(candidates) >= max_candidates:
                        break

    return candidates[:max_candidates]


def infer_etymology(
    backend: LLMBackend,
    req: ReverseEtymologyRequest,
) -> ReverseEtymologyResponse:
    """Call LLM for reverse etymology, with fallback to ``etymology_unknown``."""
    if not req.candidate_ancestors:
        return ReverseEtymologyResponse(
            modern_word_id=req.modern_word_id,
            confidence_band="unknown",
            reasoning="No candidate ancestors available.",
        )

    prompt = _build_etymology_prompt(req)
    result = backend.call(prompt, schema_hint=REVERSE_ETYMOLOGY_RESPONSE_SCHEMA)

    san: SanitizeResult = sanitize(result.raw_json, "ReverseEtymologyResponse")
    if not san.ok:
        logger.warning("Etymology sanitize failed: %s", san.errors)
        return ReverseEtymologyResponse(
            modern_word_id=req.modern_word_id,
            confidence_band="unknown",
            reasoning=f"Sanitizer rejection: {'; '.join(san.errors)}",
        )

    resp = ReverseEtymologyResponse.from_dict(san.data)  # type: ignore[arg-type]

    if resp.confidence_band == "unknown" or not resp.accepted_chain:
        resp.confidence_band = "unknown"
        logger.info("Etymology for %s: unknown — no confident chain", req.modern_word_id)

    return resp
