"""Engine-side runtime for one external agent process.

Responsibilities (``contracts/agent-protocol.md``):

* start the agent as an independent process and perform the ``init``/``ready``
  handshake within the initialisation limit;
* exchange one ``tick``/``commands`` pair per tick with a hard deadline, never
  blocking the engine on a slow, silent or flooding agent;
* count timeouts, exclude the agent after three consecutive ones, and treat a
  closed stream as a crash;
* bound everything the agent can make the engine buffer (line length, queue
  length, stderr tail) and always clean the process up.

This module contains no game rules and no match loop.
"""

from __future__ import annotations

import logging
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from neon_armada.contracts import protocol
from neon_armada.contracts.models import Exclusion, MatchConfig, PlayerCommands
from neon_armada.engine.agents import limits

logger = logging.getLogger(__name__)

STDERR_TAIL_BYTES = 64 * 1024
QUEUE_LINES = 256
END_GRACE_SECONDS = 0.5
_READ_CHUNK = 65_536

_LINE, _OVERSIZE, _EOF = "line", "oversize", "eof"


def launch_command(path: Path) -> list[str]:
    """Return the argument list that starts the agent at ``path``.

    ``.py`` files run under the engine's interpreter (unbuffered); anything
    else is executed directly. No shell is involved.
    """
    if path.suffix.lower() == ".py":
        return [sys.executable, "-u", str(path)]
    return [str(path)]


@dataclass(slots=True)
class TickResponse:
    """What the engine learns from one agent for one tick."""

    commands: PlayerCommands | None = None
    timed_out: bool = False
    malformed: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)


class _AgentProcess:
    """A child process with non-blocking, bounded I/O on all three streams."""

    def __init__(self, command: Sequence[str], cwd: Path | None, memory_mb: int):
        command, environment = limits.direct_interpreter(command)
        self._process = subprocess.Popen(
            command,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            preexec_fn=limits.preexec_function(memory_mb),
            creationflags=limits.creation_flags(),
        )
        try:
            self.job = limits.apply_after_start(self._process, memory_mb)
        except OSError:
            self._process.kill()
            self._process.wait()
            raise
        self.lines: queue.Queue[tuple[str, bytes]] = queue.Queue(maxsize=QUEUE_LINES)
        self._outbox: queue.Queue[bytes | None] = queue.Queue()
        self._stderr_tail = bytearray()
        self._closing = threading.Event()
        self._threads = [
            threading.Thread(target=self._read_stdout, daemon=True),
            threading.Thread(target=self._read_stderr, daemon=True),
            threading.Thread(target=self._write_stdin, daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    # -- background threads ---------------------------------------------------

    def _put(self, item: tuple[str, bytes]) -> bool:
        while not self._closing.is_set():
            try:
                self.lines.put(item, timeout=0.05)
                return True
            except queue.Full:
                continue  # back-pressure: a flooding agent blocks on its pipe
        return False

    def _read_stdout(self) -> None:
        stream = self._process.stdout
        assert stream is not None
        buffer = bytearray()
        discarding = False
        limit = protocol.MAX_AGENT_LINE_BYTES
        try:
            while True:
                chunk = stream.read1(_READ_CHUNK)
                if not chunk:
                    break
                buffer += chunk
                while True:
                    newline = buffer.find(b"\n")
                    if newline < 0:
                        if len(buffer) > limit:
                            # Too long without a terminator: report once, then
                            # drop bytes until the next newline.
                            if not discarding and not self._put((_OVERSIZE, b"")):
                                return
                            discarding = True
                            buffer.clear()
                        break
                    line = bytes(buffer[: newline + 1])
                    del buffer[: newline + 1]
                    if discarding:
                        discarding = False
                    elif len(line) > limit:
                        if not self._put((_OVERSIZE, b"")):
                            return
                    elif not self._put((_LINE, line)):
                        return
        except (OSError, ValueError):
            pass
        self._put((_EOF, b""))

    def _read_stderr(self) -> None:
        stream = self._process.stderr
        assert stream is not None
        try:
            while True:
                chunk = stream.read1(_READ_CHUNK)
                if not chunk:
                    break
                self._stderr_tail += chunk
                if len(self._stderr_tail) > STDERR_TAIL_BYTES:
                    del self._stderr_tail[:-STDERR_TAIL_BYTES]
        except (OSError, ValueError):
            pass

    def _write_stdin(self) -> None:
        stream = self._process.stdin
        assert stream is not None
        try:
            while True:
                data = self._outbox.get()
                if data is None:
                    break
                stream.write(data)
                stream.flush()
        except (OSError, ValueError):
            pass  # the agent closed its stdin or died; reads will report it
        finally:
            try:
                stream.close()
            except (OSError, ValueError):
                pass

    # -- engine-facing API ----------------------------------------------------

    def send(self, message: dict[str, Any]) -> None:
        """Queue a message; never blocks even if the agent stops reading."""
        self._outbox.put(protocol.encode_message(message).encode("ascii"))

    def stderr_tail(self) -> bytes:
        return bytes(self._stderr_tail)

    def kill(self) -> None:
        """Terminate the agent (and its children on Windows) immediately."""
        self._closing.set()
        self._outbox.put(None)
        self.job.terminate()
        try:
            self._process.kill()
        except OSError:
            pass
        self._reap()

    def close(self, grace_seconds: float) -> None:
        """Close stdin, give the agent ``grace_seconds`` to exit, then kill."""
        self._outbox.put(None)
        try:
            self._process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            pass
        self.kill()

    def _reap(self) -> None:
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("agent process %s did not exit", self._process.pid)
        for thread in self._threads:
            thread.join(timeout=1)
        for stream in (self._process.stdout, self._process.stderr):
            try:
                if stream is not None:
                    stream.close()
            except (OSError, ValueError):
                pass
        self.job.close()

    @property
    def returncode(self) -> int | None:
        return self._process.poll()


class AgentRuntime:
    """Protocol state machine for one agent: handshake, ticks, exclusion.

    Typical use by the match loop, for both agents at once::

        for agent in agents: agent.start(init_message)
        for agent in agents: agent.finish_start()
        each tick:
            for agent in agents: agent.request(tick_message)
            responses = [agent.collect() for agent in agents]
        for agent in agents: agent.finish(end_message)
    """

    def __init__(
        self,
        player_id: int,
        command: Sequence[str],
        config: MatchConfig,
        cwd: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.player_id = player_id
        self.command = list(command)
        self.config = config
        self.cwd = cwd
        self._clock = clock
        self._process: _AgentProcess | None = None
        self._deadline = 0.0
        self._tick = 0
        self._awaiting = False
        self.exclusion: Exclusion | None = None
        self.timeouts = 0
        self.consecutive_timeouts = 0
        self.wait_seconds = 0.0
        self.memory_limit_applied = False
        self._stderr = b""

    # -- lifecycle ------------------------------------------------------------

    def start(self, init_message: dict[str, Any]) -> None:
        """Start the process and send ``init`` (does not wait for ``ready``)."""
        self._deadline = self._clock() + self.config.init_timeout_ms / 1000
        try:
            self._process = _AgentProcess(
                self.command, self.cwd, self.config.memory_limit_mb
            )
        except (OSError, ValueError) as error:
            logger.warning("agent %d could not be started: %s", self.player_id, error)
            self.exclusion = Exclusion(0, "init_failed")
            return
        self.memory_limit_applied = self._process.job.applied
        self._process.send(init_message)

    def finish_start(self) -> list[dict[str, Any]]:
        """Wait for ``ready``; return history events (exclusion, if any)."""
        if self.exclusion is None:
            kind, line = self._next_line()
            if kind is None:
                self._exclude(0, "init_timeout")
            elif kind == _EOF:
                self._exclude(0, "crashed")
            elif kind == _OVERSIZE:
                self._exclude(0, "init_failed")
            else:
                try:
                    protocol.parse_ready(line)
                except protocol.ProtocolError:
                    self._exclude(0, "init_failed")
        if self.exclusion is None:
            return []
        return [self._excluded_event()]

    def request(self, tick_message: dict[str, Any]) -> None:
        """Send the ``tick`` message and start this agent's response clock."""
        if self.exclusion is not None or self._process is None:
            return
        self._tick = tick_message["tick"]
        self._process.send(tick_message)
        self._deadline = self._clock() + self.config.tick_timeout_ms / 1000
        self._awaiting = True

    def collect(self) -> TickResponse:
        """Return this tick's commands, or what went wrong, by the deadline."""
        response = TickResponse()
        if not self._awaiting:
            return response
        self._awaiting = False
        while True:
            kind, line = self._next_line()
            if kind is None:
                self.timeouts += 1
                self.consecutive_timeouts += 1
                response.timed_out = True
                response.events.append(
                    {
                        "type": "timeout",
                        "player": self.player_id,
                        "consecutive": self.consecutive_timeouts,
                    }
                )
                if self.consecutive_timeouts >= protocol.MAX_CONSECUTIVE_TIMEOUTS:
                    self._exclude(self._tick, "timeout")
                    response.events.append(self._excluded_event())
                return response
            if kind == _EOF:
                self._exclude(self._tick, "crashed")
                response.events.append(self._excluded_event())
                return response
            if kind == _OVERSIZE:
                response.malformed = True
            else:
                try:
                    response.commands = protocol.parse_commands(line, self._tick)
                except protocol.StaleResponseError:
                    continue  # answer to an earlier, timed-out tick: keep waiting
                except protocol.ProtocolError:
                    response.malformed = True
            # Any answer for the current tick, even a malformed one, is not a
            # timeout and therefore ends the run of consecutive timeouts.
            self.consecutive_timeouts = 0
            return response

    def finish(self, end_message: dict[str, Any]) -> None:
        """Send ``end`` and release the process (no-op if already excluded)."""
        if self._process is None:
            return
        process, self._process = self._process, None
        process.send(end_message)
        process.close(END_GRACE_SECONDS)

    def abort(self) -> None:
        """Kill the process without ceremony (engine failure path)."""
        if self._process is not None:
            process, self._process = self._process, None
            process.kill()

    def stderr_tail(self) -> bytes:
        """Return the retained tail of the agent's stderr (diagnostics)."""
        return self._stderr if self._process is None else self._process.stderr_tail()

    # -- helpers --------------------------------------------------------------

    def _next_line(self) -> tuple[str | None, bytes]:
        """Wait for the next stdout item until the current deadline."""
        assert self._process is not None
        started = self._clock()
        remaining = self._deadline - started
        try:
            if remaining > 0:
                item = self._process.lines.get(timeout=remaining)
            else:
                item = self._process.lines.get_nowait()
        except queue.Empty:
            item = (None, b"")
        self.wait_seconds += self._clock() - started
        return item

    def _exclude(self, tick: int, reason: str) -> None:
        self.exclusion = Exclusion(tick, reason)
        self._awaiting = False
        if self._process is not None:
            process, self._process = self._process, None
            process.send(protocol.end_message("excluded"))
            process.kill()
            self._stderr = process.stderr_tail()
            tail = self._stderr[-2000:].decode("utf-8", errors="replace").strip()
            logger.warning(
                "agent %d excluded at tick %d (%s)%s",
                self.player_id,
                tick,
                reason,
                f"; stderr tail:\n{tail}" if tail else "",
            )

    def _excluded_event(self) -> dict[str, Any]:
        assert self.exclusion is not None
        return {
            "type": "agent_excluded",
            "player": self.player_id,
            "reason": self.exclusion.reason,
        }
