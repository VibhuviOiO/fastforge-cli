"""pgvector (PostgreSQL) vector store provider."""

from __future__ import annotations

import re
from typing import Any

import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.vector_store import SearchResponse, SearchResult, VectorStoreProvider
from app.ai.vector_store.registry import register_vector_store

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Whitelist for table/identifier names — prevents SQL injection via env var.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@register_vector_store("pgvector")
class PgVectorStore(VectorStoreProvider):
    """PostgreSQL with pgvector extension.

    Requires: pip install asyncpg sqlalchemy pgvector
    """

    def __init__(self, settings: AISettings) -> None:
        self._dsn = settings.pgvector_dsn
        self._collection = settings.vector_store_collection
        self._dimensions = settings.embedding_dimensions
        self._engine = None
        if not _IDENT_RE.match(self._collection):
            raise ValueError(
                f"Invalid pgvector collection name {self._collection!r}: "
                "must match ^[A-Za-z_][A-Za-z0-9_]*$"
            )

    async def initialize(self) -> None:
        """Initialize async SQLAlchemy engine with pgvector."""
        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine
        except ImportError as e:
            raise ImportError(
                "sqlalchemy and asyncpg are required for pgvector. "
                "Install with: pip install sqlalchemy asyncpg pgvector"
            ) from e

        self._engine = create_async_engine(self._dsn, pool_size=5)

        # Ensure pgvector extension and table exist. Collection name is
        # whitelist-validated; dimension is a settings int.
        async with self._engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text(
                f"CREATE TABLE IF NOT EXISTS {self._collection} ("
                "id TEXT PRIMARY KEY, "
                f"embedding vector({int(self._dimensions)}), "
                "content TEXT DEFAULT '', "
                "metadata JSONB DEFAULT '{}'::jsonb"
                ")"
            ))

    @property
    def name(self) -> str:
        return "pgvector"

    @tracer.start_as_current_span("vector_store.pgvector.search")
    async def search(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        namespace: str | None = None,
    ) -> SearchResponse:
        """Search using pgvector cosine distance."""
        from sqlalchemy import text

        vector_str = "[" + ",".join(str(v) for v in vector) + "]"

        # Vector value is bound as a parameter, not interpolated. Collection name
        # is whitelisted in __init__.
        query = text(
            f"SELECT id, content, metadata, "
            "1 - (embedding <=> (:vec)::vector) AS score "
            f"FROM {self._collection} "
            "ORDER BY embedding <=> (:vec)::vector "
            "LIMIT :top_k"
        )

        async with self._engine.begin() as conn:
            result = await conn.execute(query, {"vec": vector_str, "top_k": top_k})
            rows = result.fetchall()

        results = [
            SearchResult(
                id=row[0],
                score=float(row[3]),
                content=row[1] or "",
                metadata=row[2] or {},
            )
            for row in rows
        ]

        return SearchResponse(results=results, total_count=len(results))

    @tracer.start_as_current_span("vector_store.pgvector.upsert")
    async def upsert(
        self,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        namespace: str | None = None,
    ) -> int:
        """Upsert vectors to pgvector table."""
        import json

        from sqlalchemy import text

        async with self._engine.begin() as conn:
            for i, (vec_id, vector) in enumerate(zip(ids, vectors)):
                vector_str = "[" + ",".join(str(v) for v in vector) + "]"
                meta = json.dumps(metadata[i]) if metadata else "{}"
                await conn.execute(
                    text(f"""
                        INSERT INTO {self._collection} (id, embedding, metadata)
                        VALUES (:id, :embedding::vector, :metadata::jsonb)
                        ON CONFLICT (id) DO UPDATE
                        SET embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata
                    """),
                    {"id": vec_id, "embedding": vector_str, "metadata": meta},
                )
        return len(vectors)

    @tracer.start_as_current_span("vector_store.pgvector.delete")
    async def delete(self, ids: list[str], namespace: str | None = None) -> int:
        """Delete vectors from pgvector table."""
        from sqlalchemy import text

        async with self._engine.begin() as conn:
            await conn.execute(
                text(f"DELETE FROM {self._collection} WHERE id = ANY(:ids)"),
                {"ids": ids},
            )
        return len(ids)

    async def close(self) -> None:
        """Dispose the engine."""
        if self._engine:
            await self._engine.dispose()
