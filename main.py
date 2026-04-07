import random
from pathlib import Path

from app.core.config import configs
from app.core.settings import global_settings
from app.domain.language.branch import BranchConfig, BranchLanguage
from app.domain.lexicon.factory import create_basic_lexicon_generator
from app.domain.lexicon.fossil import FossilPrefixExtractor
from app.domain.lexicon.grammaticalization_operator import GrammaticalizationOperator
from app.domain.lexicon.homophone_resolver import HomophoneResolver
from app.domain.lexicon.irregular import IrregularScarManager
from app.domain.lexicon.models import LexicalEntity
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
from app.domain.syntax.assembler import SentenceAssembler
from app.domain.syntax.csg import CSGEdge, CSGNode, ControlledSemanticGraph
from app.domain.syntax.pipeline import CSGPipeline
from app.domain.syntax.semantic_graph import SemanticGraph
from app.domain.syntax.typology import TypologyMatrix


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
    typology: TypologyMatrix | None = None,
) -> tuple[EngineHotState, TypologyMatrix]:
    inv = global_settings.inventory
    backend = NativeBackend()
    registry = build_registry(backend)
    km = KeyframeManager(configs.SNAPSHOT_DIR / "events", keyframe_interval=keyframe_interval)

    erosion = ErosionModel()
    scar_mgr = IrregularScarManager()
    gram_op = GrammaticalizationOperator(
        load_pathways(configs.DATA_DIR / "grammaticalization_pathways.yaml"), inv
    )
    drift_engine = TypologyDriftEngine()
    fossil_extractor = FossilPrefixExtractor()
    homophone_resolver = HomophoneResolver(swadesh_concepts=swadesh_concepts)

    current_typology: TypologyMatrix = typology or TypologyMatrix(
        word_order="SVO",
        tense_system="inflectional",
        morph_type="isolating",
        case_system="nominative_accusative",
        morpheme_table={},
    )

    hot = EngineHotState(current_era=0, swadesh_concepts=swadesh_concepts)
    hot.load_entities(entities)

    km.write_keyframe(0, hot.snapshot())
    print(f"\n[Era 0] 初始词库 {len(hot)} 词，已保存关键帧。")

    for era in range(1, era_steps + 1):
        rng = random.Random(global_settings.seed + era)
        changed_count = 0
        active_ops = registry.active_operators_for_era(era)

        for entity in hot.all_alive():
            effective_rate = erosion.rate(entity.frequency_weight, entity.stress_pattern)

            if scar_mgr.is_locked(entity):
                scar_result = scar_mgr.try_scar(entity, rng, inv)
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
                    era=era,
                    word_id=entity.id,
                    old_ipa=entity.ipa_current,
                    new_ipa="".join(result.output),
                    rule_name=op.name,
                )
                km.record(event)
                hot.apply_delta(event)
                changed_count += 1

            gram_result = gram_op.check(entity, hot, current_typology, era, stasis_blocked)
            if gram_result is not None:
                old_ipa = entity.ipa_current
                event = DeltaEvent(
                    event_type=DeltaEventType.SOUND_CHANGE,
                    era=era,
                    word_id=entity.id,
                    old_ipa=old_ipa,
                    new_ipa=gram_result.new_ipa,
                    rule_name=gram_result.pathway_id,
                    dag_parent_id=gram_result.host_word_id,
                )
                km.record(event)
                hot.apply_delta(event)
                edge_event = DeltaEvent(
                    event_type=DeltaEventType.DAG_EDGE_ADD,
                    era=era,
                    word_id=entity.id,
                    dag_parent_id=gram_result.host_word_id,
                    edge_type="grammaticalization",
                )
                km.record(edge_event)
                hot.apply_delta(edge_event)
                if gram_result.product_type in ("prefix", "suffix"):
                    current_typology.morpheme_table[gram_result.morpheme_key] = gram_result.new_ipa
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

        drift_stats = drift_engine.observe(hot)
        current_typology = drift_engine.maybe_drift(current_typology, drift_stats)

        drift_info = ""
        if drift_stats.gram_density >= 0.15:
            drift_info = f"  类型学: {current_typology.morph_type}"

        homophone_summary = f"  同音词消解 {resolved_count} 事件" if resolved_count else ""
        if km.should_write_keyframe(era):
            km.write_keyframe(era, hot.snapshot())
            print(
                f"[Era {era:2d}] 音变 {changed_count:3d} 词，已保存关键帧。"
                f"  活跃算子: {[o.name for o in active_ops]}{homophone_summary}{drift_info}"
            )
        else:
            print(
                f"[Era {era:2d}] 音变 {changed_count:3d} 词。"
                f"  活跃算子: {[o.name for o in active_ops]}{homophone_summary}{drift_info}"
            )

    return hot, current_typology


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
    final_typology: TypologyMatrix | None = None,
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

    hot, final_typology = evolve(generated_words, era_steps=10, swadesh_concepts=swadesh_concepts)
    print(f"\n[Main] 最终类型学: {final_typology.morph_type} / {final_typology.word_order}")

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
    demo_csg_pipeline(era0_snapshot, hot, registry, final_typology)


if __name__ == "__main__":
    main()
