"""Structured RAG anchor retrieval and new-word inference.

Phase 5 v1 uses structural retrieval over ``EngineHotState.lexicon``
and ``WordDAG`` — no vector database required.  Candidates are
ranked by concept proximity, POS match, phonological similarity
and ancestry relationships.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.llm.base import LLMBackend
from app.llm.contracts import RagLexemeRequest, RagLexemeResponse
from app.llm.sanitizer import SanitizeResult, sanitize
from app.llm.schema import RAG_LEXEME_RESPONSE_SCHEMA

logger = get_logger(__name__)


def _build_rag_prompt(req: RagLexemeRequest) -> str:
    roots_desc = "\n".join(
        f"  - {r.get('id', '?')}: /{r.get('ipa', '?')}/ ({r.get('concept', '?')})"
        for r in req.candidate_roots[:10]
    )
    return "\n".join([
        "You are a conlang lexicographer. Propose ONE new word by combining existing roots.",
        "",
        f"Era: {req.era}",
        f"Target concept: {req.anchor_concept} ({req.anchor_pos})",
        f"Candidate roots:\n{roots_desc}",
        "",
        "Reply ONLY with a JSON object:",
        '{"new_concept": "...", "new_ipa": "...", "root_ids_used": [...], '
        '"morpheme_breakdown": "...", "confidence": 0.0-1.0, "reasoning": "..."}',
    ])


def retrieve_anchor_candidates(
    lexicon: dict[str, Any],
    dag: Any,
    target_concept: str,
    target_pos: str,
    *,
    max_candidates: int = 10,
) -> list[dict[str, str]]:
    """Structure-based retrieval: select candidate roots from lexicon and DAG."""
    candidates: list[tuple[float, dict[str, str]]] = []

    for wid, entity in lexicon.items():
        if entity.is_dead:
            continue
        score = 0.0
        if entity.pos == target_pos:
            score += 0.3
        if entity.word_class == "content":
            score += 0.2
        score += entity.frequency_weight * 2.0
        ancestors = dag.ancestors(wid) if hasattr(dag, "ancestors") else set()
        if ancestors:
            score += 0.1 * min(len(ancestors), 3)

        candidates.append((score, {
            "id": wid,
            "ipa": entity.ipa_current,
            "concept": entity.concept,
            "pos": entity.pos,
        }))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [c[1] for c in candidates[:max_candidates]]


def generate_new_word(
    backend: LLMBackend,
    req: RagLexemeRequest,
) -> RagLexemeResponse | None:
    """Call LLM to propose a new compound/derived word from anchor roots."""
    prompt = _build_rag_prompt(req)
    result = backend.call(prompt, schema_hint=RAG_LEXEME_RESPONSE_SCHEMA)

    san: SanitizeResult = sanitize(result.raw_json, "RagLexemeResponse")
    if not san.ok:
        logger.warning("RAG sanitize failed: %s", san.errors)
        return None

    return RagLexemeResponse.from_dict(san.data)  # type: ignore[arg-type]
