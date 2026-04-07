from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

WordOrderScheme = Literal["SOV", "SVO", "VSO", "VOS", "OVS", "OSV"]
TenseSystem = Literal["inflectional", "isolating", "tenseless"]
MorphType = Literal["isolating", "agglutinative", "fusional"]
CaseSystem = Literal["nominative_accusative", "ergative_absolutive", "none"]

_VALID_WORD_ORDERS: frozenset[str] = frozenset(
    ["SOV", "SVO", "VSO", "VOS", "OVS", "OSV"]
)

# Coupling depth constants — used by MorphologicalState fields
ANALYTIC: int = 0
AGGLUTINATIVE: int = 1
FUSIONAL: int = 2


@dataclass
class MorphologicalState:
    """Per-domain morphological coupling depth.

    Each field represents how deeply grammatical information is fused into
    the word-form for that particular grammatical domain.

    Values:
        0 (ANALYTIC)       — information carried by free words / word order
        1 (AGGLUTINATIVE)  — transparent affixes, one marker = one meaning
        2 (FUSIONAL)       — opaque portmanteau, one marker = multiple meanings

    Different domains may evolve at different speeds.  E.g. English:
        verb_tam=1 (walk-ed), noun_case=0 (prepositions), verb_agreement=1 (-s)
    but pronouns retain fusional case (I/me/my → effectively state 2).
    """

    verb_tam: int = 0
    verb_agreement: int = 0
    noun_case: int = 0
    noun_definiteness: int = 0  # 0 or 1 only (definiteness rarely reaches fusional)

    def __post_init__(self) -> None:
        for fname in ("verb_tam", "verb_agreement", "noun_case"):
            val = getattr(self, fname)
            if val not in (0, 1, 2):
                raise ValueError(f"{fname} must be 0, 1, or 2; got {val}")
        if self.noun_definiteness not in (0, 1):
            raise ValueError(f"noun_definiteness must be 0 or 1; got {self.noun_definiteness}")

    @property
    def active_domains(self) -> list[str]:
        """Return domain names with state > 0 (synthetic realization)."""
        result: list[str] = []
        for fname in ("verb_tam", "verb_agreement", "noun_case", "noun_definiteness"):
            if getattr(self, fname) > 0:
                result.append(fname)
        return result

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, int]) -> "MorphologicalState":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class FeaturePresence:
    """Which grammatical categories exist in this language at all.

    False = category absent (planner skips entirely — the language has no
            concept of this distinction, like Mandarin has no case).
    True  = category active (realization method depends on MorphologicalState).

    This separates "the language has no case system" from "the language has
    case but expresses it analytically (word order / adpositions)".
    """

    tense: bool = True
    aspect: bool = True
    case: bool = True
    agreement: bool = True
    definiteness: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, bool]) -> "FeaturePresence":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


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

    # --- Phase 7: per-domain morphological state ---
    morph_state: MorphologicalState = field(default_factory=MorphologicalState)
    feature_presence: FeaturePresence = field(default_factory=FeaturePresence)

    def __post_init__(self) -> None:
        if self.word_order not in _VALID_WORD_ORDERS:
            raise ValueError(f"Invalid word_order: {self.word_order!r}")

    @property
    def derived_morph_type(self) -> MorphType:
        """Derive a summary label from per-domain states for UI/logging.

        This is the *output* of the morphological state, not an input.
        Legacy ``morph_type`` field is kept for backward compatibility but
        should eventually be replaced by this property everywhere.
        """
        states = [
            self.morph_state.verb_tam,
            self.morph_state.verb_agreement,
            self.morph_state.noun_case,
        ]
        avg = sum(states) / len(states) if states else 0
        if avg >= 1.5:
            return "fusional"
        if avg >= 0.5:
            return "agglutinative"
        return "isolating"

    def sync_morph_type(self) -> None:
        """Update legacy ``morph_type`` from per-domain states.

        Call after any morph_state mutation to keep backward-compat fields
        in sync until all consumers migrate to ``morph_state`` directly.
        """
        self.morph_type = self.derived_morph_type

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

    def to_dict(self) -> dict:
        """Full serializable representation including morph_state and presence."""
        return {
            "word_order": self.word_order,
            "tense_system": self.tense_system,
            "morph_type": self.morph_type,
            "case_system": self.case_system,
            "agreement_features": list(self.agreement_features),
            "morpheme_table": dict(self.morpheme_table),
            "morph_state": self.morph_state.to_dict(),
            "feature_presence": self.feature_presence.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TypologyMatrix":
        ms = d.pop("morph_state", {})
        fp = d.pop("feature_presence", {})
        af = d.pop("agreement_features", ["person", "number"])
        mt = d.pop("morpheme_table", {})
        return cls(
            word_order=d.get("word_order", "SVO"),
            tense_system=d.get("tense_system", "inflectional"),
            morph_type=d.get("morph_type", "agglutinative"),
            case_system=d.get("case_system", "nominative_accusative"),
            agreement_features=af,
            morpheme_table=mt,
            morph_state=MorphologicalState.from_dict(ms) if ms else MorphologicalState(),
            feature_presence=FeaturePresence.from_dict(fp) if fp else FeaturePresence(),
        )
