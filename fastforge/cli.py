"""FastForge CLI — Interactive project generator for production-grade FastAPI applications."""

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import questionary
from cookiecutter.main import cookiecutter
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from fastforge import __version__

console = Console()

TEMPLATE_DIR = str(Path(__file__).parent / "template")
INFRA_TEMPLATE_DIR = str(Path(__file__).parent / "infra_template")


# ── File categories for selective overwrite ──────────────────────────────────
FILE_CATEGORIES = {
    "Docker & Infrastructure": {
        "description": "Dockerfile, docker-compose, .dockerignore, docker/",
        "patterns": [
            "Dockerfile", ".dockerignore", "docker-compose.debug.yml",
            "infra/",
        ],
    },
    "Configuration": {
        "description": "pyproject.toml, .env, pre-commit, quality gate configs",
        "patterns": [
            "pyproject.toml", ".env.staging", ".pre-commit-config.yaml",
            ".secrets.baseline", "sonar-project.properties", "qodana.yaml",
            ".codeclimate.yml",
        ],
    },
    "App framework": {
        "description": "main.py, config, logging, middleware, dependencies",
        "patterns": [
            "app/main.py", "app/config.py", "app/logging_config.py",
            "app/dependencies.py", "app/middleware/", "app/__init__.py",
            "app/api/__init__.py", "app/api/exception_handlers.py",
        ],
    },
    "Business logic": {
        "description": "routes, models, services, repositories",
        "patterns": [
            "app/api/routes/", "app/api/models/", "app/services/",
            "app/repositories/",
        ],
    },
    "Tests": {
        "description": "tests/",
        "patterns": ["tests/"],
    },
    "Docs": {
        "description": "README.md",
        "patterns": ["README.md"],
    },
}


def _categorize_file(rel_path: str) -> str:
    """Return the category name for a file path, or 'Other'."""
    for category, info in FILE_CATEGORIES.items():
        for pattern in info["patterns"]:
            if pattern.endswith("/"):
                if rel_path.startswith(pattern):
                    return category
            elif rel_path == pattern:
                return category
    return "Other"


def _collect_changes(
    existing_dir: str, generated_dir: str
) -> dict[str, list[tuple[str, str]]]:
    """Compare generated vs existing project. Returns {category: [(rel_path, status)]}."""
    changes: dict[str, list[tuple[str, str]]] = {}

    for root, _dirs, files in os.walk(generated_dir):
        for f in files:
            gen_path = os.path.join(root, f)
            rel_path = os.path.relpath(gen_path, generated_dir)
            existing_path = os.path.join(existing_dir, rel_path)

            if not os.path.exists(existing_path):
                status = "new"
            elif not filecmp.cmp(gen_path, existing_path, shallow=False):
                status = "modified"
            else:
                continue  # identical, skip

            category = _categorize_file(rel_path)
            changes.setdefault(category, []).append((rel_path, status))

    return changes


def _apply_selective_overwrite(
    existing_dir: str, generated_dir: str, selected_categories: list[str],
    changes: dict[str, list[tuple[str, str]]],
) -> list[str]:
    """Copy files from generated_dir to existing_dir for selected categories. Returns log."""
    log = []
    for category in selected_categories:
        for rel_path, status in changes.get(category, []):
            src = os.path.join(generated_dir, rel_path)
            dst = os.path.join(existing_dir, rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            icon = "+" if status == "new" else "~"
            log.append(f"  [bold green]{icon}[/] {rel_path}")
    return log

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

# Questionary styling
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


# ═══════════════════════════════════════════════════════════════════════════════
# fastforge  (main — developer app)
# ═══════════════════════════════════════════════════════════════════════════════


def _section(title: str) -> None:
    """Print a styled section header."""
    console.print()
    console.print(Rule(f"[{STYLE_SECTION}] {title} [/]", style="bright_cyan"))


def ask_basics() -> dict:
    """Project basics — always asked."""
    _section("📦  Project Basics")
    return {
        "project_name": questionary.text(
            "Project name:",
            default="my-fastapi-service",
            validate=lambda x: bool(x.strip()) or "Required",
            style=CUSTOM_STYLE,
        ).ask(),
        "description": questionary.text(
            "Description:",
            default="A production-grade FastAPI service",
            style=CUSTOM_STYLE,
        ).ask(),
        "author_name": questionary.text("Author name:", default="Your Name", style=CUSTOM_STYLE).ask(),
        "author_email": questionary.text("Author email:", default="you@example.com", style=CUSTOM_STYLE).ask(),
        "python_version": questionary.select(
            "Python version:",
            choices=["3.13", "3.12", "3.11"],
            default="3.13",
            style=CUSTOM_STYLE,
        ).ask(),
        "port": questionary.text("HTTP port:", default="8000", style=CUSTOM_STYLE).ask(),
    }


def ask_model() -> dict:
    """Model name — drives CRUD stack generation."""
    _section("🧩  Domain Model")
    console.print(f"  [{STYLE_HINT}]Generates: route → service → repository → DB model (SOLID)[/]")

    model_name = questionary.text(
        "Model name (singular, lowercase):",
        default="item",
        validate=lambda x: (x.isidentifier() and x.islower()) or "Must be a valid lowercase Python identifier",
        style=CUSTOM_STYLE,
    ).ask()

    model_name_class = model_name.capitalize()
    model_name_plural = model_name + "s"

    plural = questionary.text(
        "Plural form (for route /api/v1/...):",
        default=model_name_plural,
        style=CUSTOM_STYLE,
    ).ask()

    return {
        "model_name": model_name,
        "model_name_class": model_name_class,
        "model_name_plural": plural,
    }


def ask_logging_basic() -> dict:
    """Logging — basic mode (always structlog + json)."""
    _section("📋  Logging")
    console.print(f"  [{STYLE_HINT}]Stdout → logs visible via 'docker logs' (K8s/cloud-native)[/]")
    console.print(f"  [{STYLE_HINT}]Stdout + File → enables Vector/Fluent Bit to collect & forward logs[/]")
    log_output = questionary.select(
        "Log output:",
        choices=[
            questionary.Choice("Stdout only — logs print to container output", value="stdout"),
            questionary.Choice("Stdout + File — write to /var/log/app/ for log agent forwarding", value="file"),
        ],
        default="stdout",
        style=CUSTOM_STYLE,
    ).ask()

    result = {
        "logging": "structlog",
        "log_format": "json",
        "log_connector": log_output,
        "log_agent": "none",
        "log_target": "none",
    }

    if log_output == "file":
        result.update(_ask_log_agent())

    return result


def ask_docker_basic() -> dict:
    """Docker — basic mode (always yes, just ask about debug)."""
    _section("🐳  Docker")
    debug = questionary.confirm(
        "Include debug compose (debugpy on port 5678)?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    return {"docker": "yes", "docker_debug": "yes" if debug else "no"}


# ── Log agent helper ─────────────────────────────────────────────────────────

def _ask_log_agent() -> dict:
    """Ask which log collection agent to include as a sidecar."""
    console.print(f"  [{STYLE_HINT}]A log agent runs as a sidecar in docker-compose, reads log files,[/]")
    console.print(f"  [{STYLE_HINT}]and forwards them to your chosen target (Elasticsearch, Kafka, etc.)[/]")
    agent = questionary.select(
        "Log collection agent (sidecar in docker-compose):",
        choices=[
            questionary.Choice("None — I'll collect logs myself or use an existing daemon", value="none"),
            questionary.Choice("Vector — Rust, lightweight, recommended", value="vector"),
            questionary.Choice("Fluent Bit — C, CNCF graduated, widely adopted", value="fluentbit"),
        ],
        default="vector",
        style=CUSTOM_STYLE,
    ).ask()

    if agent == "none":
        return {"log_agent": agent, "log_target": "none"}

    console.print(f"  [{STYLE_HINT}]Where should {agent} send the collected logs?[/]")
    target = questionary.select(
        "Log target:",
        choices=[
            questionary.Choice("Elasticsearch — full-text search & analytics (ELK stack)", value="elasticsearch"),
            questionary.Choice("OpenSearch — AWS-managed alternative to Elasticsearch", value="opensearch"),
            questionary.Choice("Kafka — stream to a topic for downstream consumers", value="kafka"),
            questionary.Choice("Loki — Grafana's lightweight log aggregation", value="loki"),
            questionary.Choice("HTTP endpoint — generic HTTP log ingestion API", value="http"),
        ],
        style=CUSTOM_STYLE,
    ).ask()

    return {"log_agent": agent, "log_target": target}


# ── Advanced-only questions ──────────────────────────────────────────────────

def ask_database() -> dict:
    """Database."""
    _section("🗄️  Database")
    db = questionary.select(
        "Database:",
        choices=[
            questionary.Choice("None (in-memory store)", value="none"),
            questionary.Choice("PostgreSQL (SQLAlchemy async + asyncpg)", value="postgres"),
            questionary.Choice("MySQL (SQLAlchemy async + aiomysql)", value="mysql"),
            questionary.Choice("SQLite (SQLAlchemy async + aiosqlite)", value="sqlite"),
            questionary.Choice("MongoDB (Motor async)", value="mongodb"),
        ],
        default="none",
        style=CUSTOM_STYLE,
    ).ask()

    return {"database": db}


def ask_cache() -> dict:
    """Cache backend."""
    _section("⚡  Cache")
    cache = questionary.select(
        "Cache backend:",
        choices=[
            questionary.Choice("None", value="none"),
            questionary.Choice("Redis", value="redis"),
            questionary.Choice("Memcached", value="memcached"),
            questionary.Choice("In-memory (cachetools TTLCache)", value="in_memory"),
        ],
        default="none",
        style=CUSTOM_STYLE,
    ).ask()

    return {"cache": cache}


def ask_streaming() -> dict:
    """Event streaming / messaging."""
    _section("📡  Streaming")
    streaming = questionary.select(
        "Event streaming:",
        choices=[
            questionary.Choice("None", value="none"),
            questionary.Choice("Kafka (aiokafka)", value="kafka"),
            questionary.Choice("RabbitMQ (aio-pika)", value="rabbitmq"),
            questionary.Choice("Redis Pub/Sub", value="redis_pubsub"),
            questionary.Choice("NATS", value="nats"),
        ],
        default="none",
        style=CUSTOM_STYLE,
    ).ask()

    return {"streaming": streaming}


def ask_secrets() -> dict:
    """Secret management provider."""
    _section("🔐  Secrets")
    secrets = questionary.select(
        "Secret management:",
        choices=[
            questionary.Choice("None (use .env / pydantic-settings)", value="none"),
            questionary.Choice("HashiCorp Vault", value="vault"),
            questionary.Choice("AWS Secrets Manager", value="aws_sm"),
            questionary.Choice("Azure Key Vault", value="azure_kv"),
            questionary.Choice("GCP Secret Manager", value="gcp_sm"),
        ],
        default="none",
        style=CUSTOM_STYLE,
    ).ask()

    return {"secrets": secrets}


def ask_logging_advanced() -> dict:
    """Logging — advanced mode (choice of structlog or none, format, output)."""
    _section("📋  Logging")
    enabled = questionary.confirm("Enable structured logging (structlog)?", default=True, style=CUSTOM_STYLE).ask()
    if not enabled:
        return {"logging": "none", "log_format": "console", "log_connector": "stdout", "log_agent": "none", "log_target": "none"}

    log_format = questionary.select(
        "Log format:",
        choices=["json", "console"],
        default="json",
        style=CUSTOM_STYLE,
    ).ask()

    console.print(f"  [{STYLE_HINT}]Stdout → logs visible via 'docker logs' (K8s/cloud-native)[/]")
    console.print(f"  [{STYLE_HINT}]Stdout + File → enables Vector/Fluent Bit to collect & forward logs[/]")
    log_connector = questionary.select(
        "Log output:",
        choices=[
            questionary.Choice("Stdout only — logs print to container output", value="stdout"),
            questionary.Choice("Stdout + File — write to /var/log/app/ for log agent forwarding", value="file"),
        ],
        default="stdout",
        style=CUSTOM_STYLE,
    ).ask()

    result = {"logging": "structlog", "log_format": log_format, "log_connector": log_connector, "log_agent": "none", "log_target": "none"}

    if log_connector == "file":
        result.update(_ask_log_agent())

    return result


def ask_quality_gate() -> dict:
    """Quality gate tool."""
    _section("🛡️  Quality Gate")
    gate = questionary.select(
        "Quality gate:",
        choices=[
            questionary.Choice("None", value="none"),
            questionary.Choice("SonarQube (self-hosted)", value="sonarqube"),
            questionary.Choice("SonarCloud (cloud)", value="sonarcloud"),
            questionary.Choice("Qodana (JetBrains)", value="qodana"),
            questionary.Choice("CodeClimate", value="codeclimate"),
        ],
        default="none",
        style=CUSTOM_STYLE,
    ).ask()

    return {"quality_gate": gate}


def ask_containerization() -> dict:
    """Docker setup — advanced mode."""
    _section("🐳  Docker")
    enabled = questionary.confirm("Enable Docker?", default=True, style=CUSTOM_STYLE).ask()
    if not enabled:
        return {"docker": "no", "docker_debug": "no"}

    debug = questionary.confirm(
        "Include debug compose (debugpy on port 5678)?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    return {"docker": "yes", "docker_debug": "yes" if debug else "no"}


def ask_precommit() -> dict:
    """Pre-commit hooks."""
    _section("🪝  Pre-commit")
    enabled = questionary.confirm("Enable pre-commit hooks (ruff, pytest)?", default=True, style=CUSTOM_STYLE).ask()
    return {"precommit": "yes" if enabled else "no"}


# ── Summary & Generation ─────────────────────────────────────────────────────

def show_summary(ctx: dict, mode: str) -> None:
    """Display a rich summary of selected features."""
    table = Table(
        title=f"[bold]FastForge Configuration[/]  [dim]({mode} mode)[/]",
        show_header=True,
        header_style="bold bright_white",
        border_style="bright_cyan",
        title_style="bold bright_cyan",
    )
    table.add_column("Feature", style="cyan", min_width=16)
    table.add_column("Value", style="bright_green")

    table.add_row("Project", f"[bold]{ctx['project_name']}[/] [dim](Python {ctx['python_version']})[/]")
    table.add_row("Port", ctx["port"])
    table.add_row("Model", f"[bold]{ctx['model_name_class']}[/] → /api/v1/{ctx['model_name_plural']}")
    table.add_row("Database", ctx["database"] if ctx["database"] != "none" else "[dim]in-memory[/]")

    if mode == "advanced":
        table.add_row("Cache", ctx["cache"] if ctx["cache"] != "none" else "[dim]none[/]")
        table.add_row("Streaming", ctx["streaming"] if ctx["streaming"] != "none" else "[dim]none[/]")
        table.add_row("Secrets", ctx["secrets"] if ctx["secrets"] != "none" else "[dim]none[/]")

    log_val = ctx["logging"]
    if log_val != "none":
        agent_tag = ""
        if ctx.get("log_agent", "none") != "none":
            target = ctx.get('log_target', 'none')
            agent_tag = f" + {ctx['log_agent']} → {target}"
        table.add_row("Logging", f"structlog [dim]({ctx['log_format']} → {ctx['log_connector']}{agent_tag})[/]")
    else:
        table.add_row("Logging", "[dim]disabled[/]")

    if mode == "advanced":
        table.add_row("Quality gate", ctx["quality_gate"] if ctx["quality_gate"] != "none" else "[dim]none[/]")

    docker_val = ctx["docker"]
    if docker_val == "yes":
        debug_tag = " [dim]+debug[/]" if ctx["docker_debug"] == "yes" else ""
        table.add_row("Docker", f"yes{debug_tag}")
    else:
        table.add_row("Docker", "[dim]no[/]")

    table.add_row("Pre-commit", ctx["precommit"])

    console.print()
    console.print(table)


def _basic_defaults() -> dict:
    """Defaults applied in basic mode — no DB, no cache, no streaming, no secrets."""
    return {
        "database": "none",
        "cache": "none",
        "streaming": "none",
        "secrets": "none",
        "quality_gate": "none",
        "precommit": "yes",
    }


def generate(ctx: dict) -> None:
    """Call cookiecutter with collected context."""
    ctx["project_slug"] = ctx["project_name"].lower().replace(" ", "-").replace("_", "-")
    ctx["package_name"] = ctx["project_slug"].replace("-", "_")

    output_dir = os.getcwd()
    project_dir = os.path.join(output_dir, ctx["project_slug"])

    if os.path.exists(project_dir):
        action = questionary.select(
            f'"{ctx["project_slug"]}" already exists. What do you want to do?',
            choices=[
                questionary.Choice("Update selectively (choose what to overwrite)", value="selective"),
                questionary.Choice("Delete and regenerate (removes all files)", value="delete"),
                questionary.Choice("Abort", value="abort"),
            ],
            default="selective",
        ).ask()
        if action == "abort" or action is None:
            console.print("[yellow]Aborted.[/]")
            return

        if action == "delete":
            confirm = questionary.confirm(
                "This will permanently delete all files including your code. Continue?",
                default=False,
            ).ask()
            if not confirm:
                console.print("[yellow]Aborted.[/]")
                return
            shutil.rmtree(project_dir)
            console.print(f"[dim]Removed {ctx['project_slug']}/[/]")

        elif action == "selective":
            # Generate to temp dir, compare, let user pick categories
            with tempfile.TemporaryDirectory() as tmp_dir:
                with console.status("[bold cyan]Generating to compare...[/]", spinner="dots"):
                    cookiecutter(
                        TEMPLATE_DIR,
                        no_input=True,
                        extra_context=ctx,
                        output_dir=tmp_dir,
                    )
                generated_dir = os.path.join(tmp_dir, ctx["project_slug"])
                changes = _collect_changes(project_dir, generated_dir)

                if not changes:
                    console.print("[green]No changes detected — project is up to date.[/]")
                    return

                # Build choices with file counts
                choices = []
                for category, file_list in changes.items():
                    new_count = sum(1 for _, s in file_list if s == "new")
                    mod_count = sum(1 for _, s in file_list if s == "modified")
                    parts = []
                    if new_count:
                        parts.append(f"{new_count} new")
                    if mod_count:
                        parts.append(f"{mod_count} changed")
                    desc = FILE_CATEGORIES.get(category, {}).get("description", "")
                    label = f"{category} ({', '.join(parts)}) — {desc}" if desc else f"{category} ({', '.join(parts)})"
                    choices.append(questionary.Choice(label, value=category))

                console.print()
                selected = questionary.checkbox(
                    "Select categories to update (space to toggle, enter to confirm):",
                    choices=choices,
                ).ask()

                if not selected:
                    console.print("[yellow]Nothing selected — no changes made.[/]")
                    return

                # Show what will be changed
                console.print()
                for cat in selected:
                    console.print(f"[bold cyan]{cat}:[/]")
                    for rel_path, status in changes[cat]:
                        icon = "[green]+[/]" if status == "new" else "[yellow]~[/]"
                        console.print(f"  {icon} {rel_path}")

                confirm = questionary.confirm("Apply these changes?", default=True).ask()
                if not confirm:
                    console.print("[yellow]Aborted.[/]")
                    return

                update_log = _apply_selective_overwrite(project_dir, generated_dir, selected, changes)

            console.print()
            console.print(
                Panel(
                    f"[bold green]✔ Updated:[/] [bold]{project_dir}[/]\n\n"
                    + "\n".join(update_log)
                    + "\n\n  [dim]+ = new file, ~ = updated file[/]",
                    title="[bold bright_cyan]📋 Changes Applied[/]",
                    border_style="green",
                    padding=(1, 2),
                )
            )
            return

    with console.status("[bold cyan]Generating project...[/]", spinner="dots"):
        cookiecutter(
            TEMPLATE_DIR,
            no_input=True,
            extra_context=ctx,
            output_dir=output_dir,
        )

    # Build next-steps
    steps = [f"  [bold]cd {ctx['project_slug']}[/]"]
    if ctx["docker"] == "yes":
        if ctx.get("docker_debug") == "yes":
            steps.append("  [green]docker compose -f docker-compose.debug.yml up --build[/]  [dim]# debug + auto-reload[/]")
        steps.append("  [green]docker compose -f infra/docker-compose.yml up --build[/]  [dim]# local infrastructure[/]")
    else:
        steps.append('  [green]pip install -e ".[dev]"[/]')
        steps.append("  [green]uvicorn app.main:app --reload[/]")
    steps.append("  [green]pytest[/]")
    steps.append("")
    steps.append(f"  [dim]API docs →  http://localhost:{ctx['port']}/docs[/]")
    steps.append("")
    steps.append("[bold bright_cyan]Evolve your project:[/]")
    steps.append("  [cyan]fastforge add model <name>[/]   → Add a new domain model")
    steps.append("  [cyan]fastforge add postgres[/]       → Add PostgreSQL database")
    steps.append("  [cyan]fastforge add kafka[/]          → Add Kafka streaming")
    steps.append("  [cyan]fastforge doctor[/]             → Check project health")
    steps.append("  [cyan]fastforge deploy local[/]       → Deploy locally with Docker")

    console.print()
    console.print(
        Panel(
            f"[{STYLE_SUCCESS}]✔ Project created:[/] [bold]{project_dir}[/]\n\n"
            + "\n".join(steps),
            title="[bold bright_cyan]🚀 Next Steps[/]",
            border_style="green",
            padding=(1, 2),
        )
    )


def _cmd_new():
    """Create a new FastAPI service (interactive)."""
    console.print(BANNER)

    console.print(
        Panel(
            "[bold white]Basic mode[/]  → SOLID app, JSON logging, Docker, async CRUD — [bold green]ready to run[/]\n"
            "[bold white]Advanced[/]    → + Database, Cache, Streaming, Secrets, Quality Gate",
            title="[bold bright_cyan]Choose your path[/]",
            border_style="bright_cyan",
            padding=(0, 2),
        )
    )

    try:
        ctx = {}

        # ── Always asked ─────────────────────────────────────────────────
        ctx.update(ask_basics())
        ctx.update(ask_model())

        # ── Basic vs Advanced ────────────────────────────────────────────
        console.print()
        advanced = questionary.confirm(
            "Enable advanced configuration? (database, cache, streaming, secrets, quality gate)",
            default=False,
            style=CUSTOM_STYLE,
        ).ask()

        if advanced:
            mode = "advanced"
            ctx.update(ask_database())
            ctx.update(ask_cache())
            ctx.update(ask_streaming())
            ctx.update(ask_secrets())
            ctx.update(ask_logging_advanced())
            ctx.update(ask_quality_gate())
            ctx.update(ask_containerization())
            ctx.update(ask_precommit())
        else:
            mode = "basic"
            ctx.update(_basic_defaults())
            ctx.update(ask_logging_basic())
            ctx.update(ask_docker_basic())

        show_summary(ctx, mode)

        console.print()
        proceed = questionary.confirm("Generate project?", default=True, style=CUSTOM_STYLE).ask()
        if not proceed:
            console.print(f"[{STYLE_WARN}]Aborted.[/]")
            sys.exit(0)

        generate(ctx)

    except KeyboardInterrupt:
        console.print(f"\n[{STYLE_WARN}]Aborted.[/]")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# fastforge infra  (infrastructure stack)
# ═══════════════════════════════════════════════════════════════════════════════

INFRA_BANNER = f"""
[bold bright_blue]  ╔═╗╔═╗╔═╗╔╦╗  ╔═╗╔═╗╦═╗╔═╗╔═╗[/]
[bold bright_cyan]  ╠╣ ╠═╣╚═╗ ║   ╠╣ ║ ║╠╦╝║ ╦║╣ [/]
[bold cyan]  ╚  ╩ ╩╚═╝ ╩   ╚  ╚═╝╩╚═╚═╝╚═╝[/]
[bold white]  Infrastructure Stack Generator[/]  [dim italic]v{__version__}[/]
"""


def ask_infra_basics() -> dict:
    """Infrastructure basics."""
    _section("📦  Infrastructure Basics")
    return {
        "project_slug": questionary.text(
            "Target project slug (used for container naming):",
            default="my-fastapi-service",
            validate=lambda x: bool(x.strip()) or "Required",
            style=CUSTOM_STYLE,
        ).ask(),
    }


def ask_infra_log_pipeline() -> dict:
    """Log pipeline configuration for infrastructure."""
    _section("📋  Log Pipeline")
    enabled = questionary.confirm(
        "Set up a log collection pipeline (agent → Kafka → aggregator → Elasticsearch)?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    if not enabled:
        return {"log_agent": "none", "log_aggregator": "none"}

    agent = questionary.select(
        "Log collection agent:",
        choices=[
            questionary.Choice("Vector (Rust, lightweight)", value="vector"),
            questionary.Choice("Fluent Bit (C, CNCF)", value="fluentbit"),
        ],
        default="vector",
        style=CUSTOM_STYLE,
    ).ask()

    aggregator = questionary.select(
        "Log aggregator / pipeline:",
        choices=[
            questionary.Choice("Vector aggregator", value="vector"),
            questionary.Choice("Logstash", value="logstash"),
        ],
        default="vector",
        style=CUSTOM_STYLE,
    ).ask()

    return {"log_agent": agent, "log_aggregator": aggregator}


def ask_infra_services() -> dict:
    """Supporting services."""
    _section("🔧  Services")
    result = {"streaming": "none", "database": "none", "secrets": "none"}

    if questionary.confirm("Include Kafka (message broker)?", default=False, style=CUSTOM_STYLE).ask():
        result["streaming"] = "enabled"

    db = questionary.select(
        "Database:",
        choices=[
            questionary.Choice("None", value="none"),
            questionary.Choice("PostgreSQL", value="postgres"),
            questionary.Choice("MongoDB", value="mongodb"),
        ],
        default="none",
        style=CUSTOM_STYLE,
    ).ask()
    result["database"] = db

    if questionary.confirm("Include HashiCorp Vault?", default=False, style=CUSTOM_STYLE).ask():
        result["secrets"] = "vault"

    return result


def show_infra_summary(ctx: dict) -> None:
    """Display infrastructure summary."""
    table = Table(
        title="[bold]Infrastructure Configuration[/]",
        show_header=True,
        header_style="bold bright_white",
        border_style="bright_cyan",
    )
    table.add_column("Component", style="cyan", min_width=16)
    table.add_column("Value", style="bright_green")

    table.add_row("Project", ctx["project_slug"])

    if ctx["log_agent"] != "none":
        table.add_row("Log agent", ctx["log_agent"])
        table.add_row("Log aggregator", ctx["log_aggregator"])
        table.add_row("Elasticsearch", "yes")
        table.add_row("Kafka", "yes (log transport)")
    elif ctx["streaming"] != "none":
        table.add_row("Kafka", "yes (streaming)")
    else:
        table.add_row("Kafka", "no")

    table.add_row("Database", ctx["database"] if ctx["database"] != "none" else "none")
    table.add_row("Vault", "yes" if ctx["secrets"] == "vault" else "no")

    console.print()
    console.print(table)


def generate_infra(ctx: dict) -> None:
    """Generate infrastructure stack."""
    output_dir = os.getcwd()

    with console.status("[bold cyan]Generating infrastructure...[/]", spinner="dots"):
        cookiecutter(
            INFRA_TEMPLATE_DIR,
            no_input=True,
            extra_context=ctx,
            output_dir=output_dir,
        )

    infra_dir = os.path.join(output_dir, f"{ctx['project_slug']}-infrastructure")

    console.print()
    console.print(
        Panel(
            f"[{STYLE_SUCCESS}]✔ Infrastructure created:[/] [bold]{infra_dir}[/]\n\n"
            f"  [bold]cd {ctx['project_slug']}-infrastructure[/]\n"
            f"  [green]docker compose up -d[/]",
            title="[bold bright_cyan]🚀 Next Steps[/]",
            border_style="green",
            padding=(1, 2),
        )
    )


def _cmd_infra():
    """Generate standalone infrastructure stack (interactive)."""
    console.print(INFRA_BANNER)
    console.print(f"  [{STYLE_HINT}]Generate Docker Compose infrastructure stack for your project.[/]\n")

    try:
        ctx = {}
        ctx.update(ask_infra_basics())
        ctx.update(ask_infra_log_pipeline())
        ctx.update(ask_infra_services())

        show_infra_summary(ctx)

        proceed = questionary.confirm("\nGenerate infrastructure stack?", default=True, style=CUSTOM_STYLE).ask()
        if not proceed:
            console.print(f"[{STYLE_WARN}]Aborted.[/]")
            sys.exit(0)

        generate_infra(ctx)

    except KeyboardInterrupt:
        console.print(f"\n[{STYLE_WARN}]Aborted.[/]")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# Subcommand stubs  (placeholder entry points)
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# fastforge add model
# ═══════════════════════════════════════════════════════════════════════════════


def _cmd_add_model(name: str | None = None):
    """Add a new CRUD model to the project."""
    console.print(BANNER)

    from fastforge.project_config import find_project_root, load_config

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    config = load_config(project_dir)
    console.print(f"[dim]Project: {config.get('project_slug', 'unknown')} (database: {config.get('database', 'none')})[/]\n")

    if not name:
        name = questionary.text(
            "Model name (singular, snake_case):",
            validate=lambda x: len(x.strip()) > 0 or "Model name is required",
        ).ask()
        if not name:
            return

    name = name.strip().lower().replace("-", "_").replace(" ", "_")

    from fastforge.generators.model import pluralize, to_class_name

    default_plural = pluralize(name)
    names = questionary.text("Plural name:", default=default_plural).ask()
    if not names:
        return

    Name = to_class_name(name)

    # Preview
    console.print()
    console.print(Panel(
        f"[bold]Model:[/]  {name} → {Name}\n"
        f"[bold]Plural:[/] {names}\n"
        f"[bold]Route:[/]  /api/v1/{names}\n\n"
        f"[bold green]New files:[/]\n"
        f"  + app/api/models/{name}.py\n"
        f"  + app/api/routes/{names}.py\n"
        f"  + app/services/{name}_service.py\n"
        f"  + app/repositories/{name}_repository.py\n"
        f"  + tests/test_{names}_api.py\n\n"
        f"[bold yellow]Modified files:[/]\n"
        f"  ~ app/main.py\n"
        f"  ~ app/dependencies.py\n"
        f"  ~ .fastforge.json",
        title="[bold bright_cyan]📋 Model Preview[/]",
        border_style="cyan",
        padding=(1, 2),
    ))

    confirm = questionary.confirm("Generate model?", default=True).ask()
    if not confirm:
        console.print("[yellow]Aborted.[/]")
        return

    try:
        from fastforge.generators.model import add_model

        result = add_model(name, names, project_dir)
    except (FileExistsError, ValueError) as e:
        console.print(f"[red]✘ {e}[/]")
        sys.exit(1)

    # Run tests
    console.print("\n[dim]Running tests...[/]")
    test_result = subprocess.run(
        ["pytest", "tests/", "-x", "-q", "--tb=short", "--no-header"],
        cwd=project_dir, capture_output=True, text=True,
    )

    # Show result
    lines = []
    for f in result["created"]:
        lines.append(f"  [green]+[/] {f}")
    for f in result["modified"]:
        lines.append(f"  [yellow]~[/] {f}")

    if test_result.returncode == 0:
        test_summary = "\n[bold green]✔ Tests passed[/]"
    else:
        output = test_result.stdout[-500:] if test_result.stdout else test_result.stderr[-500:]
        test_summary = f"\n[bold red]✘ Tests failed[/]\n[dim]{output}[/]"

    console.print()
    console.print(Panel(
        f"[bold green]✔ Model '{Name}' added[/]\n\n"
        + "\n".join(lines)
        + "\n\n  [dim]+ = new, ~ = modified[/]"
        + test_summary
        + f"\n\n  [dim]API: http://localhost:{config.get('port', 8000)}/api/v1/{names}[/]",
        title="[bold bright_cyan]🚀 Done[/]",
        border_style="green",
        padding=(1, 2),
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# fastforge add postgres
# ═══════════════════════════════════════════════════════════════════════════════


def _cmd_add_postgres():
    """Add PostgreSQL database support to the project."""
    console.print(BANNER)

    from fastforge.generators.postgres import add_postgres
    from fastforge.project_config import find_project_root, load_config

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    config = load_config(project_dir)

    # Idempotency check
    if config.get("database") == "postgres":
        console.print("[green]✔ PostgreSQL is already configured in this project.[/]")
        return

    if config.get("database") not in ("none", None):
        console.print(f"[yellow]⚠ Project already has database: {config['database']}. Cannot switch to postgres.[/]")
        return

    console.print(f"[dim]Project: {config.get('project_slug', 'unknown')}[/]\n")

    console.print(Panel(
        "[bold]This will:[/]\n"
        "  + Add SQLAlchemy + asyncpg to dependencies\n"
        "  + Create app/db/ with async database session\n"
        "  + Add DATABASE_URL to config and .env.staging\n"
        "  + Add postgres service to infra/docker-compose.yml\n"
        "  + Update .fastforge.json",
        title="[bold bright_cyan]📋 Add PostgreSQL[/]",
        border_style="cyan",
        padding=(1, 2),
    ))

    confirm = questionary.confirm("Proceed?", default=True).ask()
    if not confirm:
        console.print("[yellow]Aborted.[/]")
        return

    try:
        result = add_postgres(project_dir)
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]✘ {e}[/]")
        sys.exit(1)

    lines = []
    for f in result.get("created", []):
        lines.append(f"  [green]+[/] {f}")
    for f in result.get("modified", []):
        lines.append(f"  [yellow]~[/] {f}")

    console.print()
    console.print(Panel(
        "[bold green]✔ PostgreSQL added[/]\n\n"
        + "\n".join(lines)
        + "\n\n[bold]Next steps:[/]\n"
        + "  1. [green]pip install -e '.[dev]'[/]  [dim]# install new dependencies[/]\n"
        + "  2. [green]fastforge deploy local[/]   [dim]# start postgres container[/]\n"
        + "  3. Update your repositories to use SQLAlchemy",
        title="[bold bright_cyan]🚀 Done[/]",
        border_style="green",
        padding=(1, 2),
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# fastforge add <stub>
# ═══════════════════════════════════════════════════════════════════════════════


def _cmd_add_stub(feature: str, description: str):
    """Placeholder for not-yet-implemented add features."""
    console.print(BANNER)
    console.print(
        Panel(
            f"[bold yellow]fastforge add {feature}[/] — {description}\n\n"
            "This feature is not yet implemented. Coming soon!\n\n"
            "[dim]Track progress: https://github.com/VibhuviOiO/fastforge-cli[/]",
            title=f"[bold bright_cyan]fastforge add {feature}[/]",
            border_style="yellow",
            padding=(1, 2),
        )
    )


# ═══════════════════════════════════════════════════════════════════════════════
# fastforge doctor
# ═══════════════════════════════════════════════════════════════════════════════


def _cmd_doctor():
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
        checks.append(("FastForge project", False, "No .fastforge.json found"))
        _print_doctor_table(checks)
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
    checks.append(("Docker", docker_result.returncode == 0, "running" if docker_result.returncode == 0 else "not available"))

    # 4. Infra compose exists
    compose_path = os.path.join(project_dir, "infra", "docker-compose.yml")
    checks.append(("Infrastructure", os.path.isfile(compose_path), "infra/docker-compose.yml" if os.path.isfile(compose_path) else "missing"))

    # 5. Health endpoint
    port = config.get("port", 8000)
    try:
        import urllib.request
        response = urllib.request.urlopen(f"http://localhost:{port}/health", timeout=3)
        checks.append(("Health endpoint", response.status == 200, f"http://localhost:{port}/health"))
    except Exception:
        checks.append(("Health endpoint", False, f"not responding on port {port}"))

    # 6. Tests
    test_result = subprocess.run(
        ["pytest", "tests/", "-x", "-q", "--tb=no", "--no-header"],
        cwd=project_dir, capture_output=True, text=True,
    )
    if test_result.returncode == 0:
        last_line = test_result.stdout.strip().split("\n")[-1] if test_result.stdout.strip() else "passed"
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


# ═══════════════════════════════════════════════════════════════════════════════
# fastforge deploy
# ═══════════════════════════════════════════════════════════════════════════════


def _cmd_deploy(target: str):
    """Deploy the service."""
    if target == "local":
        _cmd_deploy_local()


def _cmd_deploy_local():
    """Deploy locally using Docker Compose."""
    console.print(BANNER)

    from fastforge.project_config import find_project_root

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    compose_file = os.path.join(project_dir, "infra", "docker-compose.yml")
    if not os.path.isfile(compose_file):
        console.print("[red]✘ No infra/docker-compose.yml found.[/]")
        sys.exit(1)

    console.print("[bold cyan]Starting local infrastructure...[/]\n")
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "--build"],
        cwd=project_dir,
    )
    sys.exit(result.returncode)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI entry point (argparse dispatcher)
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    """CLI entry point for `fastforge`."""
    parser = argparse.ArgumentParser(
        prog="fastforge",
        description="Production-grade FastAPI project generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'fastforge <command> --help' for more information on a command.",
    )
    subparsers = parser.add_subparsers(dest="command", title="commands")

    # fastforge new
    subparsers.add_parser("new", help="Create a new FastAPI service")

    # fastforge add
    add_parser = subparsers.add_parser("add", help="Add a feature to an existing project")
    add_sub = add_parser.add_subparsers(dest="feature", title="features")
    model_p = add_sub.add_parser("model", help="Add a new CRUD model")
    model_p.add_argument("name", nargs="?", help="Model name (singular, snake_case)")
    add_sub.add_parser("postgres", help="Add PostgreSQL database")
    add_sub.add_parser("kafka", help="Add Kafka streaming")
    add_sub.add_parser("redis", help="Add Redis cache")
    add_sub.add_parser("observability", help="Add observability stack")
    add_sub.add_parser("auth", help="Add authentication")

    # fastforge deploy
    deploy_p = subparsers.add_parser("deploy", help="Deploy the service")
    deploy_p.add_argument("target", nargs="?", default="local", choices=["local"], help="Deployment target (default: local)")

    # fastforge doctor
    subparsers.add_parser("doctor", help="Check project health")

    # fastforge infra (standalone infrastructure)
    subparsers.add_parser("infra", help="Generate standalone infrastructure stack")

    args = parser.parse_args()

    if args.command is None:
        console.print(BANNER)
        parser.print_help()
        return

    try:
        if args.command == "new":
            _cmd_new()
        elif args.command == "add":
            if not hasattr(args, "feature") or args.feature is None:
                console.print(BANNER)
                add_parser.print_help()
                return
            if args.feature == "model":
                _cmd_add_model(getattr(args, "name", None))
            elif args.feature == "postgres":
                _cmd_add_postgres()
            elif args.feature == "kafka":
                _cmd_add_stub("kafka", "Kafka streaming")
            elif args.feature == "redis":
                _cmd_add_stub("redis", "Redis cache")
            elif args.feature == "observability":
                _cmd_add_stub("observability", "Observability stack")
            elif args.feature == "auth":
                _cmd_add_stub("auth", "Authentication")
        elif args.command == "deploy":
            _cmd_deploy(args.target)
        elif args.command == "doctor":
            _cmd_doctor()
        elif args.command == "infra":
            _cmd_infra()
    except KeyboardInterrupt:
        console.print(f"\n[{STYLE_WARN}]Aborted.[/]")
        sys.exit(1)


if __name__ == "__main__":
    main()
