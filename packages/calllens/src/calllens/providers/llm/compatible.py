"""OpenAI-compatible reasoning provider (Ollama, vLLM, LM Studio...)."""

from __future__ import annotations

from calllens.config import Settings, get_settings
from calllens.providers.llm.errors import LLMNotConfigured
from calllens.providers.llm.langchain_base import LangChainLLMProvider


class CompatibleLLMProvider(LangChainLLMProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        if not settings.compatible_base_url:
            raise LLMNotConfigured(
                "COMPATIBLE_BASE_URL is not set; configure it for the 'compatible' LLM provider"
            )
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            model=settings.llm_model,
            base_url=settings.compatible_base_url,
            api_key=settings.compatible_api_key or "not-needed",
            temperature=settings.llm_temperature,
            max_retries=2,
        )
        super().__init__(model)
