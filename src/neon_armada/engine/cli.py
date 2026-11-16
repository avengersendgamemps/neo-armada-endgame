"""Command-line interface of the engine (``contracts/engine-cli.md``, v1).

``python -m neon_armada.engine run --agent-a A --agent-b B --seed N --output F``
``python -m neon_armada.engine validate HISTORY``
``python -m neon_armada.engine compare HISTORY_A HISTORY_B``
``python -m neon_armada.engine check-determinism --agent-a A --agent-b B --seed N``

stdout carries exactly one JSON line; diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from neon_armada.contracts.cli import ENGINE_MODULE, ExitCode
from neon_armada.contracts.history import HistoryError
from neon_armada.contracts.models import MAX_SEED, ContractError, MatchConfig
from neon_armada.contracts.replay import (
    Comparison,
    History,
    compare_histories,
    first_invalid_tick,
    load_history,
)
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

    validate = commands.add_parser(
        "validate", help="reconstruct a history and check every fingerprint"
    )
    validate.add_argument("history", help="history file")

    compare = commands.add_parser(
        "compare", help="report the first tick where two histories differ"
    )
    compare.add_argument("history_a", help="first history file")
    compare.add_argument("history_b", help="second history file")

    check = commands.add_parser(
        "check-determinism", help="play the same match twice and compare the runs"
    )
    add_match_arguments(check)
    check.add_argument("--output-dir", help="keep both histories in this directory")
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


def read_history(raw: str) -> History:
    try:
        return load_history(raw)
    except HistoryError as error:
        raise CliError(ExitCode.HISTORY_INVALID, str(error)) from error


def comparison_result(comparison: Comparison) -> tuple[ExitCode, dict[str, Any]]:
    code = ExitCode.OK if comparison.identical else ExitCode.DIFFERENT
    return code, {
        "identical": comparison.identical,
        "first_divergent_tick": comparison.first_divergent_tick,
        "detail": comparison.detail,
    }


def command_validate(arguments: argparse.Namespace) -> tuple[ExitCode, dict[str, Any]]:
    history = read_history(arguments.history)
    bad_tick = first_invalid_tick(history)
    if bad_tick is None:
        return ExitCode.OK, {"valid": True, "ticks": len(history.ticks)}
    return ExitCode.DIFFERENT, {
        "valid": False,
        "ticks": len(history.ticks),
        "first_invalid_tick": bad_tick,
    }


def command_compare(arguments: argparse.Namespace) -> tuple[ExitCode, dict[str, Any]]:
    first = read_history(arguments.history_a)
    second = read_history(arguments.history_b)
    return comparison_result(compare_histories(first, second))


def command_check_determinism(
    arguments: argparse.Namespace,
) -> tuple[ExitCode, dict[str, Any]]:
    """Play the match twice, store both histories and compare them as files."""
    with tempfile.TemporaryDirectory(prefix="neon-armada-") as scratch:
        directory = Path(arguments.output_dir or scratch)
        paths = [directory / f"run{index}.history.json" for index in (1, 2)]
        for path in paths:
            save(play(arguments), path)
        code, payload = comparison_result(
            compare_histories(read_history(str(paths[0])), read_history(str(paths[1])))
        )
    if arguments.output_dir:
        payload["histories"] = [str(path) for path in paths]
    return code, payload


COMMANDS = {
    "run": command_run,
    "validate": command_validate,
    "compare": command_compare,
    "check-determinism": command_check_determinism,
}


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
