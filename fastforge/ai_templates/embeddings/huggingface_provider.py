"""HuggingFace embedding provider — local sentence-transformers inference."""

from __future__ import annotations

import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.embeddings import EmbeddingProvider, EmbeddingResult
from app.ai.embeddings.registry import register_embedding_provider

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_embedding_provider("huggingface")
class HuggingFaceEmbeddings(EmbeddingProvider):
    """HuggingFace sentence-transformers embedding provider.

    Requires: pip install sentence-transformers
    Runs inference locally using the specified model.
    """

    def __init__(self, settings: AISettings) -> None:
        self._model_name = settings.huggingface_model
        self._dimensions = settings.embedding_dimensions
        self._model = None

    def _load_model(self):
        """Lazy-load the sentence transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers is required for HuggingFace embeddings. "
                    "Install with: pip install sentence-transformers"
                ) from e
            self._model = SentenceTransformer(self._model_name)
            self._dimensions = self._model.get_sentence_embedding_dimension()

    @property
    def name(self) -> str:
        return "huggingface"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @tracer.start_as_current_span("embeddings.huggingface.embed")
    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings using local sentence-transformers model."""
        import asyncio

        def _encode() -> list[list[float]]:
            self._load_model()
            return self._model.encode(texts, normalize_embeddings=True).tolist()

        vectors = await asyncio.to_thread(_encode)
        return EmbeddingResult(
            vectors=vectors,
            model=self._model_name,
            dimensions=len(vectors[0]) if vectors else self._dimensions,
        )

    @tracer.start_as_current_span("embeddings.huggingface.embed_query")
    async def embed_query(self, query: str) -> list[float]:
        """Generate a single query embedding."""
        result = await self.embed([query])
        return result.vectors[0]
