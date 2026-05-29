"""BiFrost gateway client — routes LLM calls through BiFrost proxy."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.gateway import CompletionRequest, CompletionResponse, GatewayClient
from app.ai.gateway.registry import register_gateway

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_gateway("bifrost")
class BiFrostClient(GatewayClient):
    """BiFrost gateway client.

    BiFrost provides: multi-model routing, cost management, rate limiting,
    and fallback strategies. This client calls its API.

    NOTE: This is a stub. Replace with actual BiFrost SDK integration
    once your BiFrost instance is configured.
    """

    def __init__(self, settings: AISettings) -> None:
        self._base_url = settings.gateway_base_url.rstrip("/")
        self._api_key = settings.gateway_api_key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "X-API-Key": self._api_key,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

    @tracer.start_as_current_span("gateway.bifrost.complete")
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send completion request to BiFrost."""
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            payload["tools"] = request.tools
            if request.tool_choice is not None:
                payload["tool_choice"] = request.tool_choice

        logger.debug("gateway.bifrost.request", model=request.model)

        # BiFrost uses OpenAI-compatible endpoint
        response = await self._client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        message = data["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []

        return CompletionResponse(
            content=message.get("content") or "",
            model=data.get("model", request.model),
            usage=data.get("usage", {}),
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
            metadata={"tool_calls": tool_calls} if tool_calls else {},
        )

    @tracer.start_as_current_span("gateway.bifrost.embed")
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Generate embeddings via BiFrost."""
        payload = {
            "model": model or "text-embedding-3-small",
            "input": texts,
        }

        response = await self._client.post("/v1/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()

        return [item["embedding"] for item in data["data"]]

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
