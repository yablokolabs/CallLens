"""OpenAI reasoning provider (LangChain ChatOpenAI)."""

from __future__ import annotations

from calllens.config import Settings, get_settings
from calllens.providers.llm.errors import LLMNotConfigured
from calllens.providers.llm.langchain_base import LangChainLLMProvider


class OpenAILLMProvider(LangChainLLMProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        if not settings.openai_api_key:
            raise LLMNotConfigured(
                "OPENAI_API_KEY is not set; configure it in the environment (.env)"
            )
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
            max_retries=2,
        )
        super().__init__(model)
