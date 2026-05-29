"""Embedding providers — abstract base for text-to-vector conversion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""

    vectors: list[list[float]]
    model: str
    dimensions: int
    token_count: int = 0
    metadata: dict = field(default_factory=dict)


class EmbeddingProvider(ABC):
    """Abstract base for embedding providers.

    Implementations convert text into dense vector representations.
    Each provider wraps a specific model API (OpenAI, Gemini, etc.)
    or runs inference locally.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Output vector dimensions for the configured model."""
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            EmbeddingResult with vectors in the same order as input texts.
        """
        ...

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """Generate a single embedding for a search query.

        Some providers use different models/params for queries vs documents.
        """
        ...
