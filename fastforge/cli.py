"""FastForge CLI — Interactive project generator for production-grade FastAPI applications."""

import os
import sys
from pathlib import Path

import questionary
from cookiecutter.main import cookiecutter
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

TEMPLATE_DIR = str(Path(__file__).parent / "template")
INFRA_TEMPLATE_DIR = str(Path(__file__).parent / "infra_template")

BANNER = """
[bold blue]  ___         _   ___[/]
[bold blue] | __| _ _ __| |_| __|__ _ _ __ _ ___[/]
[bold cyan] | _/ _` (_-<  _| _/ _ \\ '_/ _` / -_)[/]
[bold cyan] |_|\\__,_/__/\\__|_|\\___/_| \\__, \\___|[/]
[bold cyan]                            |___/[/]
[bold white] Production-grade FastAPI Generator[/]  [dim]v1.0.0[/]
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
        ("answer", "fg:bright_green bold"),
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
    log_output = questionary.select(
        "Log output:",
        choices=[
            questionary.Choice("Stdout (containers / cloud-native)", value="stdout"),
            questionary.Choice("Stdout + File (for log agent collection)", value="file"),
        ],
        default="stdout",
        style=CUSTOM_STYLE,
    ).ask()

    return {
        "logging": "structlog",
        "log_format": "json",
        "log_connector": log_output,
    }


def ask_docker_basic() -> dict:
    """Docker — basic mode (always yes, just ask about debug)."""
    _section("🐳  Docker")
    debug = questionary.confirm(
        "Include debug compose (debugpy on port 5678)?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    return {"docker": "yes", "docker_debug": "yes" if debug else "no"}


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
        return {"logging": "none", "log_format": "console", "log_connector": "stdout"}

    log_format = questionary.select(
        "Log format:",
        choices=["json", "console"],
        default="json",
        style=CUSTOM_STYLE,
    ).ask()

    log_connector = questionary.select(
        "Log output:",
        choices=[
            questionary.Choice("Stdout (containers)", value="stdout"),
            questionary.Choice("Stdout + File (for log agent collection)", value="file"),
        ],
        default="stdout",
        style=CUSTOM_STYLE,
    ).ask()

    return {"logging": "structlog", "log_format": log_format, "log_connector": log_connector}


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
        table.add_row("Logging", f"structlog [dim]({ctx['log_format']} → {ctx['log_connector']})[/]")
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

    with console.status("[bold cyan]Generating project...[/]", spinner="dots"):
        cookiecutter(
            TEMPLATE_DIR,
            no_input=True,
            extra_context=ctx,
            output_dir=output_dir,
        )

    project_dir = os.path.join(output_dir, ctx["project_slug"])

    # Build next-steps
    steps = [f"  [bold]cd {ctx['project_slug']}[/]"]
    if ctx["docker"] == "yes":
        steps.append("  [green]docker compose up --build[/]")
    else:
        steps.append('  [green]pip install -e ".[dev]"[/]')
        steps.append("  [green]uvicorn app.main:app --reload[/]")
    steps.append("  [green]pytest[/]")
    steps.append("")
    steps.append(f"  [dim]API docs →  http://localhost:{ctx['port']}/docs[/]")
    steps.append("")
    steps.append("[bold bright_cyan]Extend your project:[/]")
    steps.append("  [cyan]fastforge-infra[/]          → Infrastructure stack")
    steps.append("  [cyan]fastforge-cicd[/]           → CI/CD pipeline")
    steps.append("  [cyan]fastforge-secops[/]         → Security tools")
    steps.append("  [cyan]fastforge-helm[/]           → Helm chart")
    steps.append("  [cyan]fastforge-k8s[/]            → Kubernetes manifests")
    steps.append("  [cyan]fastforge-observability[/]  → Tracing + Metrics")

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


def main():
    """Entry point for `fastforge`."""
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

INFRA_BANNER = """
[bold blue]  ___         _   ___[/]
[bold blue] | __| _ _ __| |_| __|__ _ _ __ _ ___[/]
[bold cyan] | _/ _` (_-<  _| _/ _ \\ '_/ _` / -_)[/]
[bold cyan] |_|\\__,_/__/\\__|_|\\___/_| \\__, \\___|[/]
[bold cyan]                            |___/[/]
[bold white] Infrastructure Stack Generator[/]
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


def infra_main():
    """Entry point for `fastforge-infra`."""
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

def _stub_command(name: str, description: str) -> None:
    """Generic stub for not-yet-implemented subcommands."""
    console.print(BANNER)
    console.print(f"  [{STYLE_WARN}]fastforge {name}[/] — {description}\n")
    console.print(f"  [{STYLE_HINT}]This command is not yet implemented. Coming soon![/]\n")
    console.print(
        Panel(
            f"This will interactively generate {description.lower()} for your project.\n\n"
            "[dim]Track progress: https://github.com/VibhuviOiO/fastforge[/]",
            title=f"[bold bright_cyan]fastforge {name}[/]",
            border_style="yellow",
            padding=(1, 2),
        )
    )


def cicd_main():
    """Entry point for `fastforge-cicd`."""
    _stub_command("cicd", "CI/CD pipeline (GitHub Actions, GitLab CI, Bitbucket Pipelines)")


def secops_main():
    """Entry point for `fastforge-secops`."""
    _stub_command("secops", "Security tools (Bandit, Gitleaks, Trivy, OWASP ZAP, pip-audit, detect-secrets)")


def helm_main():
    """Entry point for `fastforge-helm`."""
    _stub_command("helm", "Helm chart for Kubernetes deployment")


def k8s_main():
    """Entry point for `fastforge-k8s`."""
    _stub_command("k8s", "Kubernetes manifests (Deployment, Service, Ingress, HPA)")


def swarm_main():
    """Entry point for `fastforge-swarm`."""
    _stub_command("swarm", "Docker Swarm stack definition")


def marathon_main():
    """Entry point for `fastforge-marathon`."""
    _stub_command("marathon", "Marathon (Mesos) application definition")


def observability_main():
    """Entry point for `fastforge-observability`."""
    _stub_command("observability", "Observability stack (Tracing + Metrics — ELK APM, Jaeger, Prometheus)")


def docs_main():
    """Entry point for `fastforge-docs`."""
    _stub_command("docs", "API documentation setup")


def model_main():
    """Entry point for `fastforge-model`."""
    _stub_command("model", "Add a new domain model (CRUD route + service + repository + DB model)")


if __name__ == "__main__":
    main()
