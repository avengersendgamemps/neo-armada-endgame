"""Contract tests for the engine–agent protocol messages."""

from __future__ import annotations

import json

import pytest

from neon_armada.contracts import protocol
from neon_armada.contracts.models import (
    Action,
    MatchConfig,
    MatchState,
    PlayerCommands,
    ShipCommand,
    StaticMap,
)


def _line(message: dict) -> str:
    return protocol.encode_message(message)


def test_encode_message_is_one_compact_line() -> None:
    line = _line({"type": "ready", "protocol_version": 1})
    assert line == '{"type":"ready","protocol_version":1}\n'
    assert line.count("\n") == 1


@pytest.mark.parametrize("name", ["init", "tick", "end"])
def test_engine_message_fixtures_are_valid(load_fixture, name: str) -> None:
    message = load_fixture(f"contracts/{name}.valid.json")
    assert protocol.parse_engine_message(_line(message)) == message


def test_init_message_matches_fixture(load_fixture) -> None:
    fixture = load_fixture("contracts/init.valid.json")
    config = MatchConfig.from_dict(fixture["config"])
    static_map = StaticMap.from_dict(fixture["map"])
    assert protocol.init_message(0, config, static_map) == fixture


def test_tick_message_contains_only_dynamic_state(load_fixture) -> None:
    fixture = load_fixture("contracts/tick.valid.json")
    assert set(fixture) == {
        "type",
        "tick",
        "reserves",
        "move_budgets",
        "pending_builds",
        "ships",
        "energy",
    }
    state = MatchState.from_dict(
        load_fixture("contracts/history.valid.json")["initial_state"]
    )
    assert protocol.tick_message(state) == fixture
    assert fixture["tick"] == 1


def test_ready_fixture_is_valid(load_fixture) -> None:
    protocol.parse_ready(_line(load_fixture("contracts/ready.valid.json")))


@pytest.mark.parametrize(
    "line",
    [
        "",
        "ready",
        '{"type":"ready"}',
        '{"type":"ready","protocol_version":2}',
        '{"type":"ready","protocol_version":true}',
        '{"type":"commands","tick":1,"moves":[]}',
    ],
)
def test_ready_rejects_malformed_lines(line: str) -> None:
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_ready(line)


def test_commands_fixture_is_valid(load_fixture) -> None:
    commands = protocol.parse_commands(
        _line(load_fixture("contracts/commands.valid.json")), expected_tick=1
    )
    assert commands == PlayerCommands(
        moves=(ShipCommand(ship=0, action=Action.EAST),), build=False
    )


def test_commands_accepts_bytes_crlf_and_unknown_keys() -> None:
    raw = b'{"type":"commands","tick":3,"moves":[],"build":true,"note":"x"}\r\n'
    assert protocol.parse_commands(raw, 3) == PlayerCommands(moves=(), build=True)


def test_invalid_command_fixtures(load_fixture) -> None:
    for case in load_fixture("contracts/commands.invalid.json"):
        expected = (
            protocol.StaleResponseError
            if case["expect"] == "stale"
            else protocol.ProtocolError
        )
        with pytest.raises(expected) as info:
            protocol.parse_commands(case["line"], expected_tick=1)
        if case["expect"] == "malformed":
            assert not isinstance(info.value, protocol.StaleResponseError), case


def test_malformed_move_entries_are_counted_not_fatal() -> None:
    moves = [
        {"ship": 0, "action": "N"},
        {"ship": 1, "action": "UP"},
        {"ship": "2", "action": "N"},
        {"ship": True, "action": "N"},
        {"ship": -1, "action": "N"},
        {"action": "N"},
        "N",
        {"ship": 3, "action": "STAY"},
    ]
    line = json.dumps({"type": "commands", "tick": 1, "moves": moves})
    commands = protocol.parse_commands(line, 1)
    assert commands.moves == (
        ShipCommand(0, Action.NORTH),
        ShipCommand(3, Action.STAY),
    )
    assert commands.malformed_entries == 6


def test_oversized_line_is_malformed() -> None:
    padding = "x" * protocol.MAX_AGENT_LINE_BYTES
    line = json.dumps({"type": "commands", "tick": 1, "moves": [], "pad": padding})
    with pytest.raises(protocol.ProtocolError, match="maximum"):
        protocol.parse_commands(line, 1)
    with pytest.raises(protocol.ProtocolError, match="maximum"):
        protocol.parse_commands(line.encode(), 1)


def test_invalid_utf8_is_malformed() -> None:
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_commands(b"\xff\xfe{}", 1)


@pytest.mark.parametrize(
    "line",
    [
        '{"type":"hello"}',
        '{"type":"init","protocol_version":2}',
        '{"type":"tick","tick":0}',
        '{"type":"end","reason":"whatever"}',
    ],
)
def test_parse_engine_message_rejects_invalid(line: str) -> None:
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_engine_message(line)


def test_end_message_shapes(load_fixture) -> None:
    assert protocol.end_message("excluded") == {"type": "end", "reason": "excluded"}
    with pytest.raises(ValueError):
        protocol.end_message("finished")
    with pytest.raises(ValueError):
        protocol.end_message("nope")


def test_timeout_exclusion_threshold_is_official_three() -> None:
    assert protocol.MAX_CONSECUTIVE_TIMEOUTS == 3
