from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.lexicon.pathways import GrammaticalizationPathway, MorphemeProductType

if TYPE_CHECKING:
    from app.domain.lexicon.models import LexicalEntity
    from app.domain.phonology.phoneme import PhonemeInventory
    from app.domain.storage.hot_state import EngineHotState
    from app.domain.syntax.typology import TypologyMatrix


@dataclass
class GrammaticalResult:
    """Output of one grammaticalization event on a single LexicalEntity."""

    entity_id: str
    pathway_id: str
    old_stage: int
    new_stage: int
    new_ipa: str
    new_function: str
    product_type: MorphemeProductType
    morpheme_key: str
    host_word_id: str


class GrammaticalizationOperator:
    """Applies grammaticalization logic to individual LexicalEntities.

    Two independent trigger paths:

    Path A — YAML Pathway:
        Entity concept matches a declared semantic prime in the pathways file.
        Triggers when true_freq_rank <= max_true_freq_rank AND
        erosion_stage (= len(ipa_history)) >= min_erosion_stage.
        Product type is determined by typology.morph_type.

    Path B — Stasis:
        Short high-frequency function-words blocked repeatedly by phonotactic
        guards accumulate stasis_counter. When counter >= stasis_threshold,
        force-promote to prefix/particle regardless of pathway config.

    These paths are evaluated in order; Path A takes precedence when both
    would fire simultaneously (same entity satisfies both conditions).
    """

    name: str = "grammaticalization"

    def __init__(
        self,
        pathways: list[GrammaticalizationPathway],
        inventory: "PhonemeInventory",
        stasis_threshold: int = 3,
    ) -> None:
        self._pathways = {pw.semantic_prime.upper(): pw for pw in pathways}
        self._inventory = inventory
        self.stasis_threshold = stasis_threshold

    def note_blocked(self, entity: "LexicalEntity") -> None:
        """Record a phonotactic block event for a candidate entity."""
        if self._is_stasis_candidate(entity):
            entity.stasis_counter += 1

    def note_changed(self, entity: "LexicalEntity") -> None:
        """Reset stasis counter when a phonological change succeeds."""
        entity.stasis_counter = 0

    def check(
        self,
        entity: "LexicalEntity",
        hot_state: "EngineHotState",
        typology: "TypologyMatrix",
        era: int,
        stasis_blocked: bool = False,
    ) -> GrammaticalResult | None:
        """Evaluate both paths and return a result if one fires, else None.

        Path A (YAML) is checked first. Path B (stasis) is checked second.
        Returns None if the entity is already at stage >= 3 (affix), or
        if neither path qualifies.
        """
        if entity.grammaticalization_stage >= 3 or entity.is_dead:
            return None

        if stasis_blocked:
            self.note_blocked(entity)

        alive = hot_state.all_alive()
        freq_rank = self._compute_freq_rank(entity, alive)
        erosion_stage = len(entity.ipa_history)

        pathway = self._pathways.get(entity.concept.upper())
        if pathway is not None and pathway.triggers_for(freq_rank, erosion_stage):
            return self._apply_pathway(entity, pathway, typology, alive)

        if self._is_stasis_ready(entity):
            return self._apply_stasis(entity, typology, alive)

        return None

    def _compute_freq_rank(
        self,
        entity: "LexicalEntity",
        alive: list["LexicalEntity"],
    ) -> int:
        sorted_by_freq = sorted(alive, key=lambda e: e.frequency_weight, reverse=True)
        for rank, e in enumerate(sorted_by_freq, start=1):
            if e.id == entity.id:
                return rank
        return len(alive)

    def _apply_pathway(
        self,
        entity: "LexicalEntity",
        pathway: GrammaticalizationPathway,
        typology: "TypologyMatrix",
        alive: list["LexicalEntity"],
    ) -> GrammaticalResult | None:
        product_type = pathway.product_type_for(typology.morph_type)
        host = self._pick_host(entity, alive)
        if host is None:
            return None

        new_ipa = self._reduce_ipa(entity.ipa_current, product_type)
        morpheme_key = self._morpheme_key_for(pathway.target_function, product_type)

        entity.word_class = "function"
        entity.grammaticalization_stage = 2
        entity.grammaticalized_from_id = entity.id
        entity.grammatical_function = pathway.target_function
        entity.stasis_counter = 0

        return GrammaticalResult(
            entity_id=entity.id,
            pathway_id=pathway.id,
            old_stage=0,
            new_stage=2,
            new_ipa=new_ipa,
            new_function=pathway.target_function,
            product_type=product_type,
            morpheme_key=morpheme_key,
            host_word_id=host.id,
        )

    def _apply_stasis(
        self,
        entity: "LexicalEntity",
        typology: "TypologyMatrix",
        alive: list["LexicalEntity"],
    ) -> GrammaticalResult | None:
        host = self._pick_host(entity, alive)
        if host is None:
            return None

        product_type: MorphemeProductType = (
            "free_particle" if typology.morph_type == "isolating" else "prefix"
        )
        new_ipa = self._reduce_ipa(entity.ipa_current, product_type)
        function = self._infer_function(entity)
        morpheme_key = self._morpheme_key_for(function, product_type)

        entity.word_class = "function"
        entity.grammaticalization_stage = 4
        entity.grammaticalized_from_id = entity.id
        entity.grammatical_function = function
        entity.stasis_counter = 0

        return GrammaticalResult(
            entity_id=entity.id,
            pathway_id="stasis_promotion",
            old_stage=0,
            new_stage=4,
            new_ipa=new_ipa,
            new_function=function,
            product_type=product_type,
            morpheme_key=morpheme_key,
            host_word_id=host.id,
        )

    def _is_stasis_candidate(self, entity: "LexicalEntity") -> bool:
        return (
            entity.word_class == "function"
            and entity.frequency_weight >= 0.04
            and entity.grammaticalization_stage < 3
            and self._syllable_count(entity.ipa_current) <= 1
            and self._is_nucleus_block_profile(entity.ipa_current)
        )

    def _is_stasis_ready(self, entity: "LexicalEntity") -> bool:
        return self._is_stasis_candidate(entity) and entity.stasis_counter >= self.stasis_threshold

    def _pick_host(
        self,
        entity: "LexicalEntity",
        alive: list["LexicalEntity"],
    ) -> "LexicalEntity | None":
        preferred = [e for e in alive if e.pos.startswith("verb") and e.id != entity.id and not e.is_dead]
        pool = preferred or [e for e in alive if e.id != entity.id and not e.is_dead]
        return pool[0] if pool else None

    def _reduce_ipa(self, ipa: str, product_type: MorphemeProductType) -> str:
        tokens = self._inventory.tokenize(ipa)
        if product_type in ("prefix", "free_particle"):
            reduced = tokens[:-1]
            return "".join(reduced) if reduced else ipa
        return ipa

    def _infer_function(self, entity: "LexicalEntity") -> str:
        concept = entity.concept.lower()
        if concept in ("i", "we"):
            return "agreement"
        if concept in ("you",):
            return "agreement"
        return "clitic"

    def _morpheme_key_for(self, function: str, product_type: MorphemeProductType) -> str:
        mapping: dict[str, str] = {
            "agreement": "1SG",
            "tense_marker": "PAST",
            "aspect_marker": "PERF",
            "case_marker": "ACC",
            "locative": "LOC",
            "subordinator": "COMP",
            "clitic": "CLI",
        }
        return mapping.get(function, function.upper())

    def _syllable_count(self, ipa: str) -> int:
        count = 0
        for token in self._inventory.tokenize(ipa):
            phoneme = self._inventory.find_by_symbol(token)
            if phoneme is not None and phoneme.matches({"syllabic": True}):
                count += 1
        return count

    def _is_nucleus_block_profile(self, ipa: str) -> bool:
        tokens = self._inventory.tokenize(ipa)
        if not tokens:
            return False
        last = self._inventory.find_by_symbol(tokens[-1])
        if last is None or not last.matches({"syllabic": True, "high": True}):
            return False
        for token in tokens[:-1]:
            phoneme = self._inventory.find_by_symbol(token)
            if phoneme is not None and phoneme.matches({"syllabic": True}):
                return False
        return True
