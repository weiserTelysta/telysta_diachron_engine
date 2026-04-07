from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

WordOrderScheme = Literal["SOV", "SVO", "VSO", "VOS", "OVS", "OSV"]
TenseSystem = Literal["inflectional", "isolating", "tenseless"]
MorphType = Literal["isolating", "agglutinative", "fusional"]
CaseSystem = Literal["nominative_accusative", "ergative_absolutive", "none"]

_VALID_WORD_ORDERS: frozenset[str] = frozenset(
    ["SOV", "SVO", "VSO", "VOS", "OVS", "OSV"]
)


@dataclass
class TypologyMatrix:
    """Language-typological parameters that drive morphological planning.

    morpheme_table maps grammatical function labels to IPA affix strings.
    Convention: prefix entries use format "PRE:XXX" as key, suffix entries
    use plain "XXX". Affix values are bare IPA (no hyphens).

    Example::
        morpheme_table = {
            "ACC": "o",      # accusative suffix  /...o/
            "PAST": "et",    # past-tense suffix  /...et/
            "1SG": "m",      # 1st-sg agreement   /...m/
            "3SG": "s",      # 3rd-sg agreement   /...s/
            "FUT": "ga",     # future prefix      /ga.../  (keyed "PRE:FUT")
        }
    """

    word_order: WordOrderScheme = "SVO"
    tense_system: TenseSystem = "inflectional"
    morph_type: MorphType = "agglutinative"
    case_system: CaseSystem = "nominative_accusative"
    agreement_features: list[str] = field(
        default_factory=lambda: ["person", "number"]
    )
    morpheme_table: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.word_order not in _VALID_WORD_ORDERS:
            raise ValueError(f"Invalid word_order: {self.word_order!r}")

    def get_suffix(self, function: str) -> str:
        """Return the IPA suffix for a grammatical function, or '' if absent."""
        return self.morpheme_table.get(function, "")

    def get_prefix(self, function: str) -> str:
        """Return the IPA prefix for a grammatical function, or '' if absent."""
        return self.morpheme_table.get(f"PRE:{function}", "")

    def subject_order_slot(self) -> int:
        """Position index of Subject in the word-order template (0-based)."""
        return self.word_order.index("S")

    def verb_order_slot(self) -> int:
        return self.word_order.index("V")

    def object_order_slot(self) -> int:
        return self.word_order.index("O")

    def clone_with(self, **overrides: object) -> "TypologyMatrix":
        """Return a copy of this matrix with selected fields overridden."""
        import copy
        clone = copy.deepcopy(self)
        for k, v in overrides.items():
            setattr(clone, k, v)
        clone.__post_init__()
        return clone
