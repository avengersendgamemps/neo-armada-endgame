"""Unit tests for the Qt-free engine launcher, using a fake engine (L10)."""

from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

import pytest

import neon_armada.client.launcher as launcher_module
from neon_armada.client.launcher import (
    MAX_SEED,
    EngineOutcome,
    EngineRun,
    LaunchError,
    MatchRequest,
    build_command,
    default_output_path,
    parse_seed,
    validate_request,
)

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"
FAKE_ENGINE = FIXTURES / "agents" / "fake_engine.py"
VALID_HISTORY = FIXTURES / "contracts" / "history.valid.json"


def fake_run(tmp_path: Path, mode: str, delay: float = 0.0) -> EngineRun:
    output = tmp_path / "out" / "match.history.json"
    command = [
        sys.executable,
        str(FAKE_ENGINE),
        mode,
        str(output),
        str(delay),
        str(VALID_HISTORY),
    ]
    return EngineRun(command, output)


def wait_for(run: EngineRun, timeout: float = 30.0) -> EngineOutcome:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        outcome = run.poll()
        if outcome is not None:
            return outcome
        time.sleep(0.02)
    run.cancel()
    raise AssertionError("fake engine did not finish in time")


@pytest.fixture
def agents(tmp_path: Path) -> tuple[Path, Path]:
    first, second = tmp_path / "a agent.py", tmp_path / "b.exe"
    first.write_text("", encoding="utf-8")
    second.write_text("", encoding="utf-8")
    return first, second


def test_parse_seed_accepts_only_unsigned_64_bit_integers() -> None:
    assert parse_seed("0") == 0
    assert parse_seed("  42 ") == 42
    assert parse_seed(str(MAX_SEED)) == MAX_SEED
    for bad in ("", " ", "-1", "1.5", "abc", "1e3", "0x10", str(MAX_SEED + 1), "٣"):
        assert parse_seed(bad) is None


def test_valid_request_has_no_problems(agents, tmp_path: Path) -> None:
    request = MatchRequest(agents[0], agents[1], 7, tmp_path / "h.json", 48)
    assert validate_request(request) == []


def test_validation_names_every_problem(agents, tmp_path: Path) -> None:
    request = MatchRequest(
        tmp_path / "missing.py", Path(""), MAX_SEED + 1, tmp_path, map_size=70
    )
    problems = validate_request(request)
    assert len(problems) == 5
    assert "Agent A: file not found" in problems[0]
    assert problems[1].startswith("Agent B: choose")
    assert "Seed" in problems[2] and "Map size" in problems[3]
    assert "directory" in problems[4]
    # A directory is not an agent either; too small maps are rejected.
    request = MatchRequest(tmp_path, agents[1], 1, tmp_path / "h.json", 31)
    assert len(validate_request(request)) == 2


def test_command_follows_the_cli_contract_as_an_argument_list(agents, tmp_path) -> None:
    request = MatchRequest(agents[0], agents[1], 123, tmp_path / "my out.json", 40)
    command = build_command(request, python="py")
    assert command == [
        "py",
        "-m",
        "neon_armada.engine",
        "run",
        "--agent-a",
        str(agents[0]),  # contains a space: stays one argument
        "--agent-b",
        str(agents[1]),
        "--seed",
        "123",
        "--map-size",
        "40",
        "--output",
        str(tmp_path / "my out.json"),
    ]
    assert build_command(request)[0] == sys.executable


def test_default_output_path_never_reuses_an_existing_file(tmp_path: Path) -> None:
    first = default_output_path(5, tmp_path)
    assert first == tmp_path / "match-seed5.history.json"
    first.write_text("{}", encoding="utf-8")
    second = default_output_path(5, tmp_path)
    assert second == tmp_path / "match-seed5-2.history.json"
    second.write_text("{}", encoding="utf-8")
    assert default_output_path(5, tmp_path).name == "match-seed5-3.history.json"
    assert default_output_path(9).parent.name == "histories"


def test_successful_run_reports_the_history(tmp_path: Path) -> None:
    run = fake_run(tmp_path, "ok")
    run.start()
    assert run.pid is not None
    outcome = wait_for(run)
    assert outcome == EngineOutcome(0, True, "match finished", run.history)
    assert json.loads(run.history.read_text(encoding="utf-8"))["format"]
    record = json.loads(run.record_path.read_text(encoding="utf-8"))
    assert record["command"] == run.command and record["engine_pid"] == run.pid
    assert run.poll() is outcome  # the outcome is remembered


def test_poll_never_blocks_while_the_engine_runs(tmp_path: Path) -> None:
    run = fake_run(tmp_path, "ok", delay=1.0)
    run.start()
    started = time.monotonic()
    assert run.poll() is None
    assert time.monotonic() - started < 0.5
    assert not run.history.exists()
    assert wait_for(run).succeeded


def test_engine_error_message_is_passed_on(tmp_path: Path) -> None:
    run = fake_run(tmp_path, "not_found")
    run.start()
    outcome = wait_for(run)
    assert (outcome.exit_code, outcome.succeeded, outcome.history) == (3, False, None)
    assert "agent not found: nowhere.py" in outcome.message
    assert "exit code 3 (agent not found)" in outcome.message


def test_crash_without_a_result_line_reports_stderr(tmp_path: Path) -> None:
    run = fake_run(tmp_path, "crash")
    run.start()
    outcome = wait_for(run)
    assert outcome.exit_code == 70 and not outcome.succeeded
    assert "internal error" in outcome.message
    assert "simulated engine crash" in outcome.message


@pytest.mark.parametrize("mode", ["no_history", "silent_ok"])
def test_exit_code_zero_without_a_usable_result_is_a_failure(
    tmp_path: Path, mode: str
) -> None:
    run = fake_run(tmp_path, mode)
    run.start()
    outcome = wait_for(run)
    assert outcome.exit_code == 0 and not outcome.succeeded
    assert outcome.history is None


def test_cancel_stops_a_running_engine(tmp_path: Path) -> None:
    run = fake_run(tmp_path, "hang")
    run.start()
    assert run.poll() is None
    run.cancel()
    outcome = wait_for(run)
    assert not outcome.succeeded and outcome.exit_code != 0
    run.cancel()  # harmless once finished


def test_missing_executable_is_a_launch_error(tmp_path: Path) -> None:
    output = tmp_path / "h.json"
    run = EngineRun([str(tmp_path / "no-such-python.exe"), "-m", "x"], output)
    with pytest.raises(LaunchError, match="cannot start the engine"):
        run.start()
    with pytest.raises(LaunchError):
        run.poll()


def test_a_run_cannot_be_started_twice(tmp_path: Path) -> None:
    run = fake_run(tmp_path, "ok")
    run.start()
    with pytest.raises(LaunchError):
        run.start()
    wait_for(run)


def test_launcher_uses_no_shell_no_pipes_no_qt_and_no_engine_code() -> None:
    source = Path(launcher_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.keyword):
            assert node.arg != "shell"
        elif isinstance(node, ast.Attribute):
            assert node.attr not in ("PIPE", "system", "popen")
    assert not any(name.startswith("PySide6") for name in imported)
    assert not any(name.startswith("neon_armada.engine") for name in imported)
    assert "neon_armada.contracts.cli" in imported
