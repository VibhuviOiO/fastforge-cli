"""Post-generation hook — removes files and directories for disabled features."""

import os
import shutil

PROJECT_DIR = os.path.realpath(os.path.curdir)


def remove_path(rel_path: str) -> None:
    abs_path = os.path.join(PROJECT_DIR, rel_path)
    if os.path.isdir(abs_path):
        shutil.rmtree(abs_path)
    elif os.path.isfile(abs_path):
        os.remove(abs_path)


# ── Logging ──────────────────────────────────────────────────────────────────
if "{{ cookiecutter.logging }}" == "none":
    remove_path("app/logging_config.py")
    remove_path("app/middleware/logging_middleware.py")

# ── Log Agent ────────────────────────────────────────────────────────────────
log_agent = "{{ cookiecutter.log_agent }}"
if log_agent != "vector":
    remove_path("infra/vector")
if log_agent != "fluentbit":
    remove_path("infra/fluentbit")

# ── Database ─────────────────────────────────────────────────────────────────
database = "{{ cookiecutter.database }}"
if database == "none":
    remove_path("app/db")
elif database in ("postgres", "mysql", "sqlite"):
    remove_path("app/db/mongodb.py")
elif database == "mongodb":
    remove_path("app/db/sqlalchemy.py")

# ── Cache ────────────────────────────────────────────────────────────────────
if "{{ cookiecutter.cache }}" == "none":
    remove_path("app/cache.py")

# ── Streaming ────────────────────────────────────────────────────────────────
if "{{ cookiecutter.streaming }}" == "none":
    remove_path("app/streaming")

# ── Secrets ──────────────────────────────────────────────────────────────────
if "{{ cookiecutter.secrets }}" == "none":
    remove_path("app/secrets.py")

# ── Quality Gate ─────────────────────────────────────────────────────────────
quality_gate = "{{ cookiecutter.quality_gate }}"
if quality_gate != "sonarqube" and quality_gate != "sonarcloud":
    remove_path("sonar-project.properties")
if quality_gate != "qodana":
    remove_path("qodana.yaml")
if quality_gate != "codeclimate":
    remove_path(".codeclimate.yml")

# ── Docker ───────────────────────────────────────────────────────────────────
if "{{ cookiecutter.docker }}" != "yes":
    remove_path("Dockerfile")
    remove_path(".dockerignore")
    remove_path("infra")
    remove_path("docker-compose.debug.yml")
elif "{{ cookiecutter.docker_debug }}" != "yes":
    remove_path("docker-compose.debug.yml")

# ── Pre-commit ───────────────────────────────────────────────────────────────
if "{{ cookiecutter.precommit }}" != "yes":
    remove_path(".pre-commit-config.yaml")
    remove_path(".secrets.baseline")

# ── Init git repo ────────────────────────────────────────────────────────────
os.system("git init -q")

# Auto-format generated code with ruff (handles import ordering + style)
os.system("ruff check --fix --silent . 2>/dev/null || true")
os.system("ruff format --silent . 2>/dev/null || true")

# Generate detect-secrets baseline (must happen after git init, before commit)
if "{{ cookiecutter.precommit }}" == "yes":
    os.system("detect-secrets scan > .secrets.baseline 2>/dev/null || true")

os.system("git add .")
os.system('git commit -q -m "Initial project from FastForge"')

print("\n✅ {{ cookiecutter.project_name }} generated successfully!")
print("   cd {{ cookiecutter.project_slug }} && pip install -e '.[dev]'")
