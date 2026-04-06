from app.core.config import configs
from app.core.settings import global_settings
from app.domain.lexicon.factory import create_basic_lexicon_generator
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.backends.native_backend import NativeBackend
from app.domain.phonology.operators.final_vowel_drop import FinalVowelDropOperator
from app.domain.phonology.operators.registry import OperatorRegistry
from app.domain.phonology.operators.voicing_assimilation import VoicingAssimilationOperator
from app.domain.storage.event_log import DeltaEvent, DeltaEventType, KeyframeManager
from app.domain.storage.hot_state import EngineHotState


def bootstrap_app() -> None:
    ui_mock_data = {"seed": 888, "is_llm": False}
    global_settings.modify_settings(ui_mock_data)
    print("[Main] 系统引导完成，配置已就绪。")


def build_registry(backend: NativeBackend) -> OperatorRegistry:
    inv = global_settings.inventory
    registry = OperatorRegistry()
    registry.register(VoicingAssimilationOperator(backend, inv), enabled=True, priority=20)
    registry.register(FinalVowelDropOperator(backend, inv), enabled=True, priority=10)
    return registry


def evolve(
    entities: list[LexicalEntity],
    era_steps: int = 3,
    keyframe_interval: int = 10,
) -> EngineHotState:
    inv = global_settings.inventory
    backend = NativeBackend()
    registry = build_registry(backend)
    km = KeyframeManager(configs.SNAPSHOT_DIR / "events", keyframe_interval=keyframe_interval)

    hot = EngineHotState(current_era=0)
    hot.load_entities(entities)

    km.write_keyframe(0, hot.snapshot())
    print(f"\n[Era 0] 初始词库 {len(hot)} 词，已保存关键帧。")

    for era in range(1, era_steps + 1):
        changed_count = 0

        for entity in hot.all_alive():
            tokens = inv.tokenize(entity.ipa_current)
            new_tokens = registry.apply_all(tokens)

            if new_tokens != tokens:
                old_ipa = entity.ipa_current
                new_ipa = "".join(new_tokens)
                event = DeltaEvent(
                    event_type=DeltaEventType.SOUND_CHANGE,
                    era=era,
                    word_id=entity.id,
                    old_ipa=old_ipa,
                    new_ipa=new_ipa,
                )
                km.record(event)
                hot.apply_delta(event)
                changed_count += 1

        era_event = DeltaEvent(event_type=DeltaEventType.ERA_ADVANCE, era=era, word_id="")
        hot.apply_delta(era_event)

        if km.should_write_keyframe(era):
            km.write_keyframe(era, hot.snapshot())
            print(f"[Era {era}] 音变 {changed_count} 词，已保存关键帧。")
        else:
            print(f"[Era {era}] 音变 {changed_count} 词。")

    return hot


def main() -> None:
    bootstrap_app()

    engine = create_basic_lexicon_generator(global_settings)
    generated_words = engine.generate()
    print(f"\n[Main] 创世完成，共生成 {len(generated_words)} 个核心词汇。")

    hot = evolve(generated_words, era_steps=3)

    sample = list(hot.all_alive())[:5]
    print("\n[Main] 演化后词库样本（前 5 词）：")
    for e in sample:
        history = " → ".join(e.ipa_history + [e.ipa_current]) if e.ipa_history else e.ipa_current
        print(f"  [{e.concept}] {history}")


if __name__ == "__main__":
    main()
