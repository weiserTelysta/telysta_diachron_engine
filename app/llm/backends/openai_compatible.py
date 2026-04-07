"""OpenAI-compatible LLM backend adapter.

Supports any provider exposing an OpenAI-compatible ``/v1/chat/completions``
endpoint (OpenAI, Azure, vLLM, Ollama, etc.).
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.core.logging import get_logger
from app.llm.base import LLMBackend, LLMCallResult

logger = get_logger(__name__)


class OpenAICompatibleBackend(LLMBackend):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 30,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def model_name(self) -> str:
        return self._model

    def call(self, prompt: str, *, schema_hint: dict[str, Any] | None = None) -> LLMCallResult:
        import urllib.request

        url = f"{self._base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": (
                    "You are a structured-output linguistic assistant. "
                    "Always reply with a valid JSON object matching the provided schema. "
                    "No markdown fences, no extra text."
                )},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        if schema_hint is not None:
            body["response_format"] = {"type": "json_object"}

        data = json.dumps(body).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                resp_body = json.loads(resp.read().decode())
        except Exception:
            logger.exception("OpenAI-compatible call failed")
            raise

        latency_ms = (time.monotonic() - t0) * 1000
        choice = resp_body["choices"][0]["message"]["content"]
        usage = resp_body.get("usage", {})

        logger.debug(
            "OpenAI call: model=%s, latency=%.0fms, tokens=%d+%d",
            self._model, latency_ms,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )

        return LLMCallResult(
            raw_json=choice,
            provider=self.provider_name,
            model=self._model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
        )
