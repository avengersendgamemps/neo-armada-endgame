"""Side panel with tick, player statistics, events and the final result."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from neon_armada.client.presentation import FrameView, PlayerView

PLAYER_HEX = ("#00e5ff", "#ff3d81")
MAX_EVENT_LINES = 8


def player_text(player: PlayerView) -> str:
    """Return the statistics block of one player as plain text."""
    lines = [
        f"Base energy: {player.reserve}",
        f"Ships: {player.ships}   Carried: {player.carried}",
        f"Move budget: {player.move_budget}",
        f"Invalid commands: {player.invalid_commands}",
    ]
    if player.pending_build:
        lines.append("Building a ship...")
    if player.excluded:
        lines.append(f"EXCLUDED: {player.excluded}")
    return "\n".join(lines)


class InfoPanel(QWidget):
    """Shows the textual part of a :class:`FrameView`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(260)
        layout = QVBoxLayout(self)
        self.tick_label = QLabel("No match loaded")
        self.tick_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.tick_label)
        self.name_labels: list[QLabel] = []
        self.stats_labels: list[QLabel] = []
        for color in PLAYER_HEX:
            name = QLabel("")
            name.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px;")
            stats = QLabel("")
            self.name_labels.append(name)
            self.stats_labels.append(stats)
            layout.addWidget(self._separator())
            layout.addWidget(name)
            layout.addWidget(stats)
        layout.addWidget(self._separator())
        self.events_label = QLabel("")
        self.events_label.setWordWrap(True)
        self.events_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.events_label)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-weight: bold; color: #f5e663;")
        layout.addWidget(self.result_label)
        layout.addStretch(1)

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def set_frame(self, frame: FrameView | None) -> None:
        if frame is None:
            self.tick_label.setText("No match loaded")
            for label in (*self.name_labels, *self.stats_labels):
                label.setText("")
            self.events_label.setText("")
            self.result_label.setText("")
            return
        self.tick_label.setText(f"Tick {frame.tick} / {frame.last_tick}")
        for index, player in enumerate(frame.players):
            self.name_labels[index].setText(f"Player {index}: {player.name}")
            self.stats_labels[index].setText(player_text(player))
        events = list(frame.event_summary)
        if len(events) > MAX_EVENT_LINES:
            hidden = len(events) - MAX_EVENT_LINES + 1
            events = events[: MAX_EVENT_LINES - 1] + [f"... and {hidden} more"]
        self.events_label.setText("\n".join(events))
        self.result_label.setText(frame.result_text or "")
