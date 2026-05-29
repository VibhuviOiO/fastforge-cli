"""Vector store provider registry — factory for creating the active provider."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.ai.config import AISettings
    from app.ai.vector_store import VectorStoreProvider

logger = structlog.get_logger(__name__)

# Registry of vector store providers: name -> class
_REGISTRY: dict[str, type] = {}


def register_vector_store(name: str):
    """Decorator to register a vector store implementation."""
    def decorator(cls: type):
        _REGISTRY[name] = cls
        return cls
    return decorator


async def create_vector_store(settings: "AISettings") -> "VectorStoreProvider":
    """Create the configured vector store instance.

    Async because some providers need connection setup.
    Raises KeyError if the provider is not registered.
    """
    provider_name = settings.vector_store_provider

    if provider_name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(
            f"Vector store provider '{provider_name}' not registered. "
            f"Available: {available}"
        )

    cls = _REGISTRY[provider_name]
    instance = cls(settings)

    # Call async init if the provider has one
    if hasattr(instance, "initialize"):
        await instance.initialize()

    return instance


def _try_import(module_path: str) -> None:
    try:
        importlib.import_module(module_path)
    except ImportError as e:
        logger.debug("ai.vector_store.provider_unavailable", module=module_path, error=str(e))


for _mod in (
    "app.ai.vector_store.vertex_ai_provider",
    "app.ai.vector_store.chromadb_provider",
    "app.ai.vector_store.opensearch_provider",
    "app.ai.vector_store.pgvector_provider",
    "app.ai.vector_store.qdrant_provider",
):
    _try_import(_mod)
