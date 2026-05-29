# Contributing to FastForge

Thanks for your interest. This document covers the essentials.

## Development setup

```bash
git clone https://github.com/VibhuviOiO/fastforge-cli.git
cd fastforge-cli
python3 -m pip install -e ".[dev]"
```

## Running tests

```bash
# Unit tests
python3 -m pytest -q --ignore=tests/smoke_ecosystem.py

# End-to-end smoke harness (generates all 6 preset use-cases)
python3 tests/smoke_ecosystem.py

# Coverage report
python3 -m pytest --cov=fastforge --cov-report=term-missing --ignore=tests/smoke_ecosystem.py
```

## Coverage policy

- New generator code must ship with unit tests.
- The project targets **70%+ coverage on `fastforge/`** core. PRs that lower
  coverage will be flagged in CI.

## Adding a new generator

1. Create `fastforge/generators/<name>.py` exposing either a function or a
   class that implements the `Generator` protocol in
   `fastforge/generator_protocol.py`.
2. Register it in `pyproject.toml` under `[project.entry-points."fastforge.generators"]`.
3. Add a unit test in `tests/test_<name>_generator.py`.
4. Add an integration scenario in `tests/smoke_ecosystem.py` if it's
   exposed through a preset.
5. Update [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]`.

## Adding a new CLI command

CLI code lives in `fastforge/commands/`. The layout:

```
fastforge/commands/
├── _shared.py     # console, BANNER, styles, section(), text_prompt()
├── new.py         # fastforge new
├── add.py         # fastforge add <feature>
├── deploy.py      # fastforge deploy <target>
├── doctor.py      # fastforge doctor
├── secure.py      # fastforge secure <action>
├── ci_cmd.py      # fastforge ci <provider>
├── misc.py        # fastforge upgrade / audit / plugins / list-presets
├── audit.py       # audit logic (library, no CLI output)
└── upgrade.py     # upgrade logic (library, no CLI output)
```

1. Add your command function in the appropriate module (or create a new one).
2. Register the argparse sub-command in `fastforge/cli.py:main()`.
3. Import and dispatch to your function from the `main()` dispatcher.
4. If tests need to import the function, add a re-export in `cli.py` with
   `__all__` so ruff doesn't remove it.

## Adding a new preset

1. Create `fastforge/presets/<name>.fastforge.json` (and optionally
   `.yaml` mirror).
2. Mirror it to `examples/use-cases/` for reference.
3. Add a scenario to `tests/smoke_ecosystem.py`.
4. Update the [use-cases docs](https://vibhuvi.io/products/fastforge/use-cases).

## Commit + PR conventions

- One logical change per PR. If a PR touches the template AND the CLI AND
  the docs, that is fine when they are part of the same feature.
- Run `python3 -m pytest` and `python3 tests/smoke_ecosystem.py` locally
  before pushing.
- Update `CHANGELOG.md` under `[Unreleased]` in the same PR.

## Release process

1. Move `[Unreleased]` content into a new version section in `CHANGELOG.md`.
2. Bump `version` in `pyproject.toml`.
3. Tag: `git tag -a vX.Y.Z -m "vX.Y.Z"`.
4. Push tags. CI publishes to PyPI.

## Code style

- Formatted with `ruff format`.
- Linted with `ruff check`.
- Type hints required on new public APIs.
