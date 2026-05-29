"""JSON Schema for .fastforge.json and validation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# The canonical schema for .fastforge.json.
# Generators extend this by registering their capability_schema() fragments.
FASTFORGE_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FastForge Project Configuration",
    "description": "Capability ledger for a FastForge-generated project.",
    "type": "object",
    "properties": {
        # Meta
        "fastforge_version": {
            "type": "string",
            "description": "Version of fastforge that last modified this file.",
        },
        "project_slug": {"type": "string"},
        "package_name": {"type": "string"},
        "port": {"type": ["string", "integer"]},
        "use_case": {
            "type": "string",
            "description": "Named use-case preset or 'custom' for ad-hoc projects.",
            "default": "custom",
        },
        # Project shape (Layer 0.5)
        "kind": {
            "type": "string",
            "enum": ["standalone", "app", "lib", "workspace"],
            "default": "standalone",
            "description": "Project shape. Determines emit mode for all generators.",
        },
        "platform_lib": {
            "type": ["string", "null"],
            "default": None,
            "description": "Platform library package spec (e.g. 'myorg-platform>=1.0'). Only for kind=app.",
        },
        "workspace_root": {
            "type": ["string", "null"],
            "default": None,
            "description": "Relative path to workspace root. Only for workspace members.",
        },
        "workspace_members": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
            "description": "Relative paths to member projects. Only for kind=workspace.",
        },
        # Existing capabilities (immutable keys from current version)
        "database": {
            "type": "string",
            "enum": ["none", "postgres", "mysql", "sqlite", "mongodb"],
            "default": "none",
        },
        "cache": {
            "type": "string",
            "enum": ["none", "redis", "memcached", "in_memory"],
            "default": "none",
        },
        "streaming": {
            "type": "string",
            "enum": ["none", "kafka", "rabbitmq", "redis_pubsub", "nats"],
            "default": "none",
        },
        "secrets": {
            "type": "string",
            "enum": ["none", "vault", "aws_sm", "azure_kv", "gcp_sm"],
            "default": "none",
        },
        "logging": {
            "type": "string",
            "enum": ["structlog", "none"],
            "default": "structlog",
        },
        "log_format": {
            "type": "string",
            "enum": ["json", "console"],
            "default": "json",
        },
        "log_connector": {
            "type": "string",
            "enum": ["stdout", "file"],
            "default": "stdout",
        },
        "log_agent": {
            "type": "string",
            "enum": ["none", "vector", "fluentbit"],
            "default": "none",
        },
        "log_target": {
            "type": "string",
            "enum": ["none", "elasticsearch", "opensearch", "kafka", "loki", "http"],
            "default": "none",
        },
        "quality_gate": {
            "type": "string",
            "enum": ["none", "sonarqube", "sonarcloud", "qodana", "codeclimate"],
            "default": "none",
        },
        "docker": {
            "type": "string",
            "enum": ["yes", "no"],
            "default": "yes",
        },
        "docker_debug": {
            "type": "string",
            "enum": ["yes", "no"],
            "default": "no",
        },
        "precommit": {
            "type": "string",
            "enum": ["yes", "no"],
            "default": "yes",
        },
        "observability": {
            "type": "string",
            "enum": ["none", "enabled"],
            "default": "none",
        },
        # New capabilities (roadmap)
        "auth": {
            "type": "string",
            "enum": ["none", "jwt", "oidc", "apikey", "session"],
            "default": "none",
        },
        "rbac": {
            "type": "string",
            "enum": ["none", "casbin", "builtin"],
            "default": "none",
        },
        "multitenant": {"type": "boolean", "default": False},
        "migrations": {
            "type": "string",
            "enum": ["none", "alembic", "beanie"],
            "default": "none",
        },
        "background_jobs": {
            "type": "string",
            "enum": ["none", "arq", "celery", "dramatiq", "temporal"],
            "default": "none",
        },
        "reliability": {
            "type": "object",
            "properties": {
                "timeouts": {"type": "boolean", "default": False},
                "retries": {"type": "boolean", "default": False},
                "circuit_breaker": {"type": "boolean", "default": False},
                "idempotency_keys": {"type": "boolean", "default": False},
                "outbox": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
            "default": {},
        },
        "api": {
            "type": "object",
            "properties": {
                "versioning": {
                    "type": "string",
                    "enum": ["none", "url", "header"],
                    "default": "none",
                },
                "errors": {
                    "type": "string",
                    "enum": ["default", "problem_json"],
                    "default": "default",
                },
                "contract_tests": {"type": "boolean", "default": False},
                "sdk_generation": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
            },
            "additionalProperties": False,
            "default": {},
        },
        "testing": {
            "type": "object",
            "properties": {
                "testcontainers": {"type": "boolean", "default": False},
                "factories": {"type": "boolean", "default": False},
                "perf_budget": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
            "default": {},
        },
        "supply_chain": {
            "type": "object",
            "properties": {
                "sbom": {"type": "boolean", "default": False},
                "image_scan": {"type": "boolean", "default": False},
                "image_sign": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
            "default": {},
        },
        "domain_contexts": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
        "vector_store": {
            "type": "string",
            "enum": ["none", "pgvector", "milvus", "qdrant", "pinecone", "vertex"],
            "default": "none",
        },
        "embeddings_provider": {
            "type": "string",
            "enum": ["none", "openai", "gemini", "cohere", "huggingface", "bedrock", "local"],
            "default": "none",
        },
        "llm_gateway": {
            "type": "string",
            "enum": ["none", "litellm"],
            "default": "none",
        },
        "llm_observability": {
            "type": "string",
            "enum": ["none", "langfuse"],
            "default": "none",
        },
        "ai_app_kind": {
            "type": "string",
            "enum": ["none", "semantic_search", "rag", "agent"],
            "default": "none",
        },
        "iac": {
            "type": "string",
            "enum": ["none", "terraform", "pulumi"],
            "default": "none",
        },
        "deploy_targets": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
    },
    "required": ["project_slug", "kind"],
    "additionalProperties": True,
}


def validate_config(config: dict[str, Any]) -> list[str]:
    """Validate a config dict against the schema. Returns a list of error strings.

    Uses a lightweight validation approach (no jsonschema dependency required).
    Validates required fields, enum constraints, and type constraints.
    """
    errors: list[str] = []
    schema_props = FASTFORGE_SCHEMA["properties"]

    # Check required fields
    for field in FASTFORGE_SCHEMA.get("required", []):
        if field not in config:
            errors.append(f"Missing required field: '{field}'")

    # Validate known fields
    for key, value in config.items():
        if key not in schema_props:
            continue  # additionalProperties: true

        prop_schema = schema_props[key]

        # Enum validation
        if "enum" in prop_schema:
            if value not in prop_schema["enum"]:
                errors.append(
                    f"Invalid value for '{key}': '{value}'. Must be one of: {prop_schema['enum']}"
                )

        # Type validation (basic)
        expected_type = prop_schema.get("type")
        if expected_type == "string" and not isinstance(value, str):
            # Allow null for nullable fields
            if isinstance(expected_type, list) and "null" in expected_type and value is None:
                pass
            elif not (isinstance(prop_schema.get("type"), list) and value is None):
                errors.append(f"Field '{key}' should be a string, got {type(value).__name__}")
        elif expected_type == "boolean" and not isinstance(value, bool):
            errors.append(f"Field '{key}' should be a boolean, got {type(value).__name__}")
        elif expected_type == "object" and not isinstance(value, dict):
            errors.append(f"Field '{key}' should be an object, got {type(value).__name__}")
        elif expected_type == "array" and not isinstance(value, list):
            errors.append(f"Field '{key}' should be an array, got {type(value).__name__}")

    return errors


def get_default_config(
    project_slug: str,
    kind: str = "standalone",
    platform_lib: str | None = None,
) -> dict[str, Any]:
    """Return a minimal valid .fastforge.json with all defaults populated."""
    from fastforge import __version__

    config: dict[str, Any] = {
        "fastforge_version": __version__,
        "project_slug": project_slug,
        "package_name": project_slug.replace("-", "_"),
        "use_case": "custom",
        "kind": kind,
        "platform_lib": platform_lib,
        "workspace_root": None,
        "workspace_members": [],
    }
    return config


def write_schema_file(output: Path) -> None:
    """Write the JSON schema to a file (for editor support / CI validation)."""
    with open(output, "w") as f:
        json.dump(FASTFORGE_SCHEMA, f, indent=2)
        f.write("\n")
