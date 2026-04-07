"""LLM backend abstraction.

``LLMBackend.call()`` is the single contact surface between the engine and
any LLM provider.  Implementations MUST return raw JSON strings — parsing
and validation are handled by the sanitizer and contract layers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMCallResult:
    raw_json: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


class LLMBackend(ABC):
    @abstractmethod
    def call(self, prompt: str, *, schema_hint: dict[str, Any] | None = None) -> LLMCallResult:
        """Send *prompt* to the provider and return the raw JSON response.

        ``schema_hint`` is forwarded to providers that support structured
        output (e.g. OpenAI JSON mode).  Implementations that do not
        support it may ignore the parameter.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...
