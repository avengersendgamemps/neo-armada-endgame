"""Offscreen smoke tests for the desktop shell and the map renderer (L08)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from neon_armada.client.main_window import APP_TITLE, MainWindow
from neon_armada.client.presentation import MatchPresentation
from neon_armada.client.widgets.info_panel import InfoPanel
from neon_armada.client.widgets.map_view import (
    EMPTY_CELL,
    OBSTACLE,
    PLAYER_COLORS,
    MapView,
    energy_color,
)
from neon_armada.contracts.replay import parse_history


@pytest.fixture
def history_path(load_fixture, tmp_path: Path) -> Path:
    path = tmp_path / "fixture.history.json"
    path.write_text(
        json.dumps(load_fixture("contracts/history.valid.json")), encoding="utf-8"
    )
    return path


@pytest.fixture
def presentation(load_fixture) -> MatchPresentation:
    return MatchPresentation(
        parse_history(load_fixture("contracts/history.valid.json"))
    )


def render(view: MapView) -> QImage:
    return view.grab().toImage()


def pixel(view: MapView, image: QImage, x: int, y: int, dx=0.5, dy=0.5) -> int:
    """Return the 0xRRGGBB value drawn at a relative position inside a cell."""
    rect = view.cell_rect(x, y)
    ratio = image.devicePixelRatio()
    color = image.pixelColor(
        int((rect.left() + rect.width() * dx) * ratio),
        int((rect.top() + rect.height() * dy) * ratio),
    )
    return color.rgb() & 0xFFFFFF


def rgb(color: QColor) -> int:
    return color.rgb() & 0xFFFFFF


def test_map_view_draws_every_kind_of_cell(qapp, presentation) -> None:
    view = MapView()
    view.resize(640, 640)
    frame = presentation.frame(1)  # ships have left their bases
    view.set_frame(frame)
    image = render(view)

    assert pixel(view, image, 15, 15) == rgb(EMPTY_CELL)
    assert pixel(view, image, 5, 5) == rgb(OBSTACLE)
    assert pixel(view, image, 10, 2) == rgb(energy_color(350, 350))
    assert pixel(view, image, 4, 4) == rgb(PLAYER_COLORS[0])  # ship of player 0
    assert pixel(view, image, 27, 27) == rgb(PLAYER_COLORS[1])  # ship of player 1
    # Bases: dark fill of the owner's colour with a bright border.
    assert pixel(view, image, 3, 4) == rgb(PLAYER_COLORS[0].darker(250))
    assert pixel(view, image, 28, 27) == rgb(PLAYER_COLORS[1].darker(250))
    assert view.frames_painted >= 1


def test_map_view_shows_energy_depletion_and_cargo(qapp, load_fixture) -> None:
    document = load_fixture("contracts/history.valid.json")
    document["initial_state"]["ships"][0].update(x=10, y=2)
    document["ticks"][0]["events"] = [{"type": "mined", "ship": 0, "amount": 35}]
    document["ticks"][1]["events"] = [{"type": "mined", "ship": 0, "amount": 32}]
    presentation = MatchPresentation(parse_history(document))
    view = MapView()
    view.resize(640, 640)

    view.set_frame(presentation.frame(0))
    before = pixel(view, render(view), 10, 2, 0.15, 0.15)  # deposit corner
    view.set_frame(presentation.frame(2))
    image = render(view)
    after = pixel(view, image, 10, 2, 0.15, 0.15)
    assert before == rgb(energy_color(350, 350))
    assert after == rgb(energy_color(283, 350)) != before
    # The loaded ship shows a cargo gauge (bright centre) on its owner's colour.
    assert pixel(view, image, 10, 2) != rgb(PLAYER_COLORS[0])


def test_map_view_interpolates_ship_positions(qapp, presentation) -> None:
    view = MapView()
    view.resize(640, 640)
    view.set_frame(presentation.frame(0), presentation.frame(1), progress=0.5)
    image = render(view)
    # Ship 0 moves from (3, 4) to (4, 4): halfway it straddles the cell border.
    assert pixel(view, image, 4, 4, dx=0.0) == rgb(PLAYER_COLORS[0])
    assert pixel(view, image, 4, 4, dx=0.9) != rgb(PLAYER_COLORS[0])


def test_map_view_without_a_frame_and_at_tiny_sizes(qapp, presentation) -> None:
    view = MapView()
    view.resize(400, 300)
    assert not render(view).isNull()  # placeholder text, no crash
    view.set_frame(presentation.frame(0))
    view.resize(40, 90)
    assert not render(view).isNull()
    view.set_frame(None)
    assert view.frame is None
    assert not render(view).isNull()


def test_info_panel_shows_frame_statistics(qapp, presentation) -> None:
    panel = InfoPanel()
    panel.set_frame(presentation.frame(2))
    assert panel.tick_label.text() == "Tick 2 / 2"
    assert panel.name_labels[0].text() == "Player 0: alpha"
    assert "Base energy: 500" in panel.stats_labels[0].text()
    assert "Building a ship" in panel.stats_labels[0].text()
    assert "Invalid commands: 1" in panel.stats_labels[1].text()
    assert "Winner: beta" in panel.result_label.text()
    panel.set_frame(None)
    assert panel.tick_label.text() == "No match loaded"
    assert panel.result_label.text() == ""


def test_main_window_starts_empty(qapp) -> None:
    window = MainWindow()
    assert window.windowTitle() == APP_TITLE
    assert window.presentation is None
    assert window.map_view.frame is None
    window.show_tick(3)  # nothing loaded: ignored
    assert not window.grab().isNull()
    window.close()


def test_main_window_opens_a_history(qapp, history_path: Path) -> None:
    window = MainWindow()
    assert window.open_history(history_path) is True
    assert "alpha vs beta" in window.windowTitle()
    assert window.map_view.frame.tick == 0
    assert window.info_panel.tick_label.text() == "Tick 0 / 2"
    window.show_tick(2)
    assert window.info_panel.tick_label.text() == "Tick 2 / 2"
    window.show_tick(999)  # clamped
    assert window.current_tick == 2
    assert window.error_banner.isHidden()
    window.close()


def test_main_window_reports_invalid_files_and_keeps_the_current_match(
    qapp, history_path: Path, tmp_path: Path
) -> None:
    window = MainWindow()
    window.open_history(history_path)
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text(history_path.read_text(encoding="utf-8")[:200], encoding="utf-8")
    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    for bad in (corrupt, empty, tmp_path / "missing.json"):
        assert window.open_history(bad) is False
        assert not window.error_banner.isHidden()
        assert bad.name in window.error_banner.text()
        assert window.presentation is not None  # previous match still shown
    assert window.open_history(history_path) is True
    assert window.error_banner.isHidden()
    window.close()


def run_client(*arguments: str) -> subprocess.CompletedProcess:
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    return subprocess.run(
        [sys.executable, "-m", "neon_armada.client", *arguments],
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
    )


def test_application_starts_and_renders_a_screenshot(history_path, tmp_path) -> None:
    target = tmp_path / "shot.png"
    completed = run_client(
        str(history_path), "--tick", "1", "--screenshot", str(target)
    )
    assert completed.returncode == 0, completed.stderr
    image = QImage(str(target))
    assert not image.isNull() and image.width() >= 800


def test_application_exits_with_error_for_an_invalid_history(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not a history", encoding="utf-8")
    completed = run_client(str(bad), "--screenshot", str(tmp_path / "s.png"))
    assert completed.returncode == 1
