"""Start the engine as an independent operating-system process.

The client and the engine share nothing but the command line and files
(``contracts/engine-cli.md``): this module builds the ``run`` command, starts
it detached from the client and later reads the exit code and the one-line
JSON result the engine wrote to its redirected standard output. No engine
code is imported and no pipe connects the two processes, so the engine keeps
running and finishes its history file even if the client is closed or killed.

Pure Python on purpose (no Qt), so it can be tested without a GUI.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from neon_armada.contracts.cli import ENGINE_MODULE, ExitCode

MAX_SEED = 2**64 - 1
MAP_SIZE_MIN = 32
MAP_SIZE_MAX = 64
DEFAULT_MAP_SIZE = 32
STDERR_TAIL_CHARS = 600


class LaunchError(Exception):
    """The engine process could not be started."""


@dataclass(frozen=True, slots=True)
class MatchRequest:
    """What the user chose for one match."""

    agent_a: Path
    agent_b: Path
    seed: int
    output: Path
    map_size: int = DEFAULT_MAP_SIZE


@dataclass(frozen=True, slots=True)
class EngineOutcome:
    """How a finished engine process ended."""

    exit_code: int
    succeeded: bool
    message: str
    history: Path | None


def parse_seed(text: str) -> int | None:
    """Return the seed written in ``text``, or ``None`` if it is not valid."""
    stripped = text.strip()
    if not stripped.isascii() or not stripped.isdigit():
        return None
    seed = int(stripped)
    return seed if seed <= MAX_SEED else None


def validate_request(request: MatchRequest) -> list[str]:
    """Return the problems of ``request`` as user-readable sentences."""
    problems = []
    for label, path in (("Agent A", request.agent_a), ("Agent B", request.agent_b)):
        if not str(path).strip() or str(path) == ".":
            problems.append(f"{label}: choose an agent script or executable.")
        elif not path.is_file():
            problems.append(f"{label}: file not found: {path}")
    if not 0 <= request.seed <= MAX_SEED:
        problems.append(f"Seed must be an integer between 0 and {MAX_SEED}.")
    if not MAP_SIZE_MIN <= request.map_size <= MAP_SIZE_MAX:
        problems.append(f"Map size must be {MAP_SIZE_MIN}..{MAP_SIZE_MAX}.")
    if not str(request.output).strip() or str(request.output) == ".":
        problems.append("Choose where to write the history file.")
    elif request.output.is_dir():
        problems.append(f"The history path is a directory: {request.output}")
    return problems


def build_command(request: MatchRequest, python: str | None = None) -> list[str]:
    """Return the engine ``run`` command as an argument list (never a shell string)."""
    return [
        python or sys.executable,
        "-m",
        ENGINE_MODULE,
        "run",
        "--agent-a",
        str(request.agent_a),
        "--agent-b",
        str(request.agent_b),
        "--seed",
        str(request.seed),
        "--map-size",
        str(request.map_size),
        "--output",
        str(request.output),
    ]


def default_output_path(seed: int, directory: Path | None = None) -> Path:
    """Return an unused history path such as ``histories/match-seed7.history.json``."""
    directory = directory or Path.cwd() / "histories"
    candidate = directory / f"match-seed{seed}.history.json"
    number = 2
    while candidate.exists():
        candidate = directory / f"match-seed{seed}-{number}.history.json"
        number += 1
    return candidate


def _detached_popen(command: Sequence[str], stdout, stderr) -> subprocess.Popen:
    """Start ``command`` so that it does not die with this process."""
    options: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": stdout,
        "stderr": stderr,
        "close_fds": True,
    }
    if os.name != "nt":
        return subprocess.Popen(command, start_new_session=True, **options)
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        # Also leave a job object the client may be part of (terminals and
        # IDEs often kill a whole job when their window closes).
        return subprocess.Popen(
            command,
            creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB,
            **options,
        )
    except PermissionError:
        # The job does not allow breaking away; detaching is still done.
        return subprocess.Popen(command, creationflags=flags, **options)


class EngineRun:
    """One engine process started by the client and watched through files."""

    def __init__(self, command: Sequence[str], history: Path) -> None:
        self.command = list(command)
        self.history = Path(history)
        base = self.history.name
        self.stdout_path = self.history.with_name(base + ".engine-stdout.json")
        self.stderr_path = self.history.with_name(base + ".engine-stderr.log")
        self.record_path = self.history.with_name(base + ".launch.json")
        self._process: subprocess.Popen | None = None
        self._outcome: EngineOutcome | None = None

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process else None

    def start(self) -> None:
        """Start the engine; raises :class:`LaunchError` if that is impossible."""
        if self._process is not None:
            raise LaunchError("this engine run was already started")
        try:
            self.history.parent.mkdir(parents=True, exist_ok=True)
            with (
                open(self.stdout_path, "wb") as stdout,
                open(self.stderr_path, "wb") as stderr,
            ):
                self._process = _detached_popen(self.command, stdout, stderr)
            # Diagnostic record of what was started and by whom.
            self.record_path.write_text(
                json.dumps(
                    {
                        "command": self.command,
                        "engine_pid": self._process.pid,
                        "client_pid": os.getpid(),
                    }
                ),
                encoding="utf-8",
            )
        except OSError as error:
            raise LaunchError(f"cannot start the engine: {error}") from error

    def poll(self) -> EngineOutcome | None:
        """Return the outcome once the engine has exited, ``None`` while it runs.

        Never blocks.
        """
        if self._outcome is not None:
            return self._outcome
        if self._process is None:
            raise LaunchError("the engine was not started")
        exit_code = self._process.poll()
        if exit_code is None:
            return None
        self._outcome = self._read_outcome(exit_code)
        return self._outcome

    def cancel(self) -> None:
        """Stop a running engine at the user's request."""
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()

    def _read_outcome(self, exit_code: int) -> EngineOutcome:
        reported = self._reported_result()
        if exit_code == ExitCode.OK:
            if reported.get("status") != "ok":
                return EngineOutcome(
                    exit_code, False, "the engine did not report a result", None
                )
            if not self.history.is_file():
                message = f"the engine reported success but {self.history} is missing"
                return EngineOutcome(exit_code, False, message, None)
            return EngineOutcome(exit_code, True, "match finished", self.history)
        try:
            name = ExitCode(exit_code).name.replace("_", " ").lower()
        except ValueError:
            name = "stopped or crashed"
        detail = reported.get("message") or self._stderr_tail()
        message = f"engine exit code {exit_code} ({name})"
        if detail:
            message += f": {detail}"
        return EngineOutcome(exit_code, False, message, None)

    def _reported_result(self) -> dict:
        """The JSON object the engine printed, or ``{}`` if there is none."""
        try:
            text = self.stdout_path.read_text(encoding="utf-8", errors="replace")
            lines = [line for line in text.splitlines() if line.strip()]
            result = json.loads(lines[-1]) if lines else {}
        except (OSError, json.JSONDecodeError):
            return {}
        return result if isinstance(result, dict) else {}

    def _stderr_tail(self) -> str:
        try:
            text = self.stderr_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text.strip()[-STDERR_TAIL_CHARS:]
