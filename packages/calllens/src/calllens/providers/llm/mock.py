"""Mock LLM provider.

Deterministic, offline, and fast. Tests and local development register
handlers keyed by schema; unregistered schemas fall back to a default
instance built with field defaults.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, cast

from pydantic import BaseModel

from calllens.providers.llm.errors import LLMOutputError

Handler = Callable[[str, type[BaseModel]], BaseModel]


def _default_instance(schema: type[BaseModel]) -> BaseModel:
    """Build a complete, attribute-safe instance from schema defaults."""
    values: dict[str, Any] = {}
    for name, field in schema.model_fields.items():
        if not field.is_required():
            if field.default_factory is not None:
                # CallLens registers zero-argument default factories only.
                factory = cast(Callable[[], Any], field.default_factory)
                values[name] = factory()
            elif field.default is not None:
                values[name] = field.default
    return schema.model_construct(**values)


class MockLLMProvider:
    """A deterministic LLM provider for tests and offline development."""

    def __init__(self, handlers: dict[type[BaseModel], Handler] | None = None) -> None:
        self._handlers: dict[type[BaseModel], Handler] = dict(handlers or {})
        self.completion_calls: list[str] = []
        self.structured_calls: list[tuple[str, type[BaseModel]]] = []

    def register(self, schema: type[BaseModel], handler: Handler) -> None:
        self._handlers[schema] = handler

    def register_factory(self, factory: Callable[[], BaseModel]) -> None:
        """Register a factory that returns the schema via its return annotation."""
        schema = inspect.signature(factory).return_annotation
        self.register(schema, lambda prompt, _schema: factory())

    async def completion(self, prompt: str, *, system: str | None = None) -> str:
        self.completion_calls.append(prompt)
        return "mock completion"

    async def structured_completion(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        system: str | None = None,
    ) -> BaseModel:
        self.structured_calls.append((prompt, schema))
        handler = self._handlers.get(schema)
        if handler is None:
            return _default_instance(schema)
        try:
            result = handler(prompt, schema)
        except Exception as exc:
            raise LLMOutputError(f"mock handler failed for {schema.__name__}: {exc}") from exc
        if not isinstance(result, schema):
            raise LLMOutputError(
                f"mock handler returned {type(result).__name__}, expected {schema.__name__}"
            )
        return result
