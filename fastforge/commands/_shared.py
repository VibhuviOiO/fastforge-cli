"""Shared utilities for CLI command modules.

All command modules import from here rather than re-declaring console/style.
"""

from __future__ import annotations

from collections.abc import Callable

import questionary
from rich.console import Console
from rich.rule import Rule

from fastforge import __version__

console = Console()

BANNER = f"""
[bold bright_blue]  ╔═╗╔═╗╔═╗╔╦╗  ╔═╗╔═╗╦═╗╔═╗╔═╗[/]
[bold bright_cyan]  ╠╣ ╠═╣╚═╗ ║   ╠╣ ║ ║╠╦╝║ ╦║╣ [/]
[bold cyan]  ╚  ╩ ╩╚═╝ ╩   ╚  ╚═╝╩╚═╚═╝╚═╝[/]
[bold white]  Production-grade FastAPI Generator[/]  [dim italic]v{__version__}[/]
"""

STYLE_SECTION = "bold bright_cyan"
STYLE_HINT = "dim italic"
STYLE_SUCCESS = "bold green"
STYLE_WARN = "bold yellow"

CUSTOM_STYLE = questionary.Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "fg:white bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("answer", "fg:ansibrightgreen bold"),
    ]
)


def section(title: str) -> None:
    """Print a styled section header."""
    console.print()
    console.print(Rule(f"[{STYLE_SECTION}] {title} [/]", style="bright_cyan"))


def text_prompt(
    message: str,
    *,
    default: str,
    validate: Callable[[str], bool | str] | None = None,
) -> str | None:
    """Prompt for text without pre-filling the input buffer."""
    prompt = f"{message} [default: {default}]"
    while True:
        value = questionary.text(prompt, style=CUSTOM_STYLE).ask()
        if value is None:
            return None

        effective = value.strip() or default
        if validate is None:
            return effective

        verdict = validate(effective)
        if verdict is True or verdict is None:
            return effective

        console.print(f"[{STYLE_WARN}]{verdict}[/]")
