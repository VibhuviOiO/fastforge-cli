"""Tests for fastforge.generators.ai_telemetry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fastforge.generators.ai_telemetry import AITelemetryGenerator

# ── Fixtures ─────────────────────────────────────────────────────────────────


REGISTRY_GATEWAY = '''\
"""Gateway registry."""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.ai.config import AISettings
    from app.ai.gateway import GatewayClient

_REGISTRY = {}


def register_gateway(name):
    def decorator(cls):
        _REGISTRY[name] = cls
        return cls
    return decorator


def create_gateway_client(settings):
    provider_name = settings.gateway_provider
    if provider_name not in _REGISTRY:
        raise KeyError(provider_name)
    cls = _REGISTRY[provider_name]
    return cls(settings)


def _try_import(mod):
    pass
'''


REGISTRY_EMBEDDING = REGISTRY_GATEWAY.replace(
    "create_gateway_client", "create_embedding_provider"
).replace("gateway_provider", "embedding_provider")


REGISTRY_VECTOR = REGISTRY_GATEWAY.replace("create_gateway_client", "create_vector_store").replace(
    "gateway_provider", "vector_store_provider"
)


# Realistic vector_store shape: `instance = cls(settings); ... return instance`
REGISTRY_VECTOR_ASSIGN = '''\
"""Vector store registry — async with assign-then-return."""
from __future__ import annotations


_REGISTRY = {}


async def create_vector_store(settings):
    provider_name = settings.vector_store_provider
    if provider_name not in _REGISTRY:
        raise KeyError(provider_name)
    cls = _REGISTRY[provider_name]
    instance = cls(settings)
    if hasattr(instance, "initialize"):
        await instance.initialize()
    return instance
'''


AI_CONFIG = """\
from pydantic_settings import BaseSettings


class AISettings(BaseSettings):
    gateway_provider: str = "litellm"
    embedding_provider: str = "openai"
    vector_store_provider: str = "chromadb"

    model_config = {"env_prefix": "AI_"}
"""


MAIN_PY = '''\
"""App entrypoint."""
from fastapi import FastAPI
from app.config import settings
from app.ai.dependencies import get_gateway

def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    return app

app = create_app()
'''


PYPROJECT = """\
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "fastapi>=0.115.0",
    "pydantic-settings>=2.5.0"
]
"""


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A minimally-populated FastForge AI project."""
    ai_dir = tmp_path / "app" / "ai"
    (ai_dir / "gateway").mkdir(parents=True)
    (ai_dir / "embeddings").mkdir(parents=True)
    (ai_dir / "vector_store").mkdir(parents=True)

    (ai_dir / "gateway" / "registry.py").write_text(REGISTRY_GATEWAY)
    (ai_dir / "embeddings" / "registry.py").write_text(REGISTRY_EMBEDDING)
    (ai_dir / "vector_store" / "registry.py").write_text(REGISTRY_VECTOR)
    (ai_dir / "config.py").write_text(AI_CONFIG)

    (tmp_path / "app" / "main.py").write_text(MAIN_PY)
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)

    (tmp_path / "infra").mkdir()

    (tmp_path / ".fastforge.json").write_text(json.dumps({"project_slug": "demo"}))
    return tmp_path


# ── Protocol & metadata ──────────────────────────────────────────────────────


def test_protocol_metadata():
    gen = AITelemetryGenerator()
    assert gen.name == "ai-telemetry"
    assert gen.version == "1.0.0"
    assert gen.capability_key == "ai_telemetry"
    assert gen.description


def test_refuses_when_ai_dir_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="app/ai/ not found"):
        AITelemetryGenerator().emit_inline(tmp_path, {})


# ── Emitted files ────────────────────────────────────────────────────────────


def test_emits_telemetry_package(project_dir: Path):
    result = AITelemetryGenerator().emit_inline(project_dir, {})

    tel = project_dir / "app" / "ai" / "telemetry"
    for f in ("__init__.py", "spans.py", "pricing.py", "tenant.py", "propagation.py"):
        assert (tel / f).exists(), f"missing {f}"

    assert "AITracingProxy" in (tel / "spans.py").read_text()
    assert "cost_usd" in (tel / "pricing.py").read_text()
    assert "TenantContextMiddleware" in (tel / "tenant.py").read_text()
    assert "traced_httpx_client" in (tel / "propagation.py").read_text()
    assert result["status"] == "ok"


def test_emits_collector_stack(project_dir: Path):
    AITelemetryGenerator().emit_inline(project_dir, {})

    infra = project_dir / "infra"
    assert (infra / "docker-compose.otel.yml").exists()
    assert (infra / "otel" / "otel-collector.yaml").exists()
    assert (infra / "otel" / "tempo.yaml").exists()
    assert (infra / "otel" / "prometheus.yml").exists()

    compose = (infra / "docker-compose.otel.yml").read_text()
    assert "otel-collector" in compose
    assert "demo-otel-collector" in compose  # project slug substituted


# ── Registry wrapping ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rel_path,kind,settings_attr",
    [
        ("app/ai/gateway/registry.py", "gateway", "gateway_provider"),
        ("app/ai/embeddings/registry.py", "embedding", "embedding_provider"),
        ("app/ai/vector_store/registry.py", "vector_store", "vector_store_provider"),
    ],
)
def test_wraps_registry_factory(project_dir: Path, rel_path: str, kind: str, settings_attr: str):
    AITelemetryGenerator().emit_inline(project_dir, {})
    text = (project_dir / rel_path).read_text()
    assert "from app.ai.telemetry.spans import AITracingProxy" in text
    assert "AITracingProxy(cls(settings)" in text
    assert f'kind="{kind}"' in text
    assert f"provider=settings.{settings_attr}" in text


def test_wrap_is_idempotent(project_dir: Path):
    AITelemetryGenerator().emit_inline(project_dir, {})
    text_before = (project_dir / "app/ai/gateway/registry.py").read_text()

    second = AITelemetryGenerator().emit_inline(project_dir, {})
    text_after = (project_dir / "app/ai/gateway/registry.py").read_text()

    assert text_before == text_after
    assert second["status"] == "already_configured"
    assert second["modified"] == []
    assert second["created"] == []


def test_wraps_assign_then_return_pattern(project_dir: Path):
    """Real vector_store registry uses `instance = cls(settings); return instance`."""
    vec = project_dir / "app/ai/vector_store/registry.py"
    vec.write_text(REGISTRY_VECTOR_ASSIGN)

    AITelemetryGenerator().emit_inline(project_dir, {})
    text = vec.read_text()
    assert "AITracingProxy(instance" in text
    assert 'kind="vector_store"' in text
    assert "provider=settings.vector_store_provider" in text
    # init code must still execute before wrapping
    assert "await instance.initialize()" in text


# ── Config and main wiring ───────────────────────────────────────────────────


def test_adds_settings_to_ai_config(project_dir: Path):
    AITelemetryGenerator().emit_inline(project_dir, {})
    cfg = (project_dir / "app" / "ai" / "config.py").read_text()
    assert "ai_telemetry_enabled" in cfg
    assert "ai_tenant_header" in cfg


def test_registers_tenant_middleware(project_dir: Path):
    AITelemetryGenerator().emit_inline(project_dir, {})
    main = (project_dir / "app" / "main.py").read_text()
    assert "TenantContextMiddleware" in main
    assert "app.add_middleware(TenantContextMiddleware)" in main


# ── Pyproject deps ───────────────────────────────────────────────────────────


def test_appends_otel_deps(project_dir: Path):
    AITelemetryGenerator().emit_inline(project_dir, {})
    py = (project_dir / "pyproject.toml").read_text()
    assert "opentelemetry-api" in py
    assert "opentelemetry-instrumentation-httpx" in py


# ── Capability tracking ──────────────────────────────────────────────────────


def test_records_capability_in_fastforge_json(project_dir: Path):
    AITelemetryGenerator().emit_inline(project_dir, {})
    data = json.loads((project_dir / ".fastforge.json").read_text())
    assert data["ai_telemetry"]["version"] == "1.0.0"
    assert data["ai_telemetry"]["tenant_header"] == "X-Tenant-Id"


def test_validate_clean(project_dir: Path):
    AITelemetryGenerator().emit_inline(project_dir, {})
    assert AITelemetryGenerator().validate(project_dir) == []


def test_validate_missing_files(project_dir: Path):
    AITelemetryGenerator().emit_inline(project_dir, {})
    (project_dir / "app" / "ai" / "telemetry" / "spans.py").unlink()
    warnings = AITelemetryGenerator().validate(project_dir)
    assert any("spans.py" in w for w in warnings)


# ── Generated code sanity (compiles) ─────────────────────────────────────────


def test_emitted_python_compiles(project_dir: Path):
    import py_compile

    AITelemetryGenerator().emit_inline(project_dir, {})
    for rel in (
        "app/ai/telemetry/spans.py",
        "app/ai/telemetry/pricing.py",
        "app/ai/telemetry/tenant.py",
        "app/ai/telemetry/propagation.py",
    ):
        py_compile.compile(str(project_dir / rel), doraise=True)


# ── Pricing math (the cost claim must be correct) ────────────────────────────


def test_pricing_table_values():
    """Eat our own dog food — load the emitted pricing module and verify math."""
    import sys

    # Load from disk to ensure the actual emitted source is correct.
    src_path = (
        Path(__file__).resolve().parent.parent / "fastforge" / "generators" / "ai_telemetry.py"
    )
    text = src_path.read_text()
    # Extract PRICING_PY and exec it
    start = text.index("PRICING_PY = '''") + len("PRICING_PY = '''")
    end = text.index("'''", start)
    module_src = text[start:end]

    mod = type(sys)("pricing_test")
    exec(compile(module_src, "pricing.py", "exec"), mod.__dict__)

    # 1k input tokens of gpt-4o = $0.0025
    assert mod.cost_usd("openai", "gpt-4o", 1000, 0) == pytest.approx(0.0025)
    # 1k output tokens of gpt-4o = $0.01
    assert mod.cost_usd("openai", "gpt-4o", 0, 1000) == pytest.approx(0.01)
    # Unknown model returns None
    assert mod.cost_usd("openai", "nonexistent-model", 1000, 1000) is None
    # Self-hosted has no entries → None
    assert mod.cost_usd("local", "any", 1000, 0) is None
