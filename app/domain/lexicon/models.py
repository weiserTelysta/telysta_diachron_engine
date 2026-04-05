from typing import List
from dataclasses import dataclass, field


@dataclass
class LexicalEntity:
    id: str                 # 唯一标识，如 "swadesh_1"
    concept: str            # 斯瓦迪士概念，如 "water"
    pos: str                # 词性：NOUN, VERB
    ipa_current: str        # 当前时代的 IPA 发音
    ipa_history: List[str]  # 历时演变记录，例如 ["pata", "fata", "vas"]
    frequency_weight: float # 齐夫频率权重 (0.0-1.0)
    is_dead: bool = False   # 软删除标记

