"""Contract tests for the history schema and the CLI constants."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import neon_armada.contracts as contracts_package
from neon_armada.contracts.cli import ENGINE_MODULE, ExitCode
from neon_armada.contracts.fingerprint import state_fingerprint
from neon_armada.contracts.history import (
    EVENT_FIELDS,
    HISTORY_FORMAT,
    HistoryError,
    validate_history_document,
)
from neon_armada.contracts.models import MatchState


def test_history_fixture_is_valid(load_fixture) -> None:
    document = load_fixture("contracts/history.valid.json")
    validate_history_document(document)
    assert document["format"] == HISTORY_FORMAT
    assert document["history_version"] == 1
    header = document["header"]
    assert {"seed", "config", "agents"} <= set(header)
    initial = MatchState.from_dict(document["initial_state"])
    assert state_fingerprint(initial) == document["initial_fingerprint"]


def test_history_fixture_has_no_floats_or_paths(load_fixture) -> None:
    def walk(value) -> None:
        assert not isinstance(value, float)
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            assert ":\\" not in value and not value.startswith("/")

    walk(load_fixture("contracts/history.valid.json"))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(format="other"),
        lambda d: d.update(history_version=2),
        lambda d: d.update(history_version="1"),
        lambda d: d.pop("header"),
        lambda d: d["header"].pop("seed"),
        lambda d: d["header"].update(seed=-1),
        lambda d: d["header"]["agents"].pop(),
        lambda d: d["header"]["agents"][0].update(name=5),
        lambda d: d["header"]["config"].update(map_size=40),
        lambda d: d.pop("map"),
        lambda d: d.pop("initial_state"),
        lambda d: d["initial_state"].update(tick=1),
        lambda d: d.update(initial_fingerprint="abc"),
        lambda d: d.pop("setup_events"),
        lambda d: d.update(ticks={}),
        lambda d: d["ticks"][1].update(tick=5),
        lambda d: d["ticks"][0].update(fingerprint="Z" * 64),
        lambda d: d["ticks"][0]["events"].append({"type": "teleport"}),
        lambda d: d["ticks"][0]["events"].append({"type": "ship_moved", "ship": 0}),
        lambda d: d["ticks"][0]["events"].append(
            {"type": "invalid_command", "player": 0, "reason": "because"}
        ),
        lambda d: d["ticks"][0]["events"].append(
            {"type": "agent_excluded", "player": 2, "reason": "timeout"}
        ),
        lambda d: d["ticks"][0]["events"].append(
            {"type": "collision", "x": 1, "y": 1, "ships": [3], "energy_added": 0}
        ),
        lambda d: d["ticks"].pop(),
        lambda d: d.pop("result"),
        lambda d: d["result"].update(winner=None),
    ],
)
def test_history_rejects_invalid_documents(load_fixture, mutate) -> None:
    document = load_fixture("contracts/history.valid.json")
    mutate(document)
    with pytest.raises(HistoryError):
        validate_history_document(document)


@pytest.mark.parametrize("document", [None, [], "text", 3])
def test_history_rejects_non_objects(document) -> None:
    with pytest.raises(HistoryError):
        validate_history_document(document)


def test_event_catalogue_matches_contract() -> None:
    assert set(EVENT_FIELDS) == {
        "timeout",
        "malformed_response",
        "agent_excluded",
        "invalid_command",
        "ship_spawned",
        "build_started",
        "ship_moved",
        "collision",
        "mined",
        "delivered",
    }


def test_exit_codes_match_contract() -> None:
    assert ENGINE_MODULE == "neon_armada.engine"
    assert {code.name: code.value for code in ExitCode} == {
        "OK": 0,
        "DIFFERENT": 1,
        "USAGE": 2,
        "AGENT_NOT_FOUND": 3,
        "MAP_GENERATION_FAILED": 4,
        "OUTPUT_ERROR": 5,
        "HISTORY_INVALID": 6,
        "INTERNAL_ERROR": 70,
    }


def test_contracts_package_has_no_gui_engine_or_process_imports() -> None:
    forbidden = ("PySide6", "subprocess", "neon_armada.engine", "neon_armada.client")
    for path in Path(contracts_package.__file__).parent.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(forbidden), f"{path.name} imports {name}"
