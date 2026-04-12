from contextlib import asynccontextmanager
{%- if cookiecutter.logging != "structlog" %}
from logging import getLogger
{%- endif %}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

{%- if cookiecutter.logging == "structlog" %}
from app.api.exception_handlers import register_exception_handlers
{%- endif %}
from app.api.routes.health import router as health_router
from app.api.routes.{{ cookiecutter.model_name_plural }} import router as {{ cookiecutter.model_name }}_router
from app.config import settings
{%- if cookiecutter.logging == "structlog" %}
from app.logging_config import get_logger, setup_logging
from app.middleware.logging_middleware import RequestLoggingMiddleware
{%- endif %}
from app.middleware.security_headers import SecurityHeadersMiddleware

{% if cookiecutter.logging == "structlog" -%}
setup_logging()
logger = get_logger(__name__)
{%- else -%}
logger = getLogger(__name__)
{%- endif %}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
{%- if cookiecutter.secrets != "none" %}
    from app.secrets import load_secrets

    app.state.secrets = await load_secrets()
{%- endif %}
{%- if cookiecutter.streaming != "none" %}
    from app.streaming.consumer import start_consumer
    from app.streaming.producer import init_producer

    await init_producer()
    await start_consumer(["{{ cookiecutter.project_slug }}-events"])
{%- endif %}
{%- if cookiecutter.logging == "structlog" %}
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
    )
{%- else %}
    logger.info("Starting %s v%s [%s]", settings.app_name, settings.app_version, settings.app_env)
{%- endif %}
    yield
    # ── Shutdown ───────────────────────────────────────────────────────────────
{%- if cookiecutter.streaming != "none" %}
    from app.streaming.consumer import stop_consumer
    from app.streaming.producer import close_producer

    await stop_consumer()
    await close_producer()
{%- endif %}
{%- if cookiecutter.cache != "none" %}
    from app.cache import close_cache

    await close_cache()
{%- endif %}
{%- if cookiecutter.logging == "structlog" %}
    logger.info("application_shutting_down")
{%- else %}
    logger.info("Shutting down %s", settings.app_name)
{%- endif %}


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)
{%- if cookiecutter.logging == "structlog" %}

    app.add_middleware(RequestLoggingMiddleware)

    # Structured exception handlers
    register_exception_handlers(app)
{%- endif %}

    app.include_router(health_router)
    app.include_router({{ cookiecutter.model_name }}_router)

    return app


app = create_app()
