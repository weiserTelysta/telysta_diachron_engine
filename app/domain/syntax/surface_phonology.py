from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.phonology.operators.registry import OperatorRegistry
    from app.domain.phonology.phoneme import PhonemeInventory


class SurfacePhonologyApplier:
    """Apply registered phonological operators to each token in a generated sequence.

    This is the fifth step of the CSG generation pipeline. After morphological
    planning and linearization, the concatenated surface forms may still be
    subject to synchronic or diachronic alternations (e.g., final-vowel drop
    applies across morpheme boundaries).

    Tokenization uses ``PhonemeInventory.tokenize()`` (greedy longest-match)
    so multi-character IPA digraphs are handled correctly before operator
    dispatch. Tokens unrecognized by the inventory pass through unchanged.
    """

    def __init__(
        self,
        registry: "OperatorRegistry",
        inventory: "PhonemeInventory",
    ) -> None:
        self._registry = registry
        self._inventory = inventory

    def apply(
        self,
        tokens: list[str],
        stress_pattern: str = "",
    ) -> list[str]:
        """Return a new list of surface IPA tokens after operator application.

        Each token is tokenized independently. Empty tokens are preserved as-is
        to keep positional alignment with the caller.
        """
        result: list[str] = []
        for token in tokens:
            if not token:
                result.append(token)
                continue
            phoneme_seq = self._inventory.tokenize(token)
            evolved = self._registry.apply_all(phoneme_seq, stress_pattern)
            result.append("".join(evolved))
        return result
