"""Deterministic mock LLM backend for offline development and testing.

Responses are selected by matching keywords in the prompt against a
fixture registry.  Seed-deterministic — identical prompts always
produce identical outputs.
"""

from __future__ import annotations

import json
import random
from typing import Any

from app.core.logging import get_logger
from app.core.rng import RngTree
from app.llm.base import LLMBackend, LLMCallResult

logger = get_logger(__name__)

_LORE_TAGS = ["myth", "migration", "technology", "religion", "war", "trade"]
_SHIFT_TYPES = ["metaphor", "metonymy", "broadening", "narrowing"]


class MockBackend(LLMBackend):
    """Fixture-driven mock that returns deterministic JSON payloads."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._rng_tree = RngTree(seed).child("llm", "mock_backend")
        self._call_count = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-deterministic"

    def call(self, prompt: str, *, schema_hint: dict[str, Any] | None = None) -> LLMCallResult:
        self._call_count += 1
        rng = self._rng_tree.python("call", self._call_count)

        if "lore" in prompt.lower() or "narrative" in prompt.lower():
            payload = self._lore_fixture(prompt, rng)
        elif "semantic" in prompt.lower() or "proposal" in prompt.lower():
            payload = self._proposal_fixture(prompt, rng)
        elif "rag" in prompt.lower() or "new_concept" in prompt.lower():
            payload = self._rag_fixture(prompt, rng)
        elif "etymology" in prompt.lower() or "ancestor" in prompt.lower():
            payload = self._etymology_fixture(prompt, rng)
        else:
            payload = self._lore_fixture(prompt, rng)

        raw = json.dumps(payload, ensure_ascii=False)
        logger.debug("MockBackend call #%d → %d chars", self._call_count, len(raw))
        return LLMCallResult(
            raw_json=raw,
            provider=self.provider_name,
            model=self.model_name,
        )

    @staticmethod
    def _lore_fixture(prompt: str, rng: random.Random) -> dict[str, Any]:
        tags = rng.sample(_LORE_TAGS, k=rng.randint(1, 3))
        return {
            "narrative": (
                "In this era the people witnessed great changes. "
                "Sound shifts reshaped their tongue while new trade routes "
                "brought foreign influences to the lexicon."
            ),
            "tags": tags,
        }

    @staticmethod
    def _proposal_fixture(prompt: str, rng: random.Random) -> dict[str, Any]:
        return {
            "word_id": "era_0_1",
            "shift_type": rng.choice(_SHIFT_TYPES),
            "from_prime": "SUN",
            "to_prime": "SOUL",
            "chain": ["SUN", "LIGHT", "SPIRIT", "SOUL"],
            "confidence": round(rng.uniform(0.3, 0.9), 2),
            "reasoning": "Metaphorical extension from celestial body to inner essence.",
        }

    @staticmethod
    def _rag_fixture(prompt: str, rng: random.Random) -> dict[str, Any]:
        return {
            "new_concept": "telescope",
            "new_ipa": "kiporin",
            "root_ids_used": ["era_0_78", "era_0_79"],
            "morpheme_breakdown": "eye + star",
            "confidence": round(rng.uniform(0.4, 0.85), 2),
            "reasoning": "Compound of 'eye' and 'star' roots.",
        }

    @staticmethod
    def _etymology_fixture(prompt: str, rng: random.Random) -> dict[str, Any]:
        return {
            "modern_word_id": "era_0_1",
            "accepted_chain": ["proto_root_A", "era_3_form", "era_7_form"],
            "rejected_candidates": ["proto_root_B"],
            "confidence_band": rng.choice(["high", "medium", "low"]),
            "reasoning": "Regular sound change path through known operators.",
        }
