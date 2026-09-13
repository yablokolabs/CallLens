"""Sarvam Strands adapter — OpenAI-compatible but string-only content.

Sarvam's /v1/chat/completions requires `content: string` not
`content: [{type: text, text: ...}]`. Strands OpenAIModel sends arrays
which Sarvam rejects with 'Input should be a valid string'.

This subclass stringifies user/assistant content while preserving
tool_calls/tool messages, and disables reasoning by default (sarvam-105b
defaults to reasoning_effort=low which can exhaust max_tokens on short
turns, returning length with empty content).

Also maps SARVAM_API_KEY to the bearer auth expected by OpenAI client.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from strands.models.openai import OpenAIModel

_SARVAM_BASE = "https://api.sarvam.ai/v1"
_SARVAM_MODEL = "sarvam-105b"


def _read_sarvam_key() -> str | None:
    val = os.getenv("SARVAM_API_KEY")
    if val and val.strip():
        return val.strip()
    # Fallback: read .env directly (pydantic may not have loaded it yet in some entrypoints)
    try:
        for line in Path(".env").read_text().splitlines():
            line = line.strip()
            if line.startswith("SARVAM_API_KEY="):
                v = line.split("=", 1)[1].strip().strip("'\"")
                if v:
                    return v
    except Exception:
        pass
    return None


class SarvamModel(OpenAIModel):
    """Strands Model backed by Sarvam AI (OpenAI-compatible, string content)."""

    def __init__(
        self,
        *,
        model_id: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        key = api_key or _read_sarvam_key()
        if not key:
            raise ValueError("SARVAM_API_KEY is not set (env or .env)")
        mid = model_id or _SARVAM_MODEL
        base = base_url or _SARVAM_BASE
        # Default params: disable reasoning by default, generous max_tokens
        # Must be large enough for tool calls + structured CoachDecision (incl. evidence).
        # 1200 was truncating record_agent_decision / CoachDecision (see api logs).
        default_params: dict[str, Any] = {"max_tokens": 3500}
        # Sarvam: reasoning_effort must be None to disable thinking
        # Pass via extra_body reasoning_effort=None — via params extra_body
        # But OpenAI client supports extra_body via request extras; we set via params
        # Strands passes params as-is to create(**request). For Sarvam we need
        # reasoning_effort=None. We put it in params so it becomes top-level.
        # OpenAI's API ignores unknown top-level? Sarvam docs use reasoning_effort
        # as sibling to messages/model, so it works if passed through.
        if params:
            default_params.update(params)
        # Ensure reasoning disabled unless explicitly requested
        if "reasoning_effort" not in default_params:
            default_params["reasoning_effort"] = None

        super().__init__(
            client_args={"base_url": base, "api_key": key},
            model_id=mid,
            params=default_params,
            **kwargs,
        )

    def format_request(  # type: ignore[override]
        self,
        messages: Any,
        tool_specs: Any | None = None,
        system_prompt: str | None = None,
        tool_choice: Any | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        req = super().format_request(messages, tool_specs, system_prompt, tool_choice, **kwargs)  # type: ignore[arg-type]
        # Sarvam requires string content for user/assistant/system, not array
        for m in req.get("messages", []):
            content = m.get("content")
            if isinstance(content, list):
                # Join text parts into a single string
                parts: list[str] = []
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        parts.append(str(block["text"]))
                # Sarvam expects empty string allowed, but prefer joining
                m["content"] = "\n".join(parts) if parts else ""
        # Remove reasoning_content tool handling that Sarvam doesn't need
        return req
