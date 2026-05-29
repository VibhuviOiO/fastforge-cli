"""AI provider lifespan — config-driven initialization of active providers only.

Uses the registry pattern: reads AI_* env vars, instantiates only the
configured provider for each concern (embedding, vector store, gateway).
No if/else chains — providers register themselves and the factory picks
the active one from configuration.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
from fastapi import FastAPI

from app.ai.config import AISettings
from app.ai.embeddings.registry import create_embedding_provider
from app.ai.gateway.registry import create_gateway_client
from app.ai.vector_store.registry import create_vector_store

logger = structlog.get_logger(__name__)


async def _close_safely(name: str, obj: Any) -> None:
    """Best-effort close — never raises during shutdown."""
    if obj is None or not hasattr(obj, "close"):
        return
    try:
        await obj.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("ai.lifespan.close_failed", provider=name, error=str(e))


@asynccontextmanager
async def ai_lifespan(app: FastAPI) -> AsyncGenerator[dict, None]:
    """Initialize AI providers during app startup, cleanup on shutdown.

    Instantiates only the providers specified in configuration.
    Providers are stored in app.state for dependency injection.
    """
    settings = AISettings()

    logger.info(
        "ai.lifespan.starting",
        gateway=settings.gateway_provider,
        embedding=settings.embedding_provider,
        vector_store=settings.vector_store_provider,
        app_kind=settings.app_kind,
    )

    gateway = None
    embedding_provider = None
    vector_store = None

    try:
        # Initialize providers (factory pattern — no conditionals here).
        # Each is initialized independently so partial-init still cleans up below.
        gateway = create_gateway_client(settings)
        embedding_provider = create_embedding_provider(settings)
        vector_store = await create_vector_store(settings)

        app.state.ai_settings = settings
        app.state.gateway = gateway
        app.state.embedding_provider = embedding_provider
        app.state.vector_store = vector_store

        logger.info("ai.lifespan.ready")

        yield {
            "ai_settings": settings,
            "gateway": gateway,
            "embedding_provider": embedding_provider,
            "vector_store": vector_store,
        }
    finally:
        logger.info("ai.lifespan.shutting_down")
        await _close_safely("vector_store", vector_store)
        await _close_safely("gateway", gateway)
        await _close_safely("embedding_provider", embedding_provider)
        logger.info("ai.lifespan.shutdown_complete")
