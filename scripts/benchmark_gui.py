"""Measure the replay frame rate of the desktop client.

Usage::

    python scripts/benchmark_gui.py HISTORY [HISTORY ...] [--seconds 10]
        [--speed 4] [--width 1000] [--height 760]

Each history is opened in the real main window and played in a loop for the
given time. Every repaint of the map is timestamped; one JSON line per history
is printed with the average rate and the minimum rate, both over one-second
windows and as the single slowest frame. Playback repaints on a 16 ms timer,
so about 60 frames per second is the upper bound.

The numbers depend on the machine and on the Qt platform plugin: set
``QT_QPA_PLATFORM=offscreen`` to measure without a display (no GPU, no
compositor) and leave it unset to measure a real window.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from neon_armada.client.main_window import MainWindow


def measure(path: str, seconds: float, speed: int, width: int, height: int) -> dict:
    """Play ``path`` for ``seconds`` and return the measured frame statistics."""
    app = QApplication.instance()
    window = MainWindow()
    window.resize(width, height)
    if not window.open_history(path):
        return {"history": path, "error": window.error_banner.text()}
    window.show()
    app.processEvents()
    window.set_speed(speed)
    log: list[float] = []
    window.map_view.paint_log = log

    def keep_playing() -> None:
        if not window.replay.playing:
            window.show_tick(0)
            window.toggle_playback()

    keeper = QTimer()
    keeper.setInterval(50)
    keeper.timeout.connect(keep_playing)
    keep_playing()
    keeper.start()
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.0005)
    keeper.stop()
    window.map_view.paint_log = None
    frame = window.map_view.frame
    map_view_size = [window.map_view.width(), window.map_view.height()]
    window.close()

    if len(log) < 2:
        return {"history": path, "error": "fewer than two frames were painted"}
    intervals = [after - before for before, after in zip(log, log[1:], strict=False)]
    elapsed = log[-1] - log[0]
    per_second: dict[int, int] = {}
    for stamp in log:
        bucket = int(stamp - log[0])
        per_second[bucket] = per_second.get(bucket, 0) + 1
    whole_seconds = [per_second.get(i, 0) for i in range(int(elapsed))]
    return {
        "history": path,
        "map_size": frame.size,
        "ticks": frame.last_tick,
        "speed": speed,
        "map_view_pixels": map_view_size,
        "seconds": round(elapsed, 3),
        "frames": len(log),
        "fps_average": round(len(intervals) / elapsed, 1),
        "fps_min_one_second_window": min(whole_seconds) if whole_seconds else None,
        "fps_min_slowest_frame": round(1.0 / max(intervals), 1),
        "slowest_frame_ms": round(max(intervals) * 1000, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("histories", nargs="+", help="history files to play")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--speed", type=int, default=4, choices=(1, 2, 4))
    parser.add_argument("--width", type=int, default=1000)
    parser.add_argument("--height", type=int, default=760)
    arguments = parser.parse_args()
    app = QApplication(sys.argv[:1])
    environment = {
        "qt_platform": QGuiApplication.platformName(),
        "pyside": pyside_version,
        "python": platform.python_version(),
        "os": platform.platform(),
        "processor": platform.processor(),
        "screen_hz": app.primaryScreen().refreshRate() if app.primaryScreen() else None,
    }
    print(json.dumps({"environment": environment}))
    failed = False
    for path in arguments.histories:
        result = measure(
            path, arguments.seconds, arguments.speed, arguments.width, arguments.height
        )
        failed = failed or "error" in result
        print(json.dumps(result), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
