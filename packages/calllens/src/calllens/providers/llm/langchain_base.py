"""Shared implementation for LangChain-backed LLM providers."""

from __future__ import annotations

import json
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from calllens.providers.llm.errors import LLMOutputError

logger = logging.getLogger(__name__)


class LangChainLLMProvider:
    """Implements the LLMProvider protocol over a LangChain chat model."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model
        self._provider_name = getattr(model, "__class__", type(model)).__name__

    @property
    def model_name(self) -> str:
        return str(getattr(self._model, "model_name", "") or getattr(self._model, "model", ""))

    async def completion(self, prompt: str, *, system: str | None = None) -> str:
        messages = ([SystemMessage(content=system)] if system else []) + [
            HumanMessage(content=prompt)
        ]
        response = await self._model.ainvoke(messages)
        return str(response.content)

    async def structured_completion(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        system: str | None = None,
    ) -> BaseModel:
        messages = ([SystemMessage(content=system)] if system else []) + [
            HumanMessage(content=prompt)
        ]
        try:
            structured = self._model.with_structured_output(schema)
            response = await structured.ainvoke(messages)
            if isinstance(response, schema):
                return response
            # Some providers return a dict; coerce through the schema.
            if isinstance(response, dict):
                return schema.model_validate(response)
        except Exception as exc:
            raise LLMOutputError(
                f"structured completion failed for {schema.__name__}: {exc}"
            ) from exc

        # Final fallback: parse raw JSON content.
        raw = getattr(response, "content", None)
        if isinstance(raw, str):
            try:
                return schema.model_validate(json.loads(raw))
            except (json.JSONDecodeError, Exception) as exc:  # noqa: BLE001
                raise LLMOutputError(f"unparseable output for {schema.__name__}: {exc}") from exc
        raise LLMOutputError(f"unexpected structured output for {schema.__name__}")
