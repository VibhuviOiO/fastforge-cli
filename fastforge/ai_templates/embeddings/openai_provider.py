"""OpenAI embedding provider."""

from __future__ import annotations

import httpx
import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.embeddings import EmbeddingProvider, EmbeddingResult
from app.ai.embeddings.registry import register_embedding_provider

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_embedding_provider("openai")
class OpenAIEmbeddings(EmbeddingProvider):
    """OpenAI text embeddings (text-embedding-3-small/large, ada-002)."""

    def __init__(self, settings: AISettings) -> None:
        self._model = settings.embedding_model
        self._dimensions = settings.embedding_dimensions
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

    @property
    def name(self) -> str:
        return "openai"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @tracer.start_as_current_span("embeddings.openai.embed")
    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings via OpenAI API."""
        payload = {"model": self._model, "input": texts}
        if self._dimensions and "3-" in self._model:
            payload["dimensions"] = self._dimensions

        response = await self._client.post("/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()

        vectors = [item["embedding"] for item in data["data"]]
        token_count = data.get("usage", {}).get("total_tokens", 0)

        return EmbeddingResult(
            vectors=vectors,
            model=self._model,
            dimensions=len(vectors[0]) if vectors else self._dimensions,
            token_count=token_count,
        )

    @tracer.start_as_current_span("embeddings.openai.embed_query")
    async def embed_query(self, query: str) -> list[float]:
        """Generate a single query embedding."""
        result = await self.embed([query])
        return result.vectors[0]
