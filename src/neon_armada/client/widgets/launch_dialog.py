"""Dialog for choosing two local agents, a seed and the map size of a new match."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from neon_armada.client.launcher import (
    DEFAULT_MAP_SIZE,
    MAP_SIZE_MAX,
    MAP_SIZE_MIN,
    MAX_SEED,
    MatchRequest,
    default_output_path,
    parse_seed,
    validate_request,
)

AGENT_FILTER = "Agents (*.py *.exe);;All files (*)"
HISTORY_FILTER = "Match histories (*.json);;All files (*)"


class LaunchDialog(QDialog):
    """Collects a :class:`MatchRequest`; accepts only when it is valid."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New match")
        self.setMinimumWidth(560)
        self.request: MatchRequest | None = None

        self.agent_a_edit = QLineEdit()
        self.agent_b_edit = QLineEdit()
        self.seed_edit = QLineEdit("1")
        self.seed_edit.setPlaceholderText(f"integer 0..{MAX_SEED}")
        self.map_size_box = QSpinBox()
        self.map_size_box.setRange(MAP_SIZE_MIN, MAP_SIZE_MAX)
        self.map_size_box.setValue(DEFAULT_MAP_SIZE)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("automatic: histories/match-seed<N>...")

        form = QFormLayout()
        form.addRow("Agent A (player 0)", self._with_browse(self.agent_a_edit, True))
        form.addRow("Agent B (player 1)", self._with_browse(self.agent_b_edit, True))
        form.addRow("Seed", self.seed_edit)
        form.addRow("Map size", self.map_size_box)
        form.addRow("History file", self._with_browse(self.output_edit, False))

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorBanner")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Run match")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(self.buttons)

    def _with_browse(self, edit: QLineEdit, existing_file: bool) -> QWidget:
        button = QPushButton("Browse...")
        if existing_file:
            button.clicked.connect(lambda: self._browse_agent(edit))
        else:
            button.clicked.connect(self._browse_output)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit, 1)
        layout.addWidget(button)
        return row

    def _browse_agent(self, edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose an agent", edit.text(), AGENT_FILTER
        )
        if path:
            edit.setText(path)

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "History file", self.output_edit.text(), HISTORY_FILTER
        )
        if path:
            self.output_edit.setText(path)

    def build_request(self) -> tuple[MatchRequest | None, list[str]]:
        """Return the request described by the fields and its problems."""
        seed = parse_seed(self.seed_edit.text())
        if seed is None:
            return None, [f"Seed must be an integer between 0 and {MAX_SEED}."]
        output_text = self.output_edit.text().strip()
        request = MatchRequest(
            agent_a=Path(self.agent_a_edit.text().strip()),
            agent_b=Path(self.agent_b_edit.text().strip()),
            seed=seed,
            output=Path(output_text) if output_text else default_output_path(seed),
            map_size=self.map_size_box.value(),
        )
        return request, validate_request(request)

    def accept(self) -> None:
        """Close with a valid request, or stay open and show what is wrong."""
        request, problems = self.build_request()
        if problems:
            self.error_label.setText("\n".join(problems))
            self.error_label.show()
            return
        self.request = request
        super().accept()
