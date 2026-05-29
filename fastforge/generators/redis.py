"""Add Redis cache support to an existing FastForge project.

Creates: app/cache.py, infra/docker-compose.redis.yml
Modifies: app/config.py, app/main.py, .env.staging, pyproject.toml, .fastforge.json
"""

import os
import re
import subprocess

from fastforge.project_config import load_config, save_config

CACHE_PY = '''\
"""Cache client — Redis backend."""

import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None


async def get_cache() -> redis.Redis:
    """Get the Redis cache client (lazy init)."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_cache() -> None:
    """Close the Redis connection pool."""
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.aclose()
        _client = None
'''

COMPOSE_REDIS_YML = """\
# Redis for local development
# Usage: docker compose -f infra/docker-compose.yml -f infra/docker-compose.redis.yml up -d

services:
  redis:
    image: redis:7-alpine
    container_name: {slug}-redis
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  redisdata:
    name: {slug}-redisdata
"""


def add_redis(project_dir: str) -> dict:
    """Add Redis cache support to the project. Returns summary of changes."""
    config = load_config(project_dir)

    # Idempotency
    if config.get("cache") == "redis":
        return {"status": "already_configured", "created": [], "modified": []}

    if config.get("cache") not in ("none", None):
        raise ValueError(f"Project already uses cache: {config['cache']}")

    slug = config.get("project_slug", "app")

    created: list[str] = []
    modified: list[str] = []

    # 1. Create/overwrite app/cache.py
    cache_path = os.path.join(project_dir, "app", "cache.py")
    with open(cache_path, "w") as f:
        f.write(CACHE_PY)
    if os.path.exists(cache_path):
        modified.append("app/cache.py")
    else:
        created.append("app/cache.py")

    # 2. Add redis_url to config.py
    config_path = os.path.join(project_dir, "app", "config.py")
    if os.path.isfile(config_path):
        with open(config_path) as f:
            content = f.read()

        if "redis_url" not in content:
            for anchor in ["    model_config", "    @property"]:
                if anchor in content:
                    insertion = (
                        "\n    # Redis\n"
                        '    redis_url: str = "redis://localhost:6379/0"\n\n'
                    )
                    content = content.replace(anchor, insertion + anchor, 1)
                    break

            with open(config_path, "w") as f:
                f.write(content)
            modified.append("app/config.py")

    # 3. Wire cache lifespan into main.py
    main_path = os.path.join(project_dir, "app", "main.py")
    if os.path.isfile(main_path):
        with open(main_path) as f:
            main_content = f.read()

        if "close_cache" not in main_content:
            # Add import
            import_line = "from app.cache import close_cache\n"
            if "from app" in main_content:
                # Insert after last "from app" import
                lines = main_content.split("\n")
                insert_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith("from app"):
                        insert_idx = i + 1
                lines.insert(insert_idx, import_line.rstrip())
                main_content = "\n".join(lines)
            else:
                main_content = import_line + main_content

            # Add close_cache() call in lifespan/shutdown
            if "yield" in main_content:
                # Async lifespan pattern — add close_cache after yield
                main_content = main_content.replace(
                    "    yield\n",
                    "    yield\n    await close_cache()\n",
                    1,
                )
            elif "shutdown" in main_content:
                # Event-based shutdown
                main_content = main_content.replace(
                    "async def shutdown():",
                    "async def shutdown():\n    await close_cache()",
                    1,
                )

            with open(main_path, "w") as f:
                f.write(main_content)
            modified.append("app/main.py")

    # 4. Add REDIS_URL to .env.staging
    env_path = os.path.join(project_dir, ".env.staging")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            env_content = f.read()

        if "REDIS_URL" not in env_content:
            with open(env_path, "a") as f:
                f.write("\n# Redis\nREDIS_URL=redis://localhost:6379/0\n")
            modified.append(".env.staging")

    # 5. Generate infra/docker-compose.redis.yml
    infra_dir = os.path.join(project_dir, "infra")
    os.makedirs(infra_dir, exist_ok=True)

    compose_path = os.path.join(infra_dir, "docker-compose.redis.yml")
    if not os.path.exists(compose_path):
        with open(compose_path, "w") as f:
            f.write(COMPOSE_REDIS_YML.format(slug=slug))
        created.append("infra/docker-compose.redis.yml")

    # 6. Add redis dependency to pyproject.toml
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        with open(pyproject_path) as f:
            pyproject_content = f.read()

        if "redis" not in pyproject_content.lower():
            match = re.search(
                r"(dependencies\s*=\s*\[)(.*?)(^\])", pyproject_content, re.DOTALL | re.MULTILINE
            )
            if match:
                existing = match.group(2).rstrip()
                if existing and not existing.rstrip().endswith(","):
                    existing = existing.rstrip() + ","
                new_section = existing + '\n    "redis[hiredis]>=5.0.0",\n'
                pyproject_content = (
                    pyproject_content[: match.start(2)]
                    + new_section
                    + pyproject_content[match.start(3) :]
                )
                with open(pyproject_path, "w") as f:
                    f.write(pyproject_content)
                modified.append("pyproject.toml")

    # 7. Run ruff
    subprocess.run(
        ["ruff", "check", "--fix", "--silent", "."], cwd=project_dir, capture_output=True
    )
    subprocess.run(["ruff", "format", "--silent", "."], cwd=project_dir, capture_output=True)

    # 8. Update .fastforge.json
    config["cache"] = "redis"
    save_config(config, project_dir)
    modified.append(".fastforge.json")

    return {"status": "added", "created": created, "modified": modified}
