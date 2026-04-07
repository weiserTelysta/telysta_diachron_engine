from __future__ import annotations

from dataclasses import dataclass

from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory


@dataclass(frozen=True)
class GrammaticalizationResult:
    host_word_id: str
    edge_type: str
    new_ipa: str
    grammaticalization_stage: int
    morpheme_type: str
    grammatical_function: str


class StasisDrivenCliticManager:
    """Promote repeatedly blocked high-frequency short function words into clitics."""

    def __init__(
        self,
        inventory: PhonemeInventory,
        stasis_threshold: int = 3,
        max_syllables: int = 1,
        min_frequency_weight: float = 0.04,
    ) -> None:
        self.inventory = inventory
        self.stasis_threshold = stasis_threshold
        self.max_syllables = max_syllables
        self.min_frequency_weight = min_frequency_weight

    def note_blocked_attempt(self, entity: LexicalEntity) -> None:
        if self.is_candidate(entity):
            entity.stasis_counter += 1

    def note_change(self, entity: LexicalEntity) -> None:
        entity.stasis_counter = 0

    def maybe_promote(
        self,
        entity: LexicalEntity,
        host_candidates: list[LexicalEntity],
    ) -> GrammaticalizationResult | None:
        if not self.is_ready(entity):
            return None

        host = self._pick_host(entity, host_candidates)
        if host is None:
            return None

        entity.grammaticalization_stage = 3
        entity.grammaticalized_from_id = entity.id
        entity.grammatical_function = self._infer_function(entity)
        entity.morpheme_type = "clitic"
        entity.stasis_counter = 0
        new_ipa = self._reduce_to_prefix(entity.ipa_current)
        return GrammaticalizationResult(
            host_word_id=host.id,
            edge_type="compound",
            new_ipa=new_ipa,
            grammaticalization_stage=4,
            morpheme_type="prefix",
            grammatical_function=entity.grammatical_function,
        )

    def is_candidate(self, entity: LexicalEntity) -> bool:
        return (
            entity.word_class == "function"
            and entity.frequency_weight >= self.min_frequency_weight
            and entity.grammaticalization_stage < 3
            and self._syllable_count(entity.ipa_current) <= self.max_syllables
            and self._is_nucleus_block_profile(entity.ipa_current)
        )

    def is_ready(self, entity: LexicalEntity) -> bool:
        return self.is_candidate(entity) and entity.stasis_counter >= self.stasis_threshold

    def _pick_host(
        self,
        entity: LexicalEntity,
        host_candidates: list[LexicalEntity],
    ) -> LexicalEntity | None:
        preferred = [host for host in host_candidates if host.pos.startswith("verb")]
        pool = preferred or host_candidates
        for host in pool:
            if host.id != entity.id and not host.is_dead:
                return host
        return None

    def _infer_function(self, entity: LexicalEntity) -> str:
        concept = entity.concept.lower()
        if concept == "i":
            return "agreement"
        if concept == "you":
            return "agreement"
        return "clitic"

    def _syllable_count(self, ipa: str) -> int:
        count = 0
        for token in self.inventory.tokenize(ipa):
            phoneme = self.inventory.find_by_symbol(token)
            if phoneme is not None and phoneme.matches({"syllabic": True}):
                count += 1
        return count

    def _is_nucleus_block_profile(self, ipa: str) -> bool:
        tokens = self.inventory.tokenize(ipa)
        if not tokens:
            return False

        last = self.inventory.find_by_symbol(tokens[-1])
        if last is None or not last.matches({"syllabic": True, "high": True}):
            return False

        for token in tokens[:-1]:
            phoneme = self.inventory.find_by_symbol(token)
            if phoneme is not None and phoneme.matches({"syllabic": True}):
                return False
        return True

    def _reduce_to_prefix(self, ipa: str) -> str:
        tokens = self.inventory.tokenize(ipa)
        reduced = tokens[:-1]
        return "".join(reduced) if reduced else ipa
