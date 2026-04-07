from __future__ import annotations

from dataclasses import dataclass, field
from random import randint
from typing import TYPE_CHECKING, Any

from app.core.config import configs

if TYPE_CHECKING:
    from app.domain.phonology.phoneme import PhonemeInventory


@dataclass
class GlobalSettings:
    seed: int = 0
    is_llm: bool = False
    default_lexicon_name: str = "swadesh_207.json"
    phoneme_preset: str = "ipa_minimal"

    _inventory: "PhonemeInventory | None" = field(default=None, repr=False, compare=False)

    def modify_settings(self, settings_dict: dict[str, Any]) -> None:
        if "seed" in settings_dict:
            self.seed = settings_dict["seed"]
        if "is_llm" in settings_dict:
            self.is_llm = settings_dict["is_llm"]
        if "phoneme_preset" in settings_dict:
            self.phoneme_preset = settings_dict["phoneme_preset"]
            self._inventory = None

        if self.seed == 0:
            self.seed = randint(configs.SEED_MIN, configs.SEED_MAX)
            print(f"[System] 自动生成全局种子: {self.seed}")

    @property
    def inventory(self) -> "PhonemeInventory":
        if self._inventory is None:
            from app.domain.phonology.phoneme import PhonemeInventory
            self._inventory = PhonemeInventory.from_preset(self.phoneme_preset)
        return self._inventory


global_settings = GlobalSettings()
