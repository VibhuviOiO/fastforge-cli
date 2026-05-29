"""Google Gemini embedding provider."""

from __future__ import annotations

import httpx
import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.embeddings import EmbeddingProvider, EmbeddingResult
from app.ai.embeddings.registry import register_embedding_provider

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_embedding_provider("gemini")
class GeminiEmbeddings(EmbeddingProvider):
    """Google Gemini/PaLM embedding provider."""

    def __init__(self, settings: AISettings) -> None:
        self._model = settings.gemini_model
        self._dimensions = settings.embedding_dimensions
        self._api_key = settings.gemini_api_key
        self._client = httpx.AsyncClient(
            base_url="https://generativelanguage.googleapis.com/v1beta",
            timeout=httpx.Timeout(30.0),
        )

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @tracer.start_as_current_span("embeddings.gemini.embed")
    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings via Gemini API."""
        vectors = []
        for text in texts:
            payload = {
                "model": self._model,
                "content": {"parts": [{"text": text}]},
            }
            response = await self._client.post(
                f"/{self._model}:embedContent",
                params={"key": self._api_key},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            vectors.append(data["embedding"]["values"])

        return EmbeddingResult(
            vectors=vectors,
            model=self._model,
            dimensions=len(vectors[0]) if vectors else self._dimensions,
        )

    @tracer.start_as_current_span("embeddings.gemini.embed_query")
    async def embed_query(self, query: str) -> list[float]:
        """Generate a single query embedding."""
        result = await self.embed([query])
        return result.vectors[0]
