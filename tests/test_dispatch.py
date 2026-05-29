"""Tests for fastforge.dispatch — routing to generators with correct emit mode."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from fastforge.dispatch import (
    EmitModeNotSupportedError,
    GeneratorNotFoundError,
    dispatch_add,
    dispatch_upgrade,
    dispatch_validate,
)
from fastforge.generator_protocol import BaseGenerator

# ── Fixtures ─────────────────────────────────────────────────────────────────


class MockGenerator(BaseGenerator):
    name = "mock-gen"
    version = "2.0.0"
    description = "Mock generator for testing"
    capability_key = "mock_cap"
    delegatable = True

    def emit_inline(self, project_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "created": ["mock.py"], "modified": []}

    def emit_delegated(self, project_dir: Path, lib: str, args: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "lib": lib, "created": ["mock_wire.py"], "modified": []}

    def emit_into_lib(self, lib_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "created": ["lib/mock.py"], "modified": []}

    def upgrade(self, project_dir: Path, from_version: str) -> dict[str, Any]:
        return {"status": "upgraded", "changes": [f"delta {from_version} -> {self.version}"]}

    def validate(self, project_dir: Path) -> list[str]:
        return []


class NonDelegatableGenerator(BaseGenerator):
    name = "no-deleg"
    version = "1.0.0"
    description = "Non-delegatable"
    capability_key = "no_deleg_cap"
    delegatable = False

    def emit_inline(self, project_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "created": [], "modified": []}


def _write_config(project_dir: str, config: dict):
    config_path = os.path.join(project_dir, ".fastforge.json")
    with open(config_path, "w") as f:
        json.dump(config, f)


# ── dispatch_add ─────────────────────────────────────────────────────────────


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_add_inline_mode(mock_discover, tmp_path):
    mock_discover.return_value = {"mock-gen": MockGenerator()}
    _write_config(str(tmp_path), {"project_slug": "test", "kind": "standalone"})

    result = dispatch_add("mock-gen", str(tmp_path))
    assert result["status"] == "ok"
    assert "mock.py" in result["created"]


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_add_delegated_mode(mock_discover, tmp_path):
    mock_discover.return_value = {"mock-gen": MockGenerator()}
    _write_config(
        str(tmp_path),
        {
            "project_slug": "test",
            "kind": "app",
            "platform_lib": "myorg>=1.0",
        },
    )

    result = dispatch_add("mock-gen", str(tmp_path))
    assert result["status"] == "ok"
    assert result["lib"] == "myorg>=1.0"


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_add_into_lib_mode(mock_discover, tmp_path):
    mock_discover.return_value = {"mock-gen": MockGenerator()}
    _write_config(str(tmp_path), {"project_slug": "test", "kind": "lib"})

    result = dispatch_add("mock-gen", str(tmp_path))
    assert result["status"] == "ok"
    assert "lib/mock.py" in result["created"]


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_add_generator_not_found(mock_discover, tmp_path):
    mock_discover.return_value = {}
    _write_config(str(tmp_path), {"project_slug": "test", "kind": "standalone"})

    with pytest.raises(GeneratorNotFoundError):
        dispatch_add("nope", str(tmp_path))


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_add_non_delegatable_in_app_mode(mock_discover, tmp_path):
    mock_discover.return_value = {"no-deleg": NonDelegatableGenerator()}
    _write_config(
        str(tmp_path),
        {
            "project_slug": "test",
            "kind": "app",
            "platform_lib": "lib>=1",
        },
    )

    with pytest.raises(EmitModeNotSupportedError):
        dispatch_add("no-deleg", str(tmp_path))


# ── dispatch_upgrade ─────────────────────────────────────────────────────────


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_upgrade_upgrades_configured_generator(mock_discover, tmp_path):
    mock_discover.return_value = {"mock-gen": MockGenerator()}
    _write_config(
        str(tmp_path),
        {
            "project_slug": "test",
            "kind": "standalone",
            "mock_cap": "enabled",
            "_generator_versions": {"mock-gen": "1.0.0"},
        },
    )

    result = dispatch_upgrade(str(tmp_path))
    assert len(result["upgraded"]) == 1
    assert result["upgraded"][0]["name"] == "mock-gen"
    assert result["upgraded"][0]["from"] == "1.0.0"
    assert result["upgraded"][0]["to"] == "2.0.0"


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_upgrade_skips_already_latest(mock_discover, tmp_path):
    mock_discover.return_value = {"mock-gen": MockGenerator()}
    _write_config(
        str(tmp_path),
        {
            "project_slug": "test",
            "kind": "standalone",
            "mock_cap": "enabled",
            "_generator_versions": {"mock-gen": "2.0.0"},
        },
    )

    result = dispatch_upgrade(str(tmp_path))
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["reason"] == "Already at latest version"


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_upgrade_skips_unconfigured(mock_discover, tmp_path):
    mock_discover.return_value = {"mock-gen": MockGenerator()}
    _write_config(str(tmp_path), {"project_slug": "test", "kind": "standalone"})

    result = dispatch_upgrade(str(tmp_path))
    assert len(result["skipped"]) == 1
    assert "Not configured" in result["skipped"][0]["reason"]


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_upgrade_reports_missing_generator(mock_discover, tmp_path):
    mock_discover.return_value = {}
    _write_config(str(tmp_path), {"project_slug": "test", "kind": "standalone"})

    result = dispatch_upgrade(str(tmp_path), features=["nonexistent"])
    assert len(result["errors"]) == 1
    assert "not found" in result["errors"][0]["error"]


# ── dispatch_validate ────────────────────────────────────────────────────────


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_validate_healthy(mock_discover, tmp_path):
    mock_discover.return_value = {"mock-gen": MockGenerator()}
    _write_config(
        str(tmp_path),
        {
            "project_slug": "test",
            "kind": "standalone",
            "mock_cap": "enabled",
        },
    )

    result = dispatch_validate(str(tmp_path))
    assert result == {}


@patch("fastforge.dispatch.discover_generators")
def test_dispatch_validate_with_warnings(mock_discover, tmp_path):
    gen = MockGenerator()
    gen.validate = lambda project_dir: ["something is wrong"]
    mock_discover.return_value = {"mock-gen": gen}
    _write_config(
        str(tmp_path),
        {
            "project_slug": "test",
            "kind": "standalone",
            "mock_cap": "enabled",
        },
    )

    result = dispatch_validate(str(tmp_path))
    assert "mock-gen" in result
    assert "something is wrong" in result["mock-gen"]
