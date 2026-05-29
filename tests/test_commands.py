"""Tests for fastforge.commands.upgrade and fastforge.commands.audit."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from fastforge.commands.audit import run_audit
from fastforge.commands.upgrade import run_upgrade
from fastforge.generator_protocol import BaseGenerator

# ── Fixtures ─────────────────────────────────────────────────────────────────


class DummyGenerator(BaseGenerator):
    name = "dummy"
    version = "1.0.0"
    description = "Dummy"
    capability_key = "dummy_cap"
    delegatable = True

    def emit_inline(self, project_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "created": [], "modified": []}

    def upgrade(self, project_dir: Path, from_version: str) -> dict[str, Any]:
        return {"status": "upgraded", "changes": ["applied delta"]}

    def validate(self, project_dir: Path) -> list[str]:
        return []


def _write_config(project_dir: str, config: dict):
    config_path = os.path.join(project_dir, ".fastforge.json")
    with open(config_path, "w") as f:
        json.dump(config, f)


# ── run_upgrade ──────────────────────────────────────────────────────────────


@patch("fastforge.dispatch.discover_generators")
def test_run_upgrade_no_project_root(mock_discover, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        run_upgrade()


@patch("fastforge.dispatch.discover_generators")
def test_run_upgrade_with_project_dir(mock_discover, tmp_path):
    mock_discover.return_value = {"dummy": DummyGenerator()}
    _write_config(
        str(tmp_path),
        {
            "project_slug": "test",
            "kind": "standalone",
            "dummy_cap": "yes",
            "_generator_versions": {"dummy": "0.5.0"},
        },
    )

    result = run_upgrade(str(tmp_path))
    assert len(result["upgraded"]) == 1
    assert result["upgraded"][0]["name"] == "dummy"


# ── run_audit ────────────────────────────────────────────────────────────────


@patch("fastforge.dispatch.discover_generators")
def test_run_audit_valid_project(mock_discover, tmp_path):
    mock_discover.return_value = {"dummy": DummyGenerator()}
    _write_config(
        str(tmp_path),
        {
            "project_slug": "test",
            "kind": "standalone",
            "dummy_cap": "yes",
        },
    )

    result = run_audit(str(tmp_path))
    assert "checks" in result
    assert "passed" in result
    # Schema validation should pass
    schema_check = next(c for c in result["checks"] if c["name"] == "schema_validation")
    assert schema_check["passed"] is True


@patch("fastforge.dispatch.discover_generators")
def test_run_audit_invalid_schema(mock_discover, tmp_path):
    mock_discover.return_value = {}
    _write_config(str(tmp_path), {"kind": "invalid_kind"})  # missing project_slug

    result = run_audit(str(tmp_path))
    schema_check = next(c for c in result["checks"] if c["name"] == "schema_validation")
    assert schema_check["passed"] is False


@patch("fastforge.dispatch.discover_generators")
def test_run_audit_capability_drift_detected(mock_discover, tmp_path):
    mock_discover.return_value = {}
    _write_config(
        str(tmp_path),
        {
            "project_slug": "test",
            "kind": "standalone",
            "database": "postgres",
        },
    )
    # Don't create app/db/session.py → drift should be detected

    result = run_audit(str(tmp_path))
    drift_check = next(c for c in result["checks"] if c["name"] == "capability_drift")
    assert drift_check["passed"] is False
    assert any("session.py" in d for d in drift_check["details"])


@patch("fastforge.dispatch.discover_generators")
def test_run_audit_no_project(mock_discover, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        run_audit()


@patch("fastforge.dispatch.discover_generators")
def test_run_audit_env_contract(mock_discover, tmp_path):
    mock_discover.return_value = {}
    _write_config(
        str(tmp_path),
        {
            "project_slug": "test",
            "kind": "standalone",
            "database": "postgres",
        },
    )
    # Create .env.example without DATABASE_URL
    (tmp_path / ".env.example").write_text("APP_NAME=test\n")
    # Create app/db/session.py to avoid drift
    (tmp_path / "app" / "db").mkdir(parents=True)
    (tmp_path / "app" / "db" / "session.py").write_text("")

    result = run_audit(str(tmp_path))
    env_check = next(c for c in result["checks"] if c["name"] == "env_contract")
    assert env_check["passed"] is False
    assert any("DATABASE_URL" in d for d in env_check["details"])
