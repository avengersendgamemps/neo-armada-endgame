"""End-to-end tests of the engine CLI with real agent processes (L06)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_harness import (
    DUMMY_AGENTS,
    REFERENCE_AGENT,
    TEAM_AGENT,
    cpp_agent_path,
)
from neon_armada.contracts.cli import ENGINE_MODULE, ExitCode
from neon_armada.contracts.history import validate_history_document

SCRIPTED = DUMMY_AGENTS / "scripted_agent.py"


def run_engine(*arguments: str, timeout: float = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", ENGINE_MODULE, *arguments],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_match_cli(agent_a: Path, agent_b: Path, output: Path, *extra: str, seed=7):
    completed = run_engine(
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
    lines = completed.stdout.splitlines()
    assert len(lines) == 1, completed.stdout + completed.stderr  # exactly one line
    return completed, json.loads(lines[0])


def wrapper(tmp_path: Path, mode: str, *args: str) -> Path:
    """Create a one-file agent that runs ``scripted_agent.py MODE``."""
    path = tmp_path / f"agent_{mode}.py"
    path.write_text(
        "import runpy, sys\n"
        f"sys.argv = [{str(SCRIPTED)!r}, {mode!r}, *{list(args)!r}]\n"
        f"runpy.run_path({str(SCRIPTED)!r}, run_name='__main__')\n",
        encoding="utf-8",
    )
    return path


def load(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    validate_history_document(document)
    return document


def test_full_match_reference_vs_team(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "dir" / "match.history.json"
    completed, payload = run_match_cli(REFERENCE_AGENT, TEAM_AGENT, output)
    assert completed.returncode == ExitCode.OK, completed.stderr
    assert payload["status"] == "ok" and payload["cli_version"] == 1
    assert payload["history"] == str(output)
    result = payload["result"]
    assert result["end_reason"] in ("tick_limit", "budgets_exhausted")
    assert 1 <= result["ticks_played"] <= 500
    assert result["invalid_commands"] == [0, 0]
    assert result["timeouts"] == [0, 0]
    assert result["exclusions"] == [None, None]
    assert min(result["scores"]) > 1000  # both agents really collected energy
    assert set(payload["timing"]) == {"total_ms", "agent_wait_ms", "engine_ms"}

    document = load(output)  # parent directories were created
    assert document["result"] == result
    assert document["header"]["seed"] == 7
    assert [a["name"] for a in document["header"]["agents"]] == [
        "reference_agent",
        "team_agent",
    ]
    assert len(document["ticks"]) == result["ticks_played"]
    assert not list(output.parent.glob("*.tmp"))  # no temporary file left
    assert str(tmp_path) not in output.read_text(encoding="utf-8")  # no paths


def test_same_seed_gives_identical_histories_and_other_seed_differs(tmp_path) -> None:
    outputs = [tmp_path / name for name in ("a.json", "b.json", "c.json")]
    extra = ("--max-ticks", "150", "--map-size", "40")
    for output, seed in zip(outputs, (11, 11, 12), strict=True):
        completed, _ = run_match_cli(
            TEAM_AGENT, REFERENCE_AGENT, output, *extra, seed=seed
        )
        assert completed.returncode == 0, completed.stderr
    first, second, third = (load(path) for path in outputs)
    assert first == second  # byte-for-byte identical content
    assert [t["fingerprint"] for t in first["ticks"]] != [
        t["fingerprint"] for t in third["ticks"]
    ]
    assert first["header"]["config"]["map_size"] == 40


def test_cpp_agent_plays_a_full_match(tmp_path: Path) -> None:
    cpp = cpp_agent_path()
    if cpp is None:
        pytest.skip("C++ agent not built")
    output = tmp_path / "cpp.json"
    completed, payload = run_match_cli(
        cpp, REFERENCE_AGENT, output, "--max-ticks", "200", "--tick-timeout-ms", "2000"
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["result"]["invalid_commands"] == [0, 0]
    assert payload["result"]["timeouts"] == [0, 0]
    assert payload["result"]["scores"][0] > 1000
    load(output)


def test_custom_names_and_config_are_recorded(tmp_path: Path) -> None:
    output = tmp_path / "named.json"
    _, payload = run_match_cli(
        REFERENCE_AGENT,
        REFERENCE_AGENT,
        output,
        "--name-a",
        "Alpha",
        "--name-b",
        "Beta",
        "--max-ticks",
        "10",
        "--move-budget",
        "4",
        "--tick-timeout-ms",
        "900",
        "--init-timeout-ms",
        "9000",
        "--memory-limit-mb",
        "300",
    )
    header = load(output)["header"]
    assert [a["name"] for a in header["agents"]] == ["Alpha", "Beta"]
    assert header["config"] == {
        "map_size": 32,
        "max_ticks": 10,
        "move_budget": 4,
        "tick_timeout_ms": 900,
        "init_timeout_ms": 9000,
        "memory_limit_mb": 300,
    }
    assert payload["result"]["ticks_played"] <= 10


def test_silent_agent_is_excluded_after_three_timeouts_and_match_completes(
    tmp_path: Path,
) -> None:
    output = tmp_path / "silent.json"
    completed, payload = run_match_cli(
        wrapper(tmp_path, "silent"),
        REFERENCE_AGENT,
        output,
        "--max-ticks",
        "30",
        "--tick-timeout-ms",
        "200",
    )
    assert completed.returncode == ExitCode.OK  # a faulty agent is not an error
    result = payload["result"]
    assert result["ticks_played"] == 30
    assert result["timeouts"] == [3, 0]
    assert result["exclusions"] == [{"tick": 3, "reason": "timeout"}, None]
    document = load(output)
    events = {t["tick"]: t["events"] for t in document["ticks"]}
    assert events[1][0] == {"type": "timeout", "player": 0, "consecutive": 1}
    assert events[3][:2] == [
        {"type": "timeout", "player": 0, "consecutive": 3},
        {"type": "agent_excluded", "player": 0, "reason": "timeout"},
    ]
    # The excluded agent's ship stays on the map, in place, to the end.
    assert result["ships_remaining"][0] == 1
    assert "excluded" in completed.stderr


def test_crashing_and_malformed_agents_do_not_stop_the_match(tmp_path: Path) -> None:
    output = tmp_path / "faulty.json"
    completed, payload = run_match_cli(
        wrapper(tmp_path, "crash_at_3"),
        wrapper(tmp_path, "malformed"),
        output,
        "--max-ticks",
        "12",
    )
    assert completed.returncode == ExitCode.OK
    result = payload["result"]
    assert result["ticks_played"] == 12
    assert result["exclusions"] == [{"tick": 3, "reason": "crashed"}, None]
    assert result["invalid_commands"] == [0, 12]  # one per malformed response
    assert result["timeouts"] == [0, 0]
    assert result["winner"] == 0 and result["decided_by"] == "invalid_commands"
    load(output)


def test_agents_failing_initialisation_are_excluded_at_tick_zero(tmp_path) -> None:
    output = tmp_path / "init.json"
    completed, payload = run_match_cli(
        wrapper(tmp_path, "never_ready"),
        wrapper(tmp_path, "bad_ready"),
        output,
        "--max-ticks",
        "5",
        "--init-timeout-ms",
        "1500",
    )
    assert completed.returncode == ExitCode.OK
    assert payload["result"]["exclusions"] == [
        {"tick": 0, "reason": "init_timeout"},
        {"tick": 0, "reason": "init_failed"},
    ]
    assert load(output)["setup_events"] == [
        {"type": "agent_excluded", "player": 0, "reason": "init_timeout"},
        {"type": "agent_excluded", "player": 1, "reason": "init_failed"},
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["run"],
        ["run", "--agent-a", "a.py", "--agent-b", "b.py", "--output", "o.json"],
        ["run", "--agent-a", "A", "--agent-b", "B", "--seed", "x", "--output", "o"],
        ["dance"],
    ],
)
def test_usage_errors_exit_with_code_2(arguments: list[str]) -> None:
    completed = run_engine(*arguments)
    assert completed.returncode == ExitCode.USAGE
    payload = json.loads(completed.stdout)
    assert payload["status"] == "error" and payload["code"] == 2
    assert completed.stderr.strip()


@pytest.mark.parametrize(
    "option,value",
    [
        ("--map-size", "31"),
        ("--map-size", "65"),
        ("--max-ticks", "501"),
        ("--max-ticks", "0"),
        ("--move-budget", "-1"),
        ("--seed", "-1"),
        ("--seed", str(2**64)),
    ],
)
def test_out_of_range_values_are_usage_errors(tmp_path, option, value) -> None:
    arguments = [
        "run",
        "--agent-a",
        str(REFERENCE_AGENT),
        "--agent-b",
        str(REFERENCE_AGENT),
        "--output",
        str(tmp_path / "o.json"),
    ]
    if option != "--seed":
        arguments += ["--seed", "1"]
    completed = run_engine(*arguments, option, value)
    assert completed.returncode == ExitCode.USAGE, completed.stdout
    assert not (tmp_path / "o.json").exists()


def test_missing_agent_exits_with_code_3(tmp_path: Path) -> None:
    completed, payload = run_match_cli(
        tmp_path / "ghost.py", REFERENCE_AGENT, tmp_path / "o.json"
    )
    assert completed.returncode == ExitCode.AGENT_NOT_FOUND
    assert payload["code"] == 3 and "ghost.py" in payload["message"]
    completed, _ = run_match_cli(REFERENCE_AGENT, tmp_path, tmp_path / "o.json")
    assert completed.returncode == ExitCode.AGENT_NOT_FOUND  # a directory


def test_unwritable_output_exits_with_code_5(tmp_path: Path) -> None:
    target = tmp_path / "is_a_directory"
    target.mkdir()
    completed, payload = run_match_cli(
        REFERENCE_AGENT, REFERENCE_AGENT, target, "--max-ticks", "2"
    )
    assert completed.returncode == ExitCode.OUTPUT_ERROR
    assert payload["code"] == 5


def test_existing_output_is_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "o.json"
    output.write_text("old content", encoding="utf-8")
    completed, _ = run_match_cli(
        REFERENCE_AGENT, REFERENCE_AGENT, output, "--max-ticks", "2"
    )
    assert completed.returncode == 0
    load(output)


def test_agent_paths_with_spaces_work(tmp_path: Path) -> None:
    spaced = tmp_path / "my agents" / "ref agent.py"
    spaced.parent.mkdir()
    spaced.write_text(REFERENCE_AGENT.read_text(encoding="utf-8"), encoding="utf-8")
    kit = REFERENCE_AGENT.parent / "neon_agent_kit.py"
    (spaced.parent / kit.name).write_text(
        kit.read_text(encoding="utf-8"), encoding="utf-8"
    )
    completed, payload = run_match_cli(
        spaced, REFERENCE_AGENT, tmp_path / "out dir" / "o.json", "--max-ticks", "20"
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["result"]["exclusions"] == [None, None]
