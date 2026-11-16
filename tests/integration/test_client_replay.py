"""Offscreen tests for the replay controls of the desktop client (L09)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest

from neon_armada.client.main_window import MainWindow
from neon_armada.client.widgets.replay_controls import ReplayControls
from neon_armada.contracts.fingerprint import state_fingerprint
from neon_armada.contracts.models import MatchState


@pytest.fixture
def history_path(load_fixture, tmp_path: Path) -> Path:
    path = tmp_path / "fixture.history.json"
    path.write_text(
        json.dumps(load_fixture("contracts/history.valid.json")), encoding="utf-8"
    )
    return path


@pytest.fixture
def window(qapp, history_path: Path):
    window = MainWindow()
    assert window.open_history(history_path)
    yield window
    window.close()


def click(button) -> None:
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)


def test_controls_are_disabled_until_a_match_is_loaded(qapp) -> None:
    window = MainWindow()
    controls = window.controls
    assert not controls.play_button.isEnabled()
    assert not controls.step_button.isEnabled()
    assert not controls.timeline.isEnabled()
    assert controls.position_label.text() == "- / -"
    window.toggle_playback()  # ignored without a match
    window.step_forward()
    assert not window.replay.playing and not window._timer.isActive()
    window.close()


def test_loaded_match_starts_paused_on_the_first_tick(window: MainWindow) -> None:
    controls = window.controls
    assert controls.play_button.isEnabled() and controls.play_button.text() == "Play"
    assert controls.timeline.minimum() == 0 and controls.timeline.maximum() == 2
    assert controls.timeline.value() == 0
    assert controls.position_label.text() == "0 / 2"
    assert controls.speed_buttons[1].isChecked()
    assert not window._timer.isActive()


def test_play_and_pause_buttons_drive_the_timer(window: MainWindow) -> None:
    click(window.controls.play_button)
    assert window.replay.playing and window._timer.isActive()
    assert window.controls.play_button.text() == "Pause"
    click(window.controls.play_button)
    assert not window.replay.playing and not window._timer.isActive()
    assert window.controls.play_button.text() == "Play"


def test_step_button_shows_the_next_tick_and_pauses(window: MainWindow) -> None:
    click(window.controls.play_button)
    click(window.controls.step_button)
    assert window.current_tick == 1 and not window.replay.playing
    assert window.map_view.frame.tick == 1
    assert window.info_panel.tick_label.text() == "Tick 1 / 2"
    assert window.controls.timeline.value() == 1
    click(window.controls.step_button)
    assert window.current_tick == 2
    assert not window.controls.step_button.isEnabled()  # last tick reached
    assert "Winner: beta" in window.info_panel.result_label.text()


def test_speed_buttons_select_x2_and_x4(window: MainWindow) -> None:
    click(window.controls.speed_buttons[2])
    assert window.replay.speed == 2
    click(window.controls.speed_buttons[4])
    assert window.replay.speed == 4
    checked = [s for s, b in window.controls.speed_buttons.items() if b.isChecked()]
    assert checked == [4]
    # x4 covers four times the distance of x1 in the same time.
    window.toggle_playback()
    window.advance_playback(0.05)
    fast = window.replay.position
    window.show_tick(0)
    click(window.controls.speed_buttons[1])
    window.advance_playback(0.05)
    assert fast == pytest.approx(4 * window.replay.position)


def test_timeline_seeks_to_any_tick_from_recorded_states(
    window: MainWindow, load_fixture
) -> None:
    for tick in (2, 0, 1):
        window.controls.timeline.setValue(tick)  # what dragging the handle does
        assert window.current_tick == tick
        assert window.map_view.frame.tick == tick
        assert window.info_panel.tick_label.text() == f"Tick {tick} / 2"
        assert window.controls.position_label.text() == f"{tick} / 2"
    # The frame shown after seeking is the recorded state of that tick.
    document = load_fixture("contracts/history.valid.json")
    state = window.presentation._states[1]
    assert isinstance(state, MatchState)
    assert state_fingerprint(state) == document["ticks"][0]["fingerprint"]
    ships = {(ship.id, ship.x, ship.y, ship.cargo) for ship in state.ships}
    assert ships == {(s.id, s.x, s.y, s.cargo) for s in window.map_view.frame.ships}


def test_seek_while_paused_stays_paused_and_while_playing_keeps_playing(
    window: MainWindow,
) -> None:
    window.controls.timeline.setValue(1)
    assert not window.replay.playing and not window._timer.isActive()
    window.show_tick(0)
    click(window.controls.play_button)
    window.controls.timeline.setValue(1)
    assert window.replay.playing and window._timer.isActive()
    window.controls.timeline.setValue(2)  # the end: playback stops
    assert not window.replay.playing and not window._timer.isActive()
    assert window.controls.play_button.text() == "Play"


def test_playback_interpolates_between_ticks(window: MainWindow) -> None:
    window.toggle_playback()
    window.advance_playback(0.1)  # 5 ticks/s: halfway to tick 1
    assert window.current_tick == 0
    assert window.map_view._next is not None and window.map_view._next.tick == 1
    assert window.map_view._progress == pytest.approx(0.5)
    assert window.controls.timeline.value() == 0
    window.advance_playback(0.1)
    assert window.current_tick == 1 and window.map_view._next is None


def test_playback_reaches_the_end_and_can_be_restarted(window: MainWindow) -> None:
    window.toggle_playback()
    window.advance_playback(30.0)
    assert window.current_tick == 2 and not window.replay.playing
    assert not window._timer.isActive()
    assert window.controls.timeline.value() == 2
    click(window.controls.play_button)  # Play at the end starts over
    assert window.replay.playing and window.current_tick == 0


def test_real_time_playback_does_not_block_the_event_loop(window: MainWindow) -> None:
    window.show()
    beats = []
    heartbeat = QTimer()
    heartbeat.setInterval(5)
    heartbeat.timeout.connect(lambda: beats.append(1))
    heartbeat.start()
    painted = window.map_view.frames_painted
    click(window.controls.speed_buttons[2])
    click(window.controls.play_button)
    QTest.qWait(150)
    assert window.replay.playing  # still running: 2 ticks at x2 take 200 ms
    assert 0.0 < window.replay.position < 2.0
    QTest.qWait(350)
    heartbeat.stop()
    assert not window.replay.playing and window.current_tick == 2
    assert len(beats) >= 20  # other timers kept firing during playback
    assert window.map_view.frames_painted - painted >= 5


def test_keyboard_shortcuts_exist_for_play_and_step(window: MainWindow) -> None:
    actions = {a.text(): a for a in window.playback_menu.actions()}
    actions["&Play / Pause"].trigger()
    assert window.replay.playing
    actions["&Next tick"].trigger()
    assert not window.replay.playing and window.current_tick == 1
    assert actions["&Play / Pause"].shortcut().toString() == "Space"


def test_corrupt_file_shows_an_error_and_keeps_the_running_replay(
    window: MainWindow, tmp_path: Path
) -> None:
    window.show_tick(1)
    window.toggle_playback()
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text('{"format": "neon-armada-history", "tic', encoding="utf-8")
    assert window.open_history(corrupt) is False
    assert not window.error_banner.isHidden()
    assert "corrupt.json" in window.error_banner.text()
    assert window.replay.playing and window.current_tick == 1
    assert window.controls.timeline.maximum() == 2


def test_opening_another_match_resets_playback(
    window: MainWindow, history_path: Path
) -> None:
    click(window.controls.speed_buttons[4])
    window.show_tick(2)
    assert window.open_history(history_path) is True
    assert window.current_tick == 0 and not window.replay.playing
    assert window.info_panel.tick_label.text() == "Tick 0 / 2"
    assert window.replay.speed == 4  # the chosen speed is kept


def shortened_history(load_fixture, tmp_path: Path, ticks: int) -> Path:
    document = load_fixture("contracts/history.valid.json")
    document["ticks"] = document["ticks"][:ticks]
    document["result"]["ticks_played"] = ticks
    path = tmp_path / f"short{ticks}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_history_without_ticks_is_shown_but_cannot_be_played(
    qapp, load_fixture, tmp_path: Path
) -> None:
    window = MainWindow()
    assert window.open_history(shortened_history(load_fixture, tmp_path, 0))
    assert window.map_view.frame.tick == 0
    assert window.info_panel.tick_label.text() == "Tick 0 / 0"
    assert not window.controls.play_button.isEnabled()
    assert not window.controls.step_button.isEnabled()
    assert not window.controls.timeline.isEnabled()
    window.toggle_playback()
    window.step_forward()
    window.show_tick(5)
    assert window.current_tick == 0 and not window._timer.isActive()
    window.close()


def test_one_tick_history_plays_to_its_end(qapp, load_fixture, tmp_path: Path) -> None:
    window = MainWindow()
    assert window.open_history(shortened_history(load_fixture, tmp_path, 1))
    assert window.controls.timeline.maximum() == 1
    window.toggle_playback()
    window.advance_playback(10.0)
    assert window.current_tick == 1 and not window.replay.playing
    assert not window.controls.step_button.isEnabled()
    window.close()


def test_controls_widget_emits_signals_only_for_user_actions(qapp) -> None:
    controls = ReplayControls()
    seen: list[tuple[str, int]] = []
    controls.play_toggled.connect(lambda: seen.append(("play", 0)))
    controls.step_requested.connect(lambda: seen.append(("step", 0)))
    controls.speed_selected.connect(lambda speed: seen.append(("speed", speed)))
    controls.seek_requested.connect(lambda tick: seen.append(("seek", tick)))
    controls.set_state(3, 10, playing=True, speed=2, loaded=True)
    assert seen == []  # programmatic updates are silent
    assert controls.timeline.value() == 3 and controls.speed_buttons[2].isChecked()
    click(controls.play_button)
    click(controls.step_button)
    click(controls.speed_buttons[4])
    controls.timeline.setValue(7)
    assert seen == [("play", 0), ("step", 0), ("speed", 4), ("seek", 7)]
