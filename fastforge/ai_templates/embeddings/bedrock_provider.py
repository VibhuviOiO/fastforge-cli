"""AWS Bedrock embedding provider."""

from __future__ import annotations

import json

import structlog
from opentelemetry import trace

from app.ai.config import AISettings
from app.ai.embeddings import EmbeddingProvider, EmbeddingResult
from app.ai.embeddings.registry import register_embedding_provider

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@register_embedding_provider("bedrock")
class BedrockEmbeddings(EmbeddingProvider):
    """AWS Bedrock embedding provider (Titan, Cohere on Bedrock).

    Requires: pip install boto3
    Uses the configured AWS credentials and region.
    """

    def __init__(self, settings: AISettings) -> None:
        self._model_id = settings.bedrock_model_id
        self._region = settings.bedrock_region
        self._dimensions = settings.embedding_dimensions
        self._client = None

    def _get_client(self):
        """Lazy-load boto3 bedrock-runtime client."""
        if self._client is None:
            try:
                import boto3
            except ImportError as e:
                raise ImportError(
                    "boto3 is required for Bedrock embeddings. "
                    "Install with: pip install boto3"
                ) from e
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self._region,
            )
        return self._client

    @property
    def name(self) -> str:
        return "bedrock"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @tracer.start_as_current_span("embeddings.bedrock.embed")
    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings via AWS Bedrock."""
        import asyncio

        def _invoke_all() -> list[list[float]]:
            client = self._get_client()
            out: list[list[float]] = []
            for text in texts:
                body = json.dumps({"inputText": text})
                response = client.invoke_model(
                    modelId=self._model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                result = json.loads(response["body"].read())
                out.append(result["embedding"])
            return out

        vectors = await asyncio.to_thread(_invoke_all)
        return EmbeddingResult(
            vectors=vectors,
            model=self._model_id,
            dimensions=len(vectors[0]) if vectors else self._dimensions,
        )

    @tracer.start_as_current_span("embeddings.bedrock.embed_query")
    async def embed_query(self, query: str) -> list[float]:
        """Generate a single query embedding."""
        result = await self.embed([query])
        return result.vectors[0]
