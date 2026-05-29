"""Tests for fastforge.generator_protocol — protocol, base class, and discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from fastforge.generator_protocol import (
    BaseGenerator,
    Generator,
    discover_generators,
    get_generator,
    list_generators,
)

# ── Protocol conformance ─────────────────────────────────────────────────────


class ConformingGenerator(BaseGenerator):
    name = "test-gen"
    version = "1.0.0"
    description = "A test generator"
    capability_key = "test_cap"
    delegatable = True

    def emit_inline(self, project_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "created": ["file.py"], "modified": []}


def test_conforming_generator_satisfies_protocol():
    gen = ConformingGenerator()
    assert isinstance(gen, Generator)


def test_base_generator_defaults():
    gen = BaseGenerator()
    assert gen.name == "unnamed"
    assert gen.version == "0.0.0"
    assert gen.description == ""
    assert gen.capability_key == ""
    assert gen.delegatable is True


def test_base_generator_emit_inline_raises():
    gen = BaseGenerator()
    with pytest.raises(NotImplementedError):
        gen.emit_inline(Path("/tmp"), {})


def test_base_generator_emit_delegated_raises():
    gen = BaseGenerator()
    with pytest.raises(NotImplementedError):
        gen.emit_delegated(Path("/tmp"), "some-lib", {})


def test_base_generator_emit_into_lib_raises():
    gen = BaseGenerator()
    with pytest.raises(NotImplementedError):
        gen.emit_into_lib(Path("/tmp"), {})


def test_base_generator_upgrade_returns_no_change():
    gen = BaseGenerator()
    result = gen.upgrade(Path("/tmp"), "0.0.0")
    assert result == {"status": "no_change", "changes": []}


def test_base_generator_validate_returns_empty():
    gen = BaseGenerator()
    assert gen.validate(Path("/tmp")) == []


def test_base_generator_capability_schema_returns_empty():
    gen = BaseGenerator()
    assert gen.capability_schema() == {}


# ── Discovery ────────────────────────────────────────────────────────────────


def _make_mock_entry_point(name: str, generator_cls):
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = generator_cls
    return ep


@patch("fastforge.generator_protocol.importlib.metadata.entry_points")
def test_discover_generators_with_class(mock_eps):
    mock_eps.return_value = MagicMock()
    mock_eps.return_value.select.return_value = [
        _make_mock_entry_point("test-gen", ConformingGenerator)
    ]

    generators = discover_generators()
    assert "test-gen" in generators
    assert isinstance(generators["test-gen"], ConformingGenerator)


@patch("fastforge.generator_protocol.importlib.metadata.entry_points")
def test_discover_generators_with_instance(mock_eps):
    instance = ConformingGenerator()
    mock_eps.return_value = MagicMock()
    mock_eps.return_value.select.return_value = [_make_mock_entry_point("test-gen", instance)]

    generators = discover_generators()
    assert "test-gen" in generators
    assert generators["test-gen"] is instance


@patch("fastforge.generator_protocol.importlib.metadata.entry_points")
def test_discover_generators_handles_broken_plugin(mock_eps, capsys):
    ep = MagicMock()
    ep.name = "broken"
    ep.load.side_effect = ImportError("no such module")
    mock_eps.return_value = MagicMock()
    mock_eps.return_value.select.return_value = [ep]

    generators = discover_generators()
    assert "broken" not in generators
    captured = capsys.readouterr()
    assert "Warning" in captured.err


@patch("fastforge.generator_protocol.importlib.metadata.entry_points")
def test_discover_generators_empty_group(mock_eps):
    mock_eps.return_value = MagicMock()
    mock_eps.return_value.select.return_value = []

    generators = discover_generators()
    assert generators == {}


@patch("fastforge.generator_protocol.discover_generators")
def test_get_generator_found(mock_discover):
    gen = ConformingGenerator()
    mock_discover.return_value = {"test-gen": gen}
    assert get_generator("test-gen") is gen


@patch("fastforge.generator_protocol.discover_generators")
def test_get_generator_not_found(mock_discover):
    mock_discover.return_value = {}
    assert get_generator("nope") is None


@patch("fastforge.generator_protocol.discover_generators")
def test_list_generators(mock_discover):
    gen = ConformingGenerator()
    mock_discover.return_value = {"test-gen": gen}
    result = list_generators()
    assert result == [("test-gen", "1.0.0", "A test generator")]
