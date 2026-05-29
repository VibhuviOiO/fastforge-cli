"""FastAPI dependencies for AI providers — inject via Depends()."""

from __future__ import annotations

from fastapi import Depends, Request

from app.ai.config import AISettings
from app.ai.embeddings import EmbeddingProvider
from app.ai.gateway import GatewayClient
from app.ai.vector_store import VectorStoreProvider


def get_ai_settings(request: Request) -> AISettings:
    """Get AI settings from app state."""
    return request.app.state.ai_settings


def get_gateway(request: Request) -> GatewayClient:
    """Get the active gateway client."""
    return request.app.state.gateway


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    """Get the active embedding provider."""
    return request.app.state.embedding_provider


def get_vector_store(request: Request) -> VectorStoreProvider:
    """Get the active vector store provider."""
    return request.app.state.vector_store
