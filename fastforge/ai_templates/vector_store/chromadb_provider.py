"""ChromaDB vector store provider."""

from __future__ import annotations

from typing import Any

import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.vector_store import SearchResponse, SearchResult, VectorStoreProvider
from app.ai.vector_store.registry import register_vector_store

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_vector_store("chromadb")
class ChromaDBStore(VectorStoreProvider):
    """ChromaDB vector store provider.

    Requires: pip install chromadb
    Supports both local and client/server mode.
    """

    def __init__(self, settings: AISettings) -> None:
        self._host = settings.chromadb_host
        self._port = settings.chromadb_port
        self._collection_name = settings.vector_store_collection
        self._client = None
        self._collection = None

    async def initialize(self) -> None:
        """Initialize ChromaDB client and collection."""
        try:
            import chromadb
        except ImportError as e:
            raise ImportError(
                "chromadb is required for ChromaDB vector store. "
                "Install with: pip install chromadb"
            ) from e

        self._client = chromadb.HttpClient(host=self._host, port=self._port)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def name(self) -> str:
        return "chromadb"

    @tracer.start_as_current_span("vector_store.chromadb.search")
    async def search(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        namespace: str | None = None,
    ) -> SearchResponse:
        """Search ChromaDB collection."""
        import asyncio

        query_params = {
            "query_embeddings": [vector],
            "n_results": top_k,
            "include": ["metadatas", "documents", "distances"],
        }
        if filters:
            query_params["where"] = filters

        response = await asyncio.to_thread(self._collection.query, **query_params)

        results = []
        for i, doc_id in enumerate(response["ids"][0]):
            results.append(
                SearchResult(
                    id=doc_id,
                    score=1.0 - response["distances"][0][i],  # Convert distance to similarity
                    metadata=response["metadatas"][0][i] if response["metadatas"] else {},
                    content=response["documents"][0][i] if response["documents"] else "",
                )
            )

        return SearchResponse(results=results, total_count=len(results))

    @tracer.start_as_current_span("vector_store.chromadb.upsert")
    async def upsert(
        self,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        namespace: str | None = None,
    ) -> int:
        """Upsert vectors to ChromaDB."""
        import asyncio

        await asyncio.to_thread(
            self._collection.upsert,
            ids=ids,
            embeddings=vectors,
            metadatas=metadata,
        )
        return len(vectors)

    @tracer.start_as_current_span("vector_store.chromadb.delete")
    async def delete(self, ids: list[str], namespace: str | None = None) -> int:
        """Delete vectors from ChromaDB."""
        import asyncio

        await asyncio.to_thread(self._collection.delete, ids=ids)
        return len(ids)
