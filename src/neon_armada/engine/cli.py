"""Command-line interface of the engine (``contracts/engine-cli.md``, v1).

``python -m neon_armada.engine run --agent-a A --agent-b B --seed N --output F``

stdout carries exactly one JSON line; diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from neon_armada.contracts.cli import ENGINE_MODULE, ExitCode
from neon_armada.contracts.models import MAX_SEED, ContractError, MatchConfig
from neon_armada.contracts.versions import CLI_VERSION
from neon_armada.engine.agents.runtime import AgentRuntime, launch_command
from neon_armada.engine.history.writer import write_history
from neon_armada.engine.match import MatchRecord, run_match
from neon_armada.engine.world.generator import MapGenerationError

logger = logging.getLogger(__name__)

_CONFIG_OPTIONS = (
    ("--map-size", "map_size", "map side, 32..64"),
    ("--max-ticks", "max_ticks", "tick limit, 1..500"),
    ("--move-budget", "move_budget", "move commands per player"),
    ("--tick-timeout-ms", "tick_timeout_ms", "per-tick agent time limit"),
    ("--init-timeout-ms", "init_timeout_ms", "agent initialisation time limit"),
    ("--memory-limit-mb", "memory_limit_mb", "agent memory limit"),
)


class CliError(Exception):
    """A failure with a contract exit code and a message for the user."""

    def __init__(self, code: ExitCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CliError(ExitCode.USAGE, message)


def add_match_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the options shared by every command that plays a match."""
    parser.add_argument("--agent-a", required=True, help="agent program of player 0")
    parser.add_argument("--agent-b", required=True, help="agent program of player 1")
    parser.add_argument("--seed", required=True, type=int, help="integer map seed")
    parser.add_argument("--name-a", help="display name of player 0")
    parser.add_argument("--name-b", help="display name of player 1")
    for flag, _field, text in _CONFIG_OPTIONS:
        parser.add_argument(flag, type=int, help=text)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog=f"python -m {ENGINE_MODULE}",
        description="Neon Armada headless simulation engine.",
    )
    commands = parser.add_subparsers(dest="command", parser_class=_Parser)
    run = commands.add_parser("run", help="play one match and write its history")
    add_match_arguments(run)
    run.add_argument("--output", required=True, help="history file to write")
    return parser


def config_from_arguments(arguments: argparse.Namespace) -> MatchConfig:
    """Build the match configuration; out-of-range values are usage errors."""
    overrides = {
        field: getattr(arguments, field)
        for _flag, field, _text in _CONFIG_OPTIONS
        if getattr(arguments, field) is not None
    }
    try:
        return MatchConfig(**overrides)
    except ContractError as error:
        raise CliError(ExitCode.USAGE, str(error)) from error


def resolve_agent(raw: str) -> Path:
    """Return the absolute agent path or raise ``AGENT_NOT_FOUND``."""
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise CliError(ExitCode.AGENT_NOT_FOUND, f"agent not found: {raw}")
    return path


def play(arguments: argparse.Namespace) -> MatchRecord:
    """Validate the match arguments and play the match."""
    config = config_from_arguments(arguments)
    if not 0 <= arguments.seed <= MAX_SEED:
        raise CliError(ExitCode.USAGE, f"seed must be in 0..{MAX_SEED}")
    paths = (resolve_agent(arguments.agent_a), resolve_agent(arguments.agent_b))
    names = (arguments.name_a or paths[0].stem, arguments.name_b or paths[1].stem)
    agents = [
        AgentRuntime(player, launch_command(path), config, cwd=path.parent)
        for player, path in enumerate(paths)
    ]
    try:
        return run_match(config, arguments.seed, agents, names)
    except MapGenerationError as error:
        raise CliError(ExitCode.MAP_GENERATION_FAILED, str(error)) from error


def save(record: MatchRecord, output: Path) -> None:
    try:
        write_history(record, output)
    except OSError as error:
        raise CliError(
            ExitCode.OUTPUT_ERROR, f"cannot write history {output}: {error}"
        ) from error


def timing_dict(record: MatchRecord) -> dict[str, Any]:
    return {
        "total_ms": record.timing.total_ms,
        "agent_wait_ms": list(record.timing.agent_wait_ms),
        "engine_ms": record.timing.engine_ms,
    }


def command_run(arguments: argparse.Namespace) -> tuple[ExitCode, dict[str, Any]]:
    output = Path(arguments.output)
    record = play(arguments)
    save(record, output)
    return ExitCode.OK, {
        "history": str(output),
        "result": record.result.to_dict(),
        "timing": timing_dict(record),
    }


COMMANDS = {"run": command_run}


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    logging.basicConfig(
        stream=sys.stderr, level=logging.WARNING, format="%(levelname)s %(message)s"
    )
    try:
        arguments = build_parser().parse_args(argv)
        if arguments.command is None:
            raise CliError(ExitCode.USAGE, "a command is required (try --help)")
        code, payload = COMMANDS[arguments.command](arguments)
    except CliError as error:
        print(f"error: {error.message}", file=sys.stderr)
        _emit(
            {
                "status": "error",
                "cli_version": CLI_VERSION,
                "code": int(error.code),
                "message": error.message,
            }
        )
        return int(error.code)
    except Exception as error:  # last-resort guard: report and exit with 70
        logger.exception("internal engine error")
        _emit(
            {
                "status": "error",
                "cli_version": CLI_VERSION,
                "code": int(ExitCode.INTERNAL_ERROR),
                "message": f"internal error: {error}",
            }
        )
        return int(ExitCode.INTERNAL_ERROR)
    _emit({"status": "ok", "cli_version": CLI_VERSION, **payload})
    return int(code)
