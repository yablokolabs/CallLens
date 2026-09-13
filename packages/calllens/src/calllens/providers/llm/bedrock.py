"""Amazon Bedrock reasoning provider (via LangChain ChatBedrockConverse).

This provider is tagged strands-agents-sdk / agentic-ai: it implements the
same LLMProvider protocol as the OpenAI/Anthropic providers so the Strands
Coach agent can run on Bedrock via configuration alone.

Requires: boto3 already in pyproject; actual Bedrock calls use langchain-aws
if available, otherwise boto3 converse directly. We prefer langchain-aws
because the project's structured_completion depends on JSON schema mode.
"""

from __future__ import annotations

from calllens.config import Settings, get_settings
from calllens.providers.llm.errors import LLMNotConfigured
from calllens.providers.llm.langchain_base import LangChainLLMProvider


class BedrockLLMProvider(LangChainLLMProvider):
    """LLM provider backed by Amazon Bedrock (configurable via env).

    Env:
      MODEL_PROVIDER=bedrock  (or LLM_PROVIDER=bedrock, COACH_MODEL_PROVIDER=bedrock)
      AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
      BEDROCK_MODEL_ID / COACH_MODEL_ID / LLM_MODEL
    """

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        model_id = settings.bedrock_model_id or settings.coach_model_id or settings.llm_model
        region = settings.aws_region
        if not model_id:
            raise LLMNotConfigured(
                "BEDROCK_MODEL_ID (or COACH_MODEL_ID / LLM_MODEL) is not set for Bedrock"
            )
        # Prefer langchain-aws ChatBedrockConverse (modern), fall back to langchain_aws alias
        try:
            from langchain_aws import ChatBedrockConverse

            kwargs: dict = {"model": model_id}
            if region:
                kwargs["region_name"] = region
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                kwargs["aws_access_key_id"] = settings.aws_access_key_id
                kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            model = ChatBedrockConverse(**kwargs)
        except ImportError as exc:  # pragma: no cover - missing langchain-aws
            raise LLMNotConfigured(
                "langchain-aws is required for Bedrock provider: pip install langchain-aws"
            ) from exc
        super().__init__(model)
