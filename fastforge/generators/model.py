"""Add a new domain model to an existing FastForge project.

Creates: model, route, service, repository, test
Modifies: main.py (route import + include), dependencies.py (DI wiring), .fastforge.json
"""

import os
import re
import shutil
import subprocess

from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from fastforge.project_config import load_config, save_config, find_project_root

FRAGMENTS_DIR = str(Path(__file__).parent.parent / "fragments")


def pluralize(name: str) -> str:
    """Simple English pluralization."""
    if name.endswith("y") and name[-2:] not in ("ay", "ey", "oy", "uy"):
        return name[:-1] + "ies"
    if name.endswith(("s", "sh", "ch", "x", "z")):
        return name + "es"
    return name + "s"


def to_class_name(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in name.split("_"))


def render_fragment(template_name: str, context: dict) -> str:
    """Render a Jinja2 fragment template."""
    env = Environment(
        loader=FileSystemLoader(FRAGMENTS_DIR),
        keep_trailing_newline=True,
    )
    template = env.get_template(template_name)
    return template.render(**context)


def insert_after_last_match(content: str, pattern: str, insertion: str) -> str:
    """Insert a line after the last occurrence of a regex pattern."""
    lines = content.split("\n")
    last_idx = -1
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            last_idx = i
    if last_idx == -1:
        return content
    lines.insert(last_idx + 1, insertion)
    return "\n".join(lines)


def add_model(
    name: str,
    names: str | None = None,
    project_dir: str | None = None,
) -> dict:
    """Add a new model to the project. Returns summary of changes."""
    if project_dir is None:
        project_dir = find_project_root()
    if project_dir is None:
        raise FileNotFoundError("No .fastforge.json found. Run from inside a FastForge project.")

    config = load_config(project_dir)

    # Derive names
    name = name.lower().replace("-", "_")
    Name = to_class_name(name)
    if names is None:
        names = pluralize(name)

    # Check for duplicates
    if name in config.get("models", []):
        raise ValueError(f"Model '{name}' already exists in this project.")

    # Check target files don't already exist
    new_files = {
        f"app/api/models/{name}.py": "model.py.j2",
        f"app/api/routes/{names}.py": "route.py.j2",
        f"app/services/{name}_service.py": "service.py.j2",
        f"app/repositories/{name}_repository.py": "repository.py.j2",
        f"tests/test_{names}_api.py": "test_api.py.j2",
    }
    for rel_path in new_files:
        full_path = os.path.join(project_dir, rel_path)
        if os.path.exists(full_path):
            raise FileExistsError(f"File already exists: {rel_path}")

    # Template context
    ctx = {
        "name": name,
        "Name": Name,
        "names": names,
        "logging": config.get("logging", "structlog"),
        "database": config.get("database", "none"),
    }

    created = []
    modified = []

    # ── Create new files ─────────────────────────────────────────────────────
    for rel_path, template_name in new_files.items():
        full_path = os.path.join(project_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        content = render_fragment(template_name, ctx)
        with open(full_path, "w") as f:
            f.write(content)
        created.append(rel_path)

    # ── Modify main.py — add route import + include ──────────────────────────
    main_path = os.path.join(project_dir, "app/main.py")
    if os.path.isfile(main_path):
        with open(main_path) as f:
            main_content = f.read()

        # Add import after last route import
        import_line = f"from app.api.routes.{names} import router as {name}_router"
        if import_line not in main_content:
            main_content = insert_after_last_match(
                main_content,
                r"^from app\.api\.routes\.\w+ import router as \w+_router",
                import_line,
            )

        # Add include_router after last include_router
        include_line = f"    app.include_router({name}_router)"
        if include_line not in main_content:
            main_content = insert_after_last_match(
                main_content,
                r"^\s+app\.include_router\(\w+_router\)",
                include_line,
            )

        with open(main_path, "w") as f:
            f.write(main_content)
        modified.append("app/main.py")

    # ── Modify dependencies.py — add DI wiring ──────────────────────────────
    deps_path = os.path.join(project_dir, "app/dependencies.py")
    if os.path.isfile(deps_path):
        with open(deps_path) as f:
            deps_content = f.read()

        # Add imports
        repo_import = (
            f"from app.repositories.{name}_repository import (\n"
            f"    InMemory{Name}Repository,\n"
            f")"
        )
        service_import = f"from app.services.{name}_service import {Name}Service"

        if f"from app.repositories.{name}_repository" not in deps_content:
            # Insert after last repository import block
            deps_content = insert_after_last_match(
                deps_content,
                r"^from app\.services\.\w+_service import",
                f"\n{repo_import}\n{service_import}",
            )

        # Add DI function at end of file
        database = config.get("database", "none")
        if database == "none":
            di_block = (
                f"\n\n__{name}_repo = InMemory{Name}Repository()\n\n\n"
                f"def get_{name}_service() -> {Name}Service:\n"
                f'    """Provide {Name}Service with in-memory repository."""\n'
                f"    return {Name}Service(__{name}_repo)\n"
            )
        else:
            di_block = (
                f"\n\n\ndef get_{name}_service() -> {Name}Service:\n"
                f'    """Provide {Name}Service."""\n'
                f"    repo = InMemory{Name}Repository()\n"
                f"    return {Name}Service(repo)\n"
            )

        if f"def get_{name}_service" not in deps_content:
            deps_content = deps_content.rstrip() + di_block

        with open(deps_path, "w") as f:
            f.write(deps_content)
        modified.append("app/dependencies.py")

    # ── Run ruff to auto-fix formatting ──────────────────────────────────────
    subprocess.run(
        ["ruff", "check", "--fix", "--silent", "."],
        cwd=project_dir, capture_output=True,
    )
    subprocess.run(
        ["ruff", "format", "--silent", "."],
        cwd=project_dir, capture_output=True,
    )

    # ── Update detect-secrets baseline if it exists ──────────────────────────
    baseline_path = os.path.join(project_dir, ".secrets.baseline")
    if os.path.isfile(baseline_path):
        result = subprocess.run(
            ["detect-secrets", "scan"],
            cwd=project_dir, capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout:
            with open(baseline_path, "w") as f:
                f.write(result.stdout)

    # ── Update .fastforge.json ───────────────────────────────────────────────
    config.setdefault("models", []).append(name)
    save_config(config, project_dir)
    modified.append(".fastforge.json")

    return {"created": created, "modified": modified, "name": name, "Name": Name, "names": names}
