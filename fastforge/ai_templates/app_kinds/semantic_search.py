"""Semantic Search orchestrator — search pipeline skeleton.

This is the infrastructure skeleton. You add your business logic:
- Query rewriting prompts
- Client-specific parameter adapters
- Result post-processing / field filtering
- Reranking calls
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog
from opentelemetry import trace

from app.ai.embeddings import EmbeddingProvider
from app.ai.gateway import GatewayClient, CompletionRequest
from app.ai.vector_store import VectorStoreProvider, SearchResponse

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass
class SearchQuery:
    """Normalized search query DTO.

    Your adapter layer converts client-specific parameters into this uniform DTO.
    """

    text: str
    top_k: int = 10
    filters: dict[str, Any] = field(default_factory=dict)
    namespace: str | None = None
    rewrite_query: bool = False
    include_fields: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResultItem:
    """A single search result for the client response."""

    id: str
    score: float
    content: str = ""
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResultResponse:
    """Final response returned to the client."""

    results: list[SearchResultItem]
    query: str
    total_count: int = 0
    rewritten_query: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SearchOrchestrator:
    """Semantic search pipeline orchestrator.

    Pipeline steps:
    1. (Optional) Rewrite query via LLM gateway
    2. Generate embedding for the query
    3. Search vector store
    4. (Optional) Rerank results
    5. Filter fields based on client config
    6. Return response

    This class provides the pipeline structure. Override or extend
    individual steps for your business logic.
    """

    def __init__(
        self,
        gateway: GatewayClient,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStoreProvider,
    ) -> None:
        self._gateway = gateway
        self._embedding = embedding_provider
        self._vector_store = vector_store

    @tracer.start_as_current_span("search.orchestrate")
    async def search(self, query: SearchQuery) -> SearchResultResponse:
        """Execute the full search pipeline."""
        search_text = query.text
        rewritten = None

        # Step 1: Optional query rewriting via LLM
        if query.rewrite_query:
            rewritten = await self._rewrite_query(query.text)
            search_text = rewritten

        # Step 2: Generate embedding
        query_vector = await self._embedding.embed_query(search_text)

        # Step 3: Vector similarity search
        search_response = await self._vector_store.search(
            vector=query_vector,
            top_k=query.top_k,
            filters=query.filters,
            namespace=query.namespace,
        )

        # Step 4: Build response (override for reranking, field filtering, etc.)
        results = self._build_results(search_response, query.include_fields)

        return SearchResultResponse(
            results=results,
            query=query.text,
            total_count=search_response.total_count,
            rewritten_query=rewritten,
        )

    @tracer.start_as_current_span("search.rewrite_query")
    async def _rewrite_query(self, query: str) -> str:
        """Rewrite query using LLM for better vector search retrieval.

        Override this method to customize the rewriting prompt.
        """
        request = CompletionRequest(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a search query optimizer. Rewrite the user's query "
                        "to be more effective for semantic vector search. "
                        "Return only the rewritten query, nothing else."
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=256,
        )
        response = await self._gateway.complete(request)
        return response.content.strip()

    def _build_results(
        self, search_response: SearchResponse, include_fields: list[str]
    ) -> list[SearchResultItem]:
        """Convert vector store results to client response format.

        Override this method for custom field filtering, reranking, etc.
        """
        results = []
        for hit in search_response.results:
            fields = hit.metadata
            if include_fields:
                fields = {k: v for k, v in fields.items() if k in include_fields}

            results.append(
                SearchResultItem(
                    id=hit.id,
                    score=hit.score,
                    content=hit.content,
                    fields=fields,
                )
            )
        return results
