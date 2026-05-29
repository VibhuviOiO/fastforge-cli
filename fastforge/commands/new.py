"""``fastforge new`` — Create a new FastAPI service (interactive or from preset)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import questionary
from cookiecutter.main import cookiecutter
from rich.panel import Panel
from rich.table import Table

from fastforge.commands._shared import (
    BANNER,
    CUSTOM_STYLE,
    STYLE_HINT,
    STYLE_SUCCESS,
    STYLE_WARN,
    console,
    section,
    text_prompt,
)

TEMPLATE_DIR = str(Path(__file__).resolve().parent.parent / "template")


# ── File categories for selective overwrite ──────────────────────────────────

FILE_CATEGORIES = {
    "Docker & Infrastructure": {
        "description": "Dockerfile, docker-compose, .dockerignore, docker/",
        "patterns": [
            "Dockerfile",
            ".dockerignore",
            "docker-compose.debug.yml",
            "infra/",
        ],
    },
    "Configuration": {
        "description": "pyproject.toml, .env, pre-commit, quality gate configs",
        "patterns": [
            "pyproject.toml",
            ".env.staging",
            ".pre-commit-config.yaml",
            ".secrets.baseline",
            "sonar-project.properties",
            "qodana.yaml",
            ".codeclimate.yml",
        ],
    },
    "App framework": {
        "description": "main.py, config, logging, middleware, dependencies",
        "patterns": [
            "app/main.py",
            "app/config.py",
            "app/logging_config.py",
            "app/dependencies.py",
            "app/middleware/",
            "app/__init__.py",
            "app/api/__init__.py",
            "app/api/exception_handlers.py",
        ],
    },
    "Business logic": {
        "description": "routes, models, services, repositories",
        "patterns": [
            "app/api/routes/",
            "app/api/models/",
            "app/services/",
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
    for category, info in FILE_CATEGORIES.items():
        for pattern in info["patterns"]:
            if pattern.endswith("/"):
                if rel_path.startswith(pattern):
                    return category
            elif rel_path == pattern:
                return category
    return "Other"


def _collect_changes(existing_dir: str, generated_dir: str) -> dict[str, list[tuple[str, str]]]:
    import filecmp

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
                continue
            category = _categorize_file(rel_path)
            changes.setdefault(category, []).append((rel_path, status))
    return changes


def _apply_selective_overwrite(
    existing_dir: str,
    generated_dir: str,
    selected_categories: list[str],
    changes: dict[str, list[tuple[str, str]]],
) -> list[str]:
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


# ── Interactive questions ────────────────────────────────────────────────────


def ask_basics() -> dict:
    section("📦  Project Basics")
    return {
        "project_name": text_prompt(
            "Project name:",
            default="my-fastapi-service",
            validate=lambda x: bool(x.strip()) or "Required",
        ),
        "description": text_prompt(
            "Description:",
            default="A production-grade FastAPI service",
        ),
        "author_name": text_prompt("Author name:", default="Your Name"),
        "author_email": text_prompt("Author email:", default="you@example.com"),
        "python_version": questionary.select(
            "Python version:",
            choices=["3.13", "3.12", "3.11"],
            default="3.13",
            style=CUSTOM_STYLE,
        ).ask(),
        "port": text_prompt("HTTP port:", default="8000"),
    }


def ask_model() -> dict:
    section("🧩  Domain Model")
    console.print(f"  [{STYLE_HINT}]Generates: route → service → repository → DB model (SOLID)[/]")
    model_name = text_prompt(
        "Model name (singular, lowercase):",
        default="item",
        validate=lambda x: (
            (x.isidentifier() and x.islower()) or "Must be a valid lowercase Python identifier"
        ),
    )
    model_name_class = model_name.capitalize()
    model_name_plural = model_name + "s"
    plural = text_prompt("Plural form (for route /api/v1/...):", default=model_name_plural)
    return {
        "model_name": model_name,
        "model_name_class": model_name_class,
        "model_name_plural": plural,
    }


def ask_logging_basic() -> dict:
    section("📋  Logging")
    console.print(f"  [{STYLE_HINT}]Stdout → logs visible via 'docker logs' (K8s/cloud-native)[/]")
    console.print(
        f"  [{STYLE_HINT}]Stdout + File → enables Vector/Fluent Bit to collect & forward logs[/]"
    )
    log_output = questionary.select(
        "Log output:",
        choices=[
            questionary.Choice("Stdout only — logs print to container output", value="stdout"),
            questionary.Choice(
                "Stdout + File — write to /var/log/app/ for log agent forwarding", value="file"
            ),
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
    section("🐳  Docker")
    debug = questionary.confirm(
        "Include debug compose (debugpy on port 5678)?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()
    return {"docker": "yes", "docker_debug": "yes" if debug else "no"}


def _ask_log_agent() -> dict:
    console.print(
        f"  [{STYLE_HINT}]A log agent runs as a sidecar in docker-compose, reads log files,[/]"
    )
    console.print(
        f"  [{STYLE_HINT}]and forwards them to your chosen target (Elasticsearch, Kafka, etc.)[/]"
    )
    agent = questionary.select(
        "Log collection agent (sidecar in docker-compose):",
        choices=[
            questionary.Choice(
                "None — I'll collect logs myself or use an existing daemon", value="none"
            ),
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
            questionary.Choice(
                "Elasticsearch — full-text search & analytics (ELK stack)", value="elasticsearch"
            ),
            questionary.Choice(
                "OpenSearch — AWS-managed alternative to Elasticsearch", value="opensearch"
            ),
            questionary.Choice("Kafka — stream to a topic for downstream consumers", value="kafka"),
            questionary.Choice("Loki — Grafana's lightweight log aggregation", value="loki"),
            questionary.Choice("HTTP endpoint — generic HTTP log ingestion API", value="http"),
        ],
        style=CUSTOM_STYLE,
    ).ask()
    return {"log_agent": agent, "log_target": target}


def ask_database() -> dict:
    section("🗄️  Database")
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
    section("⚡  Cache")
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
    section("📡  Streaming")
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
    section("🔐  Secrets")
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
    section("📋  Logging")
    enabled = questionary.confirm(
        "Enable structured logging (structlog)?", default=True, style=CUSTOM_STYLE
    ).ask()
    if not enabled:
        return {
            "logging": "none",
            "log_format": "console",
            "log_connector": "stdout",
            "log_agent": "none",
            "log_target": "none",
        }
    log_format = questionary.select(
        "Log format:", choices=["json", "console"], default="json", style=CUSTOM_STYLE
    ).ask()
    console.print(f"  [{STYLE_HINT}]Stdout → logs visible via 'docker logs' (K8s/cloud-native)[/]")
    console.print(
        f"  [{STYLE_HINT}]Stdout + File → enables Vector/Fluent Bit to collect & forward logs[/]"
    )
    log_connector = questionary.select(
        "Log output:",
        choices=[
            questionary.Choice("Stdout only — logs print to container output", value="stdout"),
            questionary.Choice(
                "Stdout + File — write to /var/log/app/ for log agent forwarding", value="file"
            ),
        ],
        default="stdout",
        style=CUSTOM_STYLE,
    ).ask()
    result = {
        "logging": "structlog",
        "log_format": log_format,
        "log_connector": log_connector,
        "log_agent": "none",
        "log_target": "none",
    }
    if log_connector == "file":
        result.update(_ask_log_agent())
    return result


def ask_quality_gate() -> dict:
    section("🛡️  Quality Gate")
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
    section("🐳  Docker")
    enabled = questionary.confirm("Enable Docker?", default=True, style=CUSTOM_STYLE).ask()
    if not enabled:
        return {"docker": "no", "docker_debug": "no"}
    debug = questionary.confirm(
        "Include debug compose (debugpy on port 5678)?", default=False, style=CUSTOM_STYLE
    ).ask()
    return {"docker": "yes", "docker_debug": "yes" if debug else "no"}


def ask_precommit() -> dict:
    section("🪝  Pre-commit")
    enabled = questionary.confirm(
        "Enable pre-commit hooks (ruff, pytest)?", default=True, style=CUSTOM_STYLE
    ).ask()
    return {"precommit": "yes" if enabled else "no"}


def ask_ai_capabilities() -> dict:
    section("AI Infrastructure")
    console.print(
        f"  [{STYLE_HINT}]This adds: LLM gateway client, embedding providers, vector store,[/]"
    )
    console.print(
        f"  [{STYLE_HINT}]and an orchestrator skeleton — all config-driven via env vars.[/]"
    )
    console.print()
    ai_app_kind = questionary.select(
        "AI application pattern:",
        choices=[
            questionary.Choice(
                "semantic_search — vector similarity search with optional query rewriting",
                value="semantic_search",
            ),
            questionary.Choice(
                "rag — retrieval-augmented generation (search + LLM answer)", value="rag"
            ),
            questionary.Choice("agent — tool-calling agent loop", value="agent"),
        ],
        default="semantic_search",
        style=CUSTOM_STYLE,
    ).ask()
    gateway_provider = questionary.select(
        "LLM Gateway (handles routing, fallback, budgeting):",
        choices=[
            questionary.Choice("litellm — OpenAI-compatible proxy (recommended)", value="litellm"),
            questionary.Choice("bifrost — BiFrost gateway", value="bifrost"),
        ],
        default="litellm",
        style=CUSTOM_STYLE,
    ).ask()
    embedding_provider = questionary.select(
        "Embedding provider:",
        choices=[
            questionary.Choice("openai — text-embedding-3-small/large", value="openai"),
            questionary.Choice("gemini — Google embedding models", value="gemini"),
            questionary.Choice("cohere — Cohere embed v3", value="cohere"),
            questionary.Choice("huggingface — sentence-transformers (local)", value="huggingface"),
            questionary.Choice("bedrock — AWS Bedrock Titan", value="bedrock"),
            questionary.Choice("local — fully offline inference", value="local"),
        ],
        default="openai",
        style=CUSTOM_STYLE,
    ).ask()
    vector_store_provider = questionary.select(
        "Vector store:",
        choices=[
            questionary.Choice("vertex_ai — Google Vertex AI Vector Search", value="vertex_ai"),
            questionary.Choice("chromadb — ChromaDB", value="chromadb"),
            questionary.Choice("opensearch — OpenSearch with k-NN", value="opensearch"),
            questionary.Choice("pgvector — PostgreSQL + pgvector", value="pgvector"),
            questionary.Choice("qdrant — Qdrant vector database", value="qdrant"),
        ],
        default="chromadb",
        style=CUSTOM_STYLE,
    ).ask()
    return {
        "ai_app_kind": ai_app_kind or "semantic_search",
        "llm_gateway": gateway_provider or "litellm",
        "embeddings_provider": embedding_provider or "openai",
        "vector_store": vector_store_provider or "chromadb",
    }


# ── AI generator post-scaffold ───────────────────────────────────────────────


def _apply_ai_generator(ctx: dict, project_dir: Path | None = None) -> None:
    from fastforge.generators.ai_app import AIAppGenerator

    if project_dir is None:
        project_slug = ctx.get("project_slug", ctx["project_name"].lower().replace(" ", "-"))
        project_dir = Path.cwd() / project_slug

    if not project_dir.exists():
        console.print(f"[{STYLE_WARN}]Could not find generated project at {project_dir}[/]")
        return

    generator = AIAppGenerator()
    result = generator.emit_inline(
        project_dir,
        args={
            "ai_app_kind": ctx.get("ai_app_kind", "semantic_search"),
            "gateway_provider": ctx.get("llm_gateway", "litellm"),
            "embedding_provider": ctx.get("embeddings_provider", "openai"),
            "vector_store_provider": ctx.get("vector_store", "chromadb"),
        },
    )

    if result["status"] == "ok":
        console.print("\n[bold green]AI infrastructure scaffolded[/]")
        console.print(
            f"  [dim]Created {len(result['created'])} files, modified {len(result['modified'])} files[/]"
        )
        console.print(
            f"  [dim]App kind: {ctx.get('ai_app_kind')} | Gateway: {ctx.get('llm_gateway')}[/]"
        )
        console.print(
            f"  [dim]Embeddings: {ctx.get('embeddings_provider')} | Vector store: {ctx.get('vector_store')}[/]"
        )


# ── Summary + generation ─────────────────────────────────────────────────────


def show_summary(ctx: dict, mode: str) -> None:
    table = Table(
        title=f"[bold]FastForge Configuration[/]  [dim]({mode} mode)[/]",
        show_header=True,
        header_style="bold bright_white",
        border_style="bright_cyan",
        title_style="bold bright_cyan",
    )
    table.add_column("Feature", style="cyan", min_width=16)
    table.add_column("Value", style="bright_green")
    table.add_row(
        "Project", f"[bold]{ctx['project_name']}[/] [dim](Python {ctx['python_version']})[/]"
    )
    table.add_row("Port", ctx["port"])
    table.add_row(
        "Model", f"[bold]{ctx['model_name_class']}[/] → /api/v1/{ctx['model_name_plural']}"
    )
    table.add_row("Database", ctx["database"] if ctx["database"] != "none" else "[dim]in-memory[/]")
    if mode == "advanced":
        table.add_row("Cache", ctx["cache"] if ctx["cache"] != "none" else "[dim]none[/]")
        table.add_row(
            "Streaming", ctx["streaming"] if ctx["streaming"] != "none" else "[dim]none[/]"
        )
        table.add_row("Secrets", ctx["secrets"] if ctx["secrets"] != "none" else "[dim]none[/]")
    log_val = ctx["logging"]
    if log_val != "none":
        agent_tag = ""
        if ctx.get("log_agent", "none") != "none":
            target = ctx.get("log_target", "none")
            agent_tag = f" + {ctx['log_agent']} → {target}"
        table.add_row(
            "Logging",
            f"structlog [dim]({ctx['log_format']} → {ctx['log_connector']}{agent_tag})[/]",
        )
    else:
        table.add_row("Logging", "[dim]disabled[/]")
    if mode == "advanced":
        table.add_row(
            "Quality gate", ctx["quality_gate"] if ctx["quality_gate"] != "none" else "[dim]none[/]"
        )
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

    if "kind" not in ctx:
        ctx["kind"] = "standalone"
    if "use_case" not in ctx:
        ctx["use_case"] = "custom"

    from fastforge import __version__ as _ff_version

    ctx["fastforge_version"] = _ff_version

    output_dir = os.getcwd()
    project_dir = os.path.join(output_dir, ctx["project_slug"])

    if os.path.exists(project_dir):
        action = questionary.select(
            f'"{ctx["project_slug"]}" already exists. What do you want to do?',
            choices=[
                questionary.Choice(
                    "Update selectively (choose what to overwrite)", value="selective"
                ),
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
            with tempfile.TemporaryDirectory() as tmp_dir:
                with console.status("[bold cyan]Generating to compare...[/]", spinner="dots"):
                    cookiecutter(TEMPLATE_DIR, no_input=True, extra_context=ctx, output_dir=tmp_dir)
                generated_dir = os.path.join(tmp_dir, ctx["project_slug"])
                changes = _collect_changes(project_dir, generated_dir)
                if not changes:
                    console.print("[green]No changes detected — project is up to date.[/]")
                    return
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
                    label = (
                        f"{category} ({', '.join(parts)}) — {desc}"
                        if desc
                        else f"{category} ({', '.join(parts)})"
                    )
                    choices.append(questionary.Choice(label, value=category))
                console.print()
                selected = questionary.checkbox(
                    "Select categories to update (space to toggle, enter to confirm):",
                    choices=choices,
                ).ask()
                if not selected:
                    console.print("[yellow]Nothing selected — no changes made.[/]")
                    return
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
                update_log = _apply_selective_overwrite(
                    project_dir, generated_dir, selected, changes
                )
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
        cookiecutter(TEMPLATE_DIR, no_input=True, extra_context=ctx, output_dir=output_dir)

    steps = [f"  [bold]cd {ctx['project_slug']}[/]"]
    if ctx["docker"] == "yes":
        if ctx.get("docker_debug") == "yes":
            steps.append(
                "  [green]docker compose -f docker-compose.debug.yml up --build[/]  [dim]# debug + auto-reload[/]"
            )
        steps.append(
            "  [green]docker compose -f infra/docker-compose.yml up --build[/]  [dim]# local infrastructure[/]"
        )
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
            f"[{STYLE_SUCCESS}]✔ Project created:[/] [bold]{project_dir}[/]\n\n" + "\n".join(steps),
            title="[bold bright_cyan]🚀 Next Steps[/]",
            border_style="green",
            padding=(1, 2),
        )
    )


# ── Preset helpers ───────────────────────────────────────────────────────────


def _builtin_presets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "presets"


def _list_builtin_presets() -> list[dict]:
    presets_dir = _builtin_presets_dir()
    seen: dict[str, dict] = {}
    if not presets_dir.exists():
        return []
    for path in sorted(presets_dir.iterdir()):
        if path.suffix not in (".json", ".yaml", ".yml"):
            continue
        stem = path.name
        for suf in (".fastforge.json", ".fastforge.yaml", ".fastforge.yml"):
            if stem.endswith(suf):
                stem = stem[: -len(suf)]
                break
        else:
            stem = path.stem
        if stem in seen:
            continue
        try:
            if path.suffix in (".yaml", ".yml"):
                import yaml

                data = yaml.safe_load(path.read_text())
            else:
                data = json.loads(path.read_text())
        except Exception:
            continue
        seen[stem] = {
            "name": stem,
            "path": path,
            "use_case": data.get("use_case", stem),
            "description": data.get("description", ""),
        }
    return list(seen.values())


def _resolve_preset(name_or_path: str) -> str:
    candidate = Path(name_or_path)
    if candidate.exists():
        return str(candidate)
    presets_dir = _builtin_presets_dir()
    for suf in (".fastforge.json", ".fastforge.yaml", ".fastforge.yml"):
        builtin = presets_dir / f"{name_or_path}{suf}"
        if builtin.exists():
            return str(builtin)
    raise FileNotFoundError(
        f"Preset not found: {name_or_path!r}. "
        f"Run 'fastforge list-presets' to see available built-in presets."
    )


def _load_generation_context_from_file(path: str) -> dict:
    preset_path = Path(path)
    if not preset_path.exists():
        raise FileNotFoundError(f"Preset file not found: {path}")

    text = preset_path.read_text()
    if preset_path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "PyYAML is required for YAML presets. Install it with: pip install pyyaml"
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    project_slug = data.get("project_slug") or data.get("project_name")
    if not project_slug:
        raise ValueError("Preset must define 'project_slug' or 'project_name'")

    model_name = data.get("model_name") or (data.get("models") or ["item"])[0]
    model_name = str(model_name).strip().lower().replace("-", "_").replace(" ", "_") or "item"

    author_name = data.get("author_name")
    author_email = data.get("author_email")
    if not author_name or not author_email:
        import subprocess as _sp

        if not author_name:
            try:
                author_name = (
                    _sp.run(
                        ["git", "config", "user.name"], capture_output=True, text=True
                    ).stdout.strip()
                    or "Your Name"
                )
            except Exception:
                author_name = "Your Name"
        if not author_email:
            try:
                author_email = (
                    _sp.run(
                        ["git", "config", "user.email"], capture_output=True, text=True
                    ).stdout.strip()
                    or "you@example.com"
                )
            except Exception:
                author_email = "you@example.com"

    ctx = {
        "project_name": data.get("project_name", project_slug),
        "description": data.get("description", "A production-grade FastAPI service"),
        "author_name": author_name,
        "author_email": author_email,
        "python_version": str(data.get("python_version", "3.13")),
        "port": str(data.get("port", "8000")),
        "model_name": model_name,
        "model_name_class": data.get("model_name_class", model_name.capitalize()),
        "model_name_plural": data.get(
            "model_name_plural", data.get("models_plural", model_name + "s")
        ),
        "database": data.get("database", "none"),
        "cache": data.get("cache", "none"),
        "streaming": data.get("streaming", "none"),
        "secrets": data.get("secrets", "none"),
        "logging": data.get("logging", "structlog"),
        "log_format": data.get("log_format", "json"),
        "log_connector": data.get("log_connector", "stdout"),
        "log_agent": data.get("log_agent", "none"),
        "log_target": data.get("log_target", "none"),
        "quality_gate": data.get("quality_gate", "none"),
        "docker": data.get("docker", "yes"),
        "docker_debug": data.get("docker_debug", "no"),
        "precommit": data.get("precommit", "yes"),
        "kind": data.get("kind", "standalone"),
        "use_case": data.get("use_case", "custom"),
        "platform_lib": data.get("platform_lib"),
        "workspace_root": data.get("workspace_root"),
        "observability": data.get("observability", "none"),
        "ai_app_kind": data.get("ai_app_kind", "none"),
        "llm_gateway": data.get("llm_gateway", "none"),
        "embeddings_provider": data.get("embeddings_provider", "none"),
        "vector_store": data.get("vector_store", "none"),
        "ai_telemetry": data.get("ai_telemetry"),
    }
    return ctx


# ── Main command ─────────────────────────────────────────────────────────────


def cmd_new(
    *,
    kind: str | None = None,
    use_lib: bool | None = None,
    workspace: str | None = None,
    from_file: str | None = None,
    preset: str | None = None,
    name: str | None = None,
):
    """Create a new FastAPI service (interactive).

    All arguments are optional; missing values are collected interactively.
    """
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

        kind_val = kind
        use_lib_val = use_lib
        workspace_val = workspace
        from_file_val = from_file
        preset_val = preset
        name_override = name

        if preset_val and not from_file_val:
            try:
                from_file_val = _resolve_preset(preset_val)
            except FileNotFoundError as e:
                console.print(f"[{STYLE_WARN}]Error:[/] {e}")
                sys.exit(1)

        if from_file_val:
            try:
                ctx = _load_generation_context_from_file(from_file_val)
            except FileNotFoundError as e:
                console.print(f"[{STYLE_WARN}]Error:[/] {e}")
                console.print(
                    "[dim]Hint: use an absolute path, or pick a built-in preset with --preset (see 'fastforge list-presets').[/]"
                )
                sys.exit(1)
            except (ValueError, ImportError) as e:
                console.print(f"[{STYLE_WARN}]Error:[/] {e}")
                sys.exit(1)
            if name_override:
                ctx["project_name"] = name_override
            if kind_val is not None:
                ctx["kind"] = kind_val
            if use_lib_val is not None:
                ctx["platform_lib"] = use_lib_val
            if workspace_val is not None:
                ctx["workspace_root"] = workspace_val

            mode = (
                "advanced"
                if any(
                    ctx.get(key, "none") != "none"
                    for key in ("database", "cache", "streaming", "secrets", "quality_gate")
                )
                else "basic"
            )

            source_label = (
                f"preset: {preset_val}" if preset_val else f"preset file: {from_file_val}"
            )
            console.print(f"[dim]Using {source_label}[/]")
            show_summary(ctx, mode)
            generate(ctx)

            project_dir = Path.cwd() / ctx["project_name"].lower().replace(" ", "-").replace(
                "_", "-"
            )

            if ctx.get("ai_app_kind", "none") != "none":
                _apply_ai_generator(ctx, project_dir)

            if ctx.get("observability") == "enabled":
                from fastforge.generators.observability import add_observability

                add_observability(str(project_dir), stack="grafana")

            if ctx.get("ai_telemetry"):
                from fastforge.generators.ai_telemetry import AITelemetryGenerator

                AITelemetryGenerator().emit_inline(project_dir, {})

            return

        if kind_val is None:
            section("Project Shape")
            console.print(f"  [{STYLE_HINT}]standalone = single app, all code inlined (default)[/]")
            console.print(
                f"  [{STYLE_HINT}]app = service that imports from a shared platform library[/]"
            )
            console.print(f"  [{STYLE_HINT}]lib = publishable platform library (no FastAPI app)[/]")
            console.print(
                f"  [{STYLE_HINT}]workspace = uv/hatch workspace with one lib + multiple apps[/]"
            )
            kind_val = questionary.select(
                "Project kind:",
                choices=[
                    questionary.Choice(
                        "standalone — single FastAPI service, all code inlined", value="standalone"
                    ),
                    questionary.Choice(
                        "app — FastAPI service using a shared platform library", value="app"
                    ),
                    questionary.Choice(
                        "lib — publishable platform library for other services", value="lib"
                    ),
                    questionary.Choice(
                        "workspace — monorepo with lib + multiple apps", value="workspace"
                    ),
                ],
                default="standalone",
                style=CUSTOM_STYLE,
            ).ask()
            if kind_val is None:
                console.print(f"[{STYLE_WARN}]Aborted.[/]")
                sys.exit(0)

        ctx["kind"] = kind_val

        if kind_val == "app" and use_lib_val is None:
            use_lib_val = questionary.text(
                "Platform library package (e.g. myorg-platform>=1.0):",
                validate=lambda x: bool(x.strip()) or "Required for app kind",
                style=CUSTOM_STYLE,
            ).ask()

        if use_lib_val:
            ctx["platform_lib"] = use_lib_val
        if workspace_val:
            ctx["workspace_root"] = workspace_val

        ctx.update(ask_basics())
        ctx.update(ask_model())

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

        console.print()
        ai_enabled = questionary.confirm(
            "Add AI capabilities? (LLM gateway, embeddings, vector search)",
            default=False,
            style=CUSTOM_STYLE,
        ).ask()

        if ai_enabled:
            ctx.update(ask_ai_capabilities())

        show_summary(ctx, mode)

        console.print()
        proceed = questionary.confirm("Generate project?", default=True, style=CUSTOM_STYLE).ask()
        if not proceed:
            console.print(f"[{STYLE_WARN}]Aborted.[/]")
            sys.exit(0)

        generate(ctx)

        if ai_enabled and ctx.get("ai_app_kind", "none") != "none":
            _apply_ai_generator(ctx)

    except KeyboardInterrupt:
        console.print(f"\n[{STYLE_WARN}]Aborted.[/]")
        sys.exit(1)
