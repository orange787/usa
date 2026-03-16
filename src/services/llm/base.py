"""Abstract LLM interface."""

from __future__ import annotations

import abc
from typing import Any


class BaseLLM(abc.ABC):
    """Abstract base for LLM providers."""

    @abc.abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: str | None = None,
    ) -> str:
        """Send a completion request and return the text response."""

    @abc.abstractmethod
    async def complete_json(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send a completion request and parse the response as JSON."""
