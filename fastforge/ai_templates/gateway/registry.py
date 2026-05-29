"""Gateway provider registry — factory for creating the active gateway client."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.ai.config import AISettings
    from app.ai.gateway import GatewayClient

logger = structlog.get_logger(__name__)

# Registry of gateway providers: name -> factory function
_REGISTRY: dict[str, type] = {}


def register_gateway(name: str):
    """Decorator to register a gateway client implementation."""
    def decorator(cls: type):
        _REGISTRY[name] = cls
        return cls
    return decorator


def create_gateway_client(settings: "AISettings") -> "GatewayClient":
    """Create the configured gateway client instance.

    Raises KeyError if the provider is not registered.
    """
    provider_name = settings.gateway_provider

    if provider_name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(
            f"Gateway provider '{provider_name}' not registered. "
            f"Available: {available}"
        )

    cls = _REGISTRY[provider_name]
    return cls(settings)


def _try_import(module_path: str) -> None:
    try:
        importlib.import_module(module_path)
    except ImportError as e:
        logger.debug("ai.gateway.provider_unavailable", module=module_path, error=str(e))


for _mod in (
    "app.ai.gateway.litellm_client",
    "app.ai.gateway.bifrost_client",
):
    _try_import(_mod)
