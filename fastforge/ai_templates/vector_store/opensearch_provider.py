"""OpenSearch vector store provider."""

from __future__ import annotations

from typing import Any

import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.vector_store import SearchResponse, SearchResult, VectorStoreProvider
from app.ai.vector_store.registry import register_vector_store

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_vector_store("opensearch")
class OpenSearchStore(VectorStoreProvider):
    """OpenSearch vector store with k-NN plugin.

    Requires: pip install opensearch-py
    """

    def __init__(self, settings: AISettings) -> None:
        self._host = settings.opensearch_host
        self._port = settings.opensearch_port
        self._index = settings.opensearch_index
        self._username = settings.opensearch_username
        self._password = settings.opensearch_password
        self._use_ssl = settings.opensearch_use_ssl
        self._verify_certs = settings.opensearch_verify_certs
        self._dimensions = settings.embedding_dimensions
        self._client = None

    async def initialize(self) -> None:
        """Initialize OpenSearch client."""
        try:
            from opensearchpy import OpenSearch
        except ImportError as e:
            raise ImportError(
                "opensearch-py is required for OpenSearch vector store. "
                "Install with: pip install opensearch-py"
            ) from e

        auth = (self._username, self._password) if self._username else None
        self._client = OpenSearch(
            hosts=[{"host": self._host, "port": self._port}],
            http_auth=auth,
            use_ssl=self._use_ssl,
            verify_certs=self._verify_certs,
        )

        # Create index with k-NN mapping if it doesn't exist
        if not self._client.indices.exists(index=self._index):
            self._client.indices.create(
                index=self._index,
                body={
                    "settings": {"index": {"knn": True}},
                    "mappings": {
                        "properties": {
                            "vector": {
                                "type": "knn_vector",
                                "dimension": int(self._dimensions),
                                "method": {
                                    "name": "hnsw",
                                    "space_type": "cosinesimil",
                                    "engine": "nmslib",
                                },
                            },
                            "content": {"type": "text"},
                            "metadata": {"type": "object", "enabled": True},
                        }
                    },
                },
            )

    @property
    def name(self) -> str:
        return "opensearch"

    @tracer.start_as_current_span("vector_store.opensearch.search")
    async def search(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        namespace: str | None = None,
    ) -> SearchResponse:
        """Search OpenSearch using k-NN."""
        import asyncio

        query = {
            "size": top_k,
            "query": {
                "knn": {
                    "vector": {
                        "vector": vector,
                        "k": top_k,
                    }
                }
            },
        }

        if filters:
            query["query"] = {
                "bool": {
                    "must": [query["query"]],
                    "filter": [{"term": {f"metadata.{k}": v}} for k, v in filters.items()],
                }
            }

        response = await asyncio.to_thread(
            self._client.search, index=self._index, body=query
        )

        results = []
        for hit in response["hits"]["hits"]:
            results.append(
                SearchResult(
                    id=hit["_id"],
                    score=hit["_score"],
                    metadata=hit["_source"].get("metadata", {}),
                    content=hit["_source"].get("content", ""),
                )
            )

        return SearchResponse(
            results=results,
            total_count=response["hits"]["total"]["value"],
        )

    @tracer.start_as_current_span("vector_store.opensearch.upsert")
    async def upsert(
        self,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        namespace: str | None = None,
    ) -> int:
        """Upsert vectors to OpenSearch."""
        import asyncio

        def _do_upsert() -> None:
            for i, (vec_id, vector) in enumerate(zip(ids, vectors)):
                meta_dict = dict(metadata[i]) if metadata else {}
                content = meta_dict.pop("content", "")
                doc = {
                    "vector": vector,
                    "content": content,
                    "metadata": meta_dict,
                }
                self._client.index(index=self._index, id=vec_id, body=doc)

        await asyncio.to_thread(_do_upsert)
        return len(vectors)

    @tracer.start_as_current_span("vector_store.opensearch.delete")
    async def delete(self, ids: list[str], namespace: str | None = None) -> int:
        """Delete vectors from OpenSearch."""
        import asyncio

        def _do_delete() -> None:
            for doc_id in ids:
                self._client.delete(index=self._index, id=doc_id, ignore=[404])

        await asyncio.to_thread(_do_delete)
        return len(ids)

    async def close(self) -> None:
        """Close OpenSearch client."""
        if self._client:
            self._client.close()
