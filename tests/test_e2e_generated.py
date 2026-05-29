"""End-to-end test: generate a project from preset, install it, and run its tests.

This test validates that generated code is functional — not just syntactically
correct. It generates a simple-fastapi project, installs it in a temp venv,
and runs pytest inside the generated project.

Marked with @pytest.mark.e2e so it can be filtered in CI:
    pytest -m e2e         # run only E2E tests
    pytest -m "not e2e"   # skip E2E tests
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.e2e
class TestGeneratedProjectTests:
    """Generate a project and run its test suite."""

    def _generate_project(self, tmp_dir: Path, preset_name: str = "simple-fastapi") -> Path:
        """Generate a project from a built-in preset into tmp_dir."""
        from fastforge.commands.new import (
            _load_generation_context_from_file,
            _resolve_preset,
            generate,
        )

        preset_path = _resolve_preset(preset_name)
        ctx = _load_generation_context_from_file(preset_path)

        orig_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_dir))
            generate(ctx)
        finally:
            os.chdir(orig_cwd)

        project_dir = tmp_dir / ctx["project_name"].lower().replace(" ", "-").replace("_", "-")
        assert project_dir.exists(), f"Project not generated at {project_dir}"
        return project_dir

    def _create_venv(self, project_dir: Path) -> Path:
        """Create a virtual environment in the project directory."""
        venv_dir = project_dir / ".venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
            capture_output=True,
        )
        return venv_dir

    def _install_project(self, project_dir: Path, venv_dir: Path) -> None:
        """Install the generated project with dev deps into the venv."""
        pip = venv_dir / "bin" / "pip"
        result = subprocess.run(
            [str(pip), "install", "-e", ".[dev]"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            pytest.fail(f"pip install failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")

    def _run_tests(self, project_dir: Path, venv_dir: Path) -> subprocess.CompletedProcess:
        """Run pytest inside the generated project."""
        python = venv_dir / "bin" / "python"
        return subprocess.run(
            [str(python), "-m", "pytest", "tests/", "-x", "-q", "--tb=short"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_simple_fastapi_tests_pass(self, tmp_path: Path):
        """Generate simple-fastapi preset, install it, run its tests."""
        project_dir = self._generate_project(tmp_path, "simple-fastapi")

        venv_dir = self._create_venv(project_dir)
        self._install_project(project_dir, venv_dir)

        result = self._run_tests(project_dir, venv_dir)

        assert result.returncode == 0, (
            f"Generated project tests FAILED:\n"
            f"--- stdout ---\n{result.stdout[-3000:]}\n"
            f"--- stderr ---\n{result.stderr[-1000:]}"
        )
        # Verify at least some tests ran
        assert "passed" in result.stdout

    def test_postgres_api_compiles(self, tmp_path: Path):
        """Generate postgres-api preset and verify it compiles (can't run without DB)."""
        project_dir = self._generate_project(tmp_path, "postgres-api")

        # Just verify it compiles — postgres tests need a live DB
        result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", str(project_dir / "app")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"compileall failed:\n{result.stdout}\n{result.stderr}"

    def test_event_service_compiles(self, tmp_path: Path):
        """Generate event-service preset and verify it compiles."""
        project_dir = self._generate_project(tmp_path, "event-service")

        result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", str(project_dir / "app")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"compileall failed:\n{result.stdout}\n{result.stderr}"
