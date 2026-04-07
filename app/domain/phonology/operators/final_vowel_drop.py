from __future__ import annotations

from app.domain.phonology.backends.base import Backend
from app.domain.phonology.ir import SoundChangeRule
from app.domain.phonology.operators.base import EvolutionOperator
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.phonology.rule_compiler import RuleCompiler


class FinalVowelDropOperator(EvolutionOperator):
    """Word-final vowel deletion (unstressed final vowel erosion).

    Blocking conditions (either prevents the rule from firing):
      1. stress_pattern == "final": the final syllable is stressed → protect the vowel.
      2. Deletion would expose an illegal coda final: the consonant preceding the
         target vowel is in `illegal_coda_finals` → the vowel acts as a buffer and
         must be retained.
    """

    name = "final_vowel_drop"
    default_priority = 10

    def __init__(
        self,
        backend: Backend,
        inventory: PhonemeInventory,
        enabled: bool = True,
        priority: int | None = None,
        era_start: int = 1,
        change_rate: float = 1.0,
        illegal_coda_finals: set[str] | None = None,
    ) -> None:
        compiler = RuleCompiler(inventory)
        rule = compiler.compile({
            "name": "final_high_vowel_drop",
            "priority": 10,
            "op": "delete",
            "target": {"syllabic": True, "high": True},
            "env_before": None,
            "env_after": None,
            "env_flags": {"word_final": True},
        })
        super().__init__(
            rules=[rule],
            backend=backend,
            inventory=inventory,
            enabled=enabled,
            priority=priority,
            era_start=era_start,
            change_rate=change_rate,
        )
        self.illegal_coda_finals: set[str] = illegal_coda_finals or set()
        self._vowel_symbols: frozenset[str] = frozenset(
            p.symbol for p in inventory.vowels
        )

    def _apply_rules(self, sequence: list[str], stress_pattern: str = "") -> list[str]:
        # Blocking condition 1: final-stressed words keep their final vowel
        if stress_pattern == "final":
            return sequence

        if not sequence:
            return sequence

        # Check if rule would even apply (last symbol must be in target)
        last = sequence[-1]
        last_phoneme = self.inventory.find_by_symbol(last)
        if last_phoneme is None or not self.rules[0].target_symbols or last not in self.rules[0].target_symbols:
            # Rule does not apply to this sequence's final symbol
            result = sequence
            for rule in self.rules:
                result = self.backend.apply(rule, result)
            return result

        # Blocking condition 2: if dropping the final vowel exposes an illegal coda
        # i.e. the consonant just before it is in illegal_coda_finals
        if self.illegal_coda_finals and len(sequence) >= 2:
            penultimate = sequence[-2]
            if penultimate in self.illegal_coda_finals:
                return sequence

        # Blocking condition 3: deletion would leave the word with no vowel nucleus
        post_drop = sequence[:-1]
        has_nucleus = any(
            (ph := self.inventory.find_by_symbol(t)) is not None
            and ph.features.get("syllabic")
            for t in post_drop
        )
        if not has_nucleus:
            return sequence

        result = sequence
        for rule in self.rules:
            result = self.backend.apply(rule, result)
        return result
