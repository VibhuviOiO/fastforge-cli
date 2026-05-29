"""Embedding provider registry — factory for creating the active provider."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.ai.config import AISettings
    from app.ai.embeddings import EmbeddingProvider

logger = structlog.get_logger(__name__)

# Registry of embedding providers: name -> class
_REGISTRY: dict[str, type] = {}


def register_embedding_provider(name: str):
    """Decorator to register an embedding provider implementation."""
    def decorator(cls: type):
        _REGISTRY[name] = cls
        return cls
    return decorator


def create_embedding_provider(settings: "AISettings") -> "EmbeddingProvider":
    """Create the configured embedding provider instance.

    Raises KeyError if the provider is not registered.
    """
    provider_name = settings.embedding_provider

    if provider_name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(
            f"Embedding provider '{provider_name}' not registered. "
            f"Available: {available}"
        )

    cls = _REGISTRY[provider_name]
    return cls(settings)


def _try_import(module_path: str) -> None:
    """Best-effort provider import — missing optional deps don't break registry."""
    try:
        importlib.import_module(module_path)
    except ImportError as e:
        logger.debug("ai.embeddings.provider_unavailable", module=module_path, error=str(e))


# Import implementations to trigger registration.
for _mod in (
    "app.ai.embeddings.openai_provider",
    "app.ai.embeddings.gemini_provider",
    "app.ai.embeddings.cohere_provider",
    "app.ai.embeddings.huggingface_provider",
    "app.ai.embeddings.bedrock_provider",
    "app.ai.embeddings.local_provider",
):
    _try_import(_mod)
