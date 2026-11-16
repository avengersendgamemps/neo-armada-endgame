"""Tests for the agent subprocess runtime with deliberately faulty agents (L05)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from agent_harness import DUMMY_AGENTS, REFERENCE_AGENT, cpp_agent_path
from neon_armada.contracts import protocol
from neon_armada.contracts.models import Exclusion, MatchConfig, PlayerCommands
from neon_armada.engine.agents.runtime import (
    QUEUE_LINES,
    STDERR_TAIL_BYTES,
    AgentRuntime,
    launch_command,
)

SCRIPTED = DUMMY_AGENTS / "scripted_agent.py"
TICK_TIMEOUT = 0.25
CONFIG = MatchConfig(tick_timeout_ms=250, init_timeout_ms=15_000)
FAST_INIT = MatchConfig(tick_timeout_ms=250, init_timeout_ms=400)


@pytest.fixture
def init(load_fixture) -> dict:
    return load_fixture("contracts/init.valid.json")


@pytest.fixture
def tick(load_fixture) -> dict:
    return load_fixture("contracts/tick.valid.json")


@pytest.fixture
def runtimes():
    """Create runtimes and make sure every process is cleaned up."""
    created: list[AgentRuntime] = []

    def make(mode: str, *args: str, config: MatchConfig = CONFIG, player: int = 0):
        command = [sys.executable, "-u", str(SCRIPTED), mode, *args]
        runtime = AgentRuntime(player, command, config)
        created.append(runtime)
        return runtime

    yield make
    for runtime in created:
        runtime.abort()


def started(runtime: AgentRuntime, init: dict) -> AgentRuntime:
    runtime.start(init)
    assert runtime.finish_start() == []
    assert runtime.exclusion is None
    return runtime


def exchange(runtime: AgentRuntime, tick: dict, number: int):
    runtime.request(dict(tick, tick=number))
    return runtime.collect()


def os_process(runtime: AgentRuntime):
    return runtime._process._process  # noqa: SLF001 - test inspects cleanup


# --- launch rule and healthy agents -------------------------------------------


def test_launch_command_follows_cli_contract() -> None:
    assert launch_command(Path("dir/agent.py")) == [
        sys.executable,
        "-u",
        str(Path("dir/agent.py")),
    ]
    assert launch_command(Path("dir/agent.PY"))[0] == sys.executable
    assert launch_command(Path("bin/agent.exe")) == [str(Path("bin/agent.exe"))]
    assert launch_command(Path("bin/agent")) == [str(Path("bin/agent"))]


def test_healthy_agent_handshake_ticks_and_clean_shutdown(runtimes, init, tick) -> None:
    runtime = started(runtimes("ok"), init)
    process = os_process(runtime)
    for number in (1, 2, 3):
        response = exchange(runtime, tick, number)
        assert response.commands == PlayerCommands()
        assert not response.timed_out and not response.malformed
        assert response.events == []
    assert runtime.timeouts == 0
    runtime.finish(protocol.end_message("error"))
    assert process.poll() == 0  # exited by itself after "end"


@pytest.mark.parametrize("which", ["python-reference", "cpp-starter"])
def test_real_agents_run_under_the_runtime(which, init, tick) -> None:
    path = REFERENCE_AGENT if which == "python-reference" else cpp_agent_path()
    if path is None:
        pytest.skip("C++ agent not built")
    runtime = AgentRuntime(0, launch_command(path), CONFIG, cwd=path.parent)
    try:
        started(runtime, init)
        response = exchange(runtime, tick, 1)
        assert response.commands is not None
        assert [move.ship for move in response.commands.moves] == [0]
    finally:
        runtime.finish(protocol.end_message("error"))


# --- initialisation failures --------------------------------------------------


def test_init_timeout_excludes_at_tick_zero_and_kills(runtimes, init) -> None:
    runtime = runtimes("never_ready", config=FAST_INIT)
    began = time.monotonic()
    runtime.start(init)
    process = os_process(runtime)
    events = runtime.finish_start()
    assert time.monotonic() - began < 5
    assert runtime.exclusion == Exclusion(0, "init_timeout")
    assert events == [{"type": "agent_excluded", "player": 0, "reason": "init_timeout"}]
    assert process.poll() is not None  # killed


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("bad_ready", "init_failed"),
        ("wrong_version", "init_failed"),
        ("exit_on_init", "crashed"),
    ],
)
def test_bad_handshakes_exclude_at_tick_zero(runtimes, init, mode, reason) -> None:
    runtime = runtimes(mode)
    runtime.start(init)
    events = runtime.finish_start()
    assert runtime.exclusion == Exclusion(0, reason)
    assert events == [{"type": "agent_excluded", "player": 0, "reason": reason}]


def test_missing_executable_is_init_failed(init, tick, tmp_path) -> None:
    runtime = AgentRuntime(1, [str(tmp_path / "does-not-exist")], CONFIG)
    runtime.start(init)
    assert runtime.finish_start() == [
        {"type": "agent_excluded", "player": 1, "reason": "init_failed"}
    ]
    # An excluded agent is simply skipped afterwards.
    response = exchange(runtime, tick, 1)
    assert response.commands is None and response.events == []
    runtime.finish(protocol.end_message("excluded"))


# --- timeouts -----------------------------------------------------------------


@pytest.mark.parametrize("mode", ["silent", "hang"])
def test_three_consecutive_timeouts_exclude_the_agent(
    runtimes, init, tick, mode
) -> None:
    runtime = started(runtimes(mode), init)
    process = os_process(runtime)
    began = time.monotonic()
    first = exchange(runtime, tick, 1)
    second = exchange(runtime, tick, 2)
    assert first.timed_out and first.commands is None
    assert first.events == [{"type": "timeout", "player": 0, "consecutive": 1}]
    assert second.events == [{"type": "timeout", "player": 0, "consecutive": 2}]
    assert runtime.exclusion is None  # two timeouts are not enough

    third = exchange(runtime, tick, 3)
    elapsed = time.monotonic() - began
    assert third.events == [
        {"type": "timeout", "player": 0, "consecutive": 3},
        {"type": "agent_excluded", "player": 0, "reason": "timeout"},
    ]
    assert runtime.exclusion == Exclusion(3, "timeout")
    assert runtime.timeouts == 3
    assert process.poll() is not None  # the hung process was interrupted
    # The engine waited about one timeout per tick, never longer.
    assert 3 * TICK_TIMEOUT <= elapsed < 3 * TICK_TIMEOUT + 2

    after = exchange(runtime, tick, 4)
    assert after.commands is None and after.events == [] and not after.timed_out


def test_request_never_blocks_on_an_agent_that_stopped_reading(
    runtimes, init, tick
) -> None:
    runtime = started(runtimes("hang"), init)
    big = dict(tick, tick=1, padding="x" * 2_000_000)  # far beyond any pipe buffer
    began = time.monotonic()
    runtime.request(big)
    assert time.monotonic() - began < 0.2
    assert runtime.collect().timed_out


def test_a_valid_answer_resets_the_consecutive_timeout_counter(
    runtimes, init, tick
) -> None:
    runtime = started(runtimes("slow_twice", "0.4"), init)
    assert exchange(runtime, tick, 1).timed_out
    assert exchange(runtime, tick, 2).timed_out
    assert runtime.consecutive_timeouts == 2
    time.sleep(1.0)  # let the agent catch up with its two late answers
    third = exchange(runtime, tick, 3)  # the stale answers are skipped
    assert third.commands == PlayerCommands()
    assert runtime.consecutive_timeouts == 0
    assert runtime.exclusion is None
    assert runtime.timeouts == 2


def test_late_answer_is_discarded_as_stale(runtimes, init, tick) -> None:
    runtime = started(runtimes("late_once", "0.5"), init)
    assert exchange(runtime, tick, 1).timed_out
    time.sleep(0.6)  # the answer for tick 1 arrives now, too late
    second = exchange(runtime, tick, 2)
    assert second.commands == PlayerCommands()
    assert not second.malformed and not second.timed_out


def test_slow_agent_does_not_delay_the_other_agent(runtimes, init, tick) -> None:
    silent = started(runtimes("silent", player=0), init)
    healthy = started(runtimes("move_east", player=1), dict(init, player_id=1))
    message = dict(tick, tick=1)
    began = time.monotonic()
    silent.request(message)
    healthy.request(message)
    responses = [silent.collect(), healthy.collect()]
    elapsed = time.monotonic() - began
    assert responses[0].timed_out
    assert responses[1].commands is not None
    assert len(responses[1].commands.moves) == 1
    assert elapsed < TICK_TIMEOUT + 1.0  # one timeout, not one per agent


# --- crashes ------------------------------------------------------------------


def test_crash_on_first_tick_is_excluded_as_crashed(runtimes, init, tick) -> None:
    runtime = started(runtimes("crash"), init)
    response = exchange(runtime, tick, 1)
    assert response.commands is None and not response.timed_out
    assert response.events == [
        {"type": "agent_excluded", "player": 0, "reason": "crashed"}
    ]
    assert runtime.exclusion == Exclusion(1, "crashed")
    assert b"scripted crash" in runtime.stderr_tail()


def test_crash_later_records_the_exact_tick(runtimes, init, tick) -> None:
    runtime = started(runtimes("crash_at_3"), init)
    assert exchange(runtime, tick, 1).commands is not None
    assert exchange(runtime, tick, 2).commands is not None
    assert exchange(runtime, tick, 3).events[0]["reason"] == "crashed"
    assert runtime.exclusion == Exclusion(3, "crashed")


# --- malformed and oversized output -------------------------------------------


@pytest.mark.parametrize("mode", ["malformed", "future_tick"])
def test_malformed_answers_never_exclude_or_time_out(
    runtimes, init, tick, mode
) -> None:
    runtime = started(runtimes(mode), init)
    for number in range(1, 6):
        response = exchange(runtime, tick, number)
        assert response.malformed
        assert response.commands is None
        assert not response.timed_out and response.events == []
    assert runtime.exclusion is None
    assert runtime.timeouts == 0


def test_oversized_line_is_malformed_then_agent_recovers(runtimes, init, tick) -> None:
    runtime = started(runtimes("oversize"), init)
    assert exchange(runtime, tick, 1).malformed
    second = exchange(runtime, tick, 2)
    assert second.commands == PlayerCommands() and not second.malformed


def test_stderr_flood_does_not_deadlock_and_is_bounded(runtimes, init, tick) -> None:
    runtime = started(runtimes("stderr_flood"), init)
    for number in (1, 2, 3):
        assert exchange(runtime, tick, number).commands is not None
    assert 0 < len(runtime.stderr_tail()) <= STDERR_TAIL_BYTES


def test_stdout_flood_is_bounded_and_does_not_block(runtimes, init, tick) -> None:
    runtime = started(runtimes("stdout_flood"), init)
    time.sleep(0.5)  # let the agent fill every buffer it can
    began = time.monotonic()
    for number in (1, 2, 3):
        assert exchange(runtime, tick, number).malformed
    assert time.monotonic() - began < 1.0
    assert runtime._process.lines.qsize() <= QUEUE_LINES  # noqa: SLF001
    process = os_process(runtime)
    runtime.finish(protocol.end_message("error"))
    assert process.poll() is not None


# --- memory limit ---------------------------------------------------------------


def test_memory_hog_is_stopped_by_the_memory_limit(runtimes, init, tick) -> None:
    config = MatchConfig(
        tick_timeout_ms=20_000, init_timeout_ms=15_000, memory_limit_mb=256
    )
    runtime = started(runtimes("memory_hog", config=config), init)
    if not runtime.memory_limit_applied:
        pytest.skip("no enforceable memory limit on this platform")
    response = exchange(runtime, tick, 1)
    assert response.events == [
        {"type": "agent_excluded", "player": 0, "reason": "crashed"}
    ]
    assert runtime.exclusion == Exclusion(1, "crashed")
    assert b"MemoryError" in runtime.stderr_tail()


def test_agent_within_the_memory_limit_is_unaffected(runtimes, init, tick) -> None:
    config = MatchConfig(
        tick_timeout_ms=5000, init_timeout_ms=15_000, memory_limit_mb=256
    )
    runtime = started(runtimes("ok", config=config), init)
    assert exchange(runtime, tick, 1).commands is not None


# --- cleanup ------------------------------------------------------------------


def test_finish_kills_an_agent_that_ignores_end(runtimes, init) -> None:
    runtime = started(runtimes("hang"), init)
    process = os_process(runtime)
    # "hang" only blocks after the first tick; without ticks it reads "end".
    runtime.request(
        {
            "type": "tick",
            "tick": 1,
            "reserves": [0, 0],
            "move_budgets": [0, 0],
            "pending_builds": [False, False],
            "ships": [],
            "energy": [],
        }
    )
    time.sleep(0.3)
    began = time.monotonic()
    runtime.finish(
        protocol.end_message("finished") if False else protocol.end_message("error")
    )
    assert time.monotonic() - began < 5
    assert process.poll() is not None


def test_abort_is_idempotent(runtimes, init) -> None:
    runtime = started(runtimes("ok"), init)
    process = os_process(runtime)
    runtime.abort()
    runtime.abort()
    assert process.poll() is not None
