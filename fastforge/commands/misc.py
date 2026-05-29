"""``fastforge upgrade / audit / plugins / list-presets`` — Miscellaneous commands."""

from __future__ import annotations

import subprocess
import sys

from rich.table import Table

from fastforge.commands._shared import BANNER, console


def cmd_upgrade(features: list[str] | None = None):
    """Re-apply generator deltas to bring the project to current."""
    console.print(BANNER)

    from fastforge.commands.upgrade import run_upgrade
    from fastforge.project_config import find_project_root

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    console.print("[bold cyan]Running upgrade...[/]\n")

    try:
        results = run_upgrade(project_dir, features or None)
    except Exception as e:
        console.print(f"[red]✘ {e}[/]")
        sys.exit(1)

    # Display results
    if results["upgraded"]:
        console.print("[bold green]Upgraded:[/]")
        for item in results["upgraded"]:
            console.print(f"  [green]✔[/] {item['name']} ({item['from']} → {item['to']})")

    if results["skipped"]:
        console.print("\n[dim]Skipped:[/]")
        for item in results["skipped"]:
            console.print(f"  [dim]- {item['name']}: {item['reason']}[/]")

    if results["errors"]:
        console.print("\n[bold red]Errors:[/]")
        for item in results["errors"]:
            console.print(f"  [red]✘ {item['name']}: {item['error']}[/]")

    if not results["upgraded"] and not results["errors"]:
        console.print("[green]✔ Project is already up to date.[/]")


def cmd_audit():
    """Run a comprehensive project audit."""
    console.print(BANNER)

    from fastforge.commands.audit import run_audit
    from fastforge.project_config import find_project_root

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    console.print("[bold cyan]Running audit...[/]\n")

    try:
        results = run_audit(project_dir)
    except Exception as e:
        console.print(f"[red]✘ {e}[/]")
        sys.exit(1)

    table = Table(
        title="[bold]Project Audit[/]",
        show_header=True,
        header_style="bold bright_white",
        border_style="bright_cyan",
    )
    table.add_column("Check", style="cyan", min_width=22)
    table.add_column("Status", min_width=6)
    table.add_column("Details", style="dim")

    for check in results["checks"]:
        status = "[bold green]✔[/]" if check["passed"] else "[bold red]✘[/]"
        details = "; ".join(check["details"][:3])
        if len(check["details"]) > 3:
            details += f" (+{len(check['details']) - 3} more)"
        table.add_row(check["name"].replace("_", " ").title(), status, details)

    console.print(table)

    passed_count = sum(1 for c in results["checks"] if c["passed"])
    total = len(results["checks"])
    console.print(f"\n  [dim]{passed_count}/{total} checks passed[/]")

    if not results["passed"]:
        sys.exit(1)


def cmd_plugins(action: str | None, package: str | None):
    """Manage generator plugins."""
    console.print(BANNER)

    if action == "ls" or action is None:
        from fastforge.generator_protocol import list_generators

        generators = list_generators()

        if not generators:
            console.print(
                "[dim]No generators discovered. Built-in generators will be registered as they are migrated to the Generator protocol.[/]"
            )
            console.print(
                "\n[dim]Third-party generators register via the 'fastforge.generators' entry-point group.[/]"
            )
            return

        table = Table(
            title="[bold]Discovered Generators[/]",
            show_header=True,
            header_style="bold bright_white",
            border_style="bright_cyan",
        )
        table.add_column("Name", style="cyan", min_width=16)
        table.add_column("Version", style="green")
        table.add_column("Description", style="dim")

        for name, version, description in generators:
            table.add_row(name, version, description)

        console.print(table)
        console.print(f"\n  [dim]{len(generators)} generator(s) available[/]")

    elif action == "install":
        if not package:
            console.print(
                "[red]✘ Package name required. Usage: fastforge plugins install <package>[/]"
            )
            sys.exit(1)

        console.print(f"[bold cyan]Installing {package}...[/]\n")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print(f"[green]✔ Installed {package}[/]")
            console.print("[dim]Run 'fastforge plugins ls' to see the new generator.[/]")
        else:
            console.print(f"[red]✘ Failed to install {package}[/]")
            if result.stderr:
                console.print(f"[dim]{result.stderr[:500]}[/]")
            sys.exit(1)


def cmd_list_presets():
    """List built-in use-case presets shipped with the package."""
    console.print(BANNER)

    from fastforge.commands.new import _list_builtin_presets

    presets = _list_builtin_presets()
    if not presets:
        console.print("[dim]No built-in presets found in this installation.[/]")
        return

    table = Table(
        title="[bold]Built-in Use-Case Presets[/]",
        show_header=True,
        header_style="bold bright_white",
        border_style="bright_cyan",
    )
    table.add_column("Name", style="cyan", min_width=18)
    table.add_column("Use case", style="green")
    table.add_column("Description", style="dim")

    for p in presets:
        table.add_row(p["name"], p["use_case"], p["description"] or "")

    console.print(table)
    console.print(
        f"\n  [dim]{len(presets)} preset(s) available. "
        f"Generate with:[/] [cyan]fastforge new --preset <name>[/]\n"
        f"  [dim]Override the project name with:[/] [cyan]--name my-service[/]"
    )
