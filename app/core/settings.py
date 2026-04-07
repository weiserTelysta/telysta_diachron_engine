from __future__ import annotations

import logging
from dataclasses import dataclass, field
from random import randint
from typing import TYPE_CHECKING, Any

from app.core.config import configs

if TYPE_CHECKING:
    from app.domain.phonology.phoneme import PhonemeInventory

_logger = logging.getLogger(__name__)


@dataclass
class GlobalSettings:
    seed: int = 0
    is_llm: bool = False
    default_lexicon_name: str = "swadesh_207.json"
    phoneme_preset: str = "ipa_minimal"

    # --- Phase 5: LLM integration ---
    llm_provider: str = "mock"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_timeout_s: int = 30
    llm_strict_schema: bool = True
    llm_enable_lore: bool = True
    llm_enable_callback: bool = True
    llm_enable_rag: bool = True
    llm_enable_reverse_etymology: bool = False
    llm_max_proposals_per_era: int = 5
    log_level: str = "INFO"
    log_verbose: bool = False
    log_retention_count: int = 10
    llm_log_raw_prompts: bool = False

    _inventory: "PhonemeInventory | None" = field(default=None, repr=False, compare=False)

    _LLM_FIELDS: frozenset[str] = field(
        default=frozenset({
            "is_llm", "llm_provider", "llm_model", "llm_api_key", "llm_base_url",
            "llm_timeout_s", "llm_strict_schema", "llm_enable_lore",
            "llm_enable_callback", "llm_enable_rag", "llm_enable_reverse_etymology",
            "llm_max_proposals_per_era", "log_level", "log_verbose",
            "log_retention_count", "llm_log_raw_prompts",
        }),
        repr=False, compare=False,
    )

    def modify_settings(self, settings_dict: dict[str, Any]) -> None:
        if "seed" in settings_dict:
            self.seed = settings_dict["seed"]
        if "phoneme_preset" in settings_dict:
            self.phoneme_preset = settings_dict["phoneme_preset"]
            self._inventory = None

        for key in self._LLM_FIELDS:
            if key in settings_dict:
                setattr(self, key, settings_dict[key])

        if self.seed == 0:
            self.seed = randint(configs.SEED_MIN, configs.SEED_MAX)
            _logger.info("自动生成全局种子: %d", self.seed)

    @property
    def inventory(self) -> "PhonemeInventory":
        if self._inventory is None:
            from app.domain.phonology.phoneme import PhonemeInventory
            self._inventory = PhonemeInventory.from_preset(self.phoneme_preset)
        return self._inventory


global_settings = GlobalSettings()
