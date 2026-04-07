import random

from app.core.config import configs
from app.core.settings import global_settings
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

        for entity in hot.all_alive():
            effective_rate = erosion.rate(entity.frequency_weight, entity.stress_pattern)

            # Locked words skip normal rule-based change; may acquire a scar instead
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

            for op in active_ops:
                if rng.random() > effective_rate * op.change_rate:
                    continue

                tokens = inv.tokenize(entity.ipa_current)
                result = op.apply(tokens, entity.stress_pattern)
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


def main() -> None:
    bootstrap_app()

    engine = create_basic_lexicon_generator(global_settings)
    generated_words = engine.generate()
    print(f"\n[Main] 创世完成，共生成 {len(generated_words)} 个核心词汇。")

    swadesh_concepts = {e.concept for e in generated_words}
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


if __name__ == "__main__":
    main()
