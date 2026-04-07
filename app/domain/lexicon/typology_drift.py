from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.storage.hot_state import EngineHotState
    from app.domain.syntax.typology import TypologyMatrix


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
    """Monitors lexicon-level statistics and triggers typological shifts.

    Two drift triggers:

    1. Morphological type drift (isolating → agglutinative):
       When grammaticalized-word density exceeds gram_density_threshold,
       the language starts developing regular affixes (morph_type shifts).

    2. Word-order locking (case-loss → rigid syntax):
       When case-marker density drops below case_loss_threshold, the word
       order becomes fixed and further drift of word_order is suppressed.

    Each call to :meth:`maybe_drift` returns either the unchanged typology
    or a new TypologyMatrix instance (via clone_with). The engine is
    stateless between calls except for ``word_order_locked``.
    """

    def __init__(
        self,
        gram_density_threshold: float = 0.15,
        case_loss_threshold: float = 0.02,
    ) -> None:
        self.gram_density_threshold = gram_density_threshold
        self.case_loss_threshold = case_loss_threshold
        self._word_order_locked: bool = False

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
    ) -> "TypologyMatrix":
        """Return a (possibly updated) TypologyMatrix based on observed stats.

        Word-order lock is applied first: once locked, word_order never drifts.
        Morphological type drift may still occur after locking.
        """
        updated = typology

        if not self._word_order_locked and stats.case_density < self.case_loss_threshold:
            self._word_order_locked = True

        if stats.gram_density >= self.gram_density_threshold:
            updated = self._drift_morph_type(updated)

        return updated

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
