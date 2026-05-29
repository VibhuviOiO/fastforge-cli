"""Generator dispatch — routes `fastforge add <feature>` to the correct emit mode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastforge.generator_protocol import discover_generators
from fastforge.project_config import get_emit_mode, load_config


class GeneratorNotFoundError(Exception):
    pass


class EmitModeNotSupportedError(Exception):
    pass


def dispatch_add(
    feature: str,
    project_dir: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch `fastforge add <feature>` to the correct generator and emit mode.

    1. Discovers the generator by name.
    2. Reads .fastforge.json to determine the project kind.
    3. Calls the appropriate emit method.
    """
    if args is None:
        args = {}

    generators = discover_generators()

    if feature not in generators:
        raise GeneratorNotFoundError(
            f"Generator '{feature}' not found. Available: {', '.join(sorted(generators.keys()))}"
        )

    generator = generators[feature]
    config = load_config(project_dir)
    emit_mode = get_emit_mode(config)
    path = Path(project_dir)

    if emit_mode == "inline":
        return generator.emit_inline(path, args)
    elif emit_mode == "delegated":
        if not generator.delegatable:
            raise EmitModeNotSupportedError(
                f"Generator '{feature}' does not support delegated mode. "
                f"This generator must be run in a standalone project or in a lib."
            )
        lib = config.get("platform_lib", "")
        return generator.emit_delegated(path, lib, args)
    elif emit_mode == "into_lib":
        return generator.emit_into_lib(path, args)
    else:
        raise ValueError(f"Unknown emit mode: {emit_mode}")


def dispatch_upgrade(
    project_dir: str,
    features: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Dispatch `fastforge upgrade` to all configured generators.

    If features is None, upgrades all generators that have a capability key
    set in .fastforge.json.
    """
    config = load_config(project_dir)
    generators = discover_generators()
    results: dict[str, list[dict[str, Any]]] = {"upgraded": [], "skipped": [], "errors": []}

    target_generators = features if features else list(generators.keys())

    for name in target_generators:
        if name not in generators:
            results["errors"].append({"name": name, "error": "Generator not found"})
            continue

        generator = generators[name]

        # Only upgrade generators whose capability is declared in the config
        cap_key = generator.capability_key
        if cap_key and cap_key not in config:
            results["skipped"].append({"name": name, "reason": "Not configured in this project"})
            continue

        # Get the version that was last applied
        versions = config.get("_generator_versions", {})
        from_version = versions.get(name, "0.0.0")

        if from_version == generator.version:
            results["skipped"].append({"name": name, "reason": "Already at latest version"})
            continue

        try:
            result = generator.upgrade(Path(project_dir), from_version)
            results["upgraded"].append(
                {"name": name, "from": from_version, "to": generator.version, **result}
            )

            # Record the new version
            if "_generator_versions" not in config:
                config["_generator_versions"] = {}
            config["_generator_versions"][name] = generator.version
        except Exception as e:
            results["errors"].append({"name": name, "error": str(e)})

    # Save updated version stamps
    from fastforge.project_config import save_config

    save_config(config, project_dir)

    return results


def dispatch_validate(project_dir: str) -> dict[str, list[str]]:
    """Run validate() on all configured generators. Returns {name: [warnings]}."""
    config = load_config(project_dir)
    generators = discover_generators()
    results: dict[str, list[str]] = {}

    for name, generator in generators.items():
        cap_key = generator.capability_key
        if cap_key and cap_key not in config:
            continue

        warnings = generator.validate(Path(project_dir))
        if warnings:
            results[name] = warnings

    return results
