"""Tests for fastforge.project_config — config helpers and emit mode logic."""

from __future__ import annotations

import json

import pytest

from fastforge.project_config import (
    find_project_root,
    get_emit_mode,
    get_kind,
    get_platform_lib,
    load_config,
    require_capability,
    save_config,
    set_capability,
)

# ── find_project_root / load_config / save_config ────────────────────────────


def test_find_project_root_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert find_project_root() is None


def test_find_project_root_finds_config(tmp_path, monkeypatch):
    config_file = tmp_path / ".fastforge.json"
    config_file.write_text('{"project_slug": "test", "kind": "standalone"}')
    monkeypatch.chdir(tmp_path)
    assert find_project_root() == str(tmp_path)


def test_find_project_root_walks_up(tmp_path, monkeypatch):
    config_file = tmp_path / ".fastforge.json"
    config_file.write_text('{"project_slug": "test", "kind": "standalone"}')
    subdir = tmp_path / "app" / "api"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)
    assert find_project_root() == str(tmp_path)


def test_load_config(tmp_path):
    config_data = {"project_slug": "my-app", "kind": "standalone"}
    (tmp_path / ".fastforge.json").write_text(json.dumps(config_data))
    result = load_config(str(tmp_path))
    assert result == config_data


def test_load_config_raises_when_no_config(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(str(tmp_path))


def test_save_config(tmp_path):
    (tmp_path / ".fastforge.json").write_text("{}")
    save_config({"project_slug": "new", "kind": "app"}, str(tmp_path))
    result = json.loads((tmp_path / ".fastforge.json").read_text())
    assert result["project_slug"] == "new"
    assert result["kind"] == "app"


# ── Capability helpers ───────────────────────────────────────────────────────


def test_get_kind_default():
    assert get_kind({}) == "standalone"


def test_get_kind_explicit():
    assert get_kind({"kind": "lib"}) == "lib"


def test_get_platform_lib_none():
    assert get_platform_lib({}) is None


def test_get_platform_lib_set():
    assert get_platform_lib({"platform_lib": "my-lib>=1.0"}) == "my-lib>=1.0"


def test_require_capability_passes():
    config = {"database": "postgres"}
    require_capability(config, "database", ["none", "postgres", "mysql"])


def test_require_capability_raises():
    config = {"database": "oracle"}
    with pytest.raises(ValueError, match="oracle"):
        require_capability(config, "database", ["none", "postgres", "mysql"])


def test_set_capability():
    config = {"kind": "standalone"}
    result = set_capability(config, "database", "postgres")
    assert result["database"] == "postgres"
    assert result is config  # mutates in place


# ── get_emit_mode ────────────────────────────────────────────────────────────


def test_emit_mode_standalone():
    assert get_emit_mode({"kind": "standalone"}) == "inline"


def test_emit_mode_app_with_lib():
    assert get_emit_mode({"kind": "app", "platform_lib": "x>=1"}) == "delegated"


def test_emit_mode_app_without_lib():
    assert get_emit_mode({"kind": "app"}) == "inline"


def test_emit_mode_lib():
    assert get_emit_mode({"kind": "lib"}) == "into_lib"


def test_emit_mode_workspace_defaults_to_inline():
    assert get_emit_mode({"kind": "workspace"}) == "inline"
