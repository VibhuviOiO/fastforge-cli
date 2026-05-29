"""End-to-end smoke harness for documented FastForge use-cases.

The scenarios in this file are driven by the same preset manifests published in
`examples/use-cases/*.fastforge.json`, so docs and tests stay aligned.

Usage:
    python tests/smoke_ecosystem.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRESETS_DIR = REPO_ROOT / "examples" / "use-cases"
sys.path.insert(0, str(REPO_ROOT))

from fastforge.cli import _apply_ai_generator, generate  # noqa: E402
from fastforge.generators.ai_telemetry import AITelemetryGenerator  # noqa: E402
from fastforge.generators.observability import add_observability  # noqa: E402


def _base_ctx(name: str, **overrides) -> dict:
    """Build a complete CLI context dict with sensible defaults."""
    base = {
        "project_name": name,
        "description": f"smoke-test project: {name}",
        "author_name": "Smoke Test",
        "author_email": "smoke@example.com",
        "python_version": "3.11",
        "port": "8000",
        "model_name": "item",
        "model_name_class": "Item",
        "model_name_plural": "items",
        "database": "none",
        "cache": "none",
        "streaming": "none",
        "secrets": "none",
        "logging": "structlog",
        "log_format": "json",
        "log_connector": "stdout",
        "log_agent": "none",
        "log_target": "none",
        "quality_gate": "none",
        "docker": "yes",
        "docker_debug": "no",
        "precommit": "yes",
        "kind": "standalone",
        "use_case": "custom",
    }
    base.update(overrides)
    return base


def _load_preset(filename: str) -> dict:
    return json.loads((PRESETS_DIR / filename).read_text())


def _ctx_from_preset(filename: str, **overrides) -> tuple[dict, dict]:
    preset = _load_preset(filename)
    model_name = preset.get("model_name", "item")
    ctx = _base_ctx(
        preset["project_slug"],
        use_case=preset.get("use_case", "custom"),
        kind=preset.get("kind", "standalone"),
        model_name=model_name,
        model_name_class=preset.get("model_name_class", model_name.capitalize()),
        model_name_plural=preset.get("model_name_plural", model_name + "s"),
        database=preset.get("database", "none"),
        cache=preset.get("cache", "none"),
        streaming=preset.get("streaming", "none"),
        secrets=preset.get("secrets", "none"),
        logging=preset.get("logging", "structlog"),
        log_format=preset.get("log_format", "json"),
        log_connector=preset.get("log_connector", "stdout"),
        log_agent=preset.get("log_agent", "none"),
        log_target=preset.get("log_target", "none"),
        quality_gate=preset.get("quality_gate", "none"),
        docker=preset.get("docker", "yes"),
        docker_debug=preset.get("docker_debug", "no"),
        precommit=preset.get("precommit", "yes"),
        ai_app_kind=preset.get("ai_app_kind"),
        llm_gateway=preset.get("llm_gateway"),
        embeddings_provider=preset.get("embeddings_provider"),
        vector_store=preset.get("vector_store"),
    )
    ctx.update(overrides)
    return ctx, preset


def _byte_compile(project_dir: Path) -> None:
    """Compile the `app` package to catch syntax errors in emitted code."""
    app = project_dir / "app"
    if not app.exists():
        raise AssertionError(f"app/ not generated in {project_dir}")
    r = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(app)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise AssertionError(f"compileall failed:\n{r.stdout}\n{r.stderr}")


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _assert_subset(expected: dict, actual: dict, prefix: str = "") -> None:
    # Keys that live in preset metadata but not in the generated .fastforge.json
    METADATA_ONLY = {"description"}
    for key, expected_value in expected.items():
        if not prefix and key in METADATA_ONLY:
            continue
        path = f"{prefix}.{key}" if prefix else key
        _assert(key in actual, f"missing config key: {path}")
        actual_value = actual[key]
        if isinstance(expected_value, dict):
            _assert(isinstance(actual_value, dict), f"config key is not an object: {path}")
            _assert_subset(expected_value, actual_value, path)
        else:
            _assert(
                actual_value == expected_value,
                f"config mismatch for {path}: {actual_value!r} != {expected_value!r}",
            )


# ── Scenarios ────────────────────────────────────────────────────────────────


def scenario_simple_fastapi(workdir: Path) -> dict:
    """Plain CRUD service — the smallest useful FastForge app."""
    ctx, preset = _ctx_from_preset(
        "simple-fastapi.fastforge.json",
        model_name="task",
        model_name_class="Task",
        model_name_plural="tasks",
    )
    os.chdir(workdir)
    generate(ctx)

    proj = workdir / preset["project_slug"]
    _assert(proj.exists(), "project dir missing")
    _assert((proj / "app" / "main.py").exists(), "app/main.py missing")
    _assert((proj / "Dockerfile").exists(), "Dockerfile missing")
    _assert((proj / "tests").exists(), "tests/ missing")
    _byte_compile(proj)
    _assert_subset(preset, json.loads((proj / ".fastforge.json").read_text()))

    return {"name": preset["use_case"], "path": proj, "files": _count(proj)}


def scenario_postgres_api(workdir: Path) -> dict:
    """PostgreSQL-backed API for line-of-business services."""
    ctx, preset = _ctx_from_preset("postgres-api.fastforge.json")
    os.chdir(workdir)
    generate(ctx)

    proj = workdir / preset["project_slug"]
    _byte_compile(proj)
    _assert((proj / "docker-compose.debug.yml").exists(), "debug compose missing")
    _assert((proj / "app" / "db").exists(), "app/db missing")
    _assert_subset(preset, json.loads((proj / ".fastforge.json").read_text()))
    return {"name": preset["use_case"], "path": proj, "files": _count(proj)}


def scenario_event_service(workdir: Path) -> dict:
    """Event-driven service with Kafka + Redis + Postgres."""
    ctx, preset = _ctx_from_preset("event-service.fastforge.json")
    os.chdir(workdir)
    generate(ctx)

    proj = workdir / preset["project_slug"]
    _assert((proj / "app" / "streaming").exists(), "app/streaming missing")
    _byte_compile(proj)
    _assert_subset(preset, json.loads((proj / ".fastforge.json").read_text()))
    return {"name": preset["use_case"], "path": proj, "files": _count(proj)}


def scenario_semantic_search(workdir: Path) -> dict:
    """AI semantic search app with gateway + embeddings + vector store."""
    ctx, preset = _ctx_from_preset("semantic-search.fastforge.json")
    os.chdir(workdir)
    generate(ctx)
    _apply_ai_generator(ctx)

    proj = workdir / preset["project_slug"]
    ai_dir = proj / "app" / "ai"
    _assert(ai_dir.exists(), "app/ai not generated")
    _assert((ai_dir / "gateway" / "registry.py").exists(), "gateway registry missing")
    _assert((ai_dir / "embeddings" / "registry.py").exists(), "embeddings registry missing")
    _assert((ai_dir / "vector_store" / "registry.py").exists(), "vector_store registry missing")
    _byte_compile(proj)
    _assert_subset(preset, json.loads((proj / ".fastforge.json").read_text()))

    return {"name": preset["use_case"], "path": proj, "files": _count(proj)}


def scenario_rag_observable(workdir: Path) -> dict:
    """RAG app with HTTP observability and AI call telemetry."""
    ctx, preset = _ctx_from_preset("rag-observable.fastforge.json")
    os.chdir(workdir)
    generate(ctx)
    _apply_ai_generator(ctx)

    proj = workdir / preset["project_slug"]
    observability = add_observability(str(proj), stack="grafana")
    _assert(observability["status"] in {"added", "already_configured"}, "observability failed")

    result = AITelemetryGenerator().emit_inline(proj, {})
    _assert(result["status"] == "ok", f"ai-telemetry status: {result['status']}")

    _assert((proj / "app" / "telemetry").exists(), "app/telemetry missing")
    _assert((proj / "infra" / "docker-compose.grafana.yml").exists(), "grafana compose missing")
    _assert((proj / "infra" / "docker-compose.otel.yml").exists(), "otel compose missing")
    _assert(
        (proj / "app" / "ai" / "telemetry" / "spans.py").exists(),
        "app/ai/telemetry/spans.py missing",
    )
    _byte_compile(proj)
    _assert_subset(preset, json.loads((proj / ".fastforge.json").read_text()))
    return {"name": preset["use_case"], "path": proj, "files": _count(proj)}


def scenario_observable_api(workdir: Path) -> dict:
    """Observability-only API — Postgres + Redis + OpenTelemetry, no AI."""
    ctx, preset = _ctx_from_preset("observable-api.fastforge.json")
    os.chdir(workdir)
    generate(ctx)

    proj = workdir / preset["project_slug"]
    observability = add_observability(str(proj), stack="grafana")
    _assert(observability["status"] in {"added", "already_configured"}, "observability failed")

    _assert((proj / "app" / "telemetry").exists(), "app/telemetry missing")
    _assert((proj / "infra" / "docker-compose.grafana.yml").exists(), "grafana compose missing")
    # No AI directory
    _assert(not (proj / "app" / "ai").exists(), "app/ai should NOT exist in observability-only")
    _byte_compile(proj)
    _assert_subset(preset, json.loads((proj / ".fastforge.json").read_text()))
    return {"name": preset["use_case"], "path": proj, "files": _count(proj)}


def _count(path: Path) -> int:
    return sum(1 for _ in path.rglob("*") if _.is_file())


# ── Runner ───────────────────────────────────────────────────────────────────


SCENARIOS = [
    ("Simple FastAPI service", scenario_simple_fastapi),
    ("PostgreSQL API", scenario_postgres_api),
    ("Event-driven service", scenario_event_service),
    ("AI semantic search", scenario_semantic_search),
    ("RAG + observability + AI telemetry", scenario_rag_observable),
    ("Observable API (no AI)", scenario_observable_api),
]


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="ff-smoke-"))
    print(f"\n[smoke] workdir = {workdir}\n")

    results = []
    failures = 0
    for label, fn in SCENARIOS:
        print(f"━━━ {label} ━━━")
        try:
            res = fn(workdir)
            print(f"  ✔ ok ({res['files']} files)")
            results.append((label, "ok", res))
        except Exception as e:
            print(f"  ✘ FAIL: {e}")
            failures += 1
            results.append((label, "fail", str(e)))
        print()

    print("\n━━━ SUMMARY ━━━")
    for label, status, _ in results:
        icon = "✔" if status == "ok" else "✘"
        print(f"  {icon} {label}")
    print(f"\n{len(results) - failures}/{len(results)} scenarios passed")
    print(f"[smoke] artifacts preserved at: {workdir}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
