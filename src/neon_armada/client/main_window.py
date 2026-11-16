"""Main window of the desktop client: menu, map view and information panel."""

from __future__ import annotations

from pathlib import Path

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
from neon_armada.client.widgets.info_panel import InfoPanel
from neon_armada.client.widgets.map_view import MapView
from neon_armada.contracts.history import HistoryError

APP_TITLE = "Neon Armada: Endgame"
STYLE = """
QMainWindow, QWidget { background-color: #0b0f1a; color: #d7def5; }
QMenuBar, QMenu, QStatusBar { background-color: #131a2b; color: #d7def5; }
QMenu::item:selected, QMenuBar::item:selected { background-color: #24304f; }
QLabel#errorBanner { background-color: #5c1a2b; color: #ffd7df; padding: 6px; }
"""


class MainWindow(QMainWindow):
    """Loads a match history and shows it; never talks to engine code."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setStyleSheet(STYLE)
        self.resize(1000, 760)
        self.presentation: MatchPresentation | None = None
        self.current_tick = 0

        self.error_banner = QLabel("")
        self.error_banner.setObjectName("errorBanner")
        self.error_banner.setWordWrap(True)
        self.error_banner.hide()
        self.map_view = MapView()
        self.info_panel = InfoPanel()

        content = QHBoxLayout()
        content.addWidget(self.map_view, 1)
        content.addWidget(self.info_panel)
        self.central_layout = QVBoxLayout()
        self.central_layout.addWidget(self.error_banner)
        self.central_layout.addLayout(content, 1)
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
        """Load ``path``; on failure keep the current match and show the error."""
        try:
            presentation = MatchPresentation.from_file(path)
        except HistoryError as error:
            self.show_error(f"Cannot open {Path(path).name}: {error}")
            return False
        self.clear_error()
        self.presentation = presentation
        self.setWindowTitle(f"{APP_TITLE} - {presentation.title}")
        self.statusBar().showMessage(f"Loaded {path}")
        self.show_tick(0)
        return True

    # -- display ----------------------------------------------------------------

    def show_tick(self, tick: int) -> None:
        """Display the state after ``tick`` ticks (clamped to the match)."""
        if self.presentation is None:
            return
        self.current_tick = self.presentation.clamp(tick)
        frame = self.presentation.frame(self.current_tick)
        self.map_view.set_frame(frame)
        self.info_panel.set_frame(frame)

    def show_error(self, message: str) -> None:
        self.error_banner.setText(message)
        self.error_banner.show()
        self.statusBar().showMessage(message)

    def clear_error(self) -> None:
        self.error_banner.hide()
        self.error_banner.setText("")
