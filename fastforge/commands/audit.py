"""fastforge audit — check project for capability drift, CVEs, and env-contract violations."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from fastforge.capability_schema import validate_config
from fastforge.dispatch import dispatch_validate
from fastforge.project_config import find_project_root, load_config


def run_audit(project_dir: str | None = None) -> dict[str, Any]:
    """Run a comprehensive audit of the project.

    Checks:
    1. Schema validation (keys are valid, values are in allowed sets).
    2. Capability drift (file present but flag missing, or vice versa).
    3. Generator-level validation (each generator's validate() method).
    4. Dependency CVEs (pip-audit if available).
    5. Env-contract violations (declared capabilities vs .env files).

    Returns: {"passed": bool, "checks": [...]}
    """
    if project_dir is None:
        project_dir = find_project_root()
    if project_dir is None:
        raise FileNotFoundError(
            "No .fastforge.json found. Run this from inside a FastForge project."
        )

    checks: list[dict[str, Any]] = []

    # ── 1. Schema validation ─────────────────────────────────────────────
    try:
        config = load_config(project_dir)
        schema_errors = validate_config(config)
        checks.append(
            {
                "name": "schema_validation",
                "passed": len(schema_errors) == 0,
                "details": schema_errors if schema_errors else ["Configuration is valid"],
            }
        )
    except Exception as e:
        checks.append(
            {
                "name": "schema_validation",
                "passed": False,
                "details": [f"Failed to load config: {e}"],
            }
        )
        return {"passed": False, "checks": checks}

    # ── 2. Capability drift ──────────────────────────────────────────────
    drift_errors = _check_capability_drift(config, project_dir)
    checks.append(
        {
            "name": "capability_drift",
            "passed": len(drift_errors) == 0,
            "details": drift_errors if drift_errors else ["No drift detected"],
        }
    )

    # ── 3. Generator validation ──────────────────────────────────────────
    try:
        gen_warnings = dispatch_validate(project_dir)
        all_warnings = []
        for name, warnings in gen_warnings.items():
            for w in warnings:
                all_warnings.append(f"[{name}] {w}")
        checks.append(
            {
                "name": "generator_validation",
                "passed": len(all_warnings) == 0,
                "details": all_warnings if all_warnings else ["All generators healthy"],
            }
        )
    except Exception as e:
        checks.append(
            {
                "name": "generator_validation",
                "passed": False,
                "details": [f"Failed: {e}"],
            }
        )

    # ── 4. Dependency CVEs ───────────────────────────────────────────────
    cve_result = _check_cves(project_dir)
    checks.append(cve_result)

    # ── 5. Env contract ──────────────────────────────────────────────────
    env_errors = _check_env_contract(config, project_dir)
    checks.append(
        {
            "name": "env_contract",
            "passed": len(env_errors) == 0,
            "details": env_errors if env_errors else ["Env contract is consistent"],
        }
    )

    passed = all(c["passed"] for c in checks)
    return {"passed": passed, "checks": checks}


def _check_capability_drift(config: dict, project_dir: str) -> list[str]:
    """Check for files that should exist based on config, or vice versa."""
    errors: list[str] = []

    # Database: if postgres declared, app/db/session.py should exist
    if config.get("database") == "postgres":
        if not os.path.isfile(os.path.join(project_dir, "app", "db", "session.py")):
            errors.append("database=postgres but app/db/session.py is missing")

    # Streaming: if kafka, app/streaming/ should exist
    if config.get("streaming") == "kafka":
        if not os.path.isdir(os.path.join(project_dir, "app", "streaming")):
            errors.append("streaming=kafka but app/streaming/ is missing")

    # Observability: if enabled, app/telemetry/ should exist
    if config.get("observability") == "enabled":
        if not os.path.isdir(os.path.join(project_dir, "app", "telemetry")):
            errors.append("observability=enabled but app/telemetry/ is missing")

    # Auth: if not none, app/security/ should exist
    if config.get("auth", "none") != "none":
        if not os.path.isdir(os.path.join(project_dir, "app", "security")):
            errors.append(f"auth={config['auth']} but app/security/ is missing")

    # Migrations: if alembic, migrations/ should exist
    if config.get("migrations") == "alembic":
        if not os.path.isdir(os.path.join(project_dir, "migrations")):
            errors.append("migrations=alembic but migrations/ directory is missing")

    # Vector store: if not none, app/vector_store/ should exist
    if config.get("vector_store", "none") != "none":
        if not os.path.isdir(os.path.join(project_dir, "app", "vector_store")):
            errors.append(f"vector_store={config['vector_store']} but app/vector_store/ is missing")

    return errors


def _check_cves(project_dir: str) -> dict[str, Any]:
    """Run pip-audit if available."""
    try:
        result = subprocess.run(
            ["pip-audit", "--format=json", "--desc=on"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return {
                "name": "dependency_cves",
                "passed": True,
                "details": ["No known vulnerabilities"],
            }
        else:
            # pip-audit exits non-zero when vulnerabilities are found
            return {
                "name": "dependency_cves",
                "passed": False,
                "details": [result.stdout[:500] if result.stdout else "Vulnerabilities found"],
            }
    except FileNotFoundError:
        return {
            "name": "dependency_cves",
            "passed": True,  # Skip if not installed
            "details": ["pip-audit not installed (skipped)"],
        }
    except subprocess.TimeoutExpired:
        return {
            "name": "dependency_cves",
            "passed": True,
            "details": ["pip-audit timed out (skipped)"],
        }


def _check_env_contract(config: dict, project_dir: str) -> list[str]:
    """Check that .env.example (if present) covers all capabilities."""
    errors: list[str] = []
    env_example = os.path.join(project_dir, ".env.example")

    if not os.path.isfile(env_example):
        # Not all projects have .env.example yet; skip if absent
        return []

    with open(env_example) as f:
        env_content = f.read().upper()

    # Check expected env vars based on capabilities
    expected_vars: list[tuple[str, str]] = []

    if config.get("database") == "postgres":
        expected_vars.append(("DATABASE_URL", "database=postgres"))
    if config.get("streaming") == "kafka":
        expected_vars.append(("KAFKA_BOOTSTRAP_SERVERS", "streaming=kafka"))
    if config.get("cache") == "redis":
        expected_vars.append(("REDIS_URL", "cache=redis"))
    if config.get("observability") == "enabled":
        expected_vars.append(("OTEL_ENABLED", "observability=enabled"))
    if config.get("vector_store", "none") != "none":
        expected_vars.append(("EMBEDDING_PROVIDER", "vector_store configured"))
    if config.get("llm_gateway") == "litellm":
        expected_vars.append(("LITELLM_MODE", "llm_gateway=litellm"))
    if config.get("llm_observability") == "langfuse":
        expected_vars.append(("LANGFUSE_PUBLIC_KEY", "llm_observability=langfuse"))

    for var_name, reason in expected_vars:
        if var_name not in env_content:
            errors.append(f"Missing {var_name} in .env.example (expected because {reason})")

    return errors
