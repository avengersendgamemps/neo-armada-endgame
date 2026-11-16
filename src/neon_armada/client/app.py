"""Application entry point of the desktop client.

``python -m neon_armada.client [HISTORY] [--tick N] [--screenshot PNG]``
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from neon_armada.client.main_window import MainWindow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m neon_armada.client",
        description="Neon Armada desktop client: match history viewer.",
    )
    parser.add_argument("history", nargs="?", help="history file to open at start")
    parser.add_argument("--tick", type=int, default=0, help="tick to show first")
    parser.add_argument(
        "--screenshot",
        metavar="PNG",
        help="render the window to an image file and exit (works headless)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the client; return the process exit code."""
    arguments = build_parser().parse_args(argv)
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
    window.show()
    return app.exec()
