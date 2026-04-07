from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.domain.phonology.backends.base import Backend
from app.domain.phonology.ir import SoundChangeRule
from app.domain.phonology.phoneme import PhonemeInventory


@dataclass
class OperatorResult:
    original: list[str]
    output: list[str]
    changed: bool
    operator_name: str


class EvolutionOperator(ABC):
    """Base class for pluggable phonological evolution operators.

    Each operator encapsulates a set of SoundChangeRule IRs and applies
    them to an IPA symbol sequence via a Backend. Operators must be
    stateless with respect to individual words — all mutable state lives
    in EngineHotState.
    """

    name: str = "base"
    default_priority: int = 50
    default_enabled: bool = True

    def __init__(
        self,
        rules: list[SoundChangeRule],
        backend: Backend,
        inventory: PhonemeInventory,
        enabled: bool = True,
        priority: int | None = None,
        era_start: int = 0,
        change_rate: float = 1.0,
    ) -> None:
        self.rules = rules
        self.backend = backend
        self.inventory = inventory
        self.enabled = enabled
        self.priority = priority if priority is not None else self.default_priority
        self.era_start = era_start
        self.change_rate = change_rate

    def apply(self, sequence: list[str], stress_pattern: str = "") -> OperatorResult:
        if not self.enabled:
            return OperatorResult(
                original=sequence,
                output=sequence,
                changed=False,
                operator_name=self.name,
            )
        result = self._apply_rules(sequence, stress_pattern)
        return OperatorResult(
            original=sequence,
            output=result,
            changed=result != sequence,
            operator_name=self.name,
        )

    @abstractmethod
    def _apply_rules(self, sequence: list[str], stress_pattern: str = "") -> list[str]:
        """Apply this operator's rules to the sequence and return the result."""
