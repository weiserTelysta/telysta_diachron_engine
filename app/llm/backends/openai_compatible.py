"""OpenAI-compatible LLM backend adapter.

Supports any provider exposing an OpenAI-compatible ``/v1/chat/completions``
endpoint (OpenAI, Azure, vLLM, Ollama, etc.).

Security notes:
- API key is never logged.
- Raw response content is returned as-is; sanitization is done upstream.
- On HTTP or parse failure, an exception is raised (not silently swallowed)
  so the orchestrator can decide whether to skip or abort the era capability.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from app.core.logging import get_logger
from app.llm.base import LLMBackend, LLMCallResult

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a structured-output linguistic assistant. "
    "Always reply with a valid JSON object matching the provided schema. "
    "No markdown fences, no extra text, no explanation outside the JSON object."
)


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
        url = f"{self._base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }

        if schema_hint is not None:
            # Use json_object mode universally; structured output with full
            # schema requires provider-specific support that may not be
            # available — sanitizer enforces strict constraints on our side.
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
                raw_body = resp.read().decode()
        except urllib.error.HTTPError as exc:
            logger.error(
                "OpenAI call HTTP error: status=%d model=%s base_url=%s",
                exc.code, self._model, self._base_url,
            )
            raise
        except urllib.error.URLError as exc:
            logger.error(
                "OpenAI call network error: %s model=%s base_url=%s",
                exc.reason, self._model, self._base_url,
            )
            raise
        except TimeoutError:
            logger.error(
                "OpenAI call timed out after %ds model=%s base_url=%s",
                self._timeout, self._model, self._base_url,
            )
            raise

        latency_ms = (time.monotonic() - t0) * 1000

        try:
            resp_body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            logger.error("OpenAI response is not valid JSON: %s", exc)
            raise

        try:
            choice_content = resp_body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected OpenAI response structure: %s", exc)
            raise ValueError(f"Unexpected OpenAI response structure: {exc}") from exc

        usage = resp_body.get("usage", {})
        prompt_tokens: int = usage.get("prompt_tokens", 0)
        completion_tokens: int = usage.get("completion_tokens", 0)

        logger.debug(
            "OpenAI call ok: model=%s latency=%.0fms tokens=%d+%d",
            self._model, latency_ms, prompt_tokens, completion_tokens,
        )

        return LLMCallResult(
            raw_json=choice_content,
            provider=self.provider_name,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )
