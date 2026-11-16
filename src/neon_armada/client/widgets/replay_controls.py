"""Replay transport bar: Play/Pause, next tick, speed buttons and the timeline."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)

from neon_armada.client.replay import SPEEDS


class ReplayControls(QWidget):
    """Emits what the user asks for; holds no playback state of its own."""

    play_toggled = Signal()
    step_requested = Signal()
    speed_selected = Signal(int)
    seek_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.play_button = QPushButton("Play")
        self.play_button.setMinimumWidth(72)
        self.play_button.clicked.connect(self.play_toggled)
        layout.addWidget(self.play_button)

        self.step_button = QPushButton("Next tick")
        self.step_button.clicked.connect(self.step_requested)
        layout.addWidget(self.step_button)

        self.speed_buttons: dict[int, QPushButton] = {}
        self._speed_group = QButtonGroup(self)
        self._speed_group.setExclusive(True)
        for speed in SPEEDS:
            button = QPushButton(f"x{speed}")
            button.setCheckable(True)
            button.setMaximumWidth(48)
            self._speed_group.addButton(button, speed)
            self.speed_buttons[speed] = button
            layout.addWidget(button)
        self.speed_buttons[SPEEDS[0]].setChecked(True)
        self._speed_group.idClicked.connect(self.speed_selected)

        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 0)
        self.timeline.setPageStep(10)
        self.timeline.valueChanged.connect(self.seek_requested)
        layout.addWidget(self.timeline, 1)

        self.position_label = QLabel("- / -")
        self.position_label.setMinimumWidth(80)
        self.position_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.position_label)

        self.set_state(0, 0, playing=False, speed=SPEEDS[0], loaded=False)

    def set_state(
        self, tick: int, last_tick: int, *, playing: bool, speed: int, loaded: bool
    ) -> None:
        """Show the given playback state without emitting any signal."""
        playable = loaded and last_tick > 0
        self.play_button.setText("Pause" if playing else "Play")
        self.play_button.setEnabled(playable)
        self.step_button.setEnabled(playable and tick < last_tick)
        self.timeline.setEnabled(playable)
        for value, button in self.speed_buttons.items():
            button.setEnabled(loaded)
            button.setChecked(value == speed)
        with QSignalBlocker(self.timeline):
            self.timeline.setRange(0, last_tick)
            self.timeline.setValue(tick)
        self.position_label.setText(f"{tick} / {last_tick}" if loaded else "- / -")
