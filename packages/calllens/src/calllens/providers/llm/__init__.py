"""LLM providers."""

from calllens.config import Settings, get_settings
from calllens.providers.llm.base import LLMProvider
from calllens.providers.llm.errors import LLMError, LLMNotConfigured, LLMOutputError
from calllens.providers.llm.mock import MockLLMProvider


def get_llm_provider(settings: Settings | None = None, *, force_mock: bool = False) -> LLMProvider:
    """Return the configured reasoning LLM provider.

    Defaults to the mock provider so local development and CI never require
    a paid API key. Set ``LLM_PROVIDER`` to opt into a real vendor.
    """
    settings = settings or get_settings()
    if force_mock or settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "openai":
        from calllens.providers.llm.openai import OpenAILLMProvider

        return OpenAILLMProvider(settings)
    if settings.llm_provider == "anthropic":
        from calllens.providers.llm.anthropic import AnthropicLLMProvider

        return AnthropicLLMProvider(settings)
    if settings.llm_provider == "compatible":
        from calllens.providers.llm.compatible import CompatibleLLMProvider

        return CompatibleLLMProvider(settings)
    raise LLMError(f"unknown LLM_PROVIDER: {settings.llm_provider!r}")


__all__ = ["LLMError", "LLMNotConfigured", "LLMOutputError", "MockLLMProvider", "get_llm_provider"]
