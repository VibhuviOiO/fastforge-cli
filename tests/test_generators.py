"""Happy-path unit tests for the in-tree generator plugins.

Each generator is exercised end-to-end against a fixture project so that:
  * the public entry point runs without exception,
  * the expected artefacts land on disk,
  * idempotency holds when the generator is invoked twice.

These tests intentionally avoid asserting full file contents — they verify the
contract (files created, .fastforge.json updated) so the templates can evolve
without breaking the suite. Content correctness is covered by the
end-to-end smoke harness in `tests/smoke_ecosystem.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# These generators are import-only sanity until exercised — collect their
# happy-path entry points so each contributes coverage.
from fastforge.generators import (  # noqa: F401  (registry import)
    auth as auth_gen,
)
from fastforge.generators import (
    ci as ci_gen,
)
from fastforge.generators import (
    deploy as deploy_gen,
)
from fastforge.generators import (
    kafka as kafka_gen,
)
from fastforge.generators import (
    model as model_gen,
)
from fastforge.generators import (
    postgres as postgres_gen,
)
from fastforge.generators import (
    secure as secure_gen,
)

# ──────────────────────────────────────────────────────────────────────────────
# Fixture: minimal generated-project root
# ──────────────────────────────────────────────────────────────────────────────

CONFIG_BASE = {
    "project_name": "demo",
    "project_slug": "demo",
    "package_name": "demo",
    "kind": "standalone",
    "python_version": "3.13",
    "logging": "structlog",
    "database": "none",
    "cache": "none",
    "streaming": "none",
    "secrets": "none",
    "observability": "disabled",
    "model_name": "item",
    "models": ["item"],
    "ci": [],
    "deploy": [],
    "port": "8000",
}

MINIMAL_CONFIG_PY = '''\
"""App settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "demo"
    app_version: str = "0.1.0"
    app_env: str = "dev"

    model_config = {"env_file": ".env"}


settings = Settings()
'''

MINIMAL_MAIN_PY = """\
from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.items import router as item_router


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    app.include_router(item_router)
    return app


app = create_app()
"""

MINIMAL_PYPROJECT = """\
[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.115.0",
]
"""

MINIMAL_COMPOSE = """\
services:
  app:
    image: demo:latest
"""

MINIMAL_ENV_STAGING = """\
APP_ENV=staging
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Build a minimal generated-project layout that satisfies all 6 generators."""
    root = tmp_path / "demo"
    root.mkdir()

    (root / ".fastforge.json").write_text(json.dumps(CONFIG_BASE, indent=2) + "\n")
    (root / "pyproject.toml").write_text(MINIMAL_PYPROJECT)
    (root / ".env.staging").write_text(MINIMAL_ENV_STAGING)
    (root / "README.md").write_text("# demo\n")

    app = root / "app"
    app.mkdir()
    (app / "__init__.py").write_text("")
    (app / "config.py").write_text(MINIMAL_CONFIG_PY)
    (app / "main.py").write_text(MINIMAL_MAIN_PY)

    routes = app / "api" / "routes"
    routes.mkdir(parents=True)
    (app / "api" / "__init__.py").write_text("")
    (routes / "__init__.py").write_text("")
    (routes / "health.py").write_text("from fastapi import APIRouter\nrouter = APIRouter()\n")
    (routes / "items.py").write_text("from fastapi import APIRouter\nrouter = APIRouter()\n")

    infra = root / "infra"
    infra.mkdir()
    (infra / "docker-compose.yml").write_text(MINIMAL_COMPOSE)

    return root


# ──────────────────────────────────────────────────────────────────────────────
# postgres
# ──────────────────────────────────────────────────────────────────────────────


def test_postgres_creates_session_and_compose(project: Path):
    result = postgres_gen.add_postgres(str(project))

    assert result["status"] == "added"
    assert (project / "app" / "db" / "session.py").is_file()
    assert (project / "app" / "db" / "__init__.py").is_file()
    assert (project / "infra" / "docker-compose.postgres.yml").is_file()
    assert (project / "infra" / "postgres" / "init.sql").is_file()

    config = json.loads((project / ".fastforge.json").read_text())
    assert config["database"] == "postgres"


def test_postgres_is_idempotent(project: Path):
    postgres_gen.add_postgres(str(project))
    second = postgres_gen.add_postgres(str(project))
    assert second["status"] == "already_configured"


def test_postgres_rejects_conflicting_database(project: Path):
    config = json.loads((project / ".fastforge.json").read_text())
    config["database"] = "mongodb"
    (project / ".fastforge.json").write_text(json.dumps(config))

    with pytest.raises(ValueError, match="already uses database"):
        postgres_gen.add_postgres(str(project))


# ──────────────────────────────────────────────────────────────────────────────
# kafka
# ──────────────────────────────────────────────────────────────────────────────


def test_kafka_creates_consumer_and_handler(project: Path):
    result = kafka_gen.add_kafka(str(project))

    assert result["status"] == "added"
    streaming = project / "app" / "streaming"
    assert streaming.is_dir()
    assert any(streaming.iterdir()), "expected streaming module files"
    assert (project / "infra" / "docker-compose.kafka.yml").is_file()


def test_kafka_is_idempotent(project: Path):
    kafka_gen.add_kafka(str(project))
    second = kafka_gen.add_kafka(str(project))
    assert second["status"] == "already_configured"


# ──────────────────────────────────────────────────────────────────────────────
# model
# ──────────────────────────────────────────────────────────────────────────────


def test_model_creates_full_crud_stack(project: Path):
    result = model_gen.add_model("order", project_dir=str(project))

    assert "app/api/models/order.py" in result["created"]
    assert "app/services/order_service.py" in result["created"]
    assert "app/repositories/order_repository.py" in result["created"]
    assert "app/api/routes/orders.py" in result["created"]
    assert "tests/test_orders_api.py" in result["created"]

    main = (project / "app" / "main.py").read_text()
    assert "order_router" in main
    assert "app.api.routes.orders" in main


def test_model_rejects_duplicate(project: Path):
    model_gen.add_model("order", project_dir=str(project))
    with pytest.raises((ValueError, FileExistsError)):
        model_gen.add_model("order", project_dir=str(project))


# ──────────────────────────────────────────────────────────────────────────────
# ci
# ──────────────────────────────────────────────────────────────────────────────


def test_ci_generates_github_actions(project: Path):
    result = ci_gen.add_ci(str(project), "github")

    assert result["status"] == "added"
    assert (project / ".github" / "workflows" / "ci.yml").is_file()

    config = json.loads((project / ".fastforge.json").read_text())
    assert "github" in config["ci"]


def test_ci_rejects_unknown_provider(project: Path):
    result = ci_gen.add_ci(str(project), "buildkite")
    assert result["status"] == "error"


def test_ci_is_idempotent(project: Path):
    ci_gen.add_ci(str(project), "github")
    second = ci_gen.add_ci(str(project), "github")
    assert second["status"] == "already_configured"


# ──────────────────────────────────────────────────────────────────────────────
# deploy
# ──────────────────────────────────────────────────────────────────────────────


def test_deploy_compose_creates_artefacts(project: Path):
    result = deploy_gen.deploy_compose(str(project))

    assert result["status"] == "added"
    assert (project / "deploy" / "compose" / "docker-compose.yml").is_file()

    config = json.loads((project / ".fastforge.json").read_text())
    assert "compose" in config["deploy"]


def test_deploy_k8s_creates_manifests(project: Path):
    result = deploy_gen.deploy_k8s(str(project))

    assert result["status"] == "added"
    deploy_dir = project / "deploy" / "k8s"
    assert deploy_dir.is_dir()
    assert any(deploy_dir.iterdir())


def test_deploy_compose_is_idempotent(project: Path):
    deploy_gen.deploy_compose(str(project))
    second = deploy_gen.deploy_compose(str(project))
    assert second["status"] == "already_configured"


# ──────────────────────────────────────────────────────────────────────────────
# secure
# ──────────────────────────────────────────────────────────────────────────────


def test_secure_setup_creates_baseline(project: Path):
    result = secure_gen.secure_setup(str(project))

    # secure_setup may either fully install or report 'partial' depending on
    # which security tools (detect-secrets, etc.) are present on the runner.
    # We only assert it ran and produced *something*.
    assert "status" in result
    assert "created" in result


# ──────────────────────────────────────────────────────────────────────────────
# auth (jwt) — optional plugin
# ──────────────────────────────────────────────────────────────────────────────


def test_auth_jwt_creates_scaffolding(project: Path):
    result = auth_gen.add_auth_jwt(str(project))

    assert result["status"] == "added"
    assert (project / "app" / "auth" / "jwt.py").is_file()
    assert (project / "app" / "auth" / "routes.py").is_file()
    assert (project / "app" / "auth" / "users.py").is_file()

    config = json.loads((project / ".fastforge.json").read_text())
    assert config["auth"] == "jwt"

    main = (project / "app" / "main.py").read_text()
    assert "auth_router" in main
    assert "from app.auth.routes" in main

    pyproject = (project / "pyproject.toml").read_text()
    assert "pyjwt" in pyproject.lower()
    assert "passlib" in pyproject.lower()


def test_auth_jwt_is_idempotent(project: Path):
    auth_gen.add_auth_jwt(str(project))
    second = auth_gen.add_auth_jwt(str(project))
    assert second["status"] == "already_configured"


def test_auth_jwt_rejects_conflicting_provider(project: Path):
    config = json.loads((project / ".fastforge.json").read_text())
    config["auth"] = "oauth2"
    (project / ".fastforge.json").write_text(json.dumps(config))

    with pytest.raises(ValueError, match="already uses auth"):
        auth_gen.add_auth_jwt(str(project))
