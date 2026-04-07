from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.domain.syntax.pipeline import CSGPipeline, GenerationResult
from app.domain.syntax.typology import TypologyMatrix

if TYPE_CHECKING:
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
        changed_count = 0

        for entity in self.hot_state.all_alive():
            effective_rate = erosion.rate(entity.frequency_weight, entity.stress_pattern)
            for op in active_ops:
                if rng.random() > effective_rate * op.change_rate:
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
        return changed_count

    def generate(self, csg: "ControlledSemanticGraph") -> GenerationResult:
        """Generate a surface-form sentence using this branch's current state."""
        pipeline = CSGPipeline(
            prime_graph=self._prime_graph,
            typology=self.typology,
            registry=self._registry,
            inventory=self._inventory,
        )
        return pipeline.generate(csg, self.hot_state, era=self.hot_state.current_era)

    def __repr__(self) -> str:
        return (
            f"BranchLanguage(name={self.config.name!r}, "
            f"era={self.current_era}, "
            f"words={len(self.hot_state)})"
        )
