from dataclasses import dataclass
from random import randint
from typing import Any, Dict

from app.core.config import configs


@dataclass
class GlobalSettings:
    """
    这里是全局运行时的参数，决定引擎的功能的。
    """

    seed: int = 0
    is_llm: bool = False
    default_lexicon_name: str = "swadesh_100.json"

    consonants = ["p", "t", "k", "m", "s"]
    vowels = ["a", "i", "u", "e", "o"]

    def modify_settings(self, settings_dict: Dict[str, Any]):
        if "seed" in settings_dict:
            self.seed = settings_dict["seed"]
        if "is_llm" in settings_dict:
            self.is_llm = settings_dict["is_llm"]

        if self.seed == 0:
            self.seed = randint(configs.SEED_MIN, configs.SEED_MAX)
            print(f"[System] 自动生成全局种子: {self.seed}")


global_settings = GlobalSettings()
