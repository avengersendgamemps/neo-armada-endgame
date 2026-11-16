"""Main window of the desktop client: menu, map, statistics, replay and launch."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from neon_armada.client.launcher import (
    EngineRun,
    LaunchError,
    MatchRequest,
    build_command,
    validate_request,
)
from neon_armada.client.presentation import MatchPresentation
from neon_armada.client.replay import ReplayController
from neon_armada.client.widgets.info_panel import InfoPanel
from neon_armada.client.widgets.launch_dialog import LaunchDialog
from neon_armada.client.widgets.map_view import MapView
from neon_armada.client.widgets.replay_controls import ReplayControls
from neon_armada.contracts.history import HistoryError

APP_TITLE = "Neon Armada: Endgame"
FRAME_INTERVAL_MS = 16  # playback repaint period, about 60 frames per second
ENGINE_POLL_MS = 100  # how often a running engine process is checked
STYLE = """
QMainWindow, QWidget { background-color: #0b0f1a; color: #d7def5; }
QMenuBar, QMenu, QStatusBar { background-color: #131a2b; color: #d7def5; }
QMenu::item:selected, QMenuBar::item:selected { background-color: #24304f; }
QLabel#errorBanner { background-color: #5c1a2b; color: #ffd7df; padding: 6px; }
QPushButton { background-color: #1b2540; border: 1px solid #2c3a63; padding: 5px 10px; }
QPushButton:hover { background-color: #24304f; }
QPushButton:checked { background-color: #00a5b8; color: #0b0f1a; }
QPushButton:disabled, QLabel:disabled { color: #5a6078; }
QLineEdit, QSpinBox { background-color: #131a2b; border: 1px solid #2c3a63; }
"""


class MainWindow(QMainWindow):
    """Shows match histories and starts matches; never calls engine code.

    A match is run by a separate engine process (see ``client.launcher``) that
    is only observed through its exit code and files. Closing this window
    while a match is running leaves that process alone.
    """

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
        self.engine_run: EngineRun | None = None
        self.command_builder = build_command  # replaceable in tests
        self._engine_started = 0.0
        self._engine_timer = QTimer(self)
        self._engine_timer.setInterval(ENGINE_POLL_MS)
        self._engine_timer.timeout.connect(self._poll_engine)

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
        self.new_match_action = QAction("&New match...", self)
        self.new_match_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_match_action.triggered.connect(self.choose_match)
        self.file_menu.addAction(self.new_match_action)
        self.cancel_match_action = QAction("&Cancel running match", self)
        self.cancel_match_action.setEnabled(False)
        self.cancel_match_action.triggered.connect(self.cancel_match)
        self.file_menu.addAction(self.cancel_match_action)
        self.file_menu.addSeparator()
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
        self.statusBar().showMessage(
            "Start a match (File > New match) or open a history (File > Open)."
        )

    # -- launching --------------------------------------------------------------

    @property
    def match_running(self) -> bool:
        return self.engine_run is not None

    def choose_match(self) -> None:
        """Ask for two agents and a seed, then start the match."""
        dialog = LaunchDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.request:
            self.launch_match(dialog.request)

    def launch_match(self, request: MatchRequest) -> bool:
        """Start the engine for ``request`` as a separate process.

        Returns immediately; the result is picked up by a timer and the
        history is opened when the engine has finished.
        """
        if self.match_running:
            self.show_error("A match is already running.")
            return False
        problems = validate_request(request)
        if problems:
            self.show_error("Cannot start the match: " + " ".join(problems))
            return False
        run = EngineRun(self.command_builder(request), request.output)
        try:
            run.start()
        except LaunchError as error:
            self.show_error(str(error))
            return False
        self.clear_error()
        self.engine_run = run
        self._engine_started = time.perf_counter()
        self.new_match_action.setEnabled(False)
        self.cancel_match_action.setEnabled(True)
        self.statusBar().showMessage(f"Match running (seed {request.seed})...")
        self._engine_timer.start()
        return True

    def cancel_match(self) -> None:
        """Stop the running engine process; reported like any other failure."""
        if self.engine_run is not None:
            self.engine_run.cancel()

    def _poll_engine(self) -> None:
        run = self.engine_run
        if run is None:
            self._engine_timer.stop()
            return
        outcome = run.poll()
        if outcome is None:
            seconds = time.perf_counter() - self._engine_started
            self.statusBar().showMessage(f"Match running... {seconds:.0f} s")
            return
        self._engine_timer.stop()
        self.engine_run = None
        self.new_match_action.setEnabled(True)
        self.cancel_match_action.setEnabled(False)
        if outcome.succeeded and outcome.history is not None:
            self.open_history(outcome.history)
        else:
            self.show_error(f"Match failed: {outcome.message}")

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
