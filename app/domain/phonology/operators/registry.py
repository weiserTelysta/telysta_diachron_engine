from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from app.domain.phonology.operators.base import EvolutionOperator

logger = logging.getLogger(__name__)


class OperatorRegistry:
    """Registry for pluggable evolution operators.

    Operators are registered with (class, enabled flag, priority).
    The registry owns instantiated operator objects and dispatches them
    in priority order. Adding or disabling an operator never modifies the
    dispatch core.
    """

    def __init__(self) -> None:
        self._entries: list[tuple[int, bool, "EvolutionOperator"]] = []

    def register(
        self,
        operator: "EvolutionOperator",
        enabled: bool = True,
        priority: int | None = None,
    ) -> None:
        effective_priority = priority if priority is not None else operator.priority
        operator.enabled = enabled
        operator.priority = effective_priority
        self._entries.append((effective_priority, enabled, operator))
        self._entries.sort(key=lambda x: x[0])
        logger.debug("Registered operator '%s' (priority=%d, enabled=%s)", operator.name, effective_priority, enabled)

    def enable(self, name: str) -> None:
        for i, (p, _, op) in enumerate(self._entries):
            if op.name == name:
                op.enabled = True
                self._entries[i] = (p, True, op)

    def disable(self, name: str) -> None:
        for i, (p, _, op) in enumerate(self._entries):
            if op.name == name:
                op.enabled = False
                self._entries[i] = (p, False, op)

    def apply_all(self, sequence: list[str], stress_pattern: str = "") -> list[str]:
        """Apply all enabled operators in priority order."""
        current = list(sequence)
        for _, enabled, op in self._entries:
            if enabled:
                result = op.apply(current, stress_pattern)
                current = result.output
        return current

    @property
    def active_operators(self) -> list["EvolutionOperator"]:
        return [op for _, enabled, op in self._entries if enabled]

    def active_operators_for_era(self, era: int) -> list["EvolutionOperator"]:
        """Return enabled operators whose era_start <= era, in priority order."""
        return [op for _, enabled, op in self._entries
                if enabled and era >= op.era_start]

    def __repr__(self) -> str:
        names = [(op.name, p, en) for p, en, op in self._entries]
        return f"OperatorRegistry({names})"
