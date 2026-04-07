from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.domain.syntax.csg import CSGValidator, ControlledSemanticGraph
from app.domain.syntax.feature_blackboard import FeatureBlackboard
from app.domain.syntax.generation_tree import GenerationTree
from app.domain.syntax.lexicalization import LexicalizationLayer
from app.domain.syntax.morphological_planner import MorphologicalPlanner
from app.domain.syntax.morphological_validator import MorphologicalConsistencyValidator
from app.domain.syntax.surface_phonology import SurfacePhonologyApplier
from app.domain.syntax.typology import TypologyMatrix

if TYPE_CHECKING:
    from app.domain.morphology.portmanteau import PortmanteauRegistry
    from app.domain.phonology.operators.registry import OperatorRegistry
    from app.domain.phonology.phoneme import PhonemeInventory
    from app.domain.storage.hot_state import EngineHotState
    from app.domain.syntax.semantic_graph import SemanticGraph


@dataclass
class GenerationResult:
    """Output of one CSG → surface-form generation pass."""

    era: int
    tokens: list[str]
    sentence: str
    lexmap_used: dict[str, str | None] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"[Era {self.era}] {self.sentence}"


class CSGPipeline:
    """Five-step CSG → surface IPA generation pipeline.

    Steps:
        ① Validate CSG (structure + cycle check + prime membership)
        ② Lexicalize (prime_id → alive LexicalEntity in Hot State)
        ③ Morphological planning (case/tense/agreement affixes)
        ④ GenerationTree linearization (word order from TypologyMatrix)
        ⑤ Surface phonology (re-apply registered operators to output tokens)

    The instance's default typology and operator registry are used by
    :meth:`generate` unless the caller passes overrides.  This makes it
    straightforward to run :meth:`compare_eras` with per-era typologies
    that reflect typological drift.
    """

    def __init__(
        self,
        prime_graph: "SemanticGraph",
        typology: TypologyMatrix,
        registry: "OperatorRegistry",
        inventory: "PhonemeInventory",
        portmanteau_registry: "PortmanteauRegistry | None" = None,
    ) -> None:
        self._prime_graph = prime_graph
        self._default_typology = typology
        self._validator = CSGValidator(prime_graph)
        self._morph_validator = MorphologicalConsistencyValidator()
        self._lex_layer = LexicalizationLayer(prime_graph)
        self._surface = SurfacePhonologyApplier(registry, inventory)
        self._portmanteau = portmanteau_registry

    def generate(
        self,
        csg: ControlledSemanticGraph,
        hot_state: "EngineHotState",
        era: int = 0,
        typology: TypologyMatrix | None = None,
    ) -> GenerationResult:
        """Run the full five-step pipeline for a single era / typology."""
        typ = typology if typology is not None else self._default_typology

        # ① Validate CSG structure
        errors = self._validator.validate(csg)
        warnings = [f"CSG: {e}" for e in errors]

        # ①b Validate morphological consistency
        morph_check = self._morph_validator.validate(typ)
        if morph_check.errors:
            warnings.extend(f"MORPH_ERROR: {e}" for e in morph_check.errors)
        warnings.extend(f"MORPH_WARN: {w}" for w in morph_check.warnings)

        # ② Lexicalize
        lexmap = self._lex_layer.lexicalize(hot_state)
        lexmap_used: dict[str, str | None] = {
            k: (v.ipa_current if v else None) for k, v in lexmap.items()
        }

        # ③ Morphological planning
        planner = MorphologicalPlanner(typ, portmanteau_registry=self._portmanteau)
        board = FeatureBlackboard()
        planned = planner.plan(csg, lexmap, board)

        # ④ Generation tree + linearization
        tree = GenerationTree.from_planned(typ, planned)
        tokens = tree.linearize()

        # ⑤ Surface phonology
        tokens = self._surface.apply(tokens)

        return GenerationResult(
            era=era,
            tokens=tokens,
            sentence=" ".join(tokens),
            lexmap_used=lexmap_used,
            warnings=warnings,
        )

    def compare_eras(
        self,
        csg: ControlledSemanticGraph,
        era_snapshots: dict[int, tuple["EngineHotState", TypologyMatrix]],
    ) -> list[GenerationResult]:
        """Generate the same CSG for multiple eras with per-era typologies.

        Returns results sorted by era (ascending). This enables cross-era
        comparison: same semantic content, different surface realizations
        reflecting phonological evolution and typological drift.
        """
        results: list[GenerationResult] = []
        for era in sorted(era_snapshots):
            hot_state, typ = era_snapshots[era]
            result = self.generate(csg, hot_state, era=era, typology=typ)
            results.append(result)
        return results
