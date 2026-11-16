"""Unit tests for the Qt-free replay controller (L09)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import neon_armada.client.replay as replay_module
from neon_armada.client.replay import BASE_TICKS_PER_SECOND, SPEEDS, ReplayController


def controller(last_tick: int = 10) -> ReplayController:
    return ReplayController(last_tick, ticks_per_second=10.0)


def test_starts_paused_at_the_first_tick() -> None:
    replay = controller()
    assert (replay.tick, replay.progress, replay.position) == (0, 0.0, 0.0)
    assert not replay.playing and not replay.at_end
    assert replay.speed == 1 and replay.last_tick == 10
    assert SPEEDS == (1, 2, 4) and BASE_TICKS_PER_SECOND > 0


def test_paused_controller_ignores_time() -> None:
    replay = controller()
    assert replay.advance(5.0) is False
    assert replay.position == 0.0


def test_play_advances_with_elapsed_time_and_interpolates() -> None:
    replay = controller()
    replay.play()
    assert replay.advance(0.25) is True  # 10 ticks/s -> 2.5 ticks
    assert replay.tick == 2
    assert replay.progress == pytest.approx(0.5)
    assert replay.playing


def test_pause_freezes_the_position_and_play_resumes_from_it() -> None:
    replay = controller()
    replay.play()
    replay.advance(0.25)
    replay.pause()
    assert replay.advance(1.0) is False
    assert replay.position == pytest.approx(2.5)
    replay.toggle()
    replay.advance(0.1)
    assert replay.position == pytest.approx(3.5)
    replay.toggle()
    assert not replay.playing


@pytest.mark.parametrize(("speed", "expected"), [(1, 1.0), (2, 2.0), (4, 4.0)])
def test_speed_multiplies_the_playback_rate(speed: int, expected: float) -> None:
    replay = controller()
    replay.set_speed(speed)
    replay.play()
    replay.advance(0.1)
    assert replay.position == pytest.approx(expected)


def test_speed_can_change_during_playback_and_rejects_other_values() -> None:
    replay = controller()
    replay.play()
    replay.advance(0.1)  # 1 tick at x1
    replay.set_speed(4)
    replay.advance(0.1)  # 4 ticks at x4
    assert replay.position == pytest.approx(5.0)
    assert replay.playing
    for bad in (0, 3, 8, -1):
        with pytest.raises(ValueError):
            replay.set_speed(bad)
    assert replay.speed == 4


def test_playback_stops_exactly_on_the_last_tick() -> None:
    replay = controller()
    replay.play()
    assert replay.advance(60.0) is True
    assert (replay.tick, replay.progress) == (10, 0.0)
    assert replay.at_end and not replay.playing
    assert replay.advance(1.0) is False


def test_play_at_the_end_restarts_from_the_beginning() -> None:
    replay = controller()
    replay.seek(10)
    replay.play()
    assert replay.playing and replay.position == 0.0


def test_step_pauses_and_goes_to_the_next_whole_tick() -> None:
    replay = controller()
    replay.step()
    assert replay.position == 1.0
    replay.play()
    replay.advance(0.25)  # position 3.5
    replay.step()
    assert replay.position == 4.0 and not replay.playing
    replay.seek(10)
    replay.step()  # already on the last tick
    assert replay.position == 10.0


def test_seek_clamps_to_the_match() -> None:
    replay = controller()
    replay.seek(7)
    assert (replay.tick, replay.progress) == (7, 0.0)
    replay.seek(-5)
    assert replay.tick == 0
    replay.seek(999)
    assert replay.tick == 10 and replay.at_end


def test_seek_keeps_the_play_state_except_at_the_end() -> None:
    replay = controller()
    replay.seek(4)
    assert not replay.playing  # paused stays paused
    replay.play()
    replay.advance(0.05)
    replay.seek(2)
    assert replay.playing and replay.position == 2.0  # playing continues
    replay.seek(10)
    assert not replay.playing  # nothing left to play


def test_empty_and_one_tick_matches() -> None:
    empty = controller(0)
    empty.play()
    assert not empty.playing and empty.at_end
    empty.step()
    empty.seek(3)
    assert empty.position == 0.0
    assert empty.advance(1.0) is False

    short = controller(1)
    short.play()
    short.advance(0.05)
    assert short.tick == 0 and short.progress == pytest.approx(0.5)
    short.advance(0.05)
    assert short.tick == 1 and not short.playing


def test_load_resets_position_and_keeps_the_speed() -> None:
    replay = controller()
    replay.set_speed(2)
    replay.play()
    replay.advance(0.3)
    replay.load(4)
    assert replay.position == 0.0 and not replay.playing
    assert replay.last_tick == 4 and replay.speed == 2


def test_invalid_arguments_are_rejected_or_ignored() -> None:
    with pytest.raises(ValueError):
        ReplayController(-1)
    with pytest.raises(ValueError):
        ReplayController(5, ticks_per_second=0)
    replay = controller()
    replay.play()
    for elapsed in (0.0, -1.0, float("nan"), float("inf")):
        assert replay.advance(elapsed) is False
    assert replay.position == 0.0 and replay.playing


def test_controller_module_is_independent_of_qt_and_of_the_engine() -> None:
    tree = ast.parse(Path(replay_module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported <= {"__future__", "math"}
