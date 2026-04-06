import json
import random
from dataclasses import asdict

from app.core.config import configs
from app.domain.lexicon.models import LexicalEntity


class BasicLexiconGenerator:
    def __init__(
        self, seed: int, consonants: list, vowels: list, lexicolist_filepath: str
    ):
        self.seed = seed
        self.consonants = consonants
        self.vowels = vowels
        self.lexicolist_filepath = lexicolist_filepath

        self.rng = random.Random(self.seed)

    def _JSON_get(self, filepath: str):
        """获取数据"""
        with open(filepath, "r", encoding="UTF-8") as f:
            raw_data = json.load(f)

        if isinstance(raw_data, dict):
            return list(raw_data.values())[0]

        return raw_data

    def _IPA_generate(self):
        """生成IPA语音"""
        c = self.rng.choice(self.consonants)
        v = self.rng.choice(self.vowels)
        c2 = self.rng.choice(self.consonants)
        v2 = self.rng.choice(self.vowels)
        return c + v + c2 + v2

    def _frequency_weight_generate(self, rank_index: int) -> float:
        """计算齐夫频率"""
        return 1.0 / (rank_index + 1)

    def _JSON_save(self, lexicon_data: list, filename: str):
        """将生成的实体列表保存到 data/era_snapshots 目录下"""
        # 利用 configs 拿到绝对路径，并确保目录存在
        configs.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        save_path = configs.SNAPSHOT_DIR / filename

        # 将 LexicalEntity 对象列表转换回字典列表，以便 json.dump 序列化
        dict_data = [asdict(item) for item in lexicon_data]

        with open(save_path, "w", encoding="utf-8") as f:
            # ensure_ascii=False 保证存进去的 IPA 音标不会变成乱码
            # indent=4 让生成的 JSON 文件有漂亮的缩进排版
            json.dump(dict_data, f, ensure_ascii=False, indent=4)

        print(f"\n[System] 💾 创世快照已永久保存至: {save_path}")

    def generate(self):
        """生成第一版原始数据"""
        print(f"[System] 引擎启动，当前创世种子: {self.seed}")
        print(f"[System] 正在读取语义图纸: {self.lexicolist_filepath}")

        swadesh_list = self._JSON_get(self.lexicolist_filepath)
        final_lexicon = []

        for index, item in enumerate(swadesh_list):
            concept_en = item.get("en", item.get("word", "unknown"))
            pos = item.get("pos", "n.")
            jid = item.get("id", f"era_0_{index + 1}")
            ipa_sound = self._IPA_generate()
            weight = self._frequency_weight_generate(index)

            # 使用真正的实体类来组装数据！
            word_entity = LexicalEntity(
                id=jid,
                concept=concept_en,
                pos=pos,
                ipa_current=ipa_sound,
                ipa_history=[ipa_sound],
                frequency_weight=round(weight, 4),
                is_dead=False,
            )

            final_lexicon.append(word_entity)
            print(f"[{concept_en}] ({pos}) -> /{ipa_sound}/")

        snapshot_filename = f"era_0_snapshot_seed_{self.seed}.json"
        self._JSON_save(final_lexicon, snapshot_filename)

        return final_lexicon
