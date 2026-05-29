"""``fastforge deploy`` — Deploy or generate deployment manifests."""

from __future__ import annotations

import os
import subprocess
import sys

import questionary
from rich.panel import Panel

from fastforge.commands._shared import BANNER, console


def cmd_deploy(target: str):
    """Deploy the service or generate deployment manifests."""
    if target == "local":
        cmd_deploy_local()
        return

    console.print(BANNER)

    from fastforge.generators.deploy import (
        deploy_compose,
        deploy_helm,
        deploy_k8s,
        deploy_marathon,
        deploy_swarm,
    )
    from fastforge.project_config import find_project_root, load_config

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    config = load_config(project_dir)
    deploy_list = config.get("deploy", [])

    if target in deploy_list:
        console.print(f"[green]✔ {target} deployment is already configured in this project.[/]")
        return

    target_names = {
        "compose": "Docker Compose (production)",
        "swarm": "Docker Swarm",
        "k8s": "Kubernetes",
        "helm": "Helm chart",
        "marathon": "Marathon",
    }

    console.print(f"[dim]Project: {config.get('project_slug', 'unknown')}[/]\n")
    console.print(
        Panel(
            f"[bold]Generate {target_names[target]} deployment manifests[/]\n\n"
            f"Creates deploy/{target}/ directory with production-ready manifests.",
            title=f"[bold bright_cyan]📋 Deploy → {target_names[target]}[/]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    confirm = questionary.confirm("Proceed?", default=True).ask()
    if not confirm:
        console.print("[yellow]Aborted.[/]")
        return

    generators = {
        "compose": deploy_compose,
        "swarm": deploy_swarm,
        "k8s": deploy_k8s,
        "helm": deploy_helm,
        "marathon": deploy_marathon,
    }

    try:
        result = generators[target](project_dir)
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
            f"[bold green]✔ {target_names[target]} manifests generated[/]\n\n" + "\n".join(lines),
            title="[bold bright_cyan]🚀 Done[/]",
            border_style="green",
            padding=(1, 2),
        )
    )


def cmd_deploy_local():
    """Deploy locally using Docker Compose — auto-detects all infra compose files."""
    console.print(BANNER)

    from fastforge.project_config import find_project_root

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    infra_dir = os.path.join(project_dir, "infra")
    base_compose = os.path.join(infra_dir, "docker-compose.yml")
    if not os.path.isfile(base_compose):
        console.print("[red]✘ No infra/docker-compose.yml found.[/]")
        sys.exit(1)

    # Auto-detect all docker-compose.*.yml files
    compose_files = [base_compose]
    if os.path.isdir(infra_dir):
        for f in sorted(os.listdir(infra_dir)):
            if f.startswith("docker-compose.") and f.endswith(".yml") and f != "docker-compose.yml":
                compose_files.append(os.path.join(infra_dir, f))

    # Build the command
    cmd = ["docker", "compose"]
    for cf in compose_files:
        cmd.extend(["-f", cf])
    cmd.extend(["up", "--build"])

    # Show what we're starting
    console.print("[bold cyan]Starting local services...[/]\n")
    for cf in compose_files:
        console.print(f"  [dim]→ {os.path.relpath(cf, project_dir)}[/]")
    console.print()

    result = subprocess.run(cmd, cwd=project_dir)
    sys.exit(result.returncode)
