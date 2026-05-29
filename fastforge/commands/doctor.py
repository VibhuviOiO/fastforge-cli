"""``fastforge doctor`` — Check project health."""

from __future__ import annotations

import os
import subprocess
import sys

from rich.table import Table

from fastforge.commands._shared import BANNER, console


def cmd_doctor():
    """Check project health."""
    console.print(BANNER)

    from fastforge.project_config import find_project_root, load_config

    checks: list[tuple[str, bool, str]] = []

    # 1. FastForge project
    project_dir = find_project_root()
    if project_dir:
        config = load_config(project_dir)
        checks.append(("FastForge project", True, config.get("project_slug", "unknown")))
    else:
        console.print(
            "[yellow]ℹ[/]  Not inside a FastForge project — nothing to check here.\n\n"
            "  [dim]Generate one with:[/]  [bold cyan]fastforge new[/]\n"
            "  [dim]Then re-run:[/]         [bold cyan]cd <your-project> && fastforge doctor[/]\n"
        )
        return

    # 2. Logging configured
    logging_val = config.get("logging", "none")
    if logging_val != "none":
        agent = config.get("log_agent", "none")
        detail = logging_val
        if agent != "none":
            detail += f" + {agent} → {config.get('log_target', 'none')}"
        checks.append(("Logging", True, detail))
    else:
        checks.append(("Logging", False, "disabled"))

    # 3. Docker available
    docker_result = subprocess.run(["docker", "info"], capture_output=True)
    checks.append(
        (
            "Docker",
            docker_result.returncode == 0,
            "running" if docker_result.returncode == 0 else "not available",
        )
    )

    # 4. Infra compose exists
    compose_path = os.path.join(project_dir, "infra", "docker-compose.yml")
    checks.append(
        (
            "Infrastructure",
            os.path.isfile(compose_path),
            "infra/docker-compose.yml" if os.path.isfile(compose_path) else "missing",
        )
    )

    # 5. Health endpoint
    port = config.get("port", 8000)
    try:
        import urllib.request

        response = urllib.request.urlopen(f"http://localhost:{port}/livez", timeout=3)
        checks.append(
            ("Health endpoint", response.status == 200, f"http://localhost:{port}/livez")
        )
    except Exception:
        checks.append(("Health endpoint", False, f"not responding on port {port}"))

    # 6. Tests
    test_result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-x", "-q", "--tb=no", "--no-header"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if test_result.returncode == 0:
        last_line = (
            test_result.stdout.strip().split("\n")[-1] if test_result.stdout.strip() else "passed"
        )
        checks.append(("Tests", True, last_line))
    else:
        checks.append(("Tests", False, "failing"))

    # 7. Pre-commit
    precommit_ok = config.get("precommit") == "yes" and os.path.isfile(
        os.path.join(project_dir, ".pre-commit-config.yaml")
    )
    checks.append(("Pre-commit", precommit_ok, "configured" if precommit_ok else "not configured"))

    # 8. Database
    db = config.get("database", "none")
    checks.append(("Database", db != "none", db if db != "none" else "none (in-memory)"))

    _print_doctor_table(checks)


def _print_doctor_table(checks: list[tuple[str, bool, str]]) -> None:
    """Render the doctor results table."""
    table = Table(
        title="[bold]Project Health Check[/]",
        show_header=True,
        header_style="bold bright_white",
        border_style="bright_cyan",
    )
    table.add_column("Check", style="cyan", min_width=20)
    table.add_column("Status", min_width=6)
    table.add_column("Details", style="dim")

    passed = 0
    for name, ok, detail in checks:
        status = "[bold green]✔[/]" if ok else "[bold red]✘[/]"
        table.add_row(name, status, str(detail))
        if ok:
            passed += 1

    console.print()
    console.print(table)
    console.print(f"\n  [dim]{passed}/{len(checks)} checks passed[/]")
