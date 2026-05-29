"""Liveness and readiness probes.

* ``/livez`` — process is alive. Never touches dependencies. Suitable for
  Kubernetes ``livenessProbe``.
* ``/readyz`` — process can serve traffic. Pings configured dependencies
  (database / cache as applicable). Suitable for ``readinessProbe``.
"""

from fastapi import APIRouter, HTTPException

from app.config import settings

router = APIRouter(tags=["health"])


def _service_info() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


@router.get("/livez")
async def liveness() -> dict:
    """Liveness — process is up. Does not touch dependencies."""
    return {"status": "alive", **_service_info()}


@router.get("/readyz")
async def readiness() -> dict:
    """Readiness — checks configured dependencies. 503 on failure."""
    checks: dict[str, str] = {}

{%- if cookiecutter.database in ("postgres", "mysql", "sqlite") %}
    try:
        from sqlalchemy import text

        from app.db.sqlalchemy import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — probe surface
        checks["database"] = f"error: {type(exc).__name__}"
{%- endif %}
{%- if cookiecutter.database == "mongodb" %}
    try:
        from app.db.mongodb import db

        await db.command("ping")
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"
{%- endif %}
{%- if cookiecutter.cache == "redis" %}
    try:
        from app.cache import get_cache

        cache = await get_cache()
        await cache.ping()
        checks["cache"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["cache"] = f"error: {type(exc).__name__}"
{%- endif %}

    ready = all(v == "ok" for v in checks.values())
    payload = {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
        **_service_info(),
    }
    if not ready:
        raise HTTPException(status_code=503, detail=payload)
    return payload
