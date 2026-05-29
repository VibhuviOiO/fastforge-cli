"""``fastforge ci`` — Generate CI/CD pipeline or run locally."""

from __future__ import annotations

import sys

import questionary
from rich.panel import Panel

from fastforge.commands._shared import BANNER, console


def cmd_ci(provider: str):
    """Generate CI/CD pipeline for a provider or run locally."""
    console.print(BANNER)

    from fastforge.project_config import find_project_root, load_config

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    config = load_config(project_dir)

    # ── Run pipeline locally ─────────────────────────────
    if provider == "local":
        from fastforge.generators.ci import ci_local

        console.print(f"[dim]Project: {config.get('project_slug', 'unknown')}[/]\n")
        console.print(
            Panel(
                "[bold]This will run locally:[/]\n"
                "  • ruff check (lint)\n"
                "  • ruff format --check (formatting)\n"
                "  • pytest (tests)\n"
                "  • bandit (SAST, if installed)\n"
                "  • pip-audit (dependency audit, if installed)\n"
                "  • docker build (if Dockerfile exists)\n"
                "  • trivy (container scan, if installed)",
                title="[bold bright_cyan]📋 CI Local Pipeline[/]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

        confirm = questionary.confirm("Proceed?", default=True).ask()
        if not confirm:
            console.print("[yellow]Aborted.[/]")
            return

        sys.exit(ci_local(project_dir))

    # ── Generate CI config file ──────────────────────────
    from fastforge.generators.ci import add_ci

    ci_list = config.get("ci", [])

    if provider in ci_list:
        console.print(f"[green]✔ {provider} CI/CD is already configured in this project.[/]")
        return

    provider_desc = {
        "github": ("GitHub Actions", ".github/workflows/ci.yml"),
        "gitlab": ("GitLab CI", ".gitlab-ci.yml"),
        "bitbucket": ("Bitbucket Pipelines", "bitbucket-pipelines.yml"),
        "jenkins": ("Jenkins", "Jenkinsfile"),
    }

    name, file_path = provider_desc[provider]

    console.print(f"[dim]Project: {config.get('project_slug', 'unknown')}[/]\n")
    console.print(
        Panel(
            f"[bold]This will create:[/]\n"
            f"  + {file_path}\n\n"
            "[bold]Pipeline includes:[/]\n"
            "  • Test & Lint (ruff + pytest + coverage)\n"
            "  • SAST (Bandit security scan)\n"
            "  • Secret scanning (Gitleaks)\n"
            "  • Dependency audit (pip-audit)\n"
            "  • Docker build + push\n"
            "  • Trivy container scanning",
            title=f"[bold bright_cyan]📋 CI/CD → {name}[/]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    confirm = questionary.confirm("Proceed?", default=True).ask()
    if not confirm:
        console.print("[yellow]Aborted.[/]")
        return

    try:
        result = add_ci(project_dir, provider)
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]✘ {e}[/]")
        sys.exit(1)

    lines = []
    for f in result.get("created", []):
        lines.append(f"  [green]+[/] {f}")
    for f in result.get("modified", []):
        lines.append(f"  [yellow]~[/] {f}")

    console.print()
    console.print(
        Panel(
            f"[bold green]✔ {name} pipeline added[/]\n\n" + "\n".join(lines),
            title="[bold bright_cyan]🚀 Done[/]",
            border_style="green",
            padding=(1, 2),
        )
    )
