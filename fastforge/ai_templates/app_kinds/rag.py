"""RAG (Retrieval-Augmented Generation) orchestrator — pipeline skeleton.

This is the infrastructure skeleton. You add your business logic:
- Document chunking strategies
- Prompt templates for generation
- Citation formatting
- Context window management
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog
from opentelemetry import trace

from app.ai.embeddings import EmbeddingProvider
from app.ai.gateway import CompletionRequest, GatewayClient
from app.ai.vector_store import VectorStoreProvider

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass
class RAGQuery:
    """Input for the RAG pipeline."""

    question: str
    top_k: int = 5
    filters: dict[str, Any] = field(default_factory=dict)
    namespace: str | None = None
    system_prompt: str | None = None
    model: str = "gpt-4o"
    temperature: float = 0.3
    include_sources: bool = True


@dataclass
class RAGSource:
    """A source document used in the answer."""

    id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGResponse:
    """Final RAG response."""

    answer: str
    sources: list[RAGSource]
    model: str
    query: str
    metadata: dict[str, Any] = field(default_factory=dict)


class RAGOrchestrator:
    """RAG pipeline orchestrator.

    Pipeline steps:
    1. Generate embedding for the question
    2. Retrieve relevant documents from vector store
    3. Build context from retrieved documents
    4. Generate answer using LLM with context
    5. Return answer with source citations

    Override individual methods to customize behavior.
    """

    DEFAULT_SYSTEM_PROMPT = (
        "You are a helpful assistant. Answer the user's question based on the "
        "provided context. If the context doesn't contain enough information to "
        "answer, say so. Always cite which sources you used."
    )

    def __init__(
        self,
        gateway: GatewayClient,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStoreProvider,
    ) -> None:
        self._gateway = gateway
        self._embedding = embedding_provider
        self._vector_store = vector_store

    @tracer.start_as_current_span("rag.orchestrate")
    async def query(self, rag_query: RAGQuery) -> RAGResponse:
        """Execute the full RAG pipeline."""

        # Step 1: Embed the question
        query_vector = await self._embedding.embed_query(rag_query.question)

        # Step 2: Retrieve relevant documents
        search_response = await self._vector_store.search(
            vector=query_vector,
            top_k=rag_query.top_k,
            filters=rag_query.filters,
            namespace=rag_query.namespace,
        )

        # Step 3: Build context
        sources = [
            RAGSource(
                id=hit.id,
                content=hit.content,
                score=hit.score,
                metadata=hit.metadata,
            )
            for hit in search_response.results
        ]
        context = self._build_context(sources)

        # Step 4: Generate answer
        answer = await self._generate_answer(
            question=rag_query.question,
            context=context,
            system_prompt=rag_query.system_prompt or self.DEFAULT_SYSTEM_PROMPT,
            model=rag_query.model,
            temperature=rag_query.temperature,
        )

        return RAGResponse(
            answer=answer,
            sources=sources if rag_query.include_sources else [],
            model=rag_query.model,
            query=rag_query.question,
        )

    def _build_context(self, sources: list[RAGSource]) -> str:
        """Build context string from retrieved sources.

        Override for custom context formatting.
        """
        parts = []
        for i, source in enumerate(sources, 1):
            parts.append(f"[Source {i}] (score: {source.score:.3f})\n{source.content}")
        return "\n\n---\n\n".join(parts)

    @tracer.start_as_current_span("rag.generate_answer")
    async def _generate_answer(
        self,
        question: str,
        context: str,
        system_prompt: str,
        model: str,
        temperature: float,
    ) -> str:
        """Generate answer using LLM with retrieved context.

        Override to customize the prompt template.
        """
        user_message = f"Context:\n{context}\n\nQuestion: {question}"

        request = CompletionRequest(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=2048,
        )
        response = await self._gateway.complete(request)
        return response.content
