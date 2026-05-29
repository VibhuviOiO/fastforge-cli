"""Tests for CLI subcommand parsing (upgrade, audit, plugins, new --kind)."""

from __future__ import annotations

import subprocess
import sys


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run fastforge CLI as a subprocess and return result."""
    return subprocess.run(
        [sys.executable, "-m", "fastforge.cli", *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


class TestSubcommandParsing:
    """Test that subcommands are recognized and produce expected help output."""

    def test_help_shows_subcommands(self):
        result = _run_cli("--help")
        assert result.returncode == 0
        assert "upgrade" in result.stdout
        assert "audit" in result.stdout
        assert "plugins" in result.stdout

    def test_upgrade_help(self):
        result = _run_cli("upgrade", "--help")
        assert result.returncode == 0
        assert "Re-apply" in result.stdout or "upgrade" in result.stdout.lower()

    def test_audit_help(self):
        result = _run_cli("audit", "--help")
        assert result.returncode == 0
        assert "audit" in result.stdout.lower()

    def test_plugins_help(self):
        result = _run_cli("plugins", "--help")
        assert result.returncode == 0
        assert "plugins" in result.stdout.lower() or "generator" in result.stdout.lower()

    def test_new_accepts_kind_flag(self):
        result = _run_cli("new", "--help")
        assert result.returncode == 0
        assert "--kind" in result.stdout
        assert "--use-lib" in result.stdout
        assert "--workspace" in result.stdout


class TestUpgradeCommand:
    """Test upgrade command behavior when not in a project."""

    def test_upgrade_fails_outside_project(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run_cli("upgrade")
        assert result.returncode != 0


class TestAuditCommand:
    """Test audit command behavior when not in a project."""

    def test_audit_fails_outside_project(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run_cli("audit")
        assert result.returncode != 0


class TestPluginsCommand:
    """Test plugins ls command."""

    def test_plugins_ls_runs(self):
        result = _run_cli("plugins", "ls")
        # Should succeed even with no plugins (shows informational message)
        assert result.returncode == 0
