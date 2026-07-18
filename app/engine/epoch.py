"""EpochManager — multi-epoch language evolution orchestration.

An Epoch is a named historical period (e.g. proto, ancient, medieval)
containing a configurable number of computational eras.  Each epoch can
carry a morphological type bias, a domain vocabulary injection, and a
compounding pass.

Epoch chaining passes the EngineHotState between epochs so etymological
DAG history is preserved across all periods.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

import app.core.console as console
from app.core.event_bus import get_event_bus
from app.core.logging import get_logger
from app.core.rng import RngTree

if TYPE_CHECKING:
    from app.domain.lexicon.models import LexicalEntity
    from app.domain.storage.hot_state import EngineHotState
    from app.domain.syntax.typology import TypologyMatrix
    from app.engine.evolution import EvolutionEngine
    from app.engine.vocabulary import CompoundingEngine, WordInjector
    from app.llm.orchestrator import Phase5Orchestrator

logger = get_logger(__name__)

_VALID_BIASES = frozenset({"isolating", "agglutinative", "fusional", "auto", "random"})
_MORPH_CYCLE = ["isolating", "agglutinative", "fusional"]


@dataclass
class EpochConfig:
    """Configuration for a single historical epoch."""

    name: str
    era_count: int
    morph_type_bias: str = "auto"
    domain_inject: str | None = None
    compound_enabled: bool = True

    def __post_init__(self) -> None:
        if self.morph_type_bias not in _VALID_BIASES:
            raise ValueError(
                f"Invalid morph_type_bias {self.morph_type_bias!r}. "
                f"Must be one of {sorted(_VALID_BIASES)}."
            )
        if self.era_count < 1:
            raise ValueError(f"era_count must be >= 1, got {self.era_count}")


@dataclass
class EpochResult:
    """Collected telemetry for a completed epoch."""

    epoch_name: str
    epoch_idx: int
    era_start: int
    era_end: int
    era_log: list[dict[str, Any]] = field(default_factory=list)
    injected_words: list["LexicalEntity"] = field(default_factory=list)
    compound_words: list["LexicalEntity"] = field(default_factory=list)
    replaced_concepts: list[str] = field(default_factory=list)
    typology_at_end_morph: str = "isolating"
    typology_at_end_order: str = "SVO"
    lexicon_size_at_end: int = 0


def load_epoch_config(path: str | Path) -> list[EpochConfig]:
    """Parse a YAML epoch-preset file into a list of EpochConfig objects."""
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    epochs_raw = raw.get("epochs", [])
    return [
        EpochConfig(
            name=e["name"],
            era_count=e["era_count"],
            morph_type_bias=e.get("morph_type_bias", "auto"),
            domain_inject=e.get("domain_inject"),
            compound_enabled=e.get("compound_enabled", True),
        )
        for e in epochs_raw
    ]


class EpochManager:
    """Orchestrates a sequence of Epochs over a shared EngineHotState.

    Each epoch:
      1. Resolves morph_type_bias → may override typology
      2. Calls DomainInjector (if configured)
      3. Calls CompoundingEngine (if enabled)
      4. Runs EvolutionEngine for epoch.era_count eras
      5. Runs VocabularyRenewalEngine to fill concept vacuums
      6. Collects EpochResult
    """

    def __init__(
        self,
        epochs: list[EpochConfig],
        domain_injector_factory: "WordInjectorFactory | None" = None,
        compounding_engine: "CompoundingEngine | None" = None,
        renewal_engine: "VocabularyRenewalEngine | None" = None,
        seed: int = 888,
    ) -> None:
        self._epochs = epochs
        self._domain_injector_factory = domain_injector_factory
        self._compounding_engine = compounding_engine
        self._renewal_engine = renewal_engine
        self._seed = seed
        self._rng_tree = RngTree(seed).child("epoch")

    def run(
        self,
        hot: "EngineHotState",
        typology: "TypologyMatrix",
        engine: "EvolutionEngine",
        swadesh_concepts: set[str] | None = None,
        phase5_orchestrator: "Phase5Orchestrator | None" = None,
        keyframe_interval: int = 10,
    ) -> tuple["EngineHotState", "TypologyMatrix", list[EpochResult]]:
        """Execute all epochs sequentially, returning the final state and results."""
        epoch_results: list[EpochResult] = []
        era_cursor = 0
        total_eras = sum(e.era_count for e in self._epochs)

        for epoch_idx, epoch in enumerate(self._epochs):
            logger.debug(
                "Epoch %d/%d [%s] — %d eras, bias=%s, inject=%s",
                epoch_idx + 1, len(self._epochs), epoch.name,
                epoch.era_count, epoch.morph_type_bias,
                epoch.domain_inject or "none",
            )
            console.epoch_start(
                idx=epoch_idx + 1,
                total=len(self._epochs),
                name=epoch.name,
                era_count=epoch.era_count,
            )
            get_event_bus().emit(
                "epoch", "EPOCH_START",
                name=epoch.name,
                era_start=era_cursor,
                era_end=era_cursor + epoch.era_count,
                bias=epoch.morph_type_bias,
                inject=epoch.domain_inject or "none",
            )

            typology = self._apply_bias(
                epoch,
                typology,
                self._rng_tree.python(epoch_idx, "bias"),
            )

            injected: list[LexicalEntity] = []
            if epoch.domain_inject and self._domain_injector_factory:
                injector = self._domain_injector_factory(epoch.domain_inject)
                rng = self._rng_tree.python(epoch_idx, "domain_injection")
                injected = injector.inject(hot, era_cursor, engine.inventory, rng)
                logger.debug("Epoch [%s] injected %d domain words.", epoch.name, len(injected))
                get_event_bus().emit(
                    "epoch", "INJECT",
                    name=epoch.name,
                    source=epoch.domain_inject,
                    count=len(injected),
                )

            compounds: list[LexicalEntity] = []
            if epoch.compound_enabled and self._compounding_engine:
                rng = self._rng_tree.python(epoch_idx, "compounding")
                compounds = self._compounding_engine.generate(hot, era_cursor, rng, epoch_idx=epoch_idx)
                logger.debug("Epoch [%s] generated %d compound words.", epoch.name, len(compounds))
                if compounds:
                    sample = " ".join(c.concept for c in compounds[:5])
                    get_event_bus().emit(
                        "epoch", "COMPOUNDS",
                        name=epoch.name,
                        count=len(compounds),
                        sample=sample,
                    )

            era_log: list[dict[str, Any]] = []
            hot, typology = engine.run(
                entities=[],
                era_steps=epoch.era_count,
                keyframe_interval=keyframe_interval,
                swadesh_concepts=swadesh_concepts,
                typology=typology,
                phase5_orchestrator=phase5_orchestrator,
                era_log=era_log,
                hot=hot,
                era_offset=era_cursor,
                epoch_name=epoch.name,
                total_eras=total_eras,
            )

            replaced: list[str] = []
            if self._renewal_engine and swadesh_concepts:
                rng = self._rng_tree.python(epoch_idx, "renewal")
                replaced = self._renewal_engine.renew(
                    hot, era_cursor + epoch.era_count, swadesh_concepts, engine.inventory, rng
                )
                if replaced:
                    logger.debug(
                        "Epoch [%s] renewed %d concept(s): %s",
                        epoch.name, len(replaced), replaced,
                    )

            era_cursor += epoch.era_count
            get_event_bus().emit(
                "epoch", "EPOCH_END",
                name=epoch.name,
                era_end=era_cursor,
                lexicon_size=len(hot.all_alive()),
                morph=typology.morph_type,
                order=typology.word_order,
            )
            result = EpochResult(
                epoch_name=epoch.name,
                epoch_idx=epoch_idx,
                era_start=era_cursor - epoch.era_count,
                era_end=era_cursor,
                era_log=era_log,
                injected_words=injected,
                compound_words=compounds,
                replaced_concepts=replaced,
                typology_at_end_morph=typology.morph_type,
                typology_at_end_order=typology.word_order,
                lexicon_size_at_end=len(hot.all_alive()),
            )
            epoch_results.append(result)
            logger.debug(
                "Epoch [%s] complete — alive=%d, dead=%d, morph=%s",
                epoch.name,
                len(hot.all_alive()),
                len(hot.lexicon) - len(hot.all_alive()),
                typology.morph_type,
            )
            console.epoch_end(
                alive=len(hot.all_alive()),
                morph=typology.morph_type,
                order=typology.word_order,
            )

        return hot, typology, epoch_results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_bias(
        self,
        epoch: EpochConfig,
        typology: "TypologyMatrix",
        rng: random.Random,
    ) -> "TypologyMatrix":
        """Adjust typology based on epoch's morph_type_bias.

        Instead of directly overwriting morph_type (which caused the "style
        layer override" bug), the bias sets per-domain states uniformly and
        then syncs the legacy field.  'auto' leaves everything untouched.
        """
        from app.domain.syntax.bias_profile import BiasProfile
        from app.domain.syntax.typology import AGGLUTINATIVE, ANALYTIC, FUSIONAL, MorphologicalState

        bias = epoch.morph_type_bias
        if bias == "auto":
            typology.bias_profile = BiasProfile.neutral()
            return typology
        if bias == "random":
            bias = rng.choice(_MORPH_CYCLE)

        level_map = {"isolating": ANALYTIC, "agglutinative": AGGLUTINATIVE, "fusional": FUSIONAL}
        preset_map = {
            "isolating": BiasProfile.modern,
            "agglutinative": BiasProfile.primal,
            "fusional": BiasProfile.imperial,
        }
        level = level_map.get(bias)
        if level is None:
            return typology

        def_level = min(level, 1)  # definiteness capped at 1
        typology.morph_state = MorphologicalState(
            verb_tam=level,
            verb_agreement=level,
            noun_case=level,
            noun_definiteness=def_level,
        )
        typology.sync_morph_type()
        # Attach BiasProfile so per-era drift inherits epoch-level style intention
        typology.bias_profile = preset_map[bias]()
        return typology


# Factory type alias used by EpochManager
from typing import Protocol


class WordInjectorFactory(Protocol):
    def __call__(self, domain: str) -> "WordInjector": ...


# Avoid circular import — import at call site
from typing import TYPE_CHECKING as _TC
if _TC:
    from app.engine.vocabulary import VocabularyRenewalEngine, WordInjector
