"""Process-level protocol smoke tests for every shipped agent (L04).

The agents are started as real processes and exercised through stdin/stdout
with contract fixtures. Full engine matches are covered from L06 on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_harness import (
    REFERENCE_AGENT,
    STARTER_AGENT,
    TEAM_AGENT,
    AgentSession,
    cpp_agent_path,
    play_local_match,
)
from neon_armada.contracts import protocol
from neon_armada.contracts.fingerprint import state_fingerprint
from neon_armada.contracts.models import MatchConfig


def _cpp_agent() -> Path:
    path = cpp_agent_path()
    if path is None:
        pytest.skip(
            "C++ agent not built (cmake -S agents/cpp -B build/cpp && "
            "cmake --build build/cpp)"
        )
    return path


AGENTS = {
    "python-starter": lambda: STARTER_AGENT,
    "python-reference": lambda: REFERENCE_AGENT,
    "python-team": lambda: TEAM_AGENT,
    "cpp-starter": _cpp_agent,
}


@pytest.fixture(params=sorted(AGENTS))
def agent(request) -> Path:
    return AGENTS[request.param]()


def test_handshake_tick_and_end(agent: Path, load_fixture) -> None:
    session = AgentSession(agent)
    session.send(load_fixture("contracts/init.valid.json"))
    protocol.parse_ready(session.read_line())

    session.send(load_fixture("contracts/tick.valid.json"))
    commands = protocol.parse_commands(session.read_line(), expected_tick=1)
    assert commands.malformed_entries == 0
    assert {move.ship for move in commands.moves} <= {0}  # only the own ship

    session.send(load_fixture("contracts/end.valid.json"))
    code, rest, _stderr = session.close()
    assert code == 0
    assert rest == b""  # stdout carried protocol lines only


def test_agent_answers_several_ticks_in_order(agent: Path, load_fixture) -> None:
    session = AgentSession(agent)
    session.send(load_fixture("contracts/init.valid.json"))
    protocol.parse_ready(session.read_line())
    tick = load_fixture("contracts/tick.valid.json")
    for number in (1, 2, 3):
        session.send(dict(tick, tick=number))
        protocol.parse_commands(session.read_line(), expected_tick=number)
    code, rest, _ = session.close()  # end of input without "end" is fine too
    assert code == 0 and rest == b""


def test_agent_rejects_garbage_on_stderr_not_stdout(agent: Path) -> None:
    session = AgentSession(agent)
    session.send_raw(b"this is not json\n")
    code, rest, stderr = session.close()
    assert code != 0
    assert rest == b""
    assert stderr.strip()


def test_agent_rejects_unsupported_protocol_version(agent: Path, load_fixture) -> None:
    init = load_fixture("contracts/init.valid.json")
    init["protocol_version"] = 99
    session = AgentSession(agent)
    session.send(init)
    code, rest, stderr = session.close()
    assert code != 0 and rest == b"" and stderr.strip()


CONFIG = MatchConfig(max_ticks=150)


def _assert_legal_and_productive(state, events) -> None:
    invalid = [e for tick in events for e in tick if e["type"] == "invalid_command"]
    assert invalid == []
    assert state.invalid_commands == (0, 0)
    assert state.tick == CONFIG.max_ticks


def test_reference_agent_plays_legally_and_collects_energy() -> None:
    state, events = play_local_match(REFERENCE_AGENT, REFERENCE_AGENT, 11, CONFIG)
    _assert_legal_and_productive(state, events)
    assert state.reserves[0] > 1000 and state.reserves[1] > 1000


def test_team_agent_plays_legally_builds_and_collects_energy() -> None:
    state, events = play_local_match(TEAM_AGENT, REFERENCE_AGENT, 11, CONFIG)
    _assert_legal_and_productive(state, events)
    kinds = [e["type"] for tick in events for e in tick]
    assert "build_started" in kinds and "ship_spawned" in kinds
    assert "delivered" in kinds
    team_ships = [ship for ship in state.ships if ship.owner == 0]
    assert len(team_ships) >= 2


def test_team_agent_is_a_distinct_strategy() -> None:
    """Different decisions from the reference agent on the same match."""
    as_team, _ = play_local_match(TEAM_AGENT, REFERENCE_AGENT, 11, CONFIG)
    as_reference, _ = play_local_match(REFERENCE_AGENT, REFERENCE_AGENT, 11, CONFIG)
    assert state_fingerprint(as_team) != state_fingerprint(as_reference)


def test_agents_are_deterministic() -> None:
    first, _ = play_local_match(TEAM_AGENT, REFERENCE_AGENT, 5, CONFIG)
    second, _ = play_local_match(TEAM_AGENT, REFERENCE_AGENT, 5, CONFIG)
    assert state_fingerprint(first) == state_fingerprint(second)


def test_cpp_agent_plays_legally_against_python_reference() -> None:
    state, events = play_local_match(_cpp_agent(), REFERENCE_AGENT, 11, CONFIG)
    _assert_legal_and_productive(state, events)
    assert state.reserves[0] > 1000
