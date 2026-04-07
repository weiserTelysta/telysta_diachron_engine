from __future__ import annotations

import random
from collections import defaultdict
from typing import Literal

from app.domain.lexicon.models import LexicalEntity
from app.domain.storage.event_log import DeltaEvent, DeltaEventType


MorphologicalType = Literal["agglutinative", "isolating", "fusional"]

_DEFAULT_SUFFIX_POOL = ["na", "ɾa", "li", "mu", "ta"]

# Per-era age bonus for seniority protection. A word that survived 100 eras
# gains +0.05 to its effective frequency weight, enough to outweigh a young
# low-frequency newcomer in homophone conflicts.
_SENIORITY_RATE: float = 0.0005


class HomophoneResolver:
    """Detect and resolve homophone collisions using a 5-strategy priority queue.

    Strategy selection is sensitive to morphological type (development.md §5.4):
      agglutinative → prefer affixation
      isolating     → prefer semantic_shift, then borrowing stub
      fusional      → prefer semantic_shift, then lexical_death

    Strategies:
      1. reduplication   – high-freq word form is doubled (/ta/ → /tata/)
      2. affixation      – low-freq word gets a distinguishing suffix appended
      3. semantic_shift  – low-freq word is soft-deleted (stub; Phase 3 adds fork)
      4. borrowing       – stub only; skipped when no contact language available
      5. lexical_death   – low-freq word marked is_dead as last resort
    """

    def __init__(
        self,
        suffix_pool: list[str] | None = None,
        swadesh_concepts: set[str] | None = None,
    ) -> None:
        self._suffix_pool = suffix_pool or _DEFAULT_SUFFIX_POOL
        self._swadesh_concepts: set[str] = swadesh_concepts or set()

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(
        self,
        lexicon: dict[str, LexicalEntity],
    ) -> list[tuple[LexicalEntity, LexicalEntity]]:
        """Return all pairs of alive words sharing the same ipa_current."""
        groups: dict[str, list[LexicalEntity]] = defaultdict(list)
        for entity in lexicon.values():
            if not entity.is_dead:
                groups[entity.ipa_current].append(entity)

        pairs: list[tuple[LexicalEntity, LexicalEntity]] = []
        for group in groups.values():
            if len(group) >= 2:
                # Emit every unique pair in the collision group
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        pairs.append((group[i], group[j]))
        return pairs

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(
        self,
        pair: tuple[LexicalEntity, LexicalEntity],
        era: int,
        rng: random.Random,
        morphological_type: MorphologicalType = "agglutinative",
    ) -> list[DeltaEvent]:
        """Apply the highest-priority viable strategy to the given homophone pair.

        Returns a list of DeltaEvents (may be empty if no strategy applies).
        """
        high, low = self._sort_by_frequency(pair, current_era=era)
        strategy_order = self._strategy_order(morphological_type)

        for strategy in strategy_order:
            events = self._apply_strategy(strategy, high, low, era, rng)
            if events:
                return events
        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sort_by_frequency(
        pair: tuple[LexicalEntity, LexicalEntity],
        current_era: int = 0,
    ) -> tuple[LexicalEntity, LexicalEntity]:
        """Return (higher_effective_weight, lower_effective_weight).

        effective_weight = frequency_weight + age_bonus, where age_bonus rewards
        words that have persisted many eras (seniority protection).
        """
        def _eff(e: LexicalEntity) -> float:
            return e.frequency_weight + max(0, current_era - e.era_born) * _SENIORITY_RATE

        a, b = pair
        if _eff(a) >= _eff(b):
            return a, b
        return b, a

    @staticmethod
    def _strategy_order(morphological_type: MorphologicalType) -> list[str]:
        if morphological_type == "agglutinative":
            return ["affixation", "reduplication", "semantic_shift", "borrowing", "lexical_death"]
        if morphological_type == "isolating":
            return ["semantic_shift", "borrowing", "reduplication", "affixation", "lexical_death"]
        # fusional
        return ["semantic_shift", "lexical_death", "affixation", "reduplication", "borrowing"]

    def _apply_strategy(
        self,
        strategy: str,
        high: LexicalEntity,
        low: LexicalEntity,
        era: int,
        rng: random.Random,
    ) -> list[DeltaEvent]:
        if strategy == "reduplication":
            return self._reduplication(high, era)
        if strategy == "affixation":
            return self._affixation(low, era, rng)
        if strategy == "semantic_shift":
            return self._semantic_shift(low, era, self._swadesh_concepts)
        if strategy == "borrowing":
            return []  # requires contact language; caller handles
        if strategy == "lexical_death":
            return self._lexical_death(low, era, self._swadesh_concepts)
        return []

    @staticmethod
    def _reduplication(entity: LexicalEntity, era: int) -> list[DeltaEvent]:
        new_ipa = entity.ipa_current + entity.ipa_current
        return [DeltaEvent(
            event_type=DeltaEventType.SOUND_CHANGE,
            era=era,
            word_id=entity.id,
            old_ipa=entity.ipa_current,
            new_ipa=new_ipa,
            rule_name="homophone_reduplication",
        )]

    def _affixation(
        self, entity: LexicalEntity, era: int, rng: random.Random
    ) -> list[DeltaEvent]:
        suffix = rng.choice(self._suffix_pool)
        new_ipa = entity.ipa_current + suffix
        return [DeltaEvent(
            event_type=DeltaEventType.SOUND_CHANGE,
            era=era,
            word_id=entity.id,
            old_ipa=entity.ipa_current,
            new_ipa=new_ipa,
            rule_name="homophone_affixation",
        )]

    @staticmethod
    def _semantic_shift(
        entity: LexicalEntity, era: int, swadesh_concepts: set[str]
    ) -> list[DeltaEvent]:
        if entity.concept in swadesh_concepts:
            return []
        return [DeltaEvent(
            event_type=DeltaEventType.MARK_DEAD,
            era=era,
            word_id=entity.id,
            rule_name="homophone_semantic_shift",
        )]

    @staticmethod
    def _lexical_death(
        entity: LexicalEntity, era: int, swadesh_concepts: set[str]
    ) -> list[DeltaEvent]:
        if entity.concept in swadesh_concepts:
            return []
        return [DeltaEvent(
            event_type=DeltaEventType.MARK_DEAD,
            era=era,
            word_id=entity.id,
            rule_name="homophone_lexical_death",
        )]
