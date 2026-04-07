from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.phonology.ir import SoundChangeRule


class Backend(ABC):
    """Abstract base for sound-change execution backends.

    A Backend accepts only SoundChangeRule IR objects — never raw YAML dicts,
    regex strings, or FST-specific structures. Swapping backends must not
    require any changes to the IR or YAML rule files.
    """

    @abstractmethod
    def apply(self, rule: SoundChangeRule, sequence: list[str]) -> list[str]:
        """Apply a single SoundChangeRule to an IPA symbol sequence.

        Args:
            rule: A compiled, backend-agnostic SoundChangeRule IR.
            sequence: Ordered list of IPA symbols representing a word.

        Returns:
            New symbol sequence after applying the rule.
        """
