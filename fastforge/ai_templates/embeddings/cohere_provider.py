"""Cohere embedding provider."""

from __future__ import annotations

import httpx
import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.embeddings import EmbeddingProvider, EmbeddingResult
from app.ai.embeddings.registry import register_embedding_provider

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_embedding_provider("cohere")
class CohereEmbeddings(EmbeddingProvider):
    """Cohere embedding provider (embed-english-v3.0, etc.)."""

    def __init__(self, settings: AISettings) -> None:
        self._model = settings.embedding_model
        self._dimensions = settings.embedding_dimensions
        self._client = httpx.AsyncClient(
            base_url="https://api.cohere.ai/v1",
            headers={
                "Authorization": f"Bearer {settings.cohere_api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0),
        )

    @property
    def name(self) -> str:
        return "cohere"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @tracer.start_as_current_span("embeddings.cohere.embed")
    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings via Cohere API."""
        payload = {
            "model": self._model,
            "texts": texts,
            "input_type": "search_document",
            "truncate": "END",
        }

        response = await self._client.post("/embed", json=payload)
        response.raise_for_status()
        data = response.json()

        return EmbeddingResult(
            vectors=data["embeddings"],
            model=self._model,
            dimensions=len(data["embeddings"][0]) if data["embeddings"] else self._dimensions,
        )

    @tracer.start_as_current_span("embeddings.cohere.embed_query")
    async def embed_query(self, query: str) -> list[float]:
        """Generate a single query embedding (uses search_query input type)."""
        payload = {
            "model": self._model,
            "texts": [query],
            "input_type": "search_query",
            "truncate": "END",
        }
        response = await self._client.post("/embed", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]
