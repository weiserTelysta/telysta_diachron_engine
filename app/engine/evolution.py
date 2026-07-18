"""EvolutionEngine — the core era-loop extracted from main.evolve().

Owns all evolution components (registry, erosion, scar manager, etc.)
and exposes a single ``run()`` method that returns structured results.

Both ``main.py`` (CLI) and ``streamlit_app.py`` (Web) consume this class
through ``EngineSession``, ensuring identical computation paths.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING, Any

import app.core.console as console
from app.core.config import configs
from app.core.event_bus import get_event_bus
from app.core.logging import get_logger
from app.core.rng import RngTree
from app.core.settings import GlobalSettings
from app.domain.lexicon.analogy import AnalogyPropagator
from app.domain.lexicon.fossil import FossilPrefixExtractor
from app.domain.lexicon.grammaticalization_operator import GrammaticalizationOperator
from app.domain.lexicon.homophone_resolver import HomophoneResolver
from app.domain.lexicon.irregular import IrregularScarManager
from app.domain.lexicon.pathways import load_pathways
from app.domain.lexicon.typology_drift import TypologyDriftEngine
from app.domain.phonology.backends.native_backend import NativeBackend
from app.domain.phonology.erosion import ErosionModel
from app.domain.phonology.operators.coda_cluster_assimilation import CodaClusterAssimilationOperator
from app.domain.phonology.operators.final_vowel_drop import FinalVowelDropOperator
from app.domain.phonology.operators.mid_vowel_drop import MidVowelDropOperator
from app.domain.phonology.operators.registry import OperatorRegistry
from app.domain.phonology.operators.voicing_assimilation import VoicingAssimilationOperator
from app.domain.storage.event_log import DeltaEvent, DeltaEventType, KeyframeManager
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.typology import TypologyMatrix

if TYPE_CHECKING:
    from app.domain.lexicon.models import LexicalEntity
    from app.domain.phonology.phoneme import PhonemeInventory
    from app.llm.orchestrator import Phase5Orchestrator

logger = get_logger(__name__)


class EvolutionEngine:
    """Encapsulates the full evolution pipeline.

    Constructor builds the operator registry once; ``run()`` creates
    per-run components (erosion model, scar manager, etc.) so each
    invocation is independent.
    """

    def __init__(self, settings: GlobalSettings) -> None:
        self._settings = settings
        self._rng_tree = RngTree(settings.seed)
        self._inv: PhonemeInventory = settings.inventory
        self._backend = NativeBackend()
        self._registry = self._build_registry()

    @property
    def registry(self) -> OperatorRegistry:
        return self._registry

    @property
    def inventory(self) -> "PhonemeInventory":
        return self._inv

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        entities: list[LexicalEntity],
        era_steps: int = 10,
        keyframe_interval: int = 10,
        swadesh_concepts: set[str] | None = None,
        typology: TypologyMatrix | None = None,
        phase5_orchestrator: Phase5Orchestrator | None = None,
        era_log: list[dict] | None = None,
        hot: EngineHotState | None = None,
        era_offset: int = 0,
        epoch_name: str = "",
        total_eras: int = 0,
    ) -> tuple[EngineHotState, TypologyMatrix]:
        """Execute the full evolution loop.

        Parameters
        ----------
        era_log:
            If provided, a per-era summary dict is appended at each era
            boundary.  Pass ``[]`` from UI callers to collect telemetry.
        hot:
            If provided, reuse this existing EngineHotState instead of
            creating a fresh one.  Used by EpochManager to chain epochs
            without losing DAG history.
        era_offset:
            Global era number for the first era of this run.  Era numbers
            are ``era_offset + 1 … era_offset + era_steps``.  Used for
            consistent keyframe naming and seed derivation across epochs.
        """
        km = KeyframeManager(
            configs.SNAPSHOT_DIR / "events",
            keyframe_interval=keyframe_interval,
        )

        erosion = ErosionModel()
        scar_mgr = IrregularScarManager()
        gram_op = GrammaticalizationOperator(
            load_pathways(configs.DATA_DIR / "grammaticalization_pathways.yaml"),
            self._inv,
        )
        drift_engine = TypologyDriftEngine()
        analogy_prop = AnalogyPropagator(self._inv)
        fossil_extractor = FossilPrefixExtractor()
        homophone_resolver = HomophoneResolver(swadesh_concepts=swadesh_concepts)

        current_typology: TypologyMatrix = typology or TypologyMatrix(
            word_order="SVO",
            tense_system="inflectional",
            morph_type="isolating",
            case_system="nominative_accusative",
            morpheme_table={},
        )

        if hot is None:
            hot = EngineHotState(current_era=era_offset, swadesh_concepts=swadesh_concepts)
            hot.load_entities(entities)
            km.write_keyframe(era_offset, hot.snapshot(typology=current_typology))
            logger.debug("Era %d | 初始词库 %d 词，已保存关键帧。", era_offset, len(hot))
        else:
            hot.current_era = era_offset

        _total = total_eras if total_eras > 0 else era_steps
        _prev_morph = current_typology.morph_type
        for era in range(era_offset + 1, era_offset + era_steps + 1):
            _era_start = time.monotonic()
            sound_rng = self._rng_tree.python("evolution", "era", era, "sound")
            homophone_rng = self._rng_tree.python("evolution", "era", era, "homophone")
            drift_rng = self._rng_tree.python("evolution", "era", era, "typology")
            active_ops = self._registry.active_operators_for_era(era)

            gram_op.prepare_era(hot.all_alive())

            changed_count = self._evolve_entities(
                era, hot, current_typology, sound_rng, km,
                active_ops, erosion, scar_mgr, gram_op, analogy_prop,
            )

            resolved_count = self._resolve_homophones(
                era, hot, homophone_rng, km,
                homophone_resolver, fossil_extractor,
                current_typology=current_typology,
            )

            # Era advance
            hot.apply_delta(
                DeltaEvent(event_type=DeltaEventType.ERA_ADVANCE, era=era, word_id="")
            )

            era_deltas = [e for e in km._delta_buffer if e.era == era]
            km.flush_era(era)

            # Typology drift
            drift_stats = drift_engine.observe(hot)
            _morph_before = current_typology.morph_type
            current_typology = drift_engine.maybe_drift(
                current_typology,
                drift_stats,
                era,
                rng=drift_rng,
                bias_profile=current_typology.bias_profile,
            )
            _typology_changed = current_typology.morph_type != _morph_before

            # Phase 5 LLM orchestration
            p5_summary: dict[str, Any] | None = None
            if phase5_orchestrator is not None:
                p5_summary = phase5_orchestrator.on_era_end(
                    era=era,
                    hot_state=hot,
                    active_ops=active_ops,
                    delta_events=era_deltas,
                    typology=current_typology,
                )
                if not p5_summary.get("skipped"):
                    logger.debug(
                        "Era %2d | Phase5: %s", era,
                        {k: v for k, v in p5_summary.items() if k != "era"},
                    )

            # Collect era telemetry
            if era_log is not None:
                era_log.append({
                    "era": era,
                    "changed_count": changed_count,
                    "active_ops": [o.name for o in active_ops],
                    "morph_type": current_typology.morph_type,
                    "word_order": current_typology.word_order,
                    "alive_count": len(hot.all_alive()),
                    "dead_count": len(hot.lexicon) - len(hot.all_alive()),
                    "homophone_resolved": resolved_count,
                    "phase5_summary": p5_summary,
                })

            alive_n = len(hot.all_alive())

            # Structured event log
            get_event_bus().emit(
                "engine", "ERA_END",
                era=era,
                alive=alive_n,
                changes=changed_count,
                resolved=resolved_count,
                morph=current_typology.morph_type,
            )

            # TUI dot
            notable = ""
            if _typology_changed:
                notable = "?"
            elif alive_n > 0 and changed_count > alive_n * 0.10:
                notable = "!"
            console.era_dot(era, notable)

            # Keyframe + file log
            if km.should_write_keyframe(era):
                km.write_keyframe(era, hot.snapshot(typology=current_typology))
            drift_info = f"  typology={current_typology.morph_type}" if drift_stats.gram_density >= 0.15 else ""
            logger.debug(
                "Era %2d | changes=%d  ops=%s  resolved=%d%s",
                era, changed_count, [o.name for o in active_ops], resolved_count, drift_info,
            )

        return hot, current_typology

    # ------------------------------------------------------------------
    # Private: registry
    # ------------------------------------------------------------------

    def _build_registry(self) -> OperatorRegistry:
        inv = self._inv
        b = self._backend
        registry = OperatorRegistry()
        registry.register(FinalVowelDropOperator(b, inv, era_start=1), enabled=True, priority=10)
        registry.register(MidVowelDropOperator(b, inv, era_start=4), enabled=True, priority=11)
        registry.register(VoicingAssimilationOperator(b, inv), enabled=True, priority=20)
        registry.register(CodaClusterAssimilationOperator(b, inv, era_start=5), enabled=True, priority=25)
        return registry

    # ------------------------------------------------------------------
    # Private: per-era entity evolution
    # ------------------------------------------------------------------

    def _evolve_entities(
        self,
        era: int,
        hot: EngineHotState,
        typology: TypologyMatrix,
        rng: random.Random,
        km: KeyframeManager,
        active_ops: list,
        erosion: ErosionModel,
        scar_mgr: IrregularScarManager,
        gram_op: GrammaticalizationOperator,
        analogy_prop: AnalogyPropagator,
    ) -> int:
        inv = self._inv
        changed_count = 0

        for entity in hot.all_alive():
            effective_rate = erosion.rate(entity.frequency_weight, entity.stress_pattern)

            if scar_mgr.is_locked(entity):
                scar_result = scar_mgr.try_scar(entity, rng, inv)
                if scar_result:
                    new_ipa, scar_key = scar_result
                    entity.scar_log.append(scar_key)
                    event = DeltaEvent(
                        event_type=DeltaEventType.SOUND_CHANGE,
                        era=era, word_id=entity.id,
                        old_ipa=entity.ipa_current, new_ipa=new_ipa,
                        rule_name=f"irregular_scar:{scar_key}",
                    )
                    km.record(event)
                    hot.apply_delta(event)
                    changed_count += 1
                continue

            stasis_blocked = False
            for op in active_ops:
                if rng.random() > effective_rate * op.change_rate:
                    continue
                tokens = inv.tokenize(entity.ipa_current)
                result = op.apply(tokens, entity.stress_pattern)
                if not result.changed:
                    if op.name == "final_vowel_drop":
                        stasis_blocked = True
                    continue

                gram_op.note_changed(entity)
                event = DeltaEvent(
                    event_type=DeltaEventType.SOUND_CHANGE,
                    era=era, word_id=entity.id,
                    old_ipa=entity.ipa_current,
                    new_ipa="".join(result.output),
                    rule_name=op.name,
                )
                km.record(event)
                hot.apply_delta(event)
                changed_count += 1

            gram_result = gram_op.check(entity, hot, typology, era, stasis_blocked)
            if gram_result is not None:
                old_ipa = entity.ipa_current
                event = DeltaEvent(
                    event_type=DeltaEventType.SOUND_CHANGE,
                    era=era, word_id=entity.id,
                    old_ipa=old_ipa, new_ipa=gram_result.new_ipa,
                    rule_name=gram_result.pathway_id,
                    dag_parent_id=gram_result.host_word_id,
                )
                km.record(event)
                hot.apply_delta(event)
                edge_event = DeltaEvent(
                    event_type=DeltaEventType.DAG_EDGE_ADD,
                    era=era, word_id=entity.id,
                    dag_parent_id=gram_result.host_word_id,
                    edge_type="grammaticalization",
                )
                km.record(edge_event)
                hot.apply_delta(edge_event)
                if gram_result.product_type in ("prefix", "suffix"):
                    typology.morpheme_table[gram_result.morpheme_key] = gram_result.new_ipa
                affected_ids = analogy_prop.propagate(
                    entity, hot.all_alive(),
                    gram_result.morpheme_key, gram_result.new_ipa,
                    typology, rng,
                )
                for aid in affected_ids:
                    analogy_edge = DeltaEvent(
                        event_type=DeltaEventType.DAG_EDGE_ADD,
                        era=era, word_id=aid,
                        dag_parent_id=entity.id, edge_type="analogy",
                    )
                    km.record(analogy_edge)
                    hot.apply_delta(analogy_edge)
                changed_count += 1

        return changed_count

    # ------------------------------------------------------------------
    # Private: homophone resolution at era boundary
    # ------------------------------------------------------------------

    def _resolve_homophones(
        self,
        era: int,
        hot: EngineHotState,
        rng: random.Random,
        km: KeyframeManager,
        resolver: HomophoneResolver,
        fossil_extractor: FossilPrefixExtractor,
        current_typology: TypologyMatrix | None = None,
    ) -> int:
        inv = self._inv
        homophone_pairs = resolver.detect(hot.lexicon)
        resolved_count = 0

        morph_type = current_typology.derived_morph_type if current_typology else "isolating"
        for pair in homophone_pairs:
            a, b = pair
            if a.is_dead or b.is_dead or a.ipa_current != b.ipa_current:
                continue
            events = resolver.resolve(pair, era, rng, morphological_type=morph_type)
            for ev in events:
                km.record(ev)
                hot.apply_delta(ev)
                if ev.event_type == DeltaEventType.MARK_DEAD:
                    dead_entity = hot.get(ev.word_id)
                    if dead_entity:
                        fossil = fossil_extractor.extract(dead_entity, inv, era)
                        if fossil:
                            fossil_event = DeltaEvent(
                                event_type=DeltaEventType.FOSSIL_SPAWN,
                                era=era, word_id=fossil.id,
                                new_entity=fossil,
                                dag_parent_id=dead_entity.id,
                                edge_type="fossil_prefix",
                            )
                            km.record(fossil_event)
                            hot.apply_delta(fossil_event)
            resolved_count += len(events)

        return resolved_count
