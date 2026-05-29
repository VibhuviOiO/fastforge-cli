"""fastforge upgrade — re-apply generator deltas to bring a project to current."""

from __future__ import annotations

from fastforge.dispatch import dispatch_upgrade
from fastforge.project_config import find_project_root


def run_upgrade(project_dir: str | None = None, features: list[str] | None = None) -> dict:
    """Run upgrade on all or specified generators.

    Returns the dispatch result dict with upgraded/skipped/errors.
    """
    if project_dir is None:
        project_dir = find_project_root()
    if project_dir is None:
        raise FileNotFoundError(
            "No .fastforge.json found. Run this from inside a FastForge project."
        )

    return dispatch_upgrade(project_dir, features)
