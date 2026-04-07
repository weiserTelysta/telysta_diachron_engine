import json
import random
import time

from app.core.config import configs
from app.core.settings import global_settings
from app.domain.language.branch import BranchConfig, BranchLanguage
from app.domain.lexicon.factory import create_basic_lexicon_generator
from app.domain.lexicon.fossil import FossilPrefixExtractor
from app.domain.lexicon.homophone_resolver import HomophoneResolver
from app.domain.lexicon.irregular import IrregularScarManager
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.backends.native_backend import NativeBackend
from app.domain.phonology.erosion import ErosionModel
from app.domain.phonology.operators.coda_cluster_assimilation import CodaClusterAssimilationOperator
from app.domain.phonology.operators.final_vowel_drop import FinalVowelDropOperator
from app.domain.phonology.operators.mid_vowel_drop import MidVowelDropOperator
from app.domain.phonology.operators.registry import OperatorRegistry
from app.domain.phonology.operators.voicing_assimilation import VoicingAssimilationOperator
from app.domain.storage.event_log import DeltaEvent, DeltaEventType, KeyframeManager
from app.domain.storage.hot_state import EngineHotState
from app.domain.syntax.assembler import SentenceAssembler
from app.domain.syntax.csg import CSGEdge, CSGNode, ControlledSemanticGraph
from app.domain.syntax.pipeline import CSGPipeline
from app.domain.syntax.semantic_graph import SemanticGraph
from app.domain.syntax.typology import TypologyMatrix


# region agent log
_DEBUG_LOG_PATH: str = "/home/weiser/TelystaLexisEngine/.cursor/debug-9febab.log"
_DEBUG_SESSION_ID: str = "9febab"
_DEBUG_TRACKED_IDS: frozenset[str] = frozenset({"1", "2", "5"})


def _append_debug_log(
    run_id: str,
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, object],
) -> None:
    payload: dict[str, object] = {
        "sessionId": _DEBUG_SESSION_ID,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as debug_file:
            debug_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass
# endregion


def bootstrap_app() -> None:
    ui_mock_data = {"seed": 888, "is_llm": False}
    global_settings.modify_settings(ui_mock_data)
    print("[Main] 系统引导完成，配置已就绪。")


def build_registry(backend: NativeBackend) -> OperatorRegistry:
    inv = global_settings.inventory
    registry = OperatorRegistry()
    registry.register(FinalVowelDropOperator(backend, inv, era_start=1),         enabled=True, priority=10)
    registry.register(MidVowelDropOperator(backend, inv,   era_start=4),         enabled=True, priority=11)
    registry.register(VoicingAssimilationOperator(backend, inv),                  enabled=True, priority=20)
    registry.register(CodaClusterAssimilationOperator(backend, inv, era_start=5), enabled=True, priority=25)
    return registry


def evolve(
    entities: list[LexicalEntity],
    era_steps: int = 10,
    keyframe_interval: int = 10,
    swadesh_concepts: set[str] | None = None,
) -> EngineHotState:
    inv = global_settings.inventory
    backend = NativeBackend()
    registry = build_registry(backend)
    km = KeyframeManager(configs.SNAPSHOT_DIR / "events", keyframe_interval=keyframe_interval)
    debug_run_id = f"seed-{global_settings.seed}-{int(time.time() * 1000)}"

    erosion = ErosionModel()
    scar_mgr = IrregularScarManager()
    fossil_extractor = FossilPrefixExtractor()
    homophone_resolver = HomophoneResolver(swadesh_concepts=swadesh_concepts)

    hot = EngineHotState(current_era=0, swadesh_concepts=swadesh_concepts)
    hot.load_entities(entities)

    km.write_keyframe(0, hot.snapshot())
    print(f"\n[Era 0] 初始词库 {len(hot)} 词，已保存关键帧。")

    for era in range(1, era_steps + 1):
        rng = random.Random(global_settings.seed + era)
        changed_count = 0
        active_ops = registry.active_operators_for_era(era)
        # region agent log
        _append_debug_log(
            run_id=debug_run_id,
            hypothesis_id="H3",
            location="main.py:67",
            message="era_pipeline",
            data={
                "era": era,
                "active_ops": [op.name for op in active_ops],
                "has_grammaticalization_operator": any(
                    "grammatical" in op.name for op in active_ops
                ),
            },
        )
        # endregion

        for entity in hot.all_alive():
            effective_rate = erosion.rate(entity.frequency_weight, entity.stress_pattern)
            tracked: bool = str(entity.id) in _DEBUG_TRACKED_IDS
            if tracked:
                # region agent log
                _append_debug_log(
                    run_id=debug_run_id,
                    hypothesis_id="H2",
                    location="main.py:84",
                    message="tracked_entity_state",
                    data={
                        "era": era,
                        "id": str(entity.id),
                        "concept": entity.concept,
                        "ipa": entity.ipa_current,
                        "frequency_weight": entity.frequency_weight,
                        "effective_rate": effective_rate,
                        "is_locked": scar_mgr.is_locked(entity),
                        "grammaticalization_stage": entity.grammaticalization_stage,
                        "word_class": entity.word_class,
                    },
                )
                # endregion

            # Locked words skip normal rule-based change; may acquire a scar instead
            if scar_mgr.is_locked(entity):
                scar_result = scar_mgr.try_scar(entity, rng, inv)
                if tracked:
                    # region agent log
                    _append_debug_log(
                        run_id=debug_run_id,
                        hypothesis_id="H2",
                        location="main.py:103",
                        message="tracked_entity_locked_branch",
                        data={
                            "era": era,
                            "id": str(entity.id),
                            "ipa": entity.ipa_current,
                            "scar_applied": scar_result is not None,
                        },
                    )
                    # endregion
                if scar_result:
                    new_ipa, scar_key = scar_result
                    entity.scar_log.append(scar_key)
                    event = DeltaEvent(
                        event_type=DeltaEventType.SOUND_CHANGE,
                        era=era,
                        word_id=entity.id,
                        old_ipa=entity.ipa_current,
                        new_ipa=new_ipa,
                        rule_name=f"irregular_scar:{scar_key}",
                    )
                    km.record(event)
                    hot.apply_delta(event)
                    changed_count += 1
                continue

            for op in active_ops:
                roll = rng.random()
                threshold = effective_rate * op.change_rate
                if tracked:
                    # region agent log
                    _append_debug_log(
                        run_id=debug_run_id,
                        hypothesis_id="H4",
                        location="main.py:123",
                        message="tracked_operator_gate",
                        data={
                            "era": era,
                            "id": str(entity.id),
                            "concept": entity.concept,
                            "ipa": entity.ipa_current,
                            "operator": op.name,
                            "roll": roll,
                            "threshold": threshold,
                            "passed_gate": roll <= threshold,
                        },
                    )
                    # endregion
                if roll > threshold:
                    continue

                tokens = inv.tokenize(entity.ipa_current)
                result = op.apply(tokens, entity.stress_pattern)
                if tracked:
                    # region agent log
                    _append_debug_log(
                        run_id=debug_run_id,
                        hypothesis_id="H4",
                        location="main.py:143",
                        message="tracked_operator_result",
                        data={
                            "era": era,
                            "id": str(entity.id),
                            "concept": entity.concept,
                            "operator": op.name,
                            "input": tokens,
                            "output": result.output,
                            "changed": result.changed,
                        },
                    )
                    # endregion
                if not result.changed:
                    continue

                event = DeltaEvent(
                    event_type=DeltaEventType.SOUND_CHANGE,
                    era=era,
                    word_id=entity.id,
                    old_ipa=entity.ipa_current,
                    new_ipa="".join(result.output),
                    rule_name=op.name,
                )
                km.record(event)
                hot.apply_delta(event)
                changed_count += 1

        # Homophone detection and resolution at era boundary
        homophone_pairs = homophone_resolver.detect(hot.lexicon)
        resolved_count = 0
        for pair in homophone_pairs:
            a, b = pair
            # Guard against stale pairs: earlier resolutions may have changed IPA or killed a word
            if a.is_dead or b.is_dead or a.ipa_current != b.ipa_current:
                continue
            events = homophone_resolver.resolve(pair, era, rng)
            for ev in events:
                km.record(ev)
                hot.apply_delta(ev)
                # Fossil extraction for any newly dead words
                if ev.event_type == DeltaEventType.MARK_DEAD:
                    dead_entity = hot.get(ev.word_id)
                    if dead_entity:
                        fossil = fossil_extractor.extract(dead_entity, inv, era)
                        if fossil:
                            fossil_event = DeltaEvent(
                                event_type=DeltaEventType.FOSSIL_SPAWN,
                                era=era,
                                word_id=fossil.id,
                                new_entity=fossil,
                                dag_parent_id=dead_entity.id,
                                edge_type="fossil_prefix",
                            )
                            km.record(fossil_event)
                            hot.apply_delta(fossil_event)
            resolved_count += len(events)

        era_event = DeltaEvent(event_type=DeltaEventType.ERA_ADVANCE, era=era, word_id="")
        hot.apply_delta(era_event)
        km.flush_era(era)

        homophone_summary = f"  同音词消解 {resolved_count} 事件" if resolved_count else ""
        if km.should_write_keyframe(era):
            km.write_keyframe(era, hot.snapshot())
            print(
                f"[Era {era:2d}] 音变 {changed_count:3d} 词，已保存关键帧。"
                f"  活跃算子: {[o.name for o in active_ops]}{homophone_summary}"
            )
        else:
            print(
                f"[Era {era:2d}] 音变 {changed_count:3d} 词。"
                f"  活跃算子: {[o.name for o in active_ops]}{homophone_summary}"
            )

    return hot


def _build_demo_csg() -> ControlledSemanticGraph:
    """CSG for: 'I (past-)see you' (SEE, agent=I/1sg, patient=YOU, tense=PAST)."""
    csg = ControlledSemanticGraph()
    csg.add_node(CSGNode(id="subj", prime_id="I",
                         attributes={"person": "1", "number": "sg"}))
    csg.add_node(CSGNode(id="pred", prime_id="SEE",
                         attributes={"tense": "PAST"}))
    csg.add_node(CSGNode(id="obj",  prime_id="YOU"))
    csg.add_edge(CSGEdge(from_id="subj", to_id="pred", relation="agent"))
    csg.add_edge(CSGEdge(from_id="pred", to_id="obj",  relation="patient"))
    return csg


def demo_csg_pipeline(
    era0_hot: EngineHotState,
    era10_hot: EngineHotState,
    registry: OperatorRegistry,
) -> None:
    """Phase 3 演示：跨时代同句对比 + 分支语言差异。"""
    inv = global_settings.inventory
    prime_graph = SemanticGraph.from_json(
        configs.DATA_DIR / "semantic_primes" / "primes.json"
    )

    svo_typology = TypologyMatrix(
        word_order="SVO",
        tense_system="inflectional",
        morph_type="agglutinative",
        case_system="nominative_accusative",
        agreement_features=["person", "number"],
        morpheme_table={
            "ACC": "o", "PAST": "et", "PRES": "a",
            "1SG": "m", "3SG": "s",
        },
    )
    sov_typology = svo_typology.clone_with(word_order="SOV")

    pipeline = CSGPipeline(prime_graph, svo_typology, registry, inv)
    csg = _build_demo_csg()

    print("\n" + "=" * 60)
    print("[Phase 3] CSG 跨时代同句对比")
    print("=" * 60)
    print("  CSG: I-SEE-YOU / tense=PAST / agent=1sg")

    results = pipeline.compare_eras(
        csg,
        era_snapshots={
            0:  (era0_hot,  svo_typology),
            10: (era10_hot, svo_typology),
        },
    )
    for r in results:
        lexmap_str = " | ".join(
            f"{k}={v or '?'}"
            for k, v in r.lexmap_used.items()
            if k in ("I", "SEE", "YOU")
        )
        print(f"  {r}   [{lexmap_str}]")
        if r.warnings:
            for w in r.warnings:
                print(f"    ⚠ {w}")

    print("\n" + "=" * 60)
    print("[Phase 3] 分支语言独立演化对比")
    print("=" * 60)

    branch_a = BranchLanguage(
        BranchConfig(name="北方方言 (SVO)", fork_era=0),
        era0_hot, svo_typology, prime_graph, registry, inv,
    )
    branch_b = BranchLanguage(
        BranchConfig(name="南方方言 (SOV)", fork_era=0,
                     typology_override=sov_typology),
        era0_hot, svo_typology, prime_graph, registry, inv,
    )

    rng_a = random.Random(global_settings.seed + 100)
    rng_b = random.Random(global_settings.seed + 200)
    for _ in range(5):
        branch_a.evolve_one_era(rng=rng_a)
        branch_b.evolve_one_era(rng=rng_b)

    result_a = branch_a.generate(csg)
    result_b = branch_b.generate(csg)

    print(f"  {branch_a.name:20s} (Era {branch_a.current_era}): /{result_a.sentence}/")
    print(f"  {branch_b.name:20s} (Era {branch_b.current_era}): /{result_b.sentence}/")
    print("=" * 60)


def main() -> None:
    bootstrap_app()

    engine = create_basic_lexicon_generator(global_settings)
    generated_words = engine.generate()
    print(f"\n[Main] 创世完成，共生成 {len(generated_words)} 个核心词汇。")

    swadesh_concepts = {e.concept for e in generated_words}

    era0_hot = EngineHotState(current_era=0)
    era0_hot.load_entities(generated_words)
    era0_snapshot = era0_hot.clone()

    hot = evolve(generated_words, era_steps=10, swadesh_concepts=swadesh_concepts)

    sample = list(hot.all_alive())[:5]
    print("\n[Main] 演化后词库样本（前 5 词）：")
    for e in sample:
        history = " → ".join(e.ipa_history + [e.ipa_current]) if e.ipa_history else e.ipa_current
        print(f"  [{e.concept}] {history}")

    alive = list(hot.all_alive())
    assembler = SentenceAssembler(alive)
    rng = random.Random(global_settings.seed)
    proto_sentences = assembler.assemble(n=10, rng=rng)
    print("\n[Main] Proto-sentence assembly（10 句，纯 IPA 拼接，无形态变化）：")
    for i, s in enumerate(proto_sentences, 1):
        print(f"  {i:2d}. /{s}/")

    print(f"\n[Main] DAG 词源图: {hot.dag}")

    backend = NativeBackend()
    registry = build_registry(backend)
    demo_csg_pipeline(era0_snapshot, hot, registry)


if __name__ == "__main__":
    main()
