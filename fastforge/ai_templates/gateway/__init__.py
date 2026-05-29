"""AI Gateway — abstract client for LLM API calls via a gateway (LiteLLM, BiFrost)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompletionRequest:
    """Uniform request DTO for LLM completions."""

    model: str
    messages: list[dict[str, Any]]
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Uniform response DTO from LLM completions."""

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)


class GatewayClient(ABC):
    """Abstract base for AI gateway clients.

    The gateway handles: routing, fallback, rate limiting, budgeting,
    and model management. This client just calls it.
    """

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a completion request through the gateway."""
        ...

    @abstractmethod
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Generate embeddings via the gateway (if supported)."""
        ...

    async def close(self) -> None:
        """Cleanup resources. Override if needed."""
        pass
