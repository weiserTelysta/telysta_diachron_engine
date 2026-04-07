from __future__ import annotations

from app.domain.phonology.backends.base import Backend
from app.domain.phonology.operators.base import EvolutionOperator
from app.domain.phonology.phoneme import PhonemeInventory


class CodaClusterAssimilationOperator(EvolutionOperator):
    """Regressive voicing assimilation in obstruent clusters.

    When two obstruents are adjacent (CC), the first assimilates the voicing
    of the second: /bt/ → /pt/, /dp/ → /tp/.
    Sonorants (nasals, liquids, glides) are transparent and never trigger
    or undergo this assimilation.

    Activates at era_start=5, after mid_vowel_drop (era 4) has had time to
    produce new consonant clusters through vowel elision.
    """

    name = "coda_cluster_assimilation"
    default_priority = 25

    def __init__(
        self,
        backend: Backend,
        inventory: PhonemeInventory,
        enabled: bool = True,
        priority: int | None = None,
        era_start: int = 5,
        change_rate: float = 1.0,
    ) -> None:
        super().__init__(
            rules=[],
            backend=backend,
            inventory=inventory,
            enabled=enabled,
            priority=priority,
            era_start=era_start,
            change_rate=change_rate,
        )

    def _apply_rules(self, sequence: list[str], stress_pattern: str = "") -> list[str]:
        if len(sequence) < 2:
            return sequence

        result = list(sequence)
        for i in range(len(result) - 1):
            c1_sym = result[i]
            c2_sym = result[i + 1]
            c1 = self.inventory.find_by_symbol(c1_sym)
            c2 = self.inventory.find_by_symbol(c2_sym)

            if c1 is None or c2 is None:
                continue
            if not self._is_obstruent(c1) or not self._is_obstruent(c2):
                continue

            c1_voiced = c1.features.get("voiced", False)
            c2_voiced = c2.features.get("voiced", False)
            if c1_voiced == c2_voiced:
                continue

            new_features = {**c1.features, "voiced": c2_voiced}
            target = self.inventory.find_by_features(new_features)
            if target is not None:
                result[i] = target.symbol

        return result

    @staticmethod
    def _is_obstruent(phoneme) -> bool:
        return (
            phoneme.features.get("consonantal", False)
            and not phoneme.features.get("sonorant", False)
            and not phoneme.features.get("syllabic", False)
        )
