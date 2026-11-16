"""Match-loop tests with in-process scripted agents (no subprocesses)."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

import neon_armada.engine as engine_package
from neon_armada.contracts import protocol
from neon_armada.contracts.fingerprint import state_fingerprint
from neon_armada.contracts.history import validate_history_document
from neon_armada.contracts.models import (
    Action,
    ContractError,
    Exclusion,
    MatchConfig,
    PlayerCommands,
    ShipCommand,
)
from neon_armada.engine.agents.runtime import TickResponse
from neon_armada.engine.history.writer import record_to_document
from neon_armada.engine.match import run_match
from neon_armada.engine.world.generator import (
    GeneratorParams,
    MapGenerationError,
    generate_map,
)


class ScriptedAgent:
    """In-process ``AgentPort``: decides with a plain function, logs the calls."""

    def __init__(self, decide=None, exclusion: Exclusion | None = None, log=None):
        self.decide = decide or (lambda message: PlayerCommands())
        self.exclusion = exclusion
        self.timeouts = 0
        self.wait_seconds = 0.0
        self.log: list[tuple[str, Any]] = log if log is not None else []
        self.init: dict | None = None
        self.messages: list[dict] = []
        self.end: dict | None = None
        self.aborted = False
        self._pending: dict | None = None

    def start(self, init_message: dict) -> None:
        self.init = init_message
        self.log.append(("start", init_message["player_id"]))

    def finish_start(self) -> list[dict]:
        if self.exclusion is None:
            return []
        return [
            {
                "type": "agent_excluded",
                "player": self.init["player_id"],
                "reason": self.exclusion.reason,
            }
        ]

    def request(self, tick_message: dict) -> None:
        self.messages.append(tick_message)
        self._pending = tick_message
        self.log.append(("request", tick_message["tick"]))

    def collect(self) -> TickResponse:
        self.log.append(("collect", self._pending["tick"]))
        if self.exclusion is not None:
            return TickResponse()
        outcome = self.decide(self._pending)
        if isinstance(outcome, TickResponse):
            return outcome
        return TickResponse(commands=outcome)

    def finish(self, end_message: dict) -> None:
        self.end = end_message

    def abort(self) -> None:
        self.aborted = True


def east_mover(player: int):
    def decide(message: dict) -> PlayerCommands:
        mine = [s for s in message["ships"] if s["owner"] == player]
        return PlayerCommands(
            moves=tuple(ShipCommand(s["id"], Action.EAST) for s in mine)
        )

    return decide


def test_idle_match_runs_exactly_to_the_500_tick_limit() -> None:
    agents = [ScriptedAgent(), ScriptedAgent()]
    record = run_match(MatchConfig(), 5, agents)
    assert record.result.end_reason == "tick_limit"
    assert record.result.ticks_played == 500
    assert len(record.ticks) == 500
    assert [tick.tick for tick in record.ticks] == list(range(1, 501))
    assert record.result.scores == (1000, 1000)
    assert record.result.ships_remaining == (1, 1)
    assert record.result.winner is None and record.result.decided_by == "draw"


def test_initial_state_follows_the_official_start() -> None:
    record = run_match(MatchConfig(max_ticks=1), 5, [ScriptedAgent(), ScriptedAgent()])
    generated = generate_map(5, 32)
    assert record.static_map == generated.static_map
    assert record.initial_state.reserves == (1000, 1000)
    assert [(s.owner, (s.x, s.y)) for s in record.initial_state.ships] == [
        (0, generated.static_map.bases[0]),
        (1, generated.static_map.bases[1]),
    ]
    assert record.initial_state.energy == generated.energy
    assert record.initial_fingerprint == state_fingerprint(record.initial_state)
    assert (record.seed, record.map_seed, record.map_attempt) == (5, 5, 0)


def test_messages_sent_to_agents_conform_to_the_protocol() -> None:
    agents = [ScriptedAgent(east_mover(0)), ScriptedAgent(east_mover(1))]
    record = run_match(MatchConfig(max_ticks=5), 9, agents)
    for player, agent in enumerate(agents):
        init = protocol.parse_engine_message(protocol.encode_message(agent.init))
        assert init["player_id"] == player
        assert init["map"] == record.static_map.to_dict()
        assert [m["tick"] for m in agent.messages] == [1, 2, 3, 4, 5]
        for message in agent.messages:
            protocol.parse_engine_message(protocol.encode_message(message))
            assert "map" not in message and "cells" not in message  # dynamic only
        assert agent.end == {
            "type": "end",
            "reason": "finished",
            "winner": record.result.winner,
            "scores": list(record.result.scores),
        }
    assert agents[0].messages == agents[1].messages  # same state for both


def test_all_observations_are_sent_before_any_command_is_read() -> None:
    log: list[tuple[str, Any]] = []
    agents = [ScriptedAgent(log=log), ScriptedAgent(log=log)]
    run_match(MatchConfig(max_ticks=3), 9, agents)
    assert log[:2] == [("start", 0), ("start", 1)]
    per_tick = log[2:]
    for index in range(3):
        tick = index + 1
        assert per_tick[index * 4 : index * 4 + 4] == [
            ("request", tick),
            ("request", tick),
            ("collect", tick),
            ("collect", tick),
        ]


def test_tick_message_shows_the_state_after_the_previous_tick() -> None:
    agents = [ScriptedAgent(east_mover(0)), ScriptedAgent()]
    record = run_match(MatchConfig(max_ticks=3), 9, agents)
    start_x = record.initial_state.ships[0].x
    xs = [message["ships"][0]["x"] for message in agents[0].messages]
    assert xs == [start_x, start_x + 1, start_x + 2]
    assert [m["move_budgets"][0] for m in agents[0].messages] == [1000, 999, 998]


def test_every_tick_has_the_fingerprint_of_its_state() -> None:
    agents = [ScriptedAgent(east_mover(0)), ScriptedAgent(east_mover(1))]
    record = run_match(MatchConfig(max_ticks=20), 3, agents)
    fingerprints = [tick.fingerprint for tick in record.ticks]
    assert all(len(value) == 64 for value in fingerprints)
    assert fingerprints[-1] == state_fingerprint(record.final_state)
    assert len(set(fingerprints[:3])) == 3  # the state changes while ships move


def test_same_seed_and_decisions_give_identical_records() -> None:
    def play():
        agents = [ScriptedAgent(east_mover(0)), ScriptedAgent(east_mover(1))]
        return run_match(MatchConfig(max_ticks=60, map_size=40), 77, agents)

    first, second = play(), play()
    assert first.ticks == second.ticks
    assert first.result == second.result
    assert record_to_document(first) == record_to_document(second)
    other = run_match(
        MatchConfig(max_ticks=60, map_size=40),
        78,
        [ScriptedAgent(east_mover(0)), ScriptedAgent(east_mover(1))],
    )
    assert other.initial_fingerprint != first.initial_fingerprint


def test_match_ends_early_when_budgets_are_exhausted() -> None:
    agents = [ScriptedAgent(east_mover(0)), ScriptedAgent(east_mover(1))]
    record = run_match(MatchConfig(move_budget=3), 9, agents)
    assert record.result.end_reason == "budgets_exhausted"
    assert record.final_state.move_budgets == (0, 0)
    assert 3 <= record.result.ticks_played < 500


def test_zero_budget_match_plays_one_tick() -> None:
    record = run_match(
        MatchConfig(move_budget=0), 9, [ScriptedAgent(), ScriptedAgent()]
    )
    assert record.result.end_reason == "budgets_exhausted"
    assert record.result.ticks_played == 1


def test_timeouts_malformed_answers_and_exclusion_are_recorded() -> None:
    def faulty(message: dict):
        tick = message["tick"]
        if tick <= 2:
            return TickResponse(
                timed_out=True,
                events=[{"type": "timeout", "player": 1, "consecutive": tick}],
            )
        if tick == 3:
            return TickResponse(malformed=True)
        return PlayerCommands(moves=(ShipCommand(99, Action.NORTH),))

    bad = ScriptedAgent(faulty)
    bad.timeouts = 2
    record = run_match(MatchConfig(max_ticks=5), 9, [ScriptedAgent(), bad])
    kinds = [[event["type"] for event in tick.events] for tick in record.ticks]
    assert kinds == [
        ["timeout"],
        ["timeout"],
        ["malformed_response"],
        ["invalid_command"],
        ["invalid_command"],
    ]
    assert record.result.timeouts == (0, 2)
    assert record.result.invalid_commands == (0, 3)
    assert record.result.winner == 0
    assert record.result.decided_by == "invalid_commands"


def test_agents_excluded_at_init_stay_in_the_record_and_match_continues() -> None:
    gone = ScriptedAgent(exclusion=Exclusion(0, "init_timeout"))
    record = run_match(MatchConfig(max_ticks=4), 9, [gone, ScriptedAgent()])
    assert record.setup_events == (
        {"type": "agent_excluded", "player": 0, "reason": "init_timeout"},
    )
    assert record.result.exclusions == (Exclusion(0, "init_timeout"), None)
    assert record.result.ticks_played == 4


def test_record_serialises_to_a_valid_history_document() -> None:
    agents = [ScriptedAgent(east_mover(0)), ScriptedAgent(east_mover(1))]
    record = run_match(MatchConfig(max_ticks=30), 21, agents, ("east", "west"))
    document = record_to_document(record)
    validate_history_document(document)
    assert document["header"]["seed"] == 21
    assert [a["name"] for a in document["header"]["agents"]] == ["east", "west"]
    assert "timing" not in document


def test_agents_are_aborted_when_the_engine_fails() -> None:
    def explode(message: dict):
        raise RuntimeError("boom")

    agents = [ScriptedAgent(explode), ScriptedAgent()]
    with pytest.raises(RuntimeError, match="boom"):
        run_match(MatchConfig(max_ticks=3), 9, agents)
    assert agents[0].aborted and agents[1].aborted


def test_invalid_inputs_are_rejected_before_agents_start() -> None:
    agents = [ScriptedAgent(), ScriptedAgent()]
    with pytest.raises(ContractError):
        run_match(MatchConfig(), -1, agents)
    with pytest.raises(MapGenerationError):
        impossible = GeneratorParams(
            obstacle_percent=100, deposit_percent=0, max_attempts=2
        )
        run_match(MatchConfig(), 1, agents, generator_params=impossible)
    with pytest.raises(ValueError):
        run_match(MatchConfig(), 1, agents[:1])
    assert agents[0].init is None


def test_engine_package_never_imports_the_gui() -> None:
    root = Path(engine_package.__file__).parent
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(("PySide6", "neon_armada.client")), path
