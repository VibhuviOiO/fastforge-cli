"""Qdrant vector store provider."""

from __future__ import annotations

from typing import Any

import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.vector_store import SearchResponse, SearchResult, VectorStoreProvider
from app.ai.vector_store.registry import register_vector_store

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_vector_store("qdrant")
class QdrantStore(VectorStoreProvider):
    """Qdrant vector database provider.

    Requires: pip install qdrant-client
    """

    def __init__(self, settings: AISettings) -> None:
        self._host = settings.qdrant_host
        self._port = settings.qdrant_port
        self._api_key = settings.qdrant_api_key
        self._collection = settings.vector_store_collection
        self._dimensions = settings.embedding_dimensions
        self._client = None

    async def initialize(self) -> None:
        """Initialize Qdrant client."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError as e:
            raise ImportError(
                "qdrant-client is required for Qdrant vector store. "
                "Install with: pip install qdrant-client"
            ) from e

        self._client = QdrantClient(
            host=self._host,
            port=self._port,
            api_key=self._api_key or None,
        )

        # Create collection if it doesn't exist
        collections = self._client.get_collections().collections
        if not any(c.name == self._collection for c in collections):
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=int(self._dimensions),
                    distance=Distance.COSINE,
                ),
            )

    @property
    def name(self) -> str:
        return "qdrant"

    @tracer.start_as_current_span("vector_store.qdrant.search")
    async def search(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        namespace: str | None = None,
    ) -> SearchResponse:
        """Search Qdrant collection."""
        import asyncio
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results_raw = await asyncio.to_thread(
            self._client.search,
            collection_name=self._collection,
            query_vector=vector,
            limit=top_k,
            query_filter=qdrant_filter,
        )

        results = [
            SearchResult(
                id=str(hit.id),
                score=hit.score,
                metadata=hit.payload or {},
                content=hit.payload.get("content", "") if hit.payload else "",
            )
            for hit in results_raw
        ]

        return SearchResponse(results=results, total_count=len(results))

    @tracer.start_as_current_span("vector_store.qdrant.upsert")
    async def upsert(
        self,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        namespace: str | None = None,
    ) -> int:
        """Upsert vectors to Qdrant."""
        import asyncio
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=doc_id,
                vector=vector,
                payload=metadata[i] if metadata else {},
            )
            for i, (doc_id, vector) in enumerate(zip(ids, vectors))
        ]

        await asyncio.to_thread(
            self._client.upsert,
            collection_name=self._collection,
            points=points,
        )
        return len(vectors)

    @tracer.start_as_current_span("vector_store.qdrant.delete")
    async def delete(self, ids: list[str], namespace: str | None = None) -> int:
        """Delete vectors from Qdrant."""
        import asyncio

        await asyncio.to_thread(
            self._client.delete,
            collection_name=self._collection,
            points_selector=ids,
        )
        return len(ids)

    async def close(self) -> None:
        """Close Qdrant client."""
        if self._client:
            self._client.close()
