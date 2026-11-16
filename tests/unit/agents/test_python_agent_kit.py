"""Unit tests for the Python agent starter kit (imported as a plain module)."""

from __future__ import annotations

import io
import json
import sys

import pytest

from agent_harness import PYTHON_AGENTS

sys.path.insert(0, str(PYTHON_AGENTS))
import neon_agent_kit as kit  # noqa: E402


@pytest.fixture
def init(load_fixture) -> dict:
    return load_fixture("contracts/init.valid.json")


@pytest.fixture
def tick(load_fixture) -> dict:
    return load_fixture("contracts/tick.valid.json")


def _run(decide, *messages: dict | bytes) -> tuple[int, list[dict]]:
    data = b"".join(
        m if isinstance(m, bytes) else json.dumps(m).encode() + b"\n" for m in messages
    )
    out = io.BytesIO()
    code = kit.run(decide, io.BytesIO(data), out)
    return code, [json.loads(line) for line in out.getvalue().splitlines()]


def test_kit_does_not_import_the_engine_package() -> None:
    source = (PYTHON_AGENTS / "neon_agent_kit.py").read_text(encoding="utf-8")
    assert "neon_armada" not in source.replace("Neon Armada", "")


def test_game_parses_init_and_knows_bases(init) -> None:
    game = kit.Game(init)
    assert game.player_id == 0
    assert game.size == 32
    assert game.my_base == (3, 4)
    assert game.enemy_base == (28, 27)
    assert game.max_ticks == init["config"]["max_ticks"]
    assert game.passable(0, 0)
    assert not game.passable(5, 5)  # obstacle
    assert not game.passable(28, 27)  # enemy base
    assert game.passable(3, 4)  # own base
    assert not game.passable(-1, 0) and not game.passable(32, 0)


def test_distances_are_shortest_paths_around_obstacles(init) -> None:
    game = kit.Game(init)
    assert game.distance((0, 0), (0, 0)) == 0
    assert game.distance((0, 0), (31, 31)) == 62
    assert game.distance((4, 5), (6, 5)) == 4  # obstacle at (5, 5) in between
    assert game.distance((5, 5), (0, 0)) == -1  # from inside an obstacle
    assert game.distances_from((3, 4)) is game.distances_from((3, 4))  # cached


def test_step_towards_moves_closer_and_respects_avoid(init) -> None:
    game = kit.Game(init)
    assert game.step_towards((10, 10), (10, 10)) == kit.STAY
    assert game.step_towards((10, 10), (10, 5)) == kit.NORTH
    assert game.step_towards((10, 10), (15, 10)) == kit.EAST
    assert game.step_towards((10, 10), (15, 10), avoid={(11, 10)}) == kit.STAY
    assert game.step_towards((10, 10), (15, 12), avoid={(11, 10)}) == kit.SOUTH
    # Walking a full path always arrives.
    position, steps = (0, 0), 0
    while position != (20, 9):
        position = kit.apply_action(position, game.step_towards(position, (20, 9)))
        steps += 1
    assert steps == 29


def test_tick_state_views(tick) -> None:
    state = kit.TickState(tick, player_id=1)
    assert state.tick == 1
    assert [ship.id for ship in state.my_ships] == [1]
    assert [ship.id for ship in state.enemy_ships] == [0]
    assert state.my_reserve == 1000 and state.my_budget == 1000
    assert state.my_pending_build is False
    assert state.energy[(10, 2)] == 350


def test_mining_yield_matches_official_rule() -> None:
    assert kit.mining_yield(350) == 35
    assert kit.mining_yield(351) == 36
    assert kit.mining_yield(1) == 1
    assert kit.mining_yield(0) == 0
    assert kit.mining_yield(500, cargo=95) == 5


def test_commands_message_shape() -> None:
    commands = kit.Commands()
    commands.move(4, kit.EAST)
    commands.move(2, kit.STAY)
    commands.request_build()
    assert commands.to_message(7) == {
        "type": "commands",
        "tick": 7,
        "moves": [{"ship": 2, "action": "STAY"}, {"ship": 4, "action": "E"}],
        "build": True,
    }
    with pytest.raises(ValueError):
        commands.move(1, "UP")


def test_run_loop_answers_init_and_ticks_then_stops_on_end(init, tick) -> None:
    seen = []

    def decide(game, state):
        seen.append(state.tick)
        commands = kit.Commands()
        commands.move(state.my_ships[0].id, kit.EAST)
        return commands

    second = dict(tick, tick=2)
    code, lines = _run(decide, init, tick, second, {"type": "end", "reason": "error"})
    assert code == 0
    assert seen == [1, 2]
    assert lines[0] == {"type": "ready", "protocol_version": 1}
    assert lines[1] == {
        "type": "commands",
        "tick": 1,
        "moves": [{"ship": 0, "action": "E"}],
        "build": False,
    }
    assert lines[2]["tick"] == 2
    assert len(lines) == 3


def test_run_loop_survives_a_strategy_exception(init, tick, capsys) -> None:
    def decide(game, state):
        raise RuntimeError("strategy bug")

    code, lines = _run(decide, init, tick)
    assert code == 0  # end of input
    assert lines[1] == {"type": "commands", "tick": 1, "moves": [], "build": False}
    assert "strategy bug" in capsys.readouterr().err


@pytest.mark.parametrize(
    "messages",
    [
        [b"not json\n"],
        [b"[1, 2]\n"],
        [{"type": "tick", "tick": 1}],  # tick before init
        [{"type": "init", "protocol_version": 99}],
        [{"type": "surprise"}],
    ],
)
def test_run_loop_rejects_bad_engine_messages(messages, capsys) -> None:
    code, lines = _run(lambda game, state: None, *messages)
    assert code == 1
    assert lines == []  # nothing on stdout
    assert capsys.readouterr().err  # diagnostics on stderr
