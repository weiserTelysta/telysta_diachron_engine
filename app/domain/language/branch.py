from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.domain.language.evolution_profile import EvolutionProfile
from app.domain.lexicon.typology_drift import TypologyDriftEngine
from app.domain.syntax.pipeline import CSGPipeline, GenerationResult
from app.domain.syntax.typology import TypologyMatrix

if TYPE_CHECKING:
    from app.domain.lexicon.grammaticalization_operator import GrammaticalizationOperator
    from app.domain.morphology.portmanteau import PortmanteauRegistry
    from app.domain.phonology.operators.registry import OperatorRegistry
    from app.domain.phonology.phoneme import PhonemeInventory
    from app.domain.storage.hot_state import EngineHotState
    from app.domain.syntax.csg import ControlledSemanticGraph
    from app.domain.syntax.semantic_graph import SemanticGraph


@dataclass
class BranchConfig:
    """Static configuration for a language branch (set once at fork time)."""

    name: str
    fork_era: int
    typology_override: TypologyMatrix | None = None
    evolution_profile: EvolutionProfile | None = None


class BranchLanguage:
    """An independent language branch forked from a parent EngineHotState.

    Each branch owns:
    - A deep copy of the hot state at fork time (never shares data with parent)
    - An independent TypologyMatrix (optionally overridden from base)
    - Access to the shared operator registry and phoneme inventory

    Typological divergence can be introduced by calling
    ``branch.typology = branch.typology.clone_with(...)``.

    Typical workflow::

        branch = BranchLanguage(config, parent_hot_state, base_typology,
                                prime_graph, registry, inventory)
        for _ in range(n_eras):
            branch.evolve_one_era(rng)
        result = branch.generate(csg)
    """

    def __init__(
        self,
        config: BranchConfig,
        initial_state: "EngineHotState",
        base_typology: TypologyMatrix,
        prime_graph: "SemanticGraph",
        registry: "OperatorRegistry",
        inventory: "PhonemeInventory",
        portmanteau_registry: "PortmanteauRegistry | None" = None,
        grammaticalization_operator: "GrammaticalizationOperator | None" = None,
    ) -> None:
        self.config = config
        self.hot_state: "EngineHotState" = initial_state.clone()
        self.typology: TypologyMatrix = (
            config.typology_override
            if config.typology_override is not None
            else copy.deepcopy(base_typology)
        )
        self._prime_graph = prime_graph
        self._registry = registry
        self._inventory = inventory
        self._portmanteau = portmanteau_registry
        self._drift_engine = TypologyDriftEngine()
        self._gram_op: "GrammaticalizationOperator | None" = grammaticalization_operator
        self._pipeline = CSGPipeline(
            prime_graph=prime_graph,
            typology=self.typology,
            registry=registry,
            inventory=inventory,
            portmanteau_registry=portmanteau_registry,
        )

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def current_era(self) -> int:
        return self.hot_state.current_era

    def evolve_one_era(
        self,
        rng: random.Random | None = None,
    ) -> int:
        """Apply one era of phonological evolution. Returns the count of changed words.

        Uses the branch's own operator registry and inventory. Each alive entity
        is subjected to active operators (era-gated) with probability
        ``effective_rate × op.change_rate``.

        No KeyframeManager or HomophoneResolver is invoked here — branches
        manage their own persistence externally if needed.
        """
        from app.domain.phonology.erosion import ErosionModel
        from app.domain.storage.event_log import DeltaEvent, DeltaEventType

        rng = rng or random.Random()
        next_era = self.hot_state.current_era + 1
        active_ops = self._registry.active_operators_for_era(next_era)
        erosion = ErosionModel()
        profile = self.config.evolution_profile
        changed_count = 0

        for entity in self.hot_state.all_alive():
            effective_rate = erosion.rate(entity.frequency_weight, entity.stress_pattern)
            # Differential Erosion: scale by position bias from EvolutionProfile
            if profile is not None and profile.erosion_position_bias:
                pos_bias = profile.erosion_position_bias.get(entity.stress_pattern, 1.0)
                effective_rate = min(effective_rate * pos_bias, 1.0)

            for op in active_ops:
                # Phonetic Drift: per-operator rate override from EvolutionProfile
                op_rate = op.change_rate
                if profile is not None and profile.operator_rate_overrides:
                    op_rate *= profile.operator_rate_overrides.get(op.name, 1.0)
                if rng.random() > effective_rate * op_rate:
                    continue
                tokens = self._inventory.tokenize(entity.ipa_current)
                result = op.apply(tokens, entity.stress_pattern)
                if result.changed:
                    new_ipa = "".join(result.output)
                    event = DeltaEvent(
                        event_type=DeltaEventType.SOUND_CHANGE,
                        era=next_era,
                        word_id=entity.id,
                        old_ipa=entity.ipa_current,
                        new_ipa=new_ipa,
                        rule_name=op.name,
                    )
                    self.hot_state.apply_delta(event)
                    changed_count += 1

        era_event = DeltaEvent(
            event_type=DeltaEventType.ERA_ADVANCE,
            era=next_era,
            word_id="",
        )
        self.hot_state.apply_delta(era_event)

        # Optional grammaticalization: runs if an operator was injected at
        # construction time.  Each alive entity is evaluated against configured
        # pathways and stasis rules; results are applied to the hot state.
        if self._gram_op is not None:
            alive = self.hot_state.all_alive()
            self._gram_op.prepare_era(alive)
            for entity in alive:
                gram_result = self._gram_op.check(
                    entity, self.hot_state, self.typology, next_era
                )
                if gram_result is not None:
                    self.typology.morpheme_table[gram_result.morpheme_key] = gram_result.new_ipa

        # Per-domain typology drift for this branch
        drift_stats = self._drift_engine.observe(self.hot_state)
        self._drift_engine.maybe_drift(
            self.typology, drift_stats, era=next_era, rng=rng,
            bias_profile=self.typology.bias_profile,
        )

        return changed_count

    def generate(self, csg: "ControlledSemanticGraph") -> GenerationResult:
        """Generate a surface-form sentence using this branch's current state."""
        return self._pipeline.generate(
            csg, self.hot_state, era=self.hot_state.current_era, typology=self.typology
        )

    def __repr__(self) -> str:
        return (
            f"BranchLanguage(name={self.config.name!r}, "
            f"era={self.current_era}, "
            f"words={len(self.hot_state)})"
        )
