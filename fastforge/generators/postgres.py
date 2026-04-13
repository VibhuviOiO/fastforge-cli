"""Add PostgreSQL database support to an existing FastForge project.

Creates: app/db/__init__.py, app/db/session.py
Modifies: app/config.py, .env.staging, infra/docker-compose.yml, pyproject.toml, .fastforge.json
"""

import os
import re
import subprocess

from fastforge.project_config import load_config, save_config

DB_SESSION = '''\
"""Async SQLAlchemy database session."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with async_session() as session:
        yield session
'''

DB_INIT = '"""Database package."""\n'

COMPOSE_POSTGRES_YML = """\
# PostgreSQL for local development
# Usage: docker compose -f infra/docker-compose.yml -f infra/docker-compose.postgres.yml up -d

services:
  postgres:
    image: postgres:16-alpine
    container_name: {slug}-db
    environment:
      POSTGRES_DB: {package}
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
    name: {slug}-pgdata
"""

INIT_SQL = """\
-- Init script for {package} database
-- This file runs automatically on first container start

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE {package} TO postgres;
"""


def add_postgres(project_dir: str) -> dict:
    """Add PostgreSQL support to the project. Returns summary of changes."""
    config = load_config(project_dir)

    # Idempotency
    if config.get("database") == "postgres":
        return {"status": "already_configured", "created": [], "modified": []}

    if config.get("database") not in ("none", None):
        raise ValueError(f"Project already uses database: {config['database']}")

    slug = config.get("project_slug", "app")
    package = config.get("package_name", slug.replace("-", "_"))

    created: list[str] = []
    modified: list[str] = []

    # 1. Create app/db/ with session.py
    db_dir = os.path.join(project_dir, "app", "db")
    os.makedirs(db_dir, exist_ok=True)

    init_path = os.path.join(db_dir, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write(DB_INIT)
        created.append("app/db/__init__.py")

    session_path = os.path.join(db_dir, "session.py")
    if not os.path.exists(session_path):
        with open(session_path, "w") as f:
            f.write(DB_SESSION)
        created.append("app/db/session.py")

    # 2. Add database_url to config.py
    config_path = os.path.join(project_dir, "app", "config.py")
    if os.path.isfile(config_path):
        with open(config_path) as f:
            content = f.read()

        if "database_url" not in content:
            # Insert before model_config or @property
            for anchor in ["    model_config", "    @property"]:
                if anchor in content:
                    insertion = (
                        f"\n    # PostgreSQL\n"
                        f'    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/{package}"\n\n'
                    )
                    content = content.replace(anchor, insertion + anchor, 1)
                    break

            with open(config_path, "w") as f:
                f.write(content)
            modified.append("app/config.py")

    # 3. Add DATABASE_URL to .env.staging
    env_path = os.path.join(project_dir, ".env.staging")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            env_content = f.read()

        if "DATABASE_URL" not in env_content.upper():
            with open(env_path, "a") as f:
                f.write(f"\n# PostgreSQL\nDATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/{package}\n")
            modified.append(".env.staging")

    # 4. Generate infra/docker-compose.postgres.yml + infra/postgres/init.sql
    infra_dir = os.path.join(project_dir, "infra")
    os.makedirs(infra_dir, exist_ok=True)

    compose_path = os.path.join(infra_dir, "docker-compose.postgres.yml")
    if not os.path.exists(compose_path):
        with open(compose_path, "w") as f:
            f.write(COMPOSE_POSTGRES_YML.format(slug=slug, package=package))
        created.append("infra/docker-compose.postgres.yml")

    pg_dir = os.path.join(infra_dir, "postgres")
    os.makedirs(pg_dir, exist_ok=True)

    init_path = os.path.join(pg_dir, "init.sql")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write(INIT_SQL.format(package=package))
        created.append("infra/postgres/init.sql")

    # 5. Add dependencies to pyproject.toml
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        with open(pyproject_path) as f:
            pyproject_content = f.read()

        new_deps = []
        for dep_name, dep_spec in [
            ("sqlalchemy", '"sqlalchemy[asyncio]>=2.0"'),
            ("asyncpg", '"asyncpg>=0.30.0"'),
            ("alembic", '"alembic>=1.14.0"'),
        ]:
            if dep_name not in pyproject_content.lower():
                new_deps.append(dep_spec)

        if new_deps:
            # Find the closing ] of the dependencies list (at start of line)
            match = re.search(r"(dependencies\s*=\s*\[)(.*?)(^\])", pyproject_content, re.DOTALL | re.MULTILINE)
            if match:
                existing = match.group(2).rstrip()
                # Ensure trailing comma on last existing dep
                if existing and not existing.rstrip().endswith(","):
                    existing = existing.rstrip() + ","
                new_section = existing + "\n" + "\n".join(f"    {d}," for d in new_deps) + "\n"
                pyproject_content = (
                    pyproject_content[:match.start(2)]
                    + new_section
                    + pyproject_content[match.start(3):]
                )

                with open(pyproject_path, "w") as f:
                    f.write(pyproject_content)
                modified.append("pyproject.toml")

    # 6. Run ruff
    subprocess.run(["ruff", "check", "--fix", "--silent", "."], cwd=project_dir, capture_output=True)
    subprocess.run(["ruff", "format", "--silent", "."], cwd=project_dir, capture_output=True)

    # 7. Update detect-secrets baseline
    baseline_path = os.path.join(project_dir, ".secrets.baseline")
    if os.path.isfile(baseline_path):
        result = subprocess.run(["detect-secrets", "scan"], cwd=project_dir, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout:
            with open(baseline_path, "w") as f:
                f.write(result.stdout)

    # 8. Update .fastforge.json
    config["database"] = "postgres"
    save_config(config, project_dir)
    modified.append(".fastforge.json")

    return {"status": "added", "created": created, "modified": modified}
