"""Main window of the desktop client: menu, map, statistics and replay controls."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from neon_armada.client.presentation import MatchPresentation
from neon_armada.client.replay import ReplayController
from neon_armada.client.widgets.info_panel import InfoPanel
from neon_armada.client.widgets.map_view import MapView
from neon_armada.client.widgets.replay_controls import ReplayControls
from neon_armada.contracts.history import HistoryError

APP_TITLE = "Neon Armada: Endgame"
FRAME_INTERVAL_MS = 16  # playback repaint period, about 60 frames per second
STYLE = """
QMainWindow, QWidget { background-color: #0b0f1a; color: #d7def5; }
QMenuBar, QMenu, QStatusBar { background-color: #131a2b; color: #d7def5; }
QMenu::item:selected, QMenuBar::item:selected { background-color: #24304f; }
QLabel#errorBanner { background-color: #5c1a2b; color: #ffd7df; padding: 6px; }
QPushButton { background-color: #1b2540; border: 1px solid #2c3a63; padding: 5px 10px; }
QPushButton:hover { background-color: #24304f; }
QPushButton:checked { background-color: #00a5b8; color: #0b0f1a; }
QPushButton:disabled, QLabel:disabled { color: #5a6078; }
"""


class MainWindow(QMainWindow):
    """Loads a match history and shows it; never talks to engine code."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setStyleSheet(STYLE)
        self.resize(1000, 760)
        self.presentation: MatchPresentation | None = None
        self.replay = ReplayController()
        self._shown_tick: int | None = None
        self._last_advance = 0.0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(FRAME_INTERVAL_MS)
        self._timer.timeout.connect(self._on_timer)

        self.error_banner = QLabel("")
        self.error_banner.setObjectName("errorBanner")
        self.error_banner.setWordWrap(True)
        self.error_banner.hide()
        self.map_view = MapView()
        self.info_panel = InfoPanel()
        self.controls = ReplayControls()
        self.controls.play_toggled.connect(self.toggle_playback)
        self.controls.step_requested.connect(self.step_forward)
        self.controls.speed_selected.connect(self.set_speed)
        self.controls.seek_requested.connect(self.show_tick)

        content = QHBoxLayout()
        content.addWidget(self.map_view, 1)
        content.addWidget(self.info_panel)
        self.central_layout = QVBoxLayout()
        self.central_layout.addWidget(self.error_banner)
        self.central_layout.addLayout(content, 1)
        self.central_layout.addWidget(self.controls)
        central = QWidget()
        central.setLayout(self.central_layout)
        self.setCentralWidget(central)

        self.file_menu = self.menuBar().addMenu("&File")
        open_action = QAction("&Open history...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.choose_history)
        self.file_menu.addAction(open_action)
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        self.file_menu.addAction(quit_action)
        self.playback_menu = self.menuBar().addMenu("&Playback")
        play_action = QAction("&Play / Pause", self)
        play_action.setShortcut(QKeySequence(Qt.Key.Key_Space))
        play_action.triggered.connect(self.toggle_playback)
        self.playback_menu.addAction(play_action)
        step_action = QAction("&Next tick", self)
        step_action.setShortcut(QKeySequence(Qt.Key.Key_N))
        step_action.triggered.connect(self.step_forward)
        self.playback_menu.addAction(step_action)
        self.statusBar().showMessage("Open a match history to begin (File > Open).")

    # -- loading ----------------------------------------------------------------

    def choose_history(self) -> None:
        """Ask for a history file and open it."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open match history",
            "",
            "Match histories (*.json);;All files (*)",
        )
        if path:
            self.open_history(path)

    def open_history(self, path: str | Path) -> bool:
        """Load ``path`` and show it paused at tick 0.

        On failure the current match and its playback are kept and the error
        is shown.
        """
        try:
            presentation = MatchPresentation.from_file(path)
        except HistoryError as error:
            self.show_error(f"Cannot open {Path(path).name}: {error}")
            return False
        self.clear_error()
        self.presentation = presentation
        self.setWindowTitle(f"{APP_TITLE} - {presentation.title}")
        self.statusBar().showMessage(f"Loaded {path}")
        self.replay.load(presentation.last_tick)
        self._shown_tick = None
        self._refresh()
        return True

    # -- playback ---------------------------------------------------------------

    @property
    def current_tick(self) -> int:
        return self.replay.tick

    def show_tick(self, tick: int) -> None:
        """Seek to the state after ``tick`` ticks (clamped to the match)."""
        if self.presentation is None:
            return
        self.replay.seek(tick)
        self._refresh()

    def toggle_playback(self) -> None:
        if self.presentation is None:
            return
        self.replay.toggle()
        self._refresh()

    def step_forward(self) -> None:
        """Pause and show the next tick."""
        if self.presentation is None:
            return
        self.replay.step()
        self._refresh()

    def set_speed(self, speed: int) -> None:
        self.replay.set_speed(speed)
        self._refresh()

    def advance_playback(self, elapsed_seconds: float) -> None:
        """Move playback forward by wall-clock time and redraw."""
        if self.replay.advance(elapsed_seconds):
            self._refresh()

    def _on_timer(self) -> None:
        now = time.perf_counter()
        elapsed, self._last_advance = now - self._last_advance, now
        self.advance_playback(elapsed)

    def _refresh(self) -> None:
        """Bring timer and widgets in line with the replay controller."""
        if self.replay.playing and not self._timer.isActive():
            self._last_advance = time.perf_counter()
            self._timer.start()
        elif not self.replay.playing and self._timer.isActive():
            self._timer.stop()
        self.controls.set_state(
            self.replay.tick,
            self.replay.last_tick,
            playing=self.replay.playing,
            speed=self.replay.speed,
            loaded=self.presentation is not None,
        )
        if self.presentation is None:
            return
        tick, progress = self.replay.tick, self.replay.progress
        frame = self.presentation.frame(tick)
        upcoming = self.presentation.frame(tick + 1) if progress > 0.0 else None
        self.map_view.set_frame(frame, upcoming, progress)
        if tick != self._shown_tick:
            self.info_panel.set_frame(frame)
            self._shown_tick = tick

    # -- errors -----------------------------------------------------------------

    def show_error(self, message: str) -> None:
        self.error_banner.setText(message)
        self.error_banner.show()
        self.statusBar().showMessage(message)

    def clear_error(self) -> None:
        self.error_banner.hide()
        self.error_banner.setText("")
