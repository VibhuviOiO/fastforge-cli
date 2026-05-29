"""``fastforge add`` — Add features to an existing project."""

from __future__ import annotations

import subprocess
import sys

import questionary
from rich.panel import Panel

from fastforge.commands._shared import (
    BANNER,
    STYLE_WARN,
    console,
    text_prompt,
)


def cmd_add_model(name: str | None = None):
    """Add a new CRUD model to the project."""
    console.print(BANNER)

    from fastforge.project_config import find_project_root, load_config

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    config = load_config(project_dir)
    console.print(
        f"[dim]Project: {config.get('project_slug', 'unknown')} (database: {config.get('database', 'none')})[/]\n"
    )

    if not name:
        name = text_prompt(
            "Model name (singular, snake_case):",
            default="item",
            validate=lambda x: len(x.strip()) > 0 or "Model name is required",
        )
        if not name:
            return

    name = name.strip().lower().replace("-", "_").replace(" ", "_")

    from fastforge.generators.model import pluralize, to_class_name

    default_plural = pluralize(name)
    names = text_prompt("Plural name:", default=default_plural)
    if not names:
        return

    Name = to_class_name(name)

    console.print()
    console.print(
        Panel(
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
        )
    )

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

    console.print("\n[dim]Running tests...[/]")
    try:
        test_result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-x", "-q", "--tb=short", "--no-header"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        test_result = None

    lines = []
    for f in result["created"]:
        lines.append(f"  [green]+[/] {f}")
    for f in result["modified"]:
        lines.append(f"  [yellow]~[/] {f}")

    if test_result is None:
        test_summary = "\n[dim]⚠ pytest not available — skipped test run[/]"
    elif test_result.returncode == 0:
        test_summary = "\n[bold green]✔ Tests passed[/]"
    else:
        output = test_result.stdout[-500:] if test_result.stdout else test_result.stderr[-500:]
        test_summary = f"\n[bold red]✘ Tests failed[/]\n[dim]{output}[/]"

    console.print()
    console.print(
        Panel(
            f"[bold green]✔ Model '{Name}' added[/]\n\n"
            + "\n".join(lines)
            + "\n\n  [dim]+ = new, ~ = modified[/]"
            + test_summary
            + f"\n\n  [dim]API: http://localhost:{config.get('port', 8000)}/api/v1/{names}[/]",
            title="[bold bright_cyan]🚀 Done[/]",
            border_style="green",
            padding=(1, 2),
        )
    )


def cmd_add_postgres():
    """Add PostgreSQL database support."""
    console.print(BANNER)

    from fastforge.generators.postgres import add_postgres
    from fastforge.project_config import find_project_root, load_config

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    config = load_config(project_dir)

    if config.get("database") == "postgres":
        console.print("[green]✔ PostgreSQL is already configured in this project.[/]")
        return
    if config.get("database") not in ("none", None):
        console.print(
            f"[yellow]⚠ Project already has database: {config['database']}. Cannot switch to postgres.[/]"
        )
        return

    console.print(f"[dim]Project: {config.get('project_slug', 'unknown')}[/]\n")
    console.print(
        Panel(
            "[bold]This will:[/]\n"
            "  + Add SQLAlchemy + asyncpg to dependencies\n"
            "  + Create app/db/ with async database session\n"
            "  + Add DATABASE_URL to config and .env.staging\n"
            "  + Add postgres service to infra/docker-compose.yml\n"
            "  + Update .fastforge.json",
            title="[bold bright_cyan]📋 Add PostgreSQL[/]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not questionary.confirm("Proceed?", default=True).ask():
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
    console.print(
        Panel(
            "[bold green]✔ PostgreSQL added[/]\n\n"
            + "\n".join(lines)
            + "\n\n[bold]Next steps:[/]\n"
            + "  1. [green]pip install -e '.[dev]'[/]  [dim]# install new dependencies[/]\n"
            + "  2. [green]fastforge deploy local[/]   [dim]# start postgres container[/]\n"
            + "  3. Update your repositories to use SQLAlchemy",
            title="[bold bright_cyan]🚀 Done[/]",
            border_style="green",
            padding=(1, 2),
        )
    )


def cmd_add_kafka():
    """Add Kafka streaming."""
    console.print(BANNER)

    from fastforge.generators.kafka import add_kafka
    from fastforge.project_config import find_project_root, load_config

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    config = load_config(project_dir)

    if config.get("streaming") == "kafka":
        console.print("[green]✔ Kafka streaming is already configured in this project.[/]")
        return

    console.print(f"[dim]Project: {config.get('project_slug', 'unknown')}[/]\n")
    console.print(
        Panel(
            "[bold]This will:[/]\n"
            "  + Create app/streaming/ with producer.py, consumer.py, handler.py\n"
            "  + Add aiokafka dependency\n"
            "  + Add Kafka settings to config.py and .env.staging\n"
            "  + Add consumer lifespan hooks to main.py\n"
            "  + Generate infra/docker-compose.kafka.yml\n"
            "  + Update .fastforge.json",
            title="[bold bright_cyan]📋 Add Kafka Streaming[/]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not questionary.confirm("Proceed?", default=True).ask():
        console.print("[yellow]Aborted.[/]")
        return

    try:
        result = add_kafka(project_dir)
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
            "[bold green]✔ Kafka streaming added[/]\n\n"
            + "\n".join(lines)
            + "\n\n[bold]Next steps:[/]\n"
            + "  1. [green]pip install -e '.[dev]'[/]  [dim]# install aiokafka[/]\n"
            + "  2. [green]docker compose -f infra/docker-compose.kafka.yml up -d[/]\n"
            + "  3. Edit [cyan]app/streaming/handler.py[/] with your business logic",
            title="[bold bright_cyan]🚀 Done[/]",
            border_style="green",
            padding=(1, 2),
        )
    )


def cmd_add_observability():
    """Add OpenTelemetry tracing + Prometheus metrics."""
    console.print(BANNER)

    from fastforge.generators.observability import add_observability
    from fastforge.project_config import find_project_root, load_config

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    config = load_config(project_dir)

    if config.get("observability") == "enabled":
        console.print("[green]✔ Observability is already configured in this project.[/]")
        return

    console.print(f"[dim]Project: {config.get('project_slug', 'unknown')}[/]\n")

    stack = questionary.select(
        "Which observability stack?",
        choices=[
            questionary.Choice("Jaeger — distributed tracing (lightweight)", value="jaeger"),
            questionary.Choice(
                "ELK — Elasticsearch + Kibana + APM (logs + traces + APM)", value="elk"
            ),
            questionary.Choice(
                "Grafana — Prometheus + Loki + Tempo + Grafana (full metrics + logs + traces)",
                value="grafana",
            ),
        ],
        default="jaeger",
    ).ask()
    if not stack:
        console.print("[yellow]Aborted.[/]")
        return

    stack_desc = {
        "jaeger": "Jaeger all-in-one (UI:16686, OTLP:4317)",
        "elk": "Elasticsearch + Kibana + APM Server",
        "grafana": "Prometheus + Loki + Tempo + Grafana",
    }

    console.print(
        Panel(
            "[bold]This will:[/]\n"
            "  + Create app/telemetry/ with tracing.py and metrics.py\n"
            "  + Add OpenTelemetry + Prometheus dependencies\n"
            "  + Add /metrics endpoint and tracing setup to main.py\n"
            "  + Add OTEL_* config to config.py and .env.staging\n"
            f"  + Generate infra/docker-compose.{stack}.yml ({stack_desc[stack]})\n"
            "  + Update .fastforge.json",
            title="[bold bright_cyan]📋 Add Observability[/]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not questionary.confirm("Proceed?", default=True).ask():
        console.print("[yellow]Aborted.[/]")
        return

    try:
        result = add_observability(project_dir, stack=stack)
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
            "[bold green]✔ Observability added[/]\n\n"
            + "\n".join(lines)
            + "\n\n[bold]Next steps:[/]\n"
            + "  1. [green]pip install -e '.[dev]'[/]  [dim]# install OTel + Prometheus deps[/]\n"
            + f"  2. [green]docker compose -f infra/docker-compose.{stack}.yml up -d[/]\n"
            + "  3. Set [cyan]OTEL_ENABLED=true[/] in .env.staging\n"
            + "  4. Access metrics at [cyan]/metrics[/]",
            title="[bold bright_cyan]🚀 Done[/]",
            border_style="green",
            padding=(1, 2),
        )
    )


def cmd_add_ai_telemetry():
    """Add OTel spans + token/cost attribution around AI calls."""
    console.print(BANNER)

    from fastforge.generators.ai_telemetry import AITelemetryGenerator
    from fastforge.project_config import find_project_root

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    try:
        result = AITelemetryGenerator().emit_inline(project_dir, {})
    except FileNotFoundError as e:
        console.print(f"[red]✘ {e}[/]")
        sys.exit(1)

    if result["status"] == "already_configured":
        console.print("[green]✔ ai-telemetry is already configured in this project.[/]")
        return

    lines: list[str] = []
    for f in result.get("created", []):
        lines.append(f"  [green]+[/] {f}")
    for f in result.get("modified", []):
        lines.append(f"  [yellow]~[/] {f}")

    console.print()
    console.print(
        Panel(
            "[bold green]✔ AI telemetry added[/]\n\n"
            + "\n".join(lines)
            + "\n\n[bold]Next steps:[/]\n"
            + "  1. [green]pip install -e '.[dev]'[/]  [dim]# install OTel deps[/]\n"
            + "  2. [green]docker compose -f infra/docker-compose.yml -f infra/docker-compose.otel.yml up -d[/]\n"
            + "  3. Set [cyan]OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317[/] in .env.staging\n"
            + "  4. Send a request with [cyan]X-Tenant-Id: acme[/] header\n"
            + "  5. Query Tempo at [cyan]http://localhost:3200[/] for spans with ai.cost_usd attribute",
            title="[bold bright_cyan]🚀 Done[/]",
            border_style="green",
            padding=(1, 2),
        )
    )


def cmd_add_auth(provider: str | None):
    """Add JWT authentication."""
    console.print(BANNER)

    provider = (provider or "jwt").lower()
    if provider != "jwt":
        console.print(
            f"[{STYLE_WARN}]Unknown auth provider:[/] {provider}\n"
            "Available: [bold]jwt[/]\n"
            "[dim]Other providers (oauth2, keycloak, cognito) can ship as third-party plugins.[/]"
        )
        sys.exit(1)

    from fastforge.generators.auth import add_auth_jwt
    from fastforge.project_config import find_project_root

    project_dir = find_project_root()
    if not project_dir:
        console.print(
            f"[{STYLE_WARN}]✘ No .fastforge.json found.[/] Run from inside a FastForge project."
        )
        sys.exit(1)

    console.print(
        Panel(
            "[bold]This will:[/]\n"
            "  + Create app/auth/ (jwt.py, users.py, routes.py)\n"
            "  + Add /auth/login and /auth/me endpoints\n"
            "  + Add pyjwt + passlib[bcrypt] dependencies\n"
            "  + Add JWT_SECRET / JWT_ALGORITHM / JWT_EXPIRE_MIN to config + .env.staging\n"
            "  + Wire auth_router into main.py\n\n"
            "[yellow]⚠ The generated user store is in-memory (demo only).[/]\n"
            "  Replace with a real persistence + bcrypt flow before going to production.",
            title="[bold bright_cyan]📋 Add JWT Authentication[/]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not questionary.confirm("Proceed?", default=True).ask():
        console.print(f"[{STYLE_WARN}]Aborted.[/]")
        return

    try:
        result = add_auth_jwt(project_dir)
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"[{STYLE_WARN}]Error:[/] {exc}")
        sys.exit(1)

    if result["status"] == "already_configured":
        console.print("[green]✔ JWT auth is already configured in this project.[/]")
        return

    console.print(f"\n[green]✔ Added JWT authentication.[/] ({len(result['created'])} files)")
    for path in result["created"]:
        console.print(f"  [green]+[/] {path}")
    for path in result["modified"]:
        console.print(f"  [yellow]~[/] {path}")
    console.print(
        "\n[dim]Next: run [bold]pip install -e .[/] to pick up new dependencies, then "
        "[bold]POST /auth/login[/] with demo / demo to get a token.[/]"
    )


def cmd_add_redis():
    """Add Redis cache support."""
    console.print(BANNER)

    from fastforge.generators.redis import add_redis
    from fastforge.project_config import find_project_root, load_config

    project_dir = find_project_root()
    if not project_dir:
        console.print("[red]✘ No .fastforge.json found. Run from inside a FastForge project.[/]")
        sys.exit(1)

    config = load_config(project_dir)

    if config.get("cache") == "redis":
        console.print("[green]✔ Redis cache is already configured in this project.[/]")
        return
    if config.get("cache") not in ("none", None):
        console.print(
            f"[yellow]⚠ Project already has cache: {config['cache']}. Cannot switch to redis.[/]"
        )
        return

    console.print(f"[dim]Project: {config.get('project_slug', 'unknown')}[/]\n")
    console.print(
        Panel(
            "[bold]This will:[/]\n"
            "  + Create/update app/cache.py with async Redis client\n"
            "  + Add redis_url to config.py and .env.staging\n"
            "  + Wire close_cache() into app lifespan\n"
            "  + Add redis service to infra/docker-compose.redis.yml\n"
            "  + Add redis[hiredis] dependency to pyproject.toml\n"
            "  + Update .fastforge.json",
            title="[bold bright_cyan]📋 Add Redis Cache[/]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not questionary.confirm("Proceed?", default=True).ask():
        console.print("[yellow]Aborted.[/]")
        return

    try:
        result = add_redis(project_dir)
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
            "[bold green]✔ Redis cache added[/]\n\n"
            + "\n".join(lines)
            + "\n\n[bold]Next steps:[/]\n"
            + "  1. [green]pip install -e '.[dev]'[/]  [dim]# install redis[hiredis][/]\n"
            + "  2. [green]docker compose -f infra/docker-compose.redis.yml up -d[/]\n"
            + "  3. Use [cyan]from app.cache import get_cache[/] in your services",
            title="[bold bright_cyan]🚀 Done[/]",
            border_style="green",
            padding=(1, 2),
        )
    )
