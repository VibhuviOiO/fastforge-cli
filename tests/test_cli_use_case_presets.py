"""Tests for `fastforge new --from-file` preset generation."""

from __future__ import annotations

import json
from pathlib import Path

from fastforge.cli import _cmd_new, _load_generation_context_from_file

REPO_ROOT = Path(__file__).resolve().parent.parent
PRESETS = REPO_ROOT / "examples" / "use-cases"


def test_load_generation_context_from_file_basic():
    ctx = _load_generation_context_from_file(str(PRESETS / "simple-fastapi.fastforge.json"))
    assert ctx["project_name"] == "simple-fastapi"
    assert ctx["use_case"] == "simple_fastapi"
    assert ctx["database"] == "none"
    assert ctx["model_name"] == "item"


def test_cmd_new_from_file_generates_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _cmd_new(from_file=str(PRESETS / "simple-fastapi.fastforge.json"))

    project = tmp_path / "simple-fastapi"
    assert project.exists()
    assert (project / "app" / "main.py").exists()

    config = json.loads((project / ".fastforge.json").read_text())
    assert config["use_case"] == "simple_fastapi"
    assert config["database"] == "none"


def test_cmd_new_from_file_applies_followup_generators(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _cmd_new(from_file=str(PRESETS / "rag-observable.fastforge.json"))

    project = tmp_path / "rag-observable"
    assert (project / "app" / "ai" / "telemetry" / "spans.py").exists()
    assert (project / "app" / "telemetry" / "tracing.py").exists()
    assert (project / "infra" / "docker-compose.grafana.yml").exists()
    assert (project / "infra" / "docker-compose.otel.yml").exists()

    config = json.loads((project / ".fastforge.json").read_text())
    assert config["use_case"] == "rag_observable"
    assert config["observability"] == "enabled"
    assert config["ai_telemetry"]["version"] == "1.0.0"


def test_load_generation_context_from_yaml():
    ctx = _load_generation_context_from_file(str(PRESETS / "observable-api.fastforge.yaml"))
    assert ctx["project_name"] == "observable-api"
    assert ctx["use_case"] == "observable_api"
    assert ctx["database"] == "postgres"
    assert ctx["cache"] == "redis"
    assert ctx["observability"] == "enabled"
    assert ctx.get("ai_app_kind", "none") == "none"


def test_cmd_new_from_yaml_file_generates_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _cmd_new(from_file=str(PRESETS / "observable-api.fastforge.yaml"))

    project = tmp_path / "observable-api"
    assert project.exists()
    assert (project / "app" / "main.py").exists()
    assert (project / "app" / "telemetry" / "tracing.py").exists()
    assert (project / "infra" / "docker-compose.grafana.yml").exists()

    config = json.loads((project / ".fastforge.json").read_text())
    assert config["use_case"] == "observable_api"
    assert config["observability"] == "enabled"
