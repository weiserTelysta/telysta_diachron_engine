import json
import random
from dataclasses import asdict

from app.core.config import configs
from app.domain.lexicon.models import LexicalEntity
from app.domain.phonology.phoneme import PhonemeInventory


class BasicLexiconGenerator:
    def __init__(
        self,
        seed: int,
        inventory: PhonemeInventory,
        lexicolist_filepath: str,
    ) -> None:
        self.seed = seed
        self.inventory = inventory
        self.lexicolist_filepath = lexicolist_filepath
        self.rng = random.Random(self.seed)

    def _json_get(self, filepath: str) -> list:
        with open(filepath, encoding="UTF-8") as f:
            raw_data = json.load(f)
        if isinstance(raw_data, dict):
            return list(raw_data.values())[0]
        return raw_data

    def _ipa_generate(self) -> str:
        """Generate a CVCV IPA form using weighted phoneme sampling."""
        c1 = self.inventory.sample_consonant(self.rng).symbol
        v1 = self.inventory.sample_vowel(self.rng).symbol
        c2 = self.inventory.sample_consonant(self.rng).symbol
        v2 = self.inventory.sample_vowel(self.rng).symbol
        return c1 + v1 + c2 + v2

    def _frequency_weight_generate(self, rank_index: int) -> float:
        return 1.0 / (rank_index + 1)

    def _json_save(self, lexicon_data: list[LexicalEntity], filename: str) -> None:
        configs.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        save_path = configs.SNAPSHOT_DIR / filename
        dict_data = [asdict(item) for item in lexicon_data]
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(dict_data, f, ensure_ascii=False, indent=4)
        print(f"\n[System] 创世快照已永久保存至: {save_path}")

    def generate(self) -> list[LexicalEntity]:
        print(f"[System] 引擎启动，当前创世种子: {self.seed}")
        print(f"[System] 正在读取语义图纸: {self.lexicolist_filepath}")
        print(f"[System] 使用音素库: {self.inventory}")

        swadesh_list = self._json_get(self.lexicolist_filepath)
        final_lexicon: list[LexicalEntity] = []

        for index, item in enumerate(swadesh_list):
            concept_en = item.get("en", item.get("word", "unknown"))
            pos = item.get("pos", "n.")
            jid = item.get("id", f"era_0_{index + 1}")
            ipa_sound = self._ipa_generate()
            weight = self._frequency_weight_generate(index)

            word_entity = LexicalEntity(
                id=jid,
                concept=concept_en,
                pos=pos,
                ipa_current=ipa_sound,
                ipa_history=[],
                frequency_weight=round(weight, 4),
                is_dead=False,
                ipa_exemplars=[{"form": ipa_sound, "weight": 1.0}],
            )

            final_lexicon.append(word_entity)
            print(f"[{concept_en}] ({pos}) -> /{ipa_sound}/")

        snapshot_filename = f"era_0_snapshot_seed_{self.seed}.json"
        self._json_save(final_lexicon, snapshot_filename)

        return final_lexicon
