"""LLM factory - create the right provider based on config."""

from __future__ import annotations

from src.core.config import get_settings
from src.services.llm.base import BaseLLM
from src.services.llm.claude import ClaudeLLM
from src.services.llm.openai_llm import OpenAILLM


def create_llm(provider: str | None = None) -> BaseLLM:
    """Create an LLM instance based on provider name.

    Args:
        provider: "claude" or "openai". Defaults to config setting.
    """
    settings = get_settings()
    provider = provider or settings.llm_provider

    if provider == "claude":
        return ClaudeLLM(
            api_key=settings.anthropic_api_key,
            model=settings.claude_model,
        )
    elif provider == "openai":
        return OpenAILLM(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
