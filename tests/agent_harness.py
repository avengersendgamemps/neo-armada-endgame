"""Test helpers for talking to real agent processes.

This is test-only code: a small synchronous driver for trusted agents with a
watchdog, so a hung agent fails the test instead of blocking it forever.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from neon_armada.contracts import protocol
from neon_armada.contracts.models import MatchConfig, MatchState, PlayerCommands
from neon_armada.engine.core.mechanics import (
    create_initial_state,
    end_reason,
    resolve_tick,
)
from neon_armada.engine.world.generator import generate_map

REPO_ROOT = Path(__file__).parent.parent
PYTHON_AGENTS = REPO_ROOT / "agents" / "python"
REFERENCE_AGENT = PYTHON_AGENTS / "reference_agent.py"
TEAM_AGENT = PYTHON_AGENTS / "team_agent.py"
STARTER_AGENT = PYTHON_AGENTS / "starter_agent.py"
DUMMY_AGENTS = Path(__file__).parent / "fixtures" / "agents"


def cpp_agent_path() -> Path | None:
    """Return the built C++ starter agent, or ``None`` if it was not built."""
    for name in ("neon_starter_agent.exe", "neon_starter_agent"):
        candidate = REPO_ROOT / "build" / "cpp" / "bin" / name
        if candidate.is_file():
            return candidate
    return None


def agent_command(path: Path) -> list[str]:
    """Launch rule of the CLI contract: ``.py`` runs under the interpreter."""
    if path.suffix == ".py":
        return [sys.executable, "-u", str(path)]
    return [str(path)]


class AgentSession:
    """One running agent process with line-based request/response helpers."""

    def __init__(self, path: Path, watchdog_seconds: float = 60.0) -> None:
        self.process = subprocess.Popen(
            agent_command(path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=path.parent,
        )
        self._stderr: list[bytes] = []
        self._drain = threading.Thread(target=self._read_stderr, daemon=True)
        self._drain.start()
        self._watchdog = threading.Timer(watchdog_seconds, self.process.kill)
        self._watchdog.daemon = True
        self._watchdog.start()

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for chunk in iter(lambda: self.process.stderr.read(4096), b""):
            self._stderr.append(chunk)

    def send(self, message: dict) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(protocol.encode_message(message).encode("ascii"))
        self.process.stdin.flush()

    def send_raw(self, data: bytes) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def read_line(self) -> bytes:
        assert self.process.stdout is not None
        return self.process.stdout.readline()

    def close(self) -> tuple[int, bytes, bytes]:
        """Close stdin, wait for exit; return (code, rest of stdout, stderr)."""
        assert self.process.stdin is not None and self.process.stdout is not None
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            code = self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            code = self.process.wait()
        rest = self.process.stdout.read()
        self.process.stdout.close()
        self._drain.join(timeout=5)
        self._watchdog.cancel()
        return code, rest, b"".join(self._stderr)


def play_local_match(
    agent_a: Path, agent_b: Path, seed: int, config: MatchConfig
) -> tuple[MatchState, list[tuple[dict, ...]]]:
    """Drive two real agents through the pure mechanics, without the engine.

    Returns the final state and the per-tick event tuples. No timeouts are
    applied; this checks protocol conformance and strategy legality only.
    """
    generated = generate_map(seed, config.map_size)
    state = create_initial_state(config, generated.static_map, generated.energy)
    sessions = [AgentSession(agent_a), AgentSession(agent_b)]
    events: list[tuple[dict, ...]] = []
    try:
        for player, session in enumerate(sessions):
            session.send(protocol.init_message(player, config, generated.static_map))
            protocol.parse_ready(session.read_line())
        while end_reason(state, config) is None:
            message = protocol.tick_message(state)
            for session in sessions:
                session.send(message)
            commands: list[PlayerCommands] = [
                protocol.parse_commands(session.read_line(), state.tick + 1)
                for session in sessions
            ]
            outcome = resolve_tick(state, generated.static_map, commands)
            state = outcome.state
            events.append(outcome.events)
        for session in sessions:
            session.send(protocol.end_message("error"))
    finally:
        for session in sessions:
            code, rest, stderr = session.close()
            assert code == 0, stderr.decode(errors="replace")
            assert rest == b"", "agent wrote extra data to stdout"
    return state, events
