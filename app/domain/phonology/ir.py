from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.domain.phonology.phoneme import Phoneme


@dataclass
class SoundChangeRule:
    """Backend-agnostic intermediate representation of a sound change rule.

    This IR must not contain any regex patterns, FST structures, or
    backend-specific constructs. It encodes purely linguistic semantics:
    which phoneme class changes, to what, and in what environment.
    """

    name: str
    priority: int
    op: Literal["change", "delete", "insert"]

    target_class: list[Phoneme]
    output_map: dict[str, str]

    env_before: list[Phoneme] | None
    env_after: list[Phoneme] | None
    env_flags: dict[str, bool] = field(default_factory=dict)
    # source_symbol → target Phoneme; populated by RuleCompiler for "change" ops.
    # Allows matrix batch ops to resolve target feature bits without a full inventory scan.
    output_phonemes: dict[str, Phoneme] = field(default_factory=dict)

    @property
    def target_symbols(self) -> frozenset[str]:
        return frozenset(p.symbol for p in self.target_class)

    @property
    def env_before_symbols(self) -> frozenset[str] | None:
        if self.env_before is None:
            return None
        return frozenset(p.symbol for p in self.env_before)

    @property
    def env_after_symbols(self) -> frozenset[str] | None:
        if self.env_after is None:
            return None
        return frozenset(p.symbol for p in self.env_after)

    def __repr__(self) -> str:
        targets = [p.symbol for p in self.target_class]
        return (
            f"SoundChangeRule(name={self.name!r}, op={self.op!r}, "
            f"targets={targets}, priority={self.priority})"
        )
