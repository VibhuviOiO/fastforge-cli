"""Local embedding provider — runs inference on-device without API calls."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.embeddings import EmbeddingProvider, EmbeddingResult
from app.ai.embeddings.registry import register_embedding_provider

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_embedding_provider("local")
class LocalEmbeddings(EmbeddingProvider):
    """Strictly-offline embedding provider using sentence-transformers.

    Unlike the `huggingface` provider, this one refuses network calls:
    it sets ``TRANSFORMERS_OFFLINE=1`` and ``HF_HUB_OFFLINE=1`` before
    loading the model. ``AI_HUGGINGFACE_MODEL`` must point to either a
    local filesystem path or a model that is already cached.

    Requires: pip install sentence-transformers
    """

    def __init__(self, settings: AISettings) -> None:
        self._model_name = settings.huggingface_model
        self._dimensions = settings.embedding_dimensions
        self._model = None

    def _load_model(self):
        """Lazy-load the model in strictly-offline mode."""
        if self._model is not None:
            return
        try:
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for local embeddings. "
                "Install with: pip install sentence-transformers"
            ) from e

        path = Path(self._model_name)
        if path.is_absolute() and not path.exists():
            raise FileNotFoundError(
                f"Local model path does not exist: {self._model_name}. "
                "Pre-download the model and set AI_HUGGINGFACE_MODEL to its path."
            )
        self._model = SentenceTransformer(self._model_name)
        self._dimensions = self._model.get_sentence_embedding_dimension()

    @property
    def name(self) -> str:
        return "local"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @tracer.start_as_current_span("embeddings.local.embed")
    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings locally without contacting any remote API."""
        def _encode() -> list[list[float]]:
            self._load_model()
            return self._model.encode(texts, normalize_embeddings=True).tolist()

        vectors = await asyncio.to_thread(_encode)
        return EmbeddingResult(
            vectors=vectors,
            model=self._model_name,
            dimensions=len(vectors[0]) if vectors else self._dimensions,
        )

    @tracer.start_as_current_span("embeddings.local.embed_query")
    async def embed_query(self, query: str) -> list[float]:
        """Generate a single query embedding."""
        result = await self.embed([query])
        return result.vectors[0]
