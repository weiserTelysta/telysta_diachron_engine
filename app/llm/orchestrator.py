"""Phase 5 Orchestrator — era-boundary LLM coordination.

Called once at the end of each era in ``main.evolve()``.  Reads from
``EngineHotState.snapshot()`` and delta events; writes only through
the controlled callback pipeline (never touches phonology or the
evolution loop directly).

When ``is_llm=False`` the orchestrator is a complete no-op.
"""

from __future__ import annotations

import random
from dataclasses import asdict
from typing import Any

from app.core.logging import get_logger
from app.core.settings import GlobalSettings
from app.llm.base import LLMBackend
from app.llm.callbacks import CallbackVerdict, generate_and_validate_proposal
from app.llm.contracts import (
    EraLoreRequest,
    RagLexemeRequest,
    ReverseEtymologyRequest,
    SemanticProposalRequest,
)
from app.llm.etymology import collect_candidate_ancestors, infer_etymology
from app.llm.lore import LoreSidecar, generate_era_lore
from app.llm.rag import generate_new_word, retrieve_anchor_candidates

logger = get_logger(__name__)


class Phase5Orchestrator:
    """Coordinates all Phase 5 LLM capabilities at era boundaries."""

    def __init__(
        self,
        backend: LLMBackend,
        settings: GlobalSettings,
        lore_sidecar: LoreSidecar,
    ) -> None:
        self._backend = backend
        self._settings = settings
        self._lore = lore_sidecar
        self._proposal_counter: dict[int, int] = {}

    def on_era_end(
        self,
        era: int,
        hot_state: Any,
        active_ops: list[Any],
        delta_events: list[Any],
        typology: Any,
        *,
        known_primes: set[str] | None = None,
    ) -> dict[str, Any]:
        """Run all enabled Phase 5 capabilities for *era*.

        Returns a summary dict for logging / audit.
        """
        if not self._settings.is_llm:
            return {"era": era, "skipped": True, "reason": "is_llm=False"}

        summary: dict[str, Any] = {"era": era, "skipped": False}

        if self._settings.llm_enable_lore:
            lore_result = self._run_lore(era, hot_state, active_ops, delta_events, typology)
            summary["lore"] = lore_result

        if self._settings.llm_enable_callback:
            cb_results = self._run_proposals(era, hot_state, known_primes or set())
            summary["proposals"] = cb_results

        if self._settings.llm_enable_rag:
            rag_results = self._run_rag(era, hot_state)
            summary["rag"] = rag_results

        if self._settings.llm_enable_reverse_etymology:
            etym_results = self._run_etymology(hot_state)
            summary["etymology"] = etym_results

        return summary

    # ------------------------------------------------------------------
    # Lore
    # ------------------------------------------------------------------

    def _run_lore(
        self, era: int, hot_state: Any, active_ops: list[Any],
        delta_events: list[Any], typology: Any,
    ) -> dict[str, Any]:
        repr_changes: list[dict[str, str]] = []
        for ev in delta_events[:5]:
            if hasattr(ev, "old_ipa") and ev.old_ipa and ev.new_ipa:
                repr_changes.append({
                    "word": ev.word_id,
                    "old": ev.old_ipa,
                    "new": ev.new_ipa,
                })

        alive = [e for e in hot_state.lexicon.values() if not e.is_dead]
        dead = [e for e in hot_state.lexicon.values() if e.is_dead]

        req = EraLoreRequest(
            era=era,
            active_rules=[getattr(op, "name", str(op)) for op in active_ops],
            representative_changes=repr_changes,
            morph_type=getattr(typology, "morph_type", "unknown"),
            word_order=getattr(typology, "word_order", "unknown"),
            alive_count=len(alive),
            dead_count=len(dead),
        )

        resp = generate_era_lore(self._backend, req)
        if resp:
            self._lore.save(resp)
            logger.info("Era %d lore: %s [%s]", era, resp.narrative[:60], resp.tags)
            return {"status": "ok", "tags": resp.tags}
        return {"status": "rejected"}

    # ------------------------------------------------------------------
    # Semantic proposals
    # ------------------------------------------------------------------

    def _run_proposals(
        self, era: int, hot_state: Any, known_primes: set[str],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        rng = random.Random(self._settings.seed + era * 1000)
        alive = [e for e in hot_state.lexicon.values() if not e.is_dead]
        if not alive:
            return results

        candidates = rng.sample(alive, k=min(3, len(alive)))
        for entity in candidates:
            req = SemanticProposalRequest(
                era=era,
                word_id=entity.id,
                concept=entity.concept,
                current_primes=entity.semantic_primes,
                context_chain=[],
                allowed_shift_types=["metaphor", "metonymy", "broadening", "narrowing"],
            )
            verdict: CallbackVerdict = generate_and_validate_proposal(
                self._backend, req, known_primes,
                max_proposals_per_era=self._settings.llm_max_proposals_per_era,
                proposal_counter=self._proposal_counter,
            )
            result_entry: dict[str, Any] = {
                "word_id": entity.id,
                "status": verdict.status,
                "reason": verdict.reason,
            }

            if verdict.status == "accepted" and verdict.proposal:
                from app.domain.lexicon.models import SemanticEraEntry
                entry = SemanticEraEntry(
                    era=era,
                    proposal_type=verdict.proposal.shift_type,
                    from_prime=verdict.proposal.from_prime,
                    to_prime=verdict.proposal.to_prime,
                    chain=verdict.proposal.chain,
                    validator_status="accepted",
                    reason=verdict.proposal.reasoning,
                )
                entity.semantic_era_log.append(entry)
                if verdict.proposal.to_prime and verdict.proposal.to_prime not in entity.semantic_primes:
                    entity.semantic_primes.append(verdict.proposal.to_prime)
                logger.info(
                    "Proposal accepted: %s %s->%s via %s",
                    entity.id, verdict.proposal.from_prime,
                    verdict.proposal.to_prime, verdict.proposal.shift_type,
                )
            elif verdict.status == "lore_only" and verdict.proposal:
                from app.domain.lexicon.models import SemanticEraEntry
                entry = SemanticEraEntry(
                    era=era,
                    proposal_type=verdict.proposal.shift_type,
                    from_prime=verdict.proposal.from_prime,
                    to_prime=verdict.proposal.to_prime,
                    chain=verdict.proposal.chain,
                    validator_status="lore_only",
                    reason=verdict.reason,
                    lore_only=True,
                )
                entity.semantic_era_log.append(entry)

            results.append(result_entry)

        return results

    # ------------------------------------------------------------------
    # RAG new word
    # ------------------------------------------------------------------

    def _run_rag(self, era: int, hot_state: Any) -> dict[str, Any]:
        rng = random.Random(self._settings.seed + era * 2000)
        concepts = ["telescope", "compass", "ink", "wheel", "bridge"]
        target = rng.choice(concepts)
        target_pos = "noun"

        candidates = retrieve_anchor_candidates(
            hot_state.lexicon, hot_state.dag, target, target_pos,
        )
        if not candidates:
            return {"status": "no_candidates"}

        req = RagLexemeRequest(
            era=era,
            anchor_concept=target,
            anchor_pos=target_pos,
            candidate_roots=candidates,
        )
        resp = generate_new_word(self._backend, req)
        if resp:
            logger.info("RAG new word: %s /%s/ from %s", resp.new_concept, resp.new_ipa, resp.root_ids_used)
            return {"status": "ok", "concept": resp.new_concept, "ipa": resp.new_ipa}
        return {"status": "rejected"}

    # ------------------------------------------------------------------
    # Reverse etymology
    # ------------------------------------------------------------------

    def _run_etymology(self, hot_state: Any) -> dict[str, Any]:
        rng = random.Random(self._settings.seed + 9999)
        alive = [e for e in hot_state.lexicon.values() if not e.is_dead and e.ipa_history]
        if not alive:
            return {"status": "no_candidates"}

        target = rng.choice(alive)
        candidates = collect_candidate_ancestors(
            target.id, hot_state.lexicon, hot_state.dag,
        )
        req = ReverseEtymologyRequest(
            modern_word_id=target.id,
            modern_ipa=target.ipa_current,
            candidate_ancestors=candidates,
        )
        resp = infer_etymology(self._backend, req)
        logger.info(
            "Etymology for %s: band=%s chain=%s",
            target.id, resp.confidence_band, resp.accepted_chain,
        )
        return {
            "status": "ok",
            "word_id": target.id,
            "confidence_band": resp.confidence_band,
        }
