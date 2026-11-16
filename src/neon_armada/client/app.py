"""Application entry point of the desktop client.

``python -m neon_armada.client [HISTORY] [--tick N] [--screenshot PNG]``

``python -m neon_armada.client --agent-a A --agent-b B --seed N [--map-size S]
[--output FILE]`` starts that match right away, as File > New match would.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from neon_armada.client.launcher import (
    DEFAULT_MAP_SIZE,
    MatchRequest,
    default_output_path,
    parse_seed,
)
from neon_armada.client.main_window import MainWindow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m neon_armada.client",
        description="Neon Armada desktop client: match history viewer and replay.",
    )
    parser.add_argument("history", nargs="?", help="history file to open at start")
    parser.add_argument("--tick", type=int, default=0, help="tick to show first")
    parser.add_argument(
        "--screenshot",
        metavar="PNG",
        help="render the window to an image file and exit (works headless)",
    )
    launch = parser.add_argument_group("start a match at once")
    launch.add_argument("--agent-a", help="agent program of player 0")
    launch.add_argument("--agent-b", help="agent program of player 1")
    launch.add_argument("--seed", help="integer map seed")
    launch.add_argument("--map-size", type=int, default=DEFAULT_MAP_SIZE)
    launch.add_argument("--output", help="history file to write")
    return parser


def launch_request(arguments: argparse.Namespace) -> MatchRequest | None:
    """Return the match asked for on the command line, if any."""
    if not (arguments.agent_a or arguments.agent_b or arguments.seed):
        return None
    seed = parse_seed(arguments.seed or "")
    if not (arguments.agent_a and arguments.agent_b) or seed is None:
        raise SystemExit("--agent-a, --agent-b and an integer --seed go together")
    output = Path(arguments.output) if arguments.output else default_output_path(seed)
    return MatchRequest(
        agent_a=Path(arguments.agent_a),
        agent_b=Path(arguments.agent_b),
        seed=seed,
        output=output,
        map_size=arguments.map_size,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Start the client; return the process exit code."""
    arguments = build_parser().parse_args(argv)
    request = launch_request(arguments)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = MainWindow()
    loaded = True
    if arguments.history:
        loaded = window.open_history(arguments.history)
        if loaded:
            window.show_tick(arguments.tick)
    if arguments.screenshot:
        window.show()
        app.processEvents()
        saved = window.grab().save(arguments.screenshot)
        window.close()
        return 0 if loaded and saved else 1
    if request is not None:
        window.launch_match(request)
    window.show()
    return app.exec()
