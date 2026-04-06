from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.domain.phonology.ir import SoundChangeRule
from app.domain.phonology.phoneme import Phoneme, PhonemeInventory


class RuleCompiler:
    """Compiles YAML rule definitions into backend-agnostic SoundChangeRule IR objects.

    The compiler runs once at startup. Its output (list[SoundChangeRule]) is
    passed to any Backend implementation unchanged.
    """

    def __init__(self, inventory: PhonemeInventory) -> None:
        self.inventory = inventory

    def compile_file(self, yaml_path: str | Path) -> list[SoundChangeRule]:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return [self.compile(rule_def) for rule_def in data.get("rules", [])]

    def compile(self, rule_def: dict[str, Any]) -> SoundChangeRule:
        name: str = rule_def["name"]
        priority: int = rule_def.get("priority", 50)
        op: str = rule_def.get("op", "change")

        target_spec: dict[str, bool] = rule_def.get("target", {})
        change_spec: dict[str, bool] = rule_def.get("change", {})
        env_before_spec: dict[str, bool] | None = rule_def.get("env_before")
        env_after_spec: dict[str, bool] | None = rule_def.get("env_after")
        env_flags: dict[str, bool] = rule_def.get("env_flags", {})

        target_class = self._expand_natural_class(target_spec)

        if op == "change":
            output_map = self._build_output_map(target_class, change_spec)
        else:
            output_map = {}

        env_before = (
            self._expand_natural_class(env_before_spec)
            if env_before_spec is not None
            else None
        )
        env_after = (
            self._expand_natural_class(env_after_spec)
            if env_after_spec is not None
            else None
        )

        output_phonemes = self._build_output_phonemes(target_class, change_spec) if op == "change" else {}

        return SoundChangeRule(
            name=name,
            priority=priority,
            op=op,  # type: ignore[arg-type]
            target_class=target_class,
            output_map=output_map,
            env_before=env_before,
            env_after=env_after,
            env_flags=env_flags,
            output_phonemes=output_phonemes,
        )

    def _expand_natural_class(self, feature_spec: dict[str, bool]) -> list[Phoneme]:
        """Return all phonemes in inventory matching feature_spec."""
        return self.inventory.get_natural_class(feature_spec)

    def _build_output_map(
        self, target_class: list[Phoneme], change_spec: dict[str, bool]
    ) -> dict[str, str]:
        """Build symbol→symbol mapping for each phoneme in target_class after applying change_spec."""
        output_map: dict[str, str] = {}
        for phoneme in target_class:
            result = phoneme.apply_change(change_spec, self.inventory)
            if result is not None:
                output_map[phoneme.symbol] = result.symbol
        return output_map

    def _build_output_phonemes(
        self, target_class: list[Phoneme], change_spec: dict[str, bool]
    ) -> dict[str, Phoneme]:
        """Build source_symbol→target_Phoneme mapping for matrix bit-level ops."""
        output_phonemes: dict[str, Phoneme] = {}
        for phoneme in target_class:
            result = phoneme.apply_change(change_spec, self.inventory)
            if result is not None:
                output_phonemes[phoneme.symbol] = result
        return output_phonemes
