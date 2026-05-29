"""Read and write .fastforge.json project configuration."""

from __future__ import annotations

import json
import os
from typing import Any

CONFIG_FILE = ".fastforge.json"


def find_project_root() -> str | None:
    """Walk up from cwd to find .fastforge.json."""
    path = os.path.abspath(os.getcwd())
    while True:
        if os.path.isfile(os.path.join(path, CONFIG_FILE)):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def load_config(project_dir: str | None = None) -> dict:
    """Load .fastforge.json from project directory."""
    if project_dir is None:
        project_dir = find_project_root()
    if project_dir is None:
        raise FileNotFoundError(
            f"No {CONFIG_FILE} found. Run this command from inside a FastForge project, "
            "or create a new project with `fastforge`."
        )
    config_path = os.path.join(project_dir, CONFIG_FILE)
    with open(config_path) as f:
        return json.load(f)


def save_config(config: dict, project_dir: str | None = None) -> None:
    """Write .fastforge.json to project directory."""
    if project_dir is None:
        project_dir = find_project_root()
    if project_dir is None:
        raise FileNotFoundError(f"No {CONFIG_FILE} found.")
    config_path = os.path.join(project_dir, CONFIG_FILE)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


# ── Capability helpers ───────────────────────────────────────────────────────


def get_kind(config: dict) -> str:
    """Return the project kind from config. Defaults to 'standalone'."""
    return config.get("kind", "standalone")


def get_platform_lib(config: dict) -> str | None:
    """Return the platform_lib spec, or None if not set."""
    return config.get("platform_lib")


def require_capability(config: dict, key: str, allowed: list[str]) -> None:
    """Raise ValueError if the capability key is not in the allowed set."""
    value = config.get(key, "none")
    if value not in allowed:
        raise ValueError(f"Capability '{key}' has value '{value}', expected one of: {allowed}")


def set_capability(config: dict, key: str, value: Any) -> dict:
    """Set a capability key and return the modified config (mutates in place)."""
    config[key] = value
    return config


def get_emit_mode(config: dict) -> str:
    """Determine which emit mode to use based on project kind.

    Returns: 'inline' | 'delegated' | 'into_lib'
    """
    kind = get_kind(config)
    if kind == "standalone":
        return "inline"
    elif kind == "app" and get_platform_lib(config):
        return "delegated"
    elif kind == "lib":
        return "into_lib"
    else:
        # Default to inline for unknown kinds or app without lib
        return "inline"
