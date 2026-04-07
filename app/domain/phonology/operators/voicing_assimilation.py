from __future__ import annotations

from app.domain.phonology.backends.base import Backend
from app.domain.phonology.ir import SoundChangeRule
from app.domain.phonology.operators.base import EvolutionOperator
from app.domain.phonology.phoneme import PhonemeInventory
from app.domain.phonology.rule_compiler import RuleCompiler


class VoicingAssimilationOperator(EvolutionOperator):
    """Intervocalic voicing: voiceless stops → voiced between vowels (V_V)."""

    name = "voicing_assimilation"
    default_priority = 20

    def __init__(
        self,
        backend: Backend,
        inventory: PhonemeInventory,
        enabled: bool = True,
        priority: int | None = None,
    ) -> None:
        compiler = RuleCompiler(inventory)
        rule = compiler.compile({
            "name": "intervocalic_voicing",
            "priority": 20,
            "op": "change",
            "target": {"voiced": False, "consonantal": True, "continuant": False},
            "change": {"voiced": True},
            "env_before": {"syllabic": True},
            "env_after": {"syllabic": True},
            "env_flags": {"word_initial": False, "word_final": False},
        })
        super().__init__(
            rules=[rule],
            backend=backend,
            inventory=inventory,
            enabled=enabled,
            priority=priority,
        )

    def _apply_rules(self, sequence: list[str], stress_pattern: str = "") -> list[str]:
        result = sequence
        for rule in self.rules:
            result = self.backend.apply(rule, result)
        return result
