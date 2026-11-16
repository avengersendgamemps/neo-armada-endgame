"""Launching matches from the desktop client (L10).

Covers the dialog, the main-window workflow with a fake engine, a real
end-to-end match, and the decoupling requirement: force-closing the client
while the engine is running must not stop the engine.
"""

from __future__ import annotations

import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from agent_harness import DUMMY_AGENTS, REFERENCE_AGENT, TEAM_AGENT
from neon_armada.client.launcher import MatchRequest
from neon_armada.client.main_window import MainWindow
from neon_armada.client.widgets.launch_dialog import LaunchDialog
from neon_armada.contracts.replay import first_invalid_tick, load_history

FAKE_ENGINE = DUMMY_AGENTS / "fake_engine.py"
VALID_HISTORY = DUMMY_AGENTS.parent / "contracts" / "history.valid.json"

SLOW_AGENT = '''"""Agent that answers every tick after a short pause (test only)."""
import json
import sys
import time

for raw in sys.stdin:
    message = json.loads(raw)
    if message["type"] == "init":
        reply = {"type": "ready", "protocol_version": 1}
    elif message["type"] == "end":
        break
    else:
        time.sleep(0.01)
        reply = {"type": "commands", "tick": message["tick"], "moves": [],
                 "build": False}
    sys.stdout.write(json.dumps(reply) + "\\n")
    sys.stdout.flush()
'''


def process_alive(pid: int) -> bool:
    """Whether a process exists, without sending it anything."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    synchronize, wait_timeout = 0x00100000, 0x00000102
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(synchronize, False, pid)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == wait_timeout
    finally:
        kernel32.CloseHandle(handle)


def wait_until(condition, timeout: float, step_ms: int = 20) -> bool:
    """Run the Qt event loop until ``condition()`` holds or time runs out."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        QTest.qWait(step_ms)
    return bool(condition())


def fake_builder(mode: str, delay: float = 0.0):
    def build(request: MatchRequest) -> list[str]:
        return [
            sys.executable,
            str(FAKE_ENGINE),
            mode,
            str(request.output),
            str(delay),
            str(VALID_HISTORY),
        ]

    return build


@pytest.fixture
def request_for(tmp_path: Path):
    def make(name: str = "match.history.json", seed: int = 7) -> MatchRequest:
        return MatchRequest(TEAM_AGENT, REFERENCE_AGENT, seed, tmp_path / name)

    return make


@pytest.fixture
def window(qapp):
    window = MainWindow()
    yield window
    window.cancel_match()
    window.close()


# -- dialog -----------------------------------------------------------------


def test_dialog_refuses_incomplete_input_and_says_why(qapp, tmp_path: Path) -> None:
    dialog = LaunchDialog()
    dialog.accept()  # nothing chosen yet
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.request is None
    assert not dialog.error_label.isHidden()
    assert "Agent A" in dialog.error_label.text()
    assert "Agent B" in dialog.error_label.text()

    dialog.agent_a_edit.setText(str(TEAM_AGENT))
    dialog.agent_b_edit.setText(str(tmp_path / "missing.py"))
    dialog.accept()
    assert "Agent A" not in dialog.error_label.text()
    assert "file not found" in dialog.error_label.text()

    dialog.agent_b_edit.setText(str(REFERENCE_AGENT))
    for bad_seed in ("", "abc", "-4", "1.5", str(2**64)):
        dialog.seed_edit.setText(bad_seed)
        dialog.accept()
        assert dialog.request is None
        assert "Seed" in dialog.error_label.text()


def test_dialog_returns_the_chosen_agents_seed_and_map_size(qapp, tmp_path) -> None:
    dialog = LaunchDialog()
    dialog.agent_a_edit.setText(str(TEAM_AGENT))
    dialog.agent_b_edit.setText(str(REFERENCE_AGENT))
    dialog.seed_edit.setText("18446744073709551615")
    dialog.map_size_box.setValue(64)
    dialog.output_edit.setText(str(tmp_path / "chosen.json"))
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.request == MatchRequest(
        TEAM_AGENT, REFERENCE_AGENT, 2**64 - 1, tmp_path / "chosen.json", 64
    )
    assert (dialog.map_size_box.minimum(), dialog.map_size_box.maximum()) == (32, 64)


def test_dialog_proposes_a_history_path_when_none_is_given(
    qapp, tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    dialog = LaunchDialog()
    dialog.agent_a_edit.setText(str(TEAM_AGENT))
    dialog.agent_b_edit.setText(str(REFERENCE_AGENT))
    dialog.seed_edit.setText("12")
    request, problems = dialog.build_request()
    assert problems == []
    assert request.output == tmp_path / "histories" / "match-seed12.history.json"


# -- main window with a fake engine -------------------------------------------


def test_launch_keeps_the_ui_responsive_and_opens_the_history(
    window: MainWindow, request_for
) -> None:
    window.command_builder = fake_builder("ok", delay=0.6)
    beats = []
    heartbeat = QTimer()
    heartbeat.setInterval(5)
    heartbeat.timeout.connect(lambda: beats.append(1))
    heartbeat.start()

    started = time.monotonic()
    assert window.launch_match(request_for()) is True
    assert time.monotonic() - started < 0.5  # returns at once
    assert window.match_running and window.presentation is None
    assert not window.new_match_action.isEnabled()
    assert window.cancel_match_action.isEnabled()
    assert "running" in window.statusBar().currentMessage().lower()

    assert wait_until(lambda: not window.match_running, timeout=30)
    heartbeat.stop()
    assert len(beats) >= 20  # the event loop kept running during the match
    assert window.presentation is not None  # history opened automatically
    assert "alpha vs beta" in window.windowTitle()
    assert window.info_panel.tick_label.text() == "Tick 0 / 2"
    assert window.controls.play_button.isEnabled()
    assert window.new_match_action.isEnabled()
    assert not window.cancel_match_action.isEnabled()
    assert window.error_banner.isHidden()


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("not_found", "agent not found: nowhere.py"),
        ("crash", "simulated engine crash"),
        ("no_history", "is missing"),
    ],
)
def test_engine_failures_are_shown_and_the_window_stays_usable(
    window: MainWindow, request_for, mode: str, expected: str
) -> None:
    window.command_builder = fake_builder(mode)
    assert window.launch_match(request_for()) is True
    assert wait_until(lambda: not window.match_running, timeout=30)
    assert not window.error_banner.isHidden()
    assert "Match failed" in window.error_banner.text()
    assert expected in window.error_banner.text()
    assert window.presentation is None
    assert window.new_match_action.isEnabled()
    # A following match works and clears the error.
    window.command_builder = fake_builder("ok")
    assert window.launch_match(request_for("second.history.json")) is True
    assert wait_until(lambda: not window.match_running, timeout=30)
    assert window.presentation is not None and window.error_banner.isHidden()


def test_invalid_requests_and_missing_engine_do_not_start_anything(
    window: MainWindow, request_for, tmp_path: Path
) -> None:
    bad = MatchRequest(tmp_path / "nope.py", REFERENCE_AGENT, 1, tmp_path / "h.json")
    assert window.launch_match(bad) is False
    assert "file not found" in window.error_banner.text()
    assert not window.match_running

    window.command_builder = lambda request: [str(tmp_path / "no-python.exe"), "-m"]
    assert window.launch_match(request_for()) is False
    assert "cannot start the engine" in window.error_banner.text()
    assert not window.match_running and window.new_match_action.isEnabled()


def test_only_one_match_at_a_time_and_cancel_ends_it(
    window: MainWindow, request_for
) -> None:
    window.command_builder = fake_builder("hang")
    assert window.launch_match(request_for()) is True
    assert window.launch_match(request_for("other.history.json")) is False
    assert "already running" in window.error_banner.text()
    window.cancel_match_action.trigger()
    assert wait_until(lambda: not window.match_running, timeout=30)
    assert "Match failed" in window.error_banner.text()
    assert window.new_match_action.isEnabled()


def test_running_match_does_not_disturb_the_replay_on_screen(
    window: MainWindow, request_for
) -> None:
    assert window.open_history(VALID_HISTORY)
    window.show_tick(1)
    window.command_builder = fake_builder("crash", delay=0.3)
    assert window.launch_match(request_for()) is True
    window.step_forward()
    assert window.current_tick == 2
    assert wait_until(lambda: not window.match_running, timeout=30)
    assert window.current_tick == 2 and window.presentation is not None


# -- real engine ----------------------------------------------------------------


def test_real_match_is_run_by_a_separate_process_and_opened(
    window: MainWindow, request_for
) -> None:
    request = request_for("real.history.json", seed=11)
    assert window.launch_match(request) is True
    engine_pid = window.engine_run.pid
    assert engine_pid not in (None, os.getpid())
    assert wait_until(lambda: not window.match_running, timeout=120)
    assert window.error_banner.isHidden(), window.error_banner.text()
    assert window.presentation.history.seed == 11
    assert window.presentation.history.agent_names == ("team_agent", "reference_agent")
    assert window.presentation.last_tick == 500
    assert first_invalid_tick(load_history(request.output)) is None
    # The only link was the command line and files.
    record = json.loads(
        (request.output.parent / "real.history.json.launch.json").read_text("utf-8")
    )
    assert record["command"][1:4] == ["-m", "neon_armada.engine", "run"]
    assert record["engine_pid"] == engine_pid


def test_engine_survives_force_closing_the_client(tmp_path: Path) -> None:
    """Kill the GUI process in the middle of a match: the engine must finish."""
    agent = tmp_path / "slow_agent.py"
    agent.write_text(SLOW_AGENT, encoding="utf-8")
    output = tmp_path / "survivor.history.json"
    record_path = tmp_path / "survivor.history.json.launch.json"
    gui = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "neon_armada.client",
            "--agent-a",
            str(agent),
            "--agent-b",
            str(agent),
            "--seed",
            "3",
            "--output",
            str(output),
        ],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        record = None
        deadline = time.monotonic() + 60
        while record is None and time.monotonic() < deadline:
            assert gui.poll() is None, "the client exited before launching"
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                time.sleep(0.05)
        assert record is not None, "the client never started the engine"
        client_pid, engine_pid = record["client_pid"], record["engine_pid"]
        time.sleep(1.0)  # let the match get going

        # Mid-match: both processes run and there is no history yet.
        assert process_alive(client_pid) and process_alive(engine_pid)
        assert not output.exists()

        # Force-close the client (the real interpreter and, in a virtual
        # environment on Windows, its launcher stub).
        os.kill(client_pid, signal.SIGTERM if os.name == "nt" else signal.SIGKILL)
        gui.kill()
        gui.wait(timeout=30)
        deadline = time.monotonic() + 30
        while process_alive(client_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not process_alive(client_pid)

        # The engine is still working after the client is gone...
        assert process_alive(engine_pid)
        assert not output.exists()

        # ...and finishes the match on its own.
        deadline = time.monotonic() + 120
        while process_alive(engine_pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not process_alive(engine_pid), "the engine did not finish"
    finally:
        if gui.poll() is None:
            gui.kill()

    history = load_history(output)
    assert history.result.ticks_played == 500
    assert first_invalid_tick(history) is None
    reported = json.loads(
        (tmp_path / "survivor.history.json.engine-stdout.json").read_text("utf-8")
    )
    assert reported["status"] == "ok"
