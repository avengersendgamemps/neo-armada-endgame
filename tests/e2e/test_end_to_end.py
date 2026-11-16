"""Cross-system end-to-end tests (L11).

Each test crosses at least two component boundaries of the official
architecture: agents <-> engine (standard streams), engine -> history file,
history file -> client. The engine is always a separate process started
through its command line; the client side only reads the files it produced.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_harness import DUMMY_AGENTS, REFERENCE_AGENT, TEAM_AGENT, cpp_agent_path
from neon_armada.client.main_window import MainWindow
from neon_armada.client.presentation import MatchPresentation
from neon_armada.contracts.cli import ENGINE_MODULE, ExitCode
from neon_armada.contracts.fingerprint import state_fingerprint
from neon_armada.contracts.replay import load_history

SCRIPTED = DUMMY_AGENTS / "scripted_agent.py"
MATCHES = [(32, 5), (48, 6), (64, 7)]  # (map size, seed)


def engine(*arguments: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [sys.executable, "-m", ENGINE_MODULE, *arguments],
        capture_output=True,
        text=True,
        timeout=300,
    )
    lines = completed.stdout.splitlines()
    assert len(lines) == 1, completed.stdout + completed.stderr
    return completed.returncode, json.loads(lines[0])


def run_match(agent_a: Path, agent_b: Path, seed: int, output: Path, *extra: str):
    code, payload = engine(
        "run",
        "--agent-a",
        str(agent_a),
        "--agent-b",
        str(agent_b),
        "--seed",
        str(seed),
        "--output",
        str(output),
        *extra,
    )
    assert code == ExitCode.OK, payload
    return payload


def scripted(tmp_path: Path, mode: str) -> Path:
    """Create a one-file agent that runs ``scripted_agent.py MODE``."""
    path = tmp_path / f"agent_{mode}.py"
    path.write_text(
        "import runpy, sys\n"
        f"sys.argv = [{str(SCRIPTED)!r}, {mode!r}]\n"
        f"runpy.run_path({str(SCRIPTED)!r}, run_name='__main__')\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture(scope="module")
def matches(tmp_path_factory) -> dict[int, tuple[Path, dict]]:
    """One real team-agent versus reference-agent match per map size."""
    directory = tmp_path_factory.mktemp("e2e")
    played = {}
    for size, seed in MATCHES:
        output = directory / f"m{size}.history.json"
        payload = run_match(
            TEAM_AGENT, REFERENCE_AGENT, seed, output, "--map-size", str(size)
        )
        played[size] = (output, payload)
    return played


@pytest.mark.parametrize("size", [size for size, _ in MATCHES])
def test_team_agent_plays_the_reference_agent_to_the_end(matches, size: int) -> None:
    _, payload = matches[size]
    result = payload["result"]
    assert result["ticks_played"] == 500 and result["end_reason"] == "tick_limit"
    assert result["timeouts"] == [0, 0] and result["exclusions"] == [None, None]
    assert result["invalid_commands"] == [0, 0]
    # Both agents actually played: each delivered energy beyond what a ship costs.
    assert min(result["scores"]) > 1000


@pytest.mark.parametrize("size", [size for size, _ in MATCHES])
def test_engine_history_is_valid_and_fully_replayable_by_the_client(
    matches, size: int
) -> None:
    path, payload = matches[size]
    code, verdict = engine("validate", str(path))
    assert code == ExitCode.OK and verdict["valid"] is True
    assert verdict["ticks"] == 500

    # The client adapter rebuilds every frame from the file alone.
    presentation = MatchPresentation.from_file(path)
    history = load_history(path)
    assert presentation.last_tick == 500
    for tick in range(1, 501):
        state = presentation._states[tick]
        assert state_fingerprint(state) == history.ticks[tick - 1].fingerprint
    first, last = presentation.frame(0), presentation.frame(500)
    assert first.size == size and len(first.cells) == size
    assert [player.reserve for player in first.players] == [1000, 1000]
    assert [player.ships for player in first.players] == [1, 1]
    # What the client shows at the end is what the engine reported.
    result = payload["result"]
    assert [player.reserve for player in last.players] == result["scores"]
    assert [player.ships for player in last.players] == result["ships_remaining"]
    assert [player.carried for player in last.players] == result["carried_energy"]
    assert last.result_text.startswith("Winner: team_agent")
    # Resource collection is visible: deposits shrink during the match.
    assert sum(e for _, _, e in last.energy) < sum(e for _, _, e in first.energy)


def test_same_seed_twice_gives_identical_fingerprints_and_compare_agrees(
    matches, tmp_path: Path
) -> None:
    size, seed = MATCHES[0]
    first, _ = matches[size]
    second = tmp_path / "again.history.json"
    run_match(TEAM_AGENT, REFERENCE_AGENT, seed, second, "--map-size", str(size))
    code, verdict = engine("compare", str(first), str(second))
    assert code == ExitCode.OK
    assert verdict["identical"] is True and verdict["first_divergent_tick"] is None

    other = tmp_path / "other.history.json"
    run_match(REFERENCE_AGENT, TEAM_AGENT, seed, other, "--map-size", str(size))
    code, verdict = engine("compare", str(first), str(other))
    assert code == ExitCode.DIFFERENT
    assert verdict["first_divergent_tick"] >= 1


def test_match_with_faulty_agents_is_recorded_and_shown_by_the_client(
    tmp_path: Path,
) -> None:
    output = tmp_path / "faulty.history.json"
    payload = run_match(
        scripted(tmp_path, "silent"),
        scripted(tmp_path, "malformed"),
        9,
        output,
        "--max-ticks",
        "12",
        "--tick-timeout-ms",
        "200",
    )
    result = payload["result"]
    assert result["ticks_played"] == 12  # the engine was never blocked
    assert result["timeouts"][0] == 3
    assert result["exclusions"][0] == {"tick": 3, "reason": "timeout"}
    assert result["invalid_commands"][1] == 12  # one malformed answer per tick

    code, verdict = engine("validate", str(output))
    assert code == ExitCode.OK and verdict["valid"] is True
    presentation = MatchPresentation.from_file(output)
    assert presentation.frame(2).players[0].excluded is None
    assert presentation.frame(3).players[0].excluded == "timeout at tick 3"
    assert presentation.frame(12).players[0].excluded == "timeout at tick 3"
    assert presentation.frame(12).players[1].invalid_commands == 12
    assert any("timed out" in line for line in presentation.frame(1).event_summary)


def test_cpp_starter_agent_match_is_replayable_by_the_client(tmp_path: Path) -> None:
    agent = cpp_agent_path()
    if agent is None:
        pytest.skip("C++ starter agent is not built (cmake --build build/cpp)")
    output = tmp_path / "cpp.history.json"
    payload = run_match(agent, TEAM_AGENT, 4, output, "--max-ticks", "120")
    assert payload["result"]["timeouts"] == [0, 0]
    assert payload["result"]["exclusions"] == [None, None]
    assert MatchPresentation.from_file(output).last_tick == 120


def test_client_window_replays_an_engine_history_with_all_controls(
    qapp, matches
) -> None:
    path, payload = matches[48]
    window = MainWindow()
    assert window.open_history(path) is True
    assert window.error_banner.isHidden()
    assert window.controls.timeline.maximum() == 500

    window.step_forward()  # next tick
    assert window.current_tick == 1
    window.controls.timeline.setValue(250)  # timeline
    assert window.map_view.frame.tick == 250
    window.set_speed(4)  # x4
    window.toggle_playback()  # play
    window.advance_playback(1.0)  # one second at x4 = 20 ticks
    assert window.current_tick == 270 and window.replay.playing
    window.set_speed(2)  # x2
    window.advance_playback(1.0)
    assert window.current_tick == 280
    window.toggle_playback()  # pause
    window.advance_playback(5.0)
    assert window.current_tick == 280
    window.toggle_playback()
    window.advance_playback(1000.0)  # to the end
    assert window.current_tick == 500 and not window.replay.playing
    score = payload["result"]["scores"][0]
    assert f"Base energy: {score}" in window.info_panel.stats_labels[0].text()
    assert "Winner: team_agent" in window.info_panel.result_label.text()
    window.close()
