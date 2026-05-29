"""``fastforge secure`` — Security tooling and checks."""

from __future__ import annotations

import sys

import questionary
from rich.panel import Panel

from fastforge.commands._shared import BANNER, console


def cmd_secure(action: str):
    """Run a security command."""
    console.print(BANNER)

    from fastforge.generators.secure import (
        secure_audit,
        secure_license,
        secure_owasp,
        secure_sbom,
        secure_scan,
        secure_setup,
    )
    from fastforge.project_config import find_project_root, load_config

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    config = load_config(project_dir)
    console.print(f"[dim]Project: {config.get('project_slug', 'unknown')}[/]\n")

    if action == "setup":
        if config.get("secure") == "enabled":
            console.print("[green]✔ Security configs are already set up in this project.[/]")
            return

        console.print(
            Panel(
                "[bold]This will create:[/]\n"
                "  + .gitleaks.toml — Secret scanning config\n"
                "  + .trivy.yaml — Container vulnerability scanner config",
                title="[bold bright_cyan]📋 Security Setup[/]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

        confirm = questionary.confirm("Proceed?", default=True).ask()
        if not confirm:
            console.print("[yellow]Aborted.[/]")
            return

        try:
            result = secure_setup(project_dir)
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
                "[bold green]✔ Security configs added[/]\n\n" + "\n".join(lines),
                title="[bold bright_cyan]🚀 Done[/]",
                border_style="green",
                padding=(1, 2),
            )
        )

    elif action == "scan":
        sys.exit(secure_scan(project_dir))

    elif action == "sbom":
        sys.exit(secure_sbom(project_dir))

    elif action == "license":
        sys.exit(secure_license(project_dir))

    elif action == "audit":
        sys.exit(secure_audit(project_dir))

    elif action == "owasp":
        sys.exit(secure_owasp(project_dir))
