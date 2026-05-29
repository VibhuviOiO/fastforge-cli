"""Google Vertex AI Vector Search provider."""

from __future__ import annotations

from typing import Any

import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.vector_store import SearchResponse, SearchResult, VectorStoreProvider
from app.ai.vector_store.registry import register_vector_store

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_vector_store("vertex_ai")
class VertexAIVectorSearch(VectorStoreProvider):
    """Google Vertex AI Vector Search (Matching Engine).

    Requires: pip install google-cloud-aiplatform
    """

    def __init__(self, settings: AISettings) -> None:
        self._project = settings.vertex_ai_project
        self._location = settings.vertex_ai_location
        self._index_endpoint = settings.vertex_ai_index_endpoint
        self._deployed_index_id = settings.vertex_ai_deployed_index_id
        self._endpoint = None

    async def initialize(self) -> None:
        """Initialize the Vertex AI client."""
        try:
            from google.cloud import aiplatform
        except ImportError as e:
            raise ImportError(
                "google-cloud-aiplatform is required for Vertex AI Vector Search. "
                "Install with: pip install google-cloud-aiplatform"
            ) from e

        aiplatform.init(project=self._project, location=self._location)
        self._endpoint = aiplatform.MatchingEngineIndexEndpoint(self._index_endpoint)

    @property
    def name(self) -> str:
        return "vertex_ai"

    @tracer.start_as_current_span("vector_store.vertex_ai.search")
    async def search(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        namespace: str | None = None,
    ) -> SearchResponse:
        """Search using Vertex AI Matching Engine."""
        response = self._endpoint.find_neighbors(
            deployed_index_id=self._deployed_index_id,
            queries=[vector],
            num_neighbors=top_k,
        )

        results = []
        for match in response[0]:
            results.append(
                SearchResult(
                    id=match.id,
                    score=match.distance,
                    metadata={},
                )
            )

        return SearchResponse(results=results, total_count=len(results))

    @tracer.start_as_current_span("vector_store.vertex_ai.upsert")
    async def upsert(
        self,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        namespace: str | None = None,
    ) -> int:
        """Upsert vectors to Vertex AI index.

        Vertex AI Matching Engine ingestion is index-scoped (not endpoint-scoped)
        and typically done via GCS batch import or the streaming-update API on the
        Index resource. Because the streaming path requires the Index resource
        (not the IndexEndpoint configured here), this scaffold intentionally
        fails loudly so callers implement the right path for their deployment.
        """
        raise NotImplementedError(
            "Vertex AI upsert is not implemented in the scaffold. Implement one of:\n"
            "  (a) batch import from GCS via aiplatform.MatchingEngineIndex.update_embeddings\n"
            "  (b) streaming updates via aiplatform.MatchingEngineIndex.upsert_datapoints\n"
            "Both require the Index resource ID, not the IndexEndpoint. See the README."
        )

    @tracer.start_as_current_span("vector_store.vertex_ai.delete")
    async def delete(self, ids: list[str], namespace: str | None = None) -> int:
        """Delete vectors from Vertex AI index."""
        raise NotImplementedError(
            "Vertex AI delete is not implemented in the scaffold. Use "
            "aiplatform.MatchingEngineIndex.remove_datapoints with the Index resource ID."
        )

    async def close(self) -> None:
        """No persistent connection to close for Vertex AI."""
        self._endpoint = None
