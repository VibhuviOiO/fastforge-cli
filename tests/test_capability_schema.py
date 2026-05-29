"""Tests for fastforge.capability_schema — schema definition and validation."""

from __future__ import annotations

from unittest.mock import patch

from fastforge.capability_schema import (
    FASTFORGE_SCHEMA,
    get_default_config,
    validate_config,
    write_schema_file,
)

# ── Schema structure ─────────────────────────────────────────────────────────


def test_schema_has_required_fields():
    assert "properties" in FASTFORGE_SCHEMA
    assert "required" in FASTFORGE_SCHEMA
    assert "project_slug" in FASTFORGE_SCHEMA["required"]
    assert "kind" in FASTFORGE_SCHEMA["required"]


def test_schema_defines_kind_enum():
    kind_schema = FASTFORGE_SCHEMA["properties"]["kind"]
    assert kind_schema["type"] == "string"
    assert set(kind_schema["enum"]) == {"standalone", "app", "lib", "workspace"}


def test_schema_defines_all_capability_keys():
    props = FASTFORGE_SCHEMA["properties"]
    expected_keys = [
        "use_case",
        "database",
        "cache",
        "streaming",
        "secrets",
        "logging",
        "log_format",
        "log_connector",
        "log_agent",
        "log_target",
        "quality_gate",
        "docker",
        "precommit",
        "observability",
        "auth",
        "rbac",
        "multitenant",
        "migrations",
        "background_jobs",
        "vector_store",
        "llm_gateway",
    ]
    for key in expected_keys:
        assert key in props, f"Missing schema property: {key}"


# ── validate_config ──────────────────────────────────────────────────────────


def test_validate_config_valid_minimal():
    config = {"project_slug": "my-app", "kind": "standalone"}
    errors = validate_config(config)
    assert errors == []


def test_validate_config_missing_required_field():
    config = {"kind": "standalone"}  # missing project_slug
    errors = validate_config(config)
    assert any("project_slug" in e for e in errors)


def test_validate_config_invalid_enum_value():
    config = {"project_slug": "my-app", "kind": "invalid_kind"}
    errors = validate_config(config)
    assert any("kind" in e and "invalid_kind" in e for e in errors)


def test_validate_config_invalid_database_enum():
    config = {"project_slug": "my-app", "kind": "standalone", "database": "oracle"}
    errors = validate_config(config)
    assert any("database" in e and "oracle" in e for e in errors)


def test_validate_config_valid_database_enum():
    config = {"project_slug": "my-app", "kind": "standalone", "database": "postgres"}
    errors = validate_config(config)
    assert errors == []


def test_validate_config_boolean_field():
    config = {"project_slug": "my-app", "kind": "standalone", "multitenant": "yes"}
    errors = validate_config(config)
    assert any("multitenant" in e and "boolean" in e for e in errors)


def test_validate_config_object_field():
    config = {"project_slug": "my-app", "kind": "standalone", "reliability": "string"}
    errors = validate_config(config)
    assert any("reliability" in e and "object" in e for e in errors)


def test_validate_config_array_field():
    config = {"project_slug": "my-app", "kind": "standalone", "workspace_members": "not-a-list"}
    errors = validate_config(config)
    assert any("workspace_members" in e and "array" in e for e in errors)


def test_validate_config_allows_additional_properties():
    config = {"project_slug": "my-app", "kind": "standalone", "custom_key": "whatever"}
    errors = validate_config(config)
    assert errors == []


# ── get_default_config ───────────────────────────────────────────────────────


@patch("fastforge.__version__", "0.1.0")
def test_get_default_config_standalone():
    config = get_default_config("my-app")
    assert config["project_slug"] == "my-app"
    assert config["package_name"] == "my_app"
    assert config["use_case"] == "custom"
    assert config["kind"] == "standalone"
    assert config["platform_lib"] is None
    assert config["workspace_root"] is None
    assert config["workspace_members"] == []


@patch("fastforge.__version__", "0.1.0")
def test_get_default_config_app_with_lib():
    config = get_default_config("svc-api", kind="app", platform_lib="myorg-platform>=1.0")
    assert config["kind"] == "app"
    assert config["platform_lib"] == "myorg-platform>=1.0"


# ── write_schema_file ────────────────────────────────────────────────────────


def test_write_schema_file(tmp_path):
    output = tmp_path / "schema.json"
    write_schema_file(output)
    assert output.exists()
    import json

    data = json.loads(output.read_text())
    assert data["title"] == "FastForge Project Configuration"
