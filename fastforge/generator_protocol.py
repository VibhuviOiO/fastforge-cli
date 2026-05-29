"""FastForge Generator protocol and plugin discovery.

This module defines the contract every generator must follow (built-in or
third-party) and the discovery mechanism that finds them via entry points.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# ── Generator protocol ───────────────────────────────────────────────────────


@runtime_checkable
class Generator(Protocol):
    """Contract for all FastForge generators.

    Every generator must implement at least `emit_inline`. The other emit modes
    are optional and default to raising NotImplementedError via the base class.
    """

    @property
    def name(self) -> str:
        """Short kebab-case name (e.g. 'auth', 'postgres', 'vector-store')."""
        ...

    @property
    def version(self) -> str:
        """Semver string of this generator's implementation."""
        ...

    @property
    def description(self) -> str:
        """One-line description shown in `fastforge add --help`."""
        ...

    @property
    def capability_key(self) -> str:
        """The key this generator writes in .fastforge.json."""
        ...

    @property
    def delegatable(self) -> bool:
        """Whether this generator supports emit_delegated (lib-backed mode)."""
        ...

    def emit_inline(self, project_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        """Generate code directly into the project (standalone mode).

        Returns: {"status": "ok"|"already_configured", "created": [...], "modified": [...]}
        """
        ...

    def emit_delegated(self, project_dir: Path, lib: str, args: dict[str, Any]) -> dict[str, Any]:
        """Generate thin wire-up code that imports from a platform lib.

        Only called when kind="app" and platform_lib is set.
        Generators with delegatable=False should raise NotImplementedError.
        """
        ...

    def emit_into_lib(self, lib_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        """Generate the implementation into a shared platform library.

        Only called when kind="lib".
        """
        ...

    def upgrade(self, project_dir: Path, from_version: str) -> dict[str, Any]:
        """Apply forward deltas from from_version to self.version.

        Returns: {"status": "upgraded"|"no_change", "changes": [...]}
        """
        ...

    def validate(self, project_dir: Path) -> list[str]:
        """Check that the project state is consistent with this generator's output.

        Returns a list of warning/error strings. Empty list = healthy.
        """
        ...

    def capability_schema(self) -> dict[str, Any]:
        """Return the JSON-schema fragment for the capability key(s) this generator owns."""
        ...


# ── Base class (optional convenience) ────────────────────────────────────────


class BaseGenerator:
    """Optional base class providing sensible defaults for the Generator protocol."""

    name: str = "unnamed"
    version: str = "0.0.0"
    description: str = ""
    capability_key: str = ""
    delegatable: bool = True

    def emit_inline(self, project_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{self.name}: emit_inline not implemented")

    def emit_delegated(self, project_dir: Path, lib: str, args: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.name}: delegated mode not supported. "
            f"This generator must be run in standalone or lib mode."
        )

    def emit_into_lib(self, lib_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.name}: lib mode not supported. "
            f"This generator can only be used with standalone or app projects."
        )

    def upgrade(self, project_dir: Path, from_version: str) -> dict[str, Any]:
        return {"status": "no_change", "changes": []}

    def validate(self, project_dir: Path) -> list[str]:
        return []

    def capability_schema(self) -> dict[str, Any]:
        return {}


# ── Plugin discovery ─────────────────────────────────────────────────────────

ENTRY_POINT_GROUP = "fastforge.generators"


def discover_generators() -> dict[str, Generator]:
    """Discover all registered generators via entry points.

    Returns a dict of {name: generator_instance}.
    Built-in generators are registered in pyproject.toml under
    [project.entry-points."fastforge.generators"].
    """
    generators: dict[str, Generator] = {}

    try:
        eps = importlib.metadata.entry_points()
        # Python 3.12+ returns a SelectableGroups; 3.10/3.11 returns a dict
        if hasattr(eps, "select"):
            group_eps = eps.select(group=ENTRY_POINT_GROUP)
        else:
            group_eps = eps.get(ENTRY_POINT_GROUP, [])
    except Exception:
        group_eps = []

    for ep in group_eps:
        try:
            generator_cls = ep.load()
            # Support both class (instantiate) and instance
            if isinstance(generator_cls, type):
                instance = generator_cls()
            else:
                instance = generator_cls
            generators[ep.name] = instance
        except Exception as e:
            # Don't crash the CLI if a plugin is broken
            import sys

            print(f"Warning: failed to load generator '{ep.name}': {e}", file=sys.stderr)

    return generators


def get_generator(name: str) -> Generator | None:
    """Get a specific generator by name. Returns None if not found."""
    generators = discover_generators()
    return generators.get(name)


def list_generators() -> list[tuple[str, str, str]]:
    """List all discovered generators as (name, version, description) tuples."""
    generators = discover_generators()
    return [
        (g.name, g.version, g.description)
        for g in sorted(generators.values(), key=lambda g: g.name)
    ]
