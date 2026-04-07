from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.syntax.typology import AGGLUTINATIVE, ANALYTIC, FUSIONAL

if TYPE_CHECKING:
    from app.domain.storage.hot_state import EngineHotState
    from app.domain.syntax.typology import MorphologicalState, TypologyMatrix


# Domain names that participate in per-domain Markov drift
_TERNARY_DOMAINS: tuple[str, ...] = ("verb_tam", "verb_agreement", "noun_case")
_BINARY_DOMAINS: tuple[str, ...] = ("noun_definiteness",)


@dataclass
class DriftStats:
    """Aggregate statistics over the current alive lexicon."""

    total_alive: int
    grammaticalized_count: int
    case_marker_count: int
    word_order_locked: bool

    @property
    def gram_density(self) -> float:
        if self.total_alive == 0:
            return 0.0
        return self.grammaticalized_count / self.total_alive

    @property
    def case_density(self) -> float:
        if self.total_alive == 0:
            return 0.0
        return self.case_marker_count / self.total_alive


class TypologyDriftEngine:
    """Per-domain Markov-chain typological drift engine.

    Each morphological domain (verb_tam, verb_agreement, noun_case,
    noun_definiteness) is an independent state machine:

        0 (ANALYTIC) ⇄ 1 (AGGLUTINATIVE) → 2 (FUSIONAL) → 0

    Transition probabilities are modulated by two global "climate" factors:
    - gram_density  (from DriftStats): higher → stronger 0→1 and 1→2 pull
    - erosion_pressure (proxy: case_density drop): higher → stronger 2→0 pull

    noun_definiteness only oscillates between 0 and 1 (never reaches fusional).

    Legacy behavior: after per-domain drift, ``typology.sync_morph_type()``
    updates the backward-compat ``morph_type`` field.
    """

    def __init__(
        self,
        gram_density_threshold: float = 0.008,
        case_loss_threshold: float = 0.02,
        cooldown_eras: int = 5,
        drift_probability: float = 0.15,
    ) -> None:
        self.gram_density_threshold = gram_density_threshold
        self.case_loss_threshold = case_loss_threshold
        self.cooldown_eras = cooldown_eras
        self.drift_probability = drift_probability
        self._word_order_locked: bool = False
        self._last_drift_era: int = -999

    def observe(self, hot_state: "EngineHotState") -> DriftStats:
        """Compute DriftStats from the current alive lexicon."""
        alive = hot_state.all_alive()
        gram_count = sum(
            1 for e in alive if e.grammaticalization_stage >= 2
        )
        case_count = sum(
            1 for e in alive
            if e.grammatical_function == "case_marker" and e.grammaticalization_stage >= 2
        )
        return DriftStats(
            total_alive=len(alive),
            grammaticalized_count=gram_count,
            case_marker_count=case_count,
            word_order_locked=self._word_order_locked,
        )

    def maybe_drift(
        self,
        typology: "TypologyMatrix",
        stats: DriftStats,
        era: int = 0,
        rng: random.Random | None = None,
    ) -> "TypologyMatrix":
        """Return a (possibly updated) TypologyMatrix based on observed stats.

        Word-order lock is applied first. Then per-domain Markov transitions
        are evaluated independently, each with ``drift_probability`` gated by
        cooldown.
        """
        if not self._word_order_locked and stats.case_density < self.case_loss_threshold:
            self._word_order_locked = True

        if era - self._last_drift_era < self.cooldown_eras:
            return typology

        rng = rng or random.Random()
        ms = typology.morph_state
        changed = False

        for domain in _TERNARY_DOMAINS:
            current = getattr(ms, domain)
            next_val = self._ternary_transition(current, stats, rng)
            if next_val != current:
                setattr(ms, domain, next_val)
                changed = True

        for domain in _BINARY_DOMAINS:
            current = getattr(ms, domain)
            next_val = self._binary_transition(current, stats, rng)
            if next_val != current:
                setattr(ms, domain, next_val)
                changed = True

        if changed:
            self._last_drift_era = era
            typology.sync_morph_type()

        return typology

    def _ternary_transition(
        self, current: int, stats: DriftStats, rng: random.Random
    ) -> int:
        """Markov transition for a 3-state domain (0 ↔ 1 → 2 → 0)."""
        if rng.random() > self.drift_probability:
            return current

        gram = stats.gram_density
        if current == ANALYTIC:
            # 0 → 1: driven by grammaticalization pressure
            if gram >= self.gram_density_threshold:
                return AGGLUTINATIVE
        elif current == AGGLUTINATIVE:
            # 1 → 2: phonetic fusion (higher gram density = more co-occurrence)
            if gram >= self.gram_density_threshold * 1.5:
                return FUSIONAL
            # 1 → 0: erosion can also collapse back (lower probability)
            if stats.case_density < self.case_loss_threshold and rng.random() < 0.3:
                return ANALYTIC
        elif current == FUSIONAL:
            # 2 → 0: erosion collapses endings (entropy-irreversible bypass)
            if rng.random() < 0.4:
                return ANALYTIC
        return current

    def _binary_transition(
        self, current: int, stats: DriftStats, rng: random.Random
    ) -> int:
        """Markov transition for noun_definiteness (only 0 ↔ 1)."""
        if rng.random() > self.drift_probability:
            return current
        if current == 0 and stats.gram_density >= self.gram_density_threshold:
            return 1
        if current == 1 and stats.case_density < self.case_loss_threshold:
            return 0
        return current

    # Legacy-compatible single-step helper (used by old callers)
    def _drift_morph_type(self, typology: "TypologyMatrix") -> "TypologyMatrix":
        """Advance morph_type one step along the typological cycle."""
        cycle = {"isolating": "agglutinative", "agglutinative": "fusional"}
        next_type = cycle.get(typology.morph_type)
        if next_type is None:
            return typology
        return typology.clone_with(morph_type=next_type)

    @property
    def word_order_locked(self) -> bool:
        return self._word_order_locked
