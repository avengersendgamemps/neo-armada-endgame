"""Determinism and history verification with real engine runs (L07)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_harness import REFERENCE_AGENT, TEAM_AGENT, cpp_agent_path
from neon_armada.contracts.cli import ENGINE_MODULE, ExitCode
from neon_armada.contracts.fingerprint import state_fingerprint
from neon_armada.contracts.models import MatchConfig
from neon_armada.contracts.replay import (
    compare_histories,
    first_invalid_tick,
    load_history,
    parse_history,
    reconstruct_states,
)
from neon_armada.engine.agents.runtime import AgentRuntime, launch_command
from neon_armada.engine.history.writer import record_to_document, write_history
from neon_armada.engine.match import MatchRecord, run_match


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


def play(agent_a: Path, agent_b: Path, seed: int, **config) -> MatchRecord:
    settings = MatchConfig(tick_timeout_ms=5000, init_timeout_ms=20_000, **config)
    agents = [
        AgentRuntime(player, launch_command(path), settings, cwd=path.parent)
        for player, path in enumerate((agent_a, agent_b))
    ]
    return run_match(settings, seed, agents, (agent_a.stem, agent_b.stem))


@pytest.fixture(scope="module")
def full_match() -> MatchRecord:
    return play(TEAM_AGENT, REFERENCE_AGENT, 2024)


def test_every_tick_of_a_full_match_is_reconstructed_from_the_history(
    full_match: MatchRecord, tmp_path: Path
) -> None:
    path = tmp_path / "full.history.json"
    write_history(full_match, path)
    history = load_history(path)

    states = reconstruct_states(history)
    assert len(states) == full_match.result.ticks_played + 1
    assert states[0] == full_match.initial_state
    for entry, state in zip(history.ticks, states[1:], strict=True):
        assert state.tick == entry.tick
        assert state_fingerprint(state) == entry.fingerprint
    # The last reconstructed state is exactly the engine's final state.
    assert states[-1] == full_match.final_state
    assert first_invalid_tick(history) is None
    assert history.result == full_match.result
    # The match was eventful enough to exercise the event model.
    kinds = {event["type"] for tick in history.ticks for event in tick.events}
    assert {
        "ship_moved",
        "mined",
        "delivered",
        "build_started",
        "ship_spawned",
    } <= kinds


def test_history_round_trip_preserves_the_document(full_match, tmp_path) -> None:
    path = tmp_path / "rt.history.json"
    write_history(full_match, path)
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == record_to_document(full_match)
    assert parse_history(on_disk) == load_history(path)


def test_history_contains_only_deterministic_integer_data(full_match) -> None:
    document = record_to_document(full_match)
    assert set(document) == {
        "format",
        "history_version",
        "header",
        "map",
        "initial_state",
        "initial_fingerprint",
        "setup_events",
        "ticks",
        "result",
    }

    def walk(value) -> None:
        assert not isinstance(value, float)
        if isinstance(value, dict):
            for key, item in value.items():
                assert key not in ("timing", "timestamp", "path", "pid", "command")
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(document)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_two_runs_with_the_same_seed_have_identical_fingerprints(seed: int) -> None:
    first = play(TEAM_AGENT, REFERENCE_AGENT, seed, max_ticks=120)
    second = play(TEAM_AGENT, REFERENCE_AGENT, seed, max_ticks=120)
    assert [t.fingerprint for t in first.ticks] == [t.fingerprint for t in second.ticks]
    comparison = compare_histories(
        parse_history(record_to_document(first)),
        parse_history(record_to_document(second)),
    )
    assert comparison.identical and comparison.first_divergent_tick is None


def test_fingerprint_ignores_agent_names_and_locations(tmp_path: Path) -> None:
    elsewhere = tmp_path / "copied agents"
    elsewhere.mkdir()
    for name in ("reference_agent.py", "neon_agent_kit.py"):
        source = REFERENCE_AGENT.parent / name
        (elsewhere / name).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )
    renamed = elsewhere / "renamed.py"
    (elsewhere / "reference_agent.py").rename(renamed)

    original = play(REFERENCE_AGENT, REFERENCE_AGENT, 9, max_ticks=60)
    moved = play(renamed, REFERENCE_AGENT, 9, max_ticks=60)
    assert original.agent_names != moved.agent_names
    assert [t.fingerprint for t in original.ticks] == [
        t.fingerprint for t in moved.ticks
    ]


def test_different_agents_diverge_and_the_first_tick_is_reported() -> None:
    first = play(TEAM_AGENT, REFERENCE_AGENT, 5, max_ticks=80)
    second = play(REFERENCE_AGENT, REFERENCE_AGENT, 5, max_ticks=80)
    comparison = compare_histories(
        parse_history(record_to_document(first)),
        parse_history(record_to_document(second)),
    )
    assert not comparison.identical
    expected = next(
        one.tick
        for one, two in zip(first.ticks, second.ticks, strict=True)
        if one.fingerprint != two.fingerprint
    )
    assert comparison.first_divergent_tick == expected >= 1
    # Before the divergence the two runs agree tick by tick.
    assert all(
        one.fingerprint == two.fingerprint
        for one, two in zip(first.ticks[: expected - 1], second.ticks, strict=False)
    )


def test_cli_check_determinism_reports_identical_runs(tmp_path: Path) -> None:
    code, payload = engine(
        "check-determinism",
        "--agent-a",
        str(TEAM_AGENT),
        "--agent-b",
        str(REFERENCE_AGENT),
        "--seed",
        "31",
        "--max-ticks",
        "150",
        "--output-dir",
        str(tmp_path / "runs"),
    )
    assert code == ExitCode.OK
    assert payload["identical"] is True and payload["first_divergent_tick"] is None
    run1, run2 = (Path(p) for p in payload["histories"])
    assert run1.read_bytes() == run2.read_bytes()
    assert first_invalid_tick(load_history(run1)) is None


def test_cli_check_determinism_with_cpp_agent() -> None:
    cpp = cpp_agent_path()
    if cpp is None:
        pytest.skip("C++ agent not built")
    code, payload = engine(
        "check-determinism",
        "--agent-a",
        str(cpp),
        "--agent-b",
        str(TEAM_AGENT),
        "--seed",
        "8",
        "--max-ticks",
        "100",
        "--tick-timeout-ms",
        "5000",
    )
    assert code == ExitCode.OK and payload["identical"] is True
    assert "histories" not in payload  # temporary files are not reported


def test_cli_validate_and_compare(full_match: MatchRecord, tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    write_history(full_match, good)
    assert engine("validate", str(good)) == (
        ExitCode.OK,
        {
            "status": "ok",
            "cli_version": 1,
            "valid": True,
            "ticks": full_match.result.ticks_played,
        },
    )
    assert engine("compare", str(good), str(good))[0] == ExitCode.OK

    # Tamper with tick 37: change one event and keep the old fingerprint.
    document = json.loads(good.read_text(encoding="utf-8"))
    tick = document["ticks"][36]
    assert tick["tick"] == 37
    tick["events"].append({"type": "build_started", "player": 0, "cost": 1})
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(document), encoding="utf-8")
    code, payload = engine("validate", str(tampered))
    assert code == ExitCode.DIFFERENT
    assert payload["valid"] is False and payload["first_invalid_tick"] == 37

    # A run that diverges at tick 37 is reported by compare.
    document = json.loads(good.read_text(encoding="utf-8"))
    document["ticks"][36]["fingerprint"] = "f" * 64
    diverged = tmp_path / "diverged.json"
    diverged.write_text(json.dumps(document), encoding="utf-8")
    code, payload = engine("compare", str(good), str(diverged))
    assert code == ExitCode.DIFFERENT
    assert payload == {
        "status": "ok",
        "cli_version": 1,
        "identical": False,
        "first_divergent_tick": 37,
        "detail": "fingerprint mismatch",
    }


@pytest.mark.parametrize("command", ["validate", "compare"])
def test_cli_rejects_invalid_history_files(command, full_match, tmp_path) -> None:
    good = tmp_path / "good.json"
    write_history(full_match, good)
    truncated = tmp_path / "truncated.json"
    truncated.write_bytes(good.read_bytes()[:5000])
    unsupported = tmp_path / "v2.json"
    document = json.loads(good.read_text(encoding="utf-8"))
    document["history_version"] = 2
    unsupported.write_text(json.dumps(document), encoding="utf-8")
    for bad in (truncated, unsupported, tmp_path / "missing.json"):
        arguments = [str(bad)] if command == "validate" else [str(good), str(bad)]
        code, payload = engine(command, *arguments)
        assert code == ExitCode.HISTORY_INVALID
        assert payload["status"] == "error" and payload["code"] == 6
