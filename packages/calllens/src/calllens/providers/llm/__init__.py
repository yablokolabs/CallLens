"""LLM providers."""

from calllens.config import Settings, get_settings
from calllens.providers.llm.base import LLMProvider
from calllens.providers.llm.errors import LLMError, LLMNotConfigured, LLMOutputError
from calllens.providers.llm.mock import MockLLMProvider


def _effective_provider(settings: Settings) -> str:
    """Resolve provider for agentic-ai: MODEL_PROVIDER > LLM_PROVIDER > mock."""
    # MODEL_PROVIDER is the spec's Bedrock toggle; COACH_MODEL_PROVIDER overrides for coach only
    for attr in ("model_provider", "llm_provider"):
        val = getattr(settings, attr, None)
        if val:
            return str(val).lower()
    return "mock"


def get_llm_provider(settings: Settings | None = None, *, force_mock: bool = False) -> LLMProvider:
    """Return the configured reasoning LLM provider.

    Defaults to the mock provider so local development and CI never require
    a paid API key. Set ``LLM_PROVIDER`` or ``MODEL_PROVIDER`` to opt into a real vendor.
    Bedrock is available as ``MODEL_PROVIDER=bedrock`` or ``LLM_PROVIDER=bedrock``.
    """
    settings = settings or get_settings()
    if force_mock:
        return MockLLMProvider()
    provider = _effective_provider(settings)
    if provider == "mock":
        return MockLLMProvider()
    if provider == "openai":
        from calllens.providers.llm.openai import OpenAILLMProvider

        return OpenAILLMProvider(settings)
    if provider == "anthropic":
        from calllens.providers.llm.anthropic import AnthropicLLMProvider

        return AnthropicLLMProvider(settings)
    if provider == "compatible":
        from calllens.providers.llm.compatible import CompatibleLLMProvider

        return CompatibleLLMProvider(settings)
    if provider == "bedrock":
        from calllens.providers.llm.bedrock import BedrockLLMProvider

        return BedrockLLMProvider(settings)
    raise LLMError(f"unknown LLM_PROVIDER/MODEL_PROVIDER: {provider!r}")


__all__ = ["LLMError", "LLMNotConfigured", "LLMOutputError", "MockLLMProvider", "get_llm_provider"]
