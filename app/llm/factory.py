"""Backend factory — creates the appropriate LLMBackend from settings."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.settings import GlobalSettings
from app.llm.base import LLMBackend

logger = get_logger(__name__)


def create_backend(settings: GlobalSettings) -> LLMBackend:
    provider = settings.llm_provider.lower()

    if provider == "mock":
        from app.llm.backends.mock_backend import MockBackend
        logger.info("Using MockBackend (seed=%d)", settings.seed)
        return MockBackend(seed=settings.seed)

    if provider in ("openai", "openai_compatible"):
        from app.llm.backends.openai_compatible import OpenAICompatibleBackend
        logger.info("Using OpenAICompatibleBackend (model=%s)", settings.llm_model)
        return OpenAICompatibleBackend(
            api_key=settings.llm_api_key,
            model=settings.llm_model or "gpt-4o-mini",
            base_url=settings.llm_base_url or "https://api.openai.com/v1",
            timeout=settings.llm_timeout_s,
        )

    raise ValueError(f"Unknown LLM provider: {provider!r}")
