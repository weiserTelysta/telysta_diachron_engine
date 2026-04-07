from __future__ import annotations

from app.domain.phonology.backends.base import Backend
from app.domain.phonology.ir import SoundChangeRule
from app.domain.phonology.operators.base import EvolutionOperator
from app.domain.phonology.phoneme import Phoneme, PhonemeInventory


class CompensatoryLengtheningOperator(EvolutionOperator):
    """Compensatory lengthening: word-final sonorant deletion + preceding vowel lengthening.

    When a word-final sonorant consonant (l, r, n, m, ŋ) is in coda position and
    the preceding phoneme is a short vowel, the consonant weakens to silence while
    its mora is transferred to the vowel, producing a long vowel.

    Example: /bol/ → /boː/   /ten/ → /teː/   /kar/ → /kaː/

    This operator runs at priority=8 (before FinalVowelDropOperator at priority=10),
    so it "saves" certain CVC words from further erosion by converting them to CV:
    rather than letting them collapse to CV after consonant loss.

    The operator only fires when:
      - The sequence ends in a sonorant consonant (sonorant=True, consonantal=True)
      - The penultimate phoneme is a short vowel (syllabic=True, long=False)
      - A long version of that vowel exists in the inventory (long=True, same other features)

    If the inventory has no long vowels, the operator is a no-op (graceful degradation).
    """

    name = "compensatory_lengthening"
    default_priority = 8

    def __init__(
        self,
        backend: Backend,
        inventory: PhonemeInventory,
        enabled: bool = True,
        priority: int | None = None,
        era_start: int = 2,
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
        self._vowel_symbols: frozenset[str] = frozenset(
            p.symbol for p in inventory.vowels
        )
        self._sonorant_consonants: frozenset[str] = frozenset(
            p.symbol for p in inventory.phonemes
            if p.matches({"sonorant": True, "consonantal": True})
        )
        self._has_long_vowels: bool = any(
            p.features.get("long") is True for p in inventory.phonemes
        )

    def _apply_rules(self, sequence: list[str], stress_pattern: str = "") -> list[str]:
        if not self._has_long_vowels:
            return sequence

        if len(sequence) < 2:
            return sequence

        final = sequence[-1]
        penultimate = sequence[-2]

        if final not in self._sonorant_consonants:
            return sequence

        if penultimate not in self._vowel_symbols:
            return sequence

        penultimate_phoneme = self.inventory.find_by_symbol(penultimate)
        if penultimate_phoneme is None:
            return sequence

        # Only lengthen short vowels (long feature must be explicitly False)
        if penultimate_phoneme.features.get("long") is not False:
            return sequence

        long_vowel = penultimate_phoneme.apply_change({"long": True}, self.inventory)
        if long_vowel is None:
            return sequence

        return list(sequence[:-2]) + [long_vowel.symbol]
