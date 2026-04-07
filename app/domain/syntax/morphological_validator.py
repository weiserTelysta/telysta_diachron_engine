"""Morphological consistency validator — pre-generation structural checks.

Catches logical contradictions in a TypologyMatrix *before* the CSGPipeline
attempts generation.  Two layers:

1. **Structural Validator** — hard constraint violations that would crash
   the planner or produce gibberish (e.g. fusional state without a
   morpheme table, definiteness=1 with FeaturePresence.definiteness=False).

2. **Typological Scorer** — soft plausibility heuristics that *warn* but
   do not block generation (e.g. noun_case=2 + verb_agreement=0 is rare
   but attested in some Caucasian languages).

Usage::

    from app.domain.syntax.morphological_validator import MorphologicalConsistencyValidator
    validator = MorphologicalConsistencyValidator()
    errors, warnings = validator.validate(typology)
    if errors:
        raise ValueError(errors)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.syntax.typology import TypologyMatrix


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


class MorphologicalConsistencyValidator:
    """Validate a TypologyMatrix for internal consistency."""

    def validate(self, typ: "TypologyMatrix") -> ValidationResult:
        result = ValidationResult()
        self._check_presence_vs_state(typ, result)
        self._check_fusional_requirements(typ, result)
        self._check_definiteness_ceiling(typ, result)
        self._score_typological_plausibility(typ, result)
        return result

    def _check_presence_vs_state(self, typ: "TypologyMatrix", r: ValidationResult) -> None:
        """Feature absent in FeaturePresence but domain state > 0 is contradictory."""
        fp = typ.feature_presence
        ms = typ.morph_state
        if not fp.tense and ms.verb_tam > 0:
            r.errors.append(
                "verb_tam state > 0 but FeaturePresence.tense is False"
            )
        if not fp.agreement and ms.verb_agreement > 0:
            r.errors.append(
                "verb_agreement state > 0 but FeaturePresence.agreement is False"
            )
        if not fp.case and ms.noun_case > 0:
            r.errors.append(
                "noun_case state > 0 but FeaturePresence.case is False"
            )
        if not fp.definiteness and ms.noun_definiteness > 0:
            r.errors.append(
                "noun_definiteness state > 0 but FeaturePresence.definiteness is False"
            )

    def _check_fusional_requirements(self, typ: "TypologyMatrix", r: ValidationResult) -> None:
        """Fusional state (2) requires existing morpheme_table entries to fuse."""
        ms = typ.morph_state
        mt = typ.morpheme_table
        if ms.verb_tam == 2 and not any(
            k in mt for k in ("PAST", "FUT", "PRES", "PERF", "IMPF", "PAST+1SG")
        ):
            r.warnings.append(
                "verb_tam=2 (fusional) but morpheme_table has no TAM entries — "
                "fusion lookup will always fall back to agglutinative"
            )
        if ms.noun_case == 2 and not any(
            k in mt for k in ("NOM", "ACC", "GEN", "DAT", "LOC", "ABL")
        ):
            r.warnings.append(
                "noun_case=2 (fusional) but morpheme_table has no case entries — "
                "fusion lookup will always fall back to agglutinative"
            )

    def _check_definiteness_ceiling(self, typ: "TypologyMatrix", r: ValidationResult) -> None:
        ms = typ.morph_state
        if ms.noun_definiteness > 1:
            r.errors.append(
                f"noun_definiteness must be 0 or 1; got {ms.noun_definiteness}"
            )

    def _score_typological_plausibility(self, typ: "TypologyMatrix", r: ValidationResult) -> None:
        """Soft heuristic warnings for rare but valid cross-linguistic combinations."""
        ms = typ.morph_state
        if ms.noun_case == 2 and ms.verb_agreement == 0:
            r.warnings.append(
                "noun_case=2 + verb_agreement=0 is rare; most fusional case "
                "languages also have some verb agreement"
            )
        if ms.verb_tam == 0 and ms.verb_agreement == 2:
            r.warnings.append(
                "verb_tam=0 + verb_agreement=2 is unusual; fusional agreement "
                "typically co-occurs with at least agglutinative TAM"
            )
