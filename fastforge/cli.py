"""FastForge CLI — Interactive project generator for production-grade FastAPI applications.

This module is a thin dispatcher. All command logic lives in fastforge.commands.*.
"""

import argparse
import sys

from fastforge.commands._shared import BANNER, STYLE_WARN, console
from fastforge.commands.new import (
    _apply_ai_generator,
    _load_generation_context_from_file,
    generate,
)
from fastforge.commands.new import (
    cmd_new as _cmd_new,
)

__all__ = [
    "main",
    "_cmd_new",
    "_load_generation_context_from_file",
    "generate",
    "_apply_ai_generator",
]


# ═══════════════════════════════════════════════════════════════════════════════
# CLI entry point (argparse dispatcher)
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    """CLI entry point for ``fastforge``."""
    parser = argparse.ArgumentParser(
        prog="fastforge",
        description="Production-grade FastAPI project generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'fastforge <command> --help' for more information on a command.",
    )
    subparsers = parser.add_subparsers(dest="command", title="commands")

    # ─── fastforge new [service] ─────────────────────────
    new_parser = subparsers.add_parser(
        "new",
        help="Create a new FastAPI service",
        description="Scaffold a production-grade FastAPI project with interactive prompts for database, cache, streaming, secrets, logging, quality gates, and Docker support.",
    )
    new_parser.add_argument(
        "type",
        nargs="?",
        default="service",
        choices=["service"],
        help="Project type (default: service)",
    )
    new_parser.add_argument(
        "--kind",
        choices=["standalone", "app", "lib", "workspace"],
        default=None,
        help="Project shape (standalone, app, lib, workspace)",
    )
    new_parser.add_argument(
        "--use-lib",
        dest="use_lib",
        default=None,
        help="Platform library package spec (for kind=app)",
    )
    new_parser.add_argument(
        "--workspace", default=None, help="Path to workspace root (for workspace members)"
    )
    new_parser.add_argument(
        "--from-file",
        dest="from_file",
        default=None,
        help="Load a non-interactive project preset from a .fastforge.json or .fastforge.yaml file",
    )
    new_parser.add_argument(
        "--preset",
        dest="preset",
        default=None,
        help="Use a built-in preset by name (run 'fastforge list-presets' to see options)",
    )
    new_parser.add_argument(
        "--name", dest="name", default=None, help="Override the project_slug from the preset"
    )

    # ─── fastforge add <feature> ─────────────────────────
    add_parser = subparsers.add_parser(
        "add",
        help="Add a feature to an existing project",
        description="Add features to an existing FastForge project: models, databases, observability, and more.",
    )
    add_sub = add_parser.add_subparsers(dest="feature", title="features")
    model_p = add_sub.add_parser("model", help="Add a new CRUD model")
    model_p.add_argument("name", nargs="?", help="Model name (singular, snake_case)")
    add_sub.add_parser("postgres", help="Add PostgreSQL database")
    add_sub.add_parser("kafka", help="Add Kafka streaming")
    add_sub.add_parser("redis", help="Add Redis cache")
    add_sub.add_parser("observability", help="Add OpenTelemetry tracing + Prometheus metrics")
    add_sub.add_parser("ai-telemetry", help="Add OTel spans + USD cost attribution around AI calls")
    auth_p = add_sub.add_parser(
        "auth",
        help="Add authentication (optional — skip if auth lives at your API gateway)",
        description=(
            "Add an authentication strategy. JWT is supported in-tree; other strategies "
            "(oauth2, keycloak, etc.) can ship as third-party plugins."
        ),
    )
    auth_p.add_argument(
        "provider",
        nargs="?",
        default="jwt",
        choices=["jwt"],
        help="Auth provider (default: jwt)",
    )

    # ─── fastforge deploy <target> ───────────────────────
    deploy_p = subparsers.add_parser(
        "deploy",
        help="Deploy the service or generate deployment manifests",
        description="Run the service locally or generate deployment manifests for Kubernetes, Docker Swarm, Helm, Marathon, or Docker Compose.",
    )
    deploy_p.add_argument(
        "target",
        choices=["local", "compose", "swarm", "k8s", "helm", "marathon"],
        help="Deployment target",
    )

    # ─── fastforge secure <action> ───────────────────────
    secure_p = subparsers.add_parser(
        "secure",
        help="Security tooling and checks",
        description="Security commands: setup configs, scan images, generate SBOM, check licenses, audit dependencies, OWASP ZAP scan.",
    )
    secure_p.add_argument(
        "action",
        choices=["setup", "scan", "sbom", "license", "audit", "owasp"],
        help="Security action to perform",
    )

    # ─── fastforge ci <provider> ─────────────────────────
    ci_p = subparsers.add_parser(
        "ci",
        help="Generate CI/CD pipeline or run locally",
        description="Generate CI/CD pipeline configuration for GitHub Actions, GitLab CI, Bitbucket Pipelines, Jenkins, or run the pipeline locally.",
    )
    ci_p.add_argument(
        "provider",
        choices=["github", "gitlab", "bitbucket", "jenkins", "local"],
        help="CI/CD provider or 'local' to run pipeline locally",
    )

    # ─── fastforge doctor ────────────────────────────────
    subparsers.add_parser(
        "doctor",
        help="Check project health",
        description="Run 8 health checks: pyproject.toml, app/ structure, Dockerfile, tests/, .pre-commit-config.yaml, .fastforge.json, ruff lint, and pytest.",
    )

    # ─── fastforge upgrade ───────────────────────────────
    upgrade_p = subparsers.add_parser(
        "upgrade",
        help="Re-apply generator deltas to bring the project to current",
        description="For each generator declared in .fastforge.json, apply forward deltas from the recorded version to the current version.",
    )
    upgrade_p.add_argument(
        "features",
        nargs="*",
        help="Specific generators to upgrade (default: all configured)",
    )

    # ─── fastforge audit ─────────────────────────────────
    subparsers.add_parser(
        "audit",
        help="Check project for capability drift, CVEs, and env-contract violations",
        description="Run schema validation, capability drift detection, generator validation, dependency CVE scan (pip-audit), and env-contract checks.",
    )

    # ─── fastforge plugins ───────────────────────────────
    plugins_p = subparsers.add_parser(
        "plugins",
        help="Manage generator plugins",
        description="List or install third-party FastForge generators.",
    )
    plugins_sub = plugins_p.add_subparsers(dest="plugins_action", title="actions")
    plugins_sub.add_parser("ls", help="List all discovered generators")
    plugins_install_p = plugins_sub.add_parser("install", help="Install a generator plugin package")
    plugins_install_p.add_argument("package", help="Package to install (pip spec)")

    # ─── fastforge list-presets ──────────────────────────
    subparsers.add_parser(
        "list-presets",
        help="List built-in use-case presets",
        description="Show all use-case presets shipped with the fastforge-cli package. Use any name with 'fastforge new --preset <name>'.",
    )

    args = parser.parse_args()

    if args.command is None:
        console.print(BANNER)
        parser.print_help()
        return

    try:
        if args.command == "new":
            from fastforge.commands.new import cmd_new

            cmd_new(
                kind=getattr(args, "kind", None),
                use_lib=getattr(args, "use_lib", None),
                workspace=getattr(args, "workspace", None),
                from_file=getattr(args, "from_file", None),
                preset=getattr(args, "preset", None),
                name=getattr(args, "name", None),
            )
        elif args.command == "add":
            from fastforge.commands.add import (
                cmd_add_ai_telemetry,
                cmd_add_auth,
                cmd_add_kafka,
                cmd_add_model,
                cmd_add_observability,
                cmd_add_postgres,
                cmd_add_redis,
            )

            if not hasattr(args, "feature") or args.feature is None:
                console.print(BANNER)
                add_parser.print_help()
                return
            if args.feature == "model":
                cmd_add_model(getattr(args, "name", None))
            elif args.feature == "postgres":
                cmd_add_postgres()
            elif args.feature == "kafka":
                cmd_add_kafka()
            elif args.feature == "redis":
                cmd_add_redis()
            elif args.feature == "observability":
                cmd_add_observability()
            elif args.feature == "ai-telemetry":
                cmd_add_ai_telemetry()
            elif args.feature == "auth":
                cmd_add_auth(getattr(args, "provider", "jwt"))
        elif args.command == "deploy":
            from fastforge.commands.deploy import cmd_deploy

            cmd_deploy(args.target)
        elif args.command == "secure":
            from fastforge.commands.secure import cmd_secure

            cmd_secure(args.action)
        elif args.command == "ci":
            from fastforge.commands.ci_cmd import cmd_ci

            cmd_ci(args.provider)
        elif args.command == "doctor":
            from fastforge.commands.doctor import cmd_doctor

            cmd_doctor()
        elif args.command == "upgrade":
            from fastforge.commands.misc import cmd_upgrade

            cmd_upgrade(getattr(args, "features", None))
        elif args.command == "audit":
            from fastforge.commands.misc import cmd_audit

            cmd_audit()
        elif args.command == "plugins":
            from fastforge.commands.misc import cmd_plugins

            cmd_plugins(getattr(args, "plugins_action", None), getattr(args, "package", None))
        elif args.command == "list-presets":
            from fastforge.commands.misc import cmd_list_presets

            cmd_list_presets()
    except KeyboardInterrupt:
        console.print(f"\n[{STYLE_WARN}]Aborted.[/]")
        sys.exit(1)


if __name__ == "__main__":
    main()
