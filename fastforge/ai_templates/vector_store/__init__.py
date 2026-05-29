"""Vector store providers — abstract base for similarity search."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """A single search result from the vector store."""

    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    content: str = ""


@dataclass
class SearchResponse:
    """Response from a vector similarity search."""

    results: list[SearchResult]
    query_vector: list[float] | None = None
    total_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStoreProvider(ABC):
    """Abstract base for vector store providers.

    Implementations wrap a specific vector database and provide
    a uniform interface for indexing and searching.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        ...

    @abstractmethod
    async def search(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        namespace: str | None = None,
    ) -> SearchResponse:
        """Perform a vector similarity search.

        Args:
            vector: Query vector.
            top_k: Number of results to return.
            filters: Optional metadata filters.
            namespace: Optional namespace/partition for multi-tenant isolation.

        Returns:
            SearchResponse with ranked results.
        """
        ...

    @abstractmethod
    async def upsert(
        self,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        namespace: str | None = None,
    ) -> int:
        """Insert or update vectors.

        Returns: Number of vectors upserted.
        """
        ...

    @abstractmethod
    async def delete(
        self,
        ids: list[str],
        namespace: str | None = None,
    ) -> int:
        """Delete vectors by ID.

        Returns: Number of vectors deleted.
        """
        ...

    async def close(self) -> None:
        """Cleanup resources. Override if needed."""
        pass
