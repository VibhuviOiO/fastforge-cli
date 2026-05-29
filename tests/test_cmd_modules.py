"""Tests for CLI command modules — doctor, deploy, secure, ci, misc, add.

These test the command functions by mocking interactive prompts and
subprocess calls where needed.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal FastForge project for command tests."""
    config = {
        "project_slug": "test-app",
        "package_name": "test_app",
        "database": "none",
        "cache": "none",
        "streaming": "none",
        "logging": "structlog",
        "log_agent": "none",
        "log_target": "none",
        "precommit": "yes",
        "port": 8000,
    }
    (tmp_path / ".fastforge.json").write_text(json.dumps(config))
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("")
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "docker-compose.yml").write_text("services: {}")
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("")
    return tmp_path


# ═══════════════════════════════════════════════════════════════════════════════
# Doctor
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdDoctor:
    def test_doctor_outside_project(self):
        """Doctor prints helpful message when not in a project."""
        from fastforge.commands.doctor import cmd_doctor

        with patch("fastforge.project_config.find_project_root", return_value=None):
            cmd_doctor()

    def test_doctor_in_project(self, project_dir):
        """Doctor runs checks and prints table when in a project."""
        from fastforge.commands.doctor import cmd_doctor

        with (
            patch("fastforge.project_config.find_project_root", return_value=str(project_dir)),
            patch("subprocess.run") as mock_run,
            patch("urllib.request.urlopen", side_effect=Exception("not running")),
        ):
            docker_mock = MagicMock()
            docker_mock.returncode = 0
            test_mock = MagicMock()
            test_mock.returncode = 0
            test_mock.stdout = "5 passed\n"
            mock_run.side_effect = [docker_mock, test_mock]

            cmd_doctor()

    def test_doctor_docker_not_available(self, project_dir):
        """Doctor handles docker not being available."""
        from fastforge.commands.doctor import cmd_doctor

        with (
            patch("fastforge.project_config.find_project_root", return_value=str(project_dir)),
            patch("subprocess.run") as mock_run,
            patch("urllib.request.urlopen", side_effect=Exception("not running")),
        ):
            docker_mock = MagicMock()
            docker_mock.returncode = 1
            test_mock = MagicMock()
            test_mock.returncode = 1
            test_mock.stdout = ""
            mock_run.side_effect = [docker_mock, test_mock]

            cmd_doctor()


# ═══════════════════════════════════════════════════════════════════════════════
# Deploy
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdDeploy:
    def test_deploy_local_no_project(self):
        """deploy local exits when no project found."""
        from fastforge.commands.deploy import cmd_deploy_local

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_deploy_local()

    def test_deploy_local_no_compose(self, project_dir):
        """deploy local exits when no infra/docker-compose.yml."""
        os.remove(project_dir / "infra" / "docker-compose.yml")

        from fastforge.commands.deploy import cmd_deploy_local

        with (
            patch(
                "fastforge.project_config.find_project_root", return_value=str(project_dir)
            ),
            pytest.raises(SystemExit),
        ):
            cmd_deploy_local()

    def test_deploy_target_no_project(self):
        """deploy <target> exits when no project found."""
        from fastforge.commands.deploy import cmd_deploy

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_deploy("compose")

    def test_deploy_target_already_configured(self, project_dir):
        """deploy <target> exits early when already configured."""
        config = json.loads((project_dir / ".fastforge.json").read_text())
        config["deploy"] = ["compose"]
        (project_dir / ".fastforge.json").write_text(json.dumps(config))

        from fastforge.commands.deploy import cmd_deploy

        with patch(
            "fastforge.project_config.find_project_root", return_value=str(project_dir)
        ):
            cmd_deploy("compose")


# ═══════════════════════════════════════════════════════════════════════════════
# Secure
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdSecure:
    def test_secure_no_project(self):
        """secure exits when no project found."""
        from fastforge.commands.secure import cmd_secure

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_secure("setup")

    def test_secure_setup_already_configured(self, project_dir):
        """secure setup prints message when already configured."""
        config = json.loads((project_dir / ".fastforge.json").read_text())
        config["secure"] = "enabled"
        (project_dir / ".fastforge.json").write_text(json.dumps(config))

        from fastforge.commands.secure import cmd_secure

        with patch(
            "fastforge.project_config.find_project_root", return_value=str(project_dir)
        ):
            cmd_secure("setup")

    def test_secure_setup_with_confirm(self, project_dir):
        """secure setup creates files when confirmed."""
        from fastforge.commands.secure import cmd_secure

        with (
            patch("fastforge.project_config.find_project_root", return_value=str(project_dir)),
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_confirm.return_value.ask.return_value = True
            cmd_secure("setup")

        assert (project_dir / ".gitleaks.toml").exists()
        assert (project_dir / ".trivy.yaml").exists()

    def test_secure_setup_abort(self, project_dir):
        """secure setup does nothing when user aborts."""
        from fastforge.commands.secure import cmd_secure

        with (
            patch("fastforge.project_config.find_project_root", return_value=str(project_dir)),
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_confirm.return_value.ask.return_value = False
            cmd_secure("setup")

        assert not (project_dir / ".gitleaks.toml").exists()


# ═══════════════════════════════════════════════════════════════════════════════
# CI
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdCi:
    def test_ci_no_project(self):
        """ci exits when no project found."""
        from fastforge.commands.ci_cmd import cmd_ci

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_ci("github")

    def test_ci_already_configured(self, project_dir):
        """ci prints message when already configured."""
        config = json.loads((project_dir / ".fastforge.json").read_text())
        config["ci"] = ["github"]
        (project_dir / ".fastforge.json").write_text(json.dumps(config))

        from fastforge.commands.ci_cmd import cmd_ci

        with patch(
            "fastforge.project_config.find_project_root", return_value=str(project_dir)
        ):
            cmd_ci("github")

    def test_ci_local_no_project(self):
        """ci local exits when no project found."""
        from fastforge.commands.ci_cmd import cmd_ci

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_ci("local")


# ═══════════════════════════════════════════════════════════════════════════════
# Misc (upgrade, audit, plugins, list-presets)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdMisc:
    def test_upgrade_no_project(self):
        """upgrade exits when no project found."""
        from fastforge.commands.misc import cmd_upgrade

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_upgrade()

    def test_audit_no_project(self):
        """audit exits when no project found."""
        from fastforge.commands.misc import cmd_audit

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_audit()

    def test_plugins_ls_empty(self):
        """plugins ls works with no generators."""
        from fastforge.commands.misc import cmd_plugins

        with patch("fastforge.generator_protocol.list_generators", return_value=[]):
            cmd_plugins("ls", None)

    def test_plugins_ls_with_generators(self):
        """plugins ls displays discovered generators."""
        from fastforge.commands.misc import cmd_plugins

        mock_gens = [("test-gen", "1.0.0", "A test generator")]
        with patch("fastforge.generator_protocol.list_generators", return_value=mock_gens):
            cmd_plugins("ls", None)

    def test_plugins_default_action_is_ls(self):
        """plugins with no action defaults to ls."""
        from fastforge.commands.misc import cmd_plugins

        with patch("fastforge.generator_protocol.list_generators", return_value=[]):
            cmd_plugins(None, None)

    def test_plugins_install_no_package(self):
        """plugins install exits when no package given."""
        from fastforge.commands.misc import cmd_plugins

        with pytest.raises(SystemExit):
            cmd_plugins("install", None)

    def test_plugins_install_success(self):
        """plugins install runs pip and reports success."""
        from fastforge.commands.misc import cmd_plugins

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd_plugins("install", "fastforge-test-plugin")

    def test_plugins_install_failure(self):
        """plugins install exits on pip failure."""
        from fastforge.commands.misc import cmd_plugins

        with (
            patch("subprocess.run") as mock_run,
            pytest.raises(SystemExit),
        ):
            mock_run.return_value = MagicMock(returncode=1, stderr="not found")
            cmd_plugins("install", "nonexistent-package")

    def test_list_presets(self):
        """list-presets works without crashing."""
        from fastforge.commands.misc import cmd_list_presets

        cmd_list_presets()


# ═══════════════════════════════════════════════════════════════════════════════
# generators/secure.py — unit tests for previously untested functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecureGenerator:
    def test_secure_setup(self, project_dir):
        """secure_setup creates config files."""
        from fastforge.generators.secure import secure_setup

        result = secure_setup(str(project_dir))
        assert result["status"] == "added"
        assert ".gitleaks.toml" in result["created"]
        assert ".trivy.yaml" in result["created"]
        assert (project_dir / ".gitleaks.toml").exists()
        assert (project_dir / ".trivy.yaml").exists()

    def test_secure_setup_idempotent(self, project_dir):
        """secure_setup returns early when already configured."""
        from fastforge.generators.secure import secure_setup

        secure_setup(str(project_dir))
        result = secure_setup(str(project_dir))
        assert result["status"] == "already_configured"

    def test_secure_scan_no_trivy(self, project_dir):
        """secure_scan returns 1 when trivy is not installed."""
        from fastforge.generators.secure import secure_scan

        with patch("shutil.which", return_value=None):
            assert secure_scan(str(project_dir)) == 1

    def test_secure_sbom_no_tool(self, project_dir):
        """secure_sbom returns 1 when cyclonedx-py is not available."""
        from fastforge.generators.secure import secure_sbom

        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1)),
        ):
            assert secure_sbom(str(project_dir)) == 1

    def test_secure_license_no_tool(self, project_dir):
        """secure_license returns 1 when pip-licenses is not available."""
        from fastforge.generators.secure import secure_license

        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1)),
        ):
            assert secure_license(str(project_dir)) == 1

    def test_secure_audit_no_tool(self, project_dir):
        """secure_audit returns 1 when pip-audit is not available."""
        from fastforge.generators.secure import secure_audit

        with (
            patch("shutil.which", return_value=None),
            patch("subprocess.run", return_value=MagicMock(returncode=1)),
        ):
            assert secure_audit(str(project_dir)) == 1

    def test_secure_owasp_no_docker(self, project_dir):
        """secure_owasp returns 1 when docker is not installed."""
        from fastforge.generators.secure import secure_owasp

        with patch("shutil.which", return_value=None):
            assert secure_owasp(str(project_dir)) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# generators/redis.py
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# commands/add.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdAdd:
    def test_add_model_no_project(self):
        from fastforge.commands.add import cmd_add_model

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_add_model("item")

    def test_add_model_abort(self, project_dir):
        from fastforge.commands.add import cmd_add_model

        with (
            patch("fastforge.project_config.find_project_root", return_value=str(project_dir)),
            patch("fastforge.commands.add.text_prompt", side_effect=["item", "items"]),
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_confirm.return_value.ask.return_value = False
            cmd_add_model()

    def test_add_postgres_no_project(self):
        from fastforge.commands.add import cmd_add_postgres

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_add_postgres()

    def test_add_postgres_already_configured(self, project_dir):
        config = json.loads((project_dir / ".fastforge.json").read_text())
        config["database"] = "postgres"
        (project_dir / ".fastforge.json").write_text(json.dumps(config))

        from fastforge.commands.add import cmd_add_postgres

        with patch("fastforge.project_config.find_project_root", return_value=str(project_dir)):
            cmd_add_postgres()

    def test_add_postgres_abort(self, project_dir):
        from fastforge.commands.add import cmd_add_postgres

        with (
            patch("fastforge.project_config.find_project_root", return_value=str(project_dir)),
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_confirm.return_value.ask.return_value = False
            cmd_add_postgres()

    def test_add_kafka_no_project(self):
        from fastforge.commands.add import cmd_add_kafka

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_add_kafka()

    def test_add_kafka_already_configured(self, project_dir):
        config = json.loads((project_dir / ".fastforge.json").read_text())
        config["streaming"] = "kafka"
        (project_dir / ".fastforge.json").write_text(json.dumps(config))

        from fastforge.commands.add import cmd_add_kafka

        with patch("fastforge.project_config.find_project_root", return_value=str(project_dir)):
            cmd_add_kafka()

    def test_add_kafka_abort(self, project_dir):
        from fastforge.commands.add import cmd_add_kafka

        with (
            patch("fastforge.project_config.find_project_root", return_value=str(project_dir)),
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_confirm.return_value.ask.return_value = False
            cmd_add_kafka()

    def test_add_observability_no_project(self):
        from fastforge.commands.add import cmd_add_observability

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_add_observability()

    def test_add_observability_already_configured(self, project_dir):
        config = json.loads((project_dir / ".fastforge.json").read_text())
        config["observability"] = "enabled"
        (project_dir / ".fastforge.json").write_text(json.dumps(config))

        from fastforge.commands.add import cmd_add_observability

        with patch("fastforge.project_config.find_project_root", return_value=str(project_dir)):
            cmd_add_observability()

    def test_add_observability_abort_at_stack(self, project_dir):
        from fastforge.commands.add import cmd_add_observability

        with (
            patch("fastforge.project_config.find_project_root", return_value=str(project_dir)),
            patch("questionary.select") as mock_select,
        ):
            mock_select.return_value.ask.return_value = None
            cmd_add_observability()

    def test_add_ai_telemetry_no_project(self):
        from fastforge.commands.add import cmd_add_ai_telemetry

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_add_ai_telemetry()

    def test_add_auth_unknown_provider(self):
        from fastforge.commands.add import cmd_add_auth

        with pytest.raises(SystemExit):
            cmd_add_auth("oauth2")

    def test_add_auth_no_project(self):
        from fastforge.commands.add import cmd_add_auth

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_add_auth("jwt")

    def test_add_auth_abort(self, project_dir):
        from fastforge.commands.add import cmd_add_auth

        with (
            patch("fastforge.project_config.find_project_root", return_value=str(project_dir)),
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_confirm.return_value.ask.return_value = False
            cmd_add_auth("jwt")

    def test_add_redis_no_project(self):
        from fastforge.commands.add import cmd_add_redis

        with (
            patch("fastforge.project_config.find_project_root", return_value=None),
            pytest.raises(SystemExit),
        ):
            cmd_add_redis()

    def test_add_redis_already_configured(self, project_dir):
        config = json.loads((project_dir / ".fastforge.json").read_text())
        config["cache"] = "redis"
        (project_dir / ".fastforge.json").write_text(json.dumps(config))

        from fastforge.commands.add import cmd_add_redis

        with patch("fastforge.project_config.find_project_root", return_value=str(project_dir)):
            cmd_add_redis()

    def test_add_redis_different_cache(self, project_dir):
        config = json.loads((project_dir / ".fastforge.json").read_text())
        config["cache"] = "memcached"
        (project_dir / ".fastforge.json").write_text(json.dumps(config))

        from fastforge.commands.add import cmd_add_redis

        with patch("fastforge.project_config.find_project_root", return_value=str(project_dir)):
            cmd_add_redis()

    def test_add_redis_abort(self, project_dir):
        from fastforge.commands.add import cmd_add_redis

        with (
            patch("fastforge.project_config.find_project_root", return_value=str(project_dir)),
            patch("questionary.confirm") as mock_confirm,
        ):
            mock_confirm.return_value.ask.return_value = False
            cmd_add_redis()


# ═══════════════════════════════════════════════════════════════════════════════
# generators/redis.py
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def redis_project(tmp_path):
    """Create a minimal FastForge project layout for redis tests."""
    config = {
        "project_slug": "my-app",
        "package_name": "my_app",
        "cache": "none",
        "database": "none",
    }
    (tmp_path / ".fastforge.json").write_text(json.dumps(config))

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "config.py").write_text(
        'from pydantic_settings import BaseSettings\n\n\nclass Settings(BaseSettings):\n    app_name: str = "my-app"\n\n    model_config = {"env_prefix": ""}\n\n\nsettings = Settings()\n'
    )
    (app_dir / "main.py").write_text(
        "from contextlib import asynccontextmanager\nfrom fastapi import FastAPI\nfrom app.config import settings\n\n@asynccontextmanager\nasync def lifespan(app: FastAPI):\n    yield\n\napp = FastAPI(lifespan=lifespan)\n"
    )
    (app_dir / "cache.py").write_text('"""Cache — none configured."""\n')
    (tmp_path / ".env.staging").write_text("APP_NAME=my-app\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "my-app"\ndependencies = [\n    "fastapi>=0.100",\n]\n'
    )
    (tmp_path / "infra").mkdir()
    return tmp_path


class TestRedisGenerator:
    def test_adds_redis_successfully(self, redis_project):
        from fastforge.generators.redis import add_redis

        result = add_redis(str(redis_project))

        assert result["status"] == "added"
        assert "infra/docker-compose.redis.yml" in result["created"]
        assert ".fastforge.json" in result["modified"]

        config = json.loads((redis_project / ".fastforge.json").read_text())
        assert config["cache"] == "redis"

        config_content = (redis_project / "app" / "config.py").read_text()
        assert "redis_url" in config_content

        cache_content = (redis_project / "app" / "cache.py").read_text()
        assert "redis.asyncio" in cache_content

        compose = (redis_project / "infra" / "docker-compose.redis.yml").read_text()
        assert "redis:7-alpine" in compose

        env = (redis_project / ".env.staging").read_text()
        assert "REDIS_URL" in env

        pyproject = (redis_project / "pyproject.toml").read_text()
        assert "redis[hiredis]" in pyproject

    def test_idempotent_when_already_configured(self, redis_project):
        from fastforge.generators.redis import add_redis

        add_redis(str(redis_project))
        result = add_redis(str(redis_project))
        assert result["status"] == "already_configured"

    def test_raises_when_different_cache_exists(self, redis_project):
        from fastforge.generators.redis import add_redis

        config = json.loads((redis_project / ".fastforge.json").read_text())
        config["cache"] = "memcached"
        (redis_project / ".fastforge.json").write_text(json.dumps(config))

        with pytest.raises(ValueError, match="already uses cache"):
            add_redis(str(redis_project))

    def test_wires_close_cache_into_lifespan(self, redis_project):
        from fastforge.generators.redis import add_redis

        add_redis(str(redis_project))

        main_content = (redis_project / "app" / "main.py").read_text()
        assert "close_cache" in main_content


# ═══════════════════════════════════════════════════════════════════════════════
# generators/ci.py — ci_local
# ═══════════════════════════════════════════════════════════════════════════════


class TestCiLocal:
    def test_ci_local_all_pass(self, project_dir):
        """ci_local returns 0 when all steps pass."""
        from fastforge.generators.ci import ci_local

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = ci_local(str(project_dir))
        assert result == 0

    def test_ci_local_lint_fails(self, project_dir):
        """ci_local returns 1 when a step fails."""
        from fastforge.generators.ci import ci_local

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = ci_local(str(project_dir))
        assert result == 1

    def test_ci_local_with_bandit(self, project_dir):
        """ci_local includes bandit when available."""
        from fastforge.generators.ci import ci_local

        with (
            patch("subprocess.run") as mock_run,
            patch("shutil.which", side_effect=lambda x: "/usr/bin/" + x if x == "bandit" else None),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = ci_local(str(project_dir))
        assert result == 0
        # Verify bandit was called
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("bandit" in c for c in calls)
