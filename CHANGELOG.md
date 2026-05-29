# Changelog

All notable changes to **fastforge-cli** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] — 2026-05-30

### Added
- **`fastforge add redis`** — real Redis cache generator (replaces the stub).
  Creates `app/cache.py` with async redis client, adds `redis_url` to
  `config.py`, wires `close_cache` into `main.py` lifespan, generates
  `infra/docker-compose.redis.yml`, adds `redis[hiredis]` dep.
- **`fastforge add auth jwt`** — JWT authentication plugin (PyJWT +
  passlib bcrypt). Creates `app/auth/` with login/me routes, settings, env
  vars, and wires `auth_router` into `main.py`.
- **Pagination** on generated list endpoints: `?limit=` (1-200, default 50)
  and `?offset=` (>=0). Response includes `limit` and `offset`. Repository
  contract uses `list(limit, offset)` returning `(page_items, total)`.
- **End-to-end generated project tests** (`tests/test_e2e_generated.py`) —
  generates projects from presets, creates venvs, installs deps, and runs
  `pytest` inside. Validates generated code is functional, not just syntactic.
- 56 new unit tests for CLI command modules, Redis generator, CI local runner,
  and secure generator. Total: **202 unit tests + 3 E2E tests**.
- Coverage gate raised from 50% → **70%** in CI workflow.

### Changed
- **Health endpoints finalized**: only `/livez` (liveness) and `/readyz`
  (readiness) remain. All deprecated aliases (`/healthz`, `/health`, `/ready`)
  removed from templates, Dockerfiles, docker-compose configs, and generators.
- **Split `cli.py` (2,608 LOC) into `fastforge/commands/`** — thin 270-line
  argparse dispatcher importing from
  `commands/{new, add, deploy, doctor, secure, ci_cmd, misc}.py` plus a
  shared `_shared.py` for console/styles/prompts.
- **CI workflow** now runs `ruff check`, `ruff format --check`,
  `pytest --cov` (with a 70% gate), E2E job, and smoke harness across
  Python 3.10 / 3.11 / 3.12 / 3.13.
- `fastforge add model` no longer crashes when `detect-secrets` or `pytest`
  aren't installed — guarded with `shutil.which()` and graceful fallback.
- `ruff` subprocess in model generator guarded with `shutil.which()`.

### Fixed
- Loop-variable closure bug in `ai_telemetry._add_deps`: `lambda m: ...` was
  capturing `dep` by reference. Fixed with `lambda m, _dep=dep:`.
- `_load_generation_context_from_file` raises `ImportError` with proper
  `from exc` chain when PyYAML is missing.

### Removed
- Deprecated health endpoint aliases (`/healthz`, `/health`, `/ready`).

## [0.2.0] — 2026-05-29

### Added
- **Built-in preset library** shipped inside the wheel (`fastforge/presets/`):
  `simple-fastapi`, `postgres-api`, `event-service`, `semantic-search`,
  `rag-observable`, `observable-api`.
- `fastforge new --preset <name>` — generate from a built-in preset without
  needing to clone the repo.
- `fastforge new --name <slug>` — override the project slug from a preset.
- `fastforge list-presets` — discover available presets from the CLI.
- YAML support for preset files (`.fastforge.yaml`, `.fastforge.yml`)
  alongside JSON.
- `.env.example` rendered in every generated project, scoped to the chosen
  database / cache / streaming / secrets options.
- Friendly error message (no raw traceback) when `--from-file` / `--preset`
  cannot resolve a preset.
- Author name and email now auto-resolve from `git config` when not specified
  in the preset.
- `model_name` is now stored in `.fastforge.json` (was only in the `models`
  array before).

### Changed
- README quickstart now shows `fastforge new --preset ...` instead of
  relative `--from-file` paths that only worked from the repo root.
- README "Quick Start" now says `fastforge new` (the bare `fastforge` command
  only prints help).

### Fixed
- `_wrap_registry` in the `ai-telemetry` generator now correctly handles
  the assign-then-return pattern and inserts imports after `from __future__`
  lines.

### Removed
- Orphaned `test_log_agents.py` at the repo root (used dead template fields).

## [0.1.0] — 2026-04-12

### Added
- Initial public release: `fastforge new`, `fastforge add`, `fastforge deploy`,
  `fastforge doctor`, AI app and AI telemetry generators, observability
  generator with Grafana / Jaeger / ELK stacks.

[Unreleased]: https://github.com/VibhuviOiO/fastforge-cli/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/VibhuviOiO/fastforge-cli/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/VibhuviOiO/fastforge-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/VibhuviOiO/fastforge-cli/releases/tag/v0.1.0
