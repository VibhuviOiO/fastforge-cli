"""Read and write .fastforge.json project configuration."""

import json
import os

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
