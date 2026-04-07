from __future__ import annotations

from app.domain.phonology.backends.base import Backend
from app.domain.phonology.operators.base import EvolutionOperator
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.phonology.rule_compiler import RuleCompiler


class MidVowelDropOperator(EvolutionOperator):
    """Word-final mid vowel deletion.

    Targets /e ɛ o ɔ/ (syllabic, non-high, non-low) in word-final position.
    Activates after era_start (default 4) — after high vowels have largely
    completed their drop, the mid vowels begin eroding.
    """

    name = "mid_vowel_drop"
    default_priority = 11

    def __init__(
        self,
        backend: Backend,
        inventory: PhonemeInventory,
        enabled: bool = True,
        priority: int | None = None,
        era_start: int = 4,
        change_rate: float = 0.9,
    ) -> None:
        compiler = RuleCompiler(inventory)
        rule = compiler.compile({
            "name": "final_mid_vowel_drop",
            "priority": 11,
            "op": "delete",
            "target": {"syllabic": True, "high": False, "low": False},  # /e ɛ o ɔ/
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

    def _apply_rules(self, sequence: list[str], stress_pattern: str = "") -> list[str]:
        result = sequence
        for rule in self.rules:
            result = self.backend.apply(rule, result)
        return result
