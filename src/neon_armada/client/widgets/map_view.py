"""2D map widget: terrain, energy deposits, bases and ships of one frame."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from neon_armada.client.presentation import FrameView, ShipView

BACKGROUND = QColor("#0b0f1a")
EMPTY_CELL = QColor("#131a2b")
OBSTACLE = QColor("#5a6078")
GRID_LINE = QColor("#1c2540")
ENERGY_LOW = QColor("#0f3b3a")
ENERGY_HIGH = QColor("#f5e663")
COLLISION = QColor("#ff8a00")
PLAYER_COLORS = (QColor("#00e5ff"), QColor("#ff3d81"))
SHIP_CAPACITY = 100


def energy_color(amount: int, maximum: int) -> QColor:
    """Blend from dark teal to bright yellow with the amount of energy."""
    share = max(0.0, min(1.0, amount / max(1, maximum)))
    share = 0.25 + 0.75 * share  # keep nearly empty deposits visible
    return QColor(
        round(ENERGY_LOW.red() + (ENERGY_HIGH.red() - ENERGY_LOW.red()) * share),
        round(ENERGY_LOW.green() + (ENERGY_HIGH.green() - ENERGY_LOW.green()) * share),
        round(ENERGY_LOW.blue() + (ENERGY_HIGH.blue() - ENERGY_LOW.blue()) * share),
    )


class MapView(QWidget):
    """Draws a :class:`FrameView`; knows nothing about histories or rules.

    ``set_frame`` may also receive the following frame and a progress value in
    ``[0, 1)``; ships are then drawn between their two positions, which gives
    smooth motion during playback.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self._frame: FrameView | None = None
        self._next: FrameView | None = None
        self._progress = 0.0
        self._terrain: QPixmap | None = None
        self._terrain_key: tuple | None = None
        self.frames_painted = 0

    def set_frame(
        self,
        frame: FrameView | None,
        next_frame: FrameView | None = None,
        progress: float = 0.0,
    ) -> None:
        self._frame = frame
        self._next = next_frame
        self._progress = max(0.0, min(1.0, progress))
        self.update()

    @property
    def frame(self) -> FrameView | None:
        return self._frame

    # -- geometry -------------------------------------------------------------

    def cell_rect(self, x: int, y: int) -> QRectF:
        """Return the widget rectangle of map cell ``(x, y)``."""
        cell, left, top = self._geometry()
        return QRectF(left + x * cell, top + y * cell, cell, cell)

    def _geometry(self) -> tuple[float, float, float]:
        size = self._frame.size if self._frame else 1
        side = min(self.width(), self.height())
        cell = side / size
        return cell, (self.width() - side) / 2, (self.height() - side) / 2

    # -- painting -------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.fillRect(self.rect(), BACKGROUND)
        if self._frame is None:
            painter.setPen(QColor("#8f9bbd"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Open a match history"
            )
            painter.end()
            return
        frame = self._frame
        cell, left, top = self._geometry()
        painter.drawPixmap(0, 0, self._terrain_pixmap(frame))
        self._paint_energy(painter, frame, cell, left, top)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, cell >= 6)
        self._paint_collisions(painter, frame, cell, left, top)
        self._paint_ships(painter, frame, cell, left, top)
        painter.end()
        self.frames_painted += 1

    def _terrain_pixmap(self, frame: FrameView) -> QPixmap:
        """Static layer (cells, obstacles, grid, bases), cached per map and size."""
        key = (id(frame.cells), self.width(), self.height())
        if self._terrain is not None and self._terrain_key == key:
            return self._terrain
        pixmap = QPixmap(self.size())
        pixmap.fill(BACKGROUND)
        painter = QPainter(pixmap)
        cell, left, top = self._geometry()
        side = cell * frame.size
        painter.fillRect(QRectF(left, top, side, side), EMPTY_CELL)
        for y, row in enumerate(frame.cells):
            for x, kind in enumerate(row):
                if kind == "#":
                    painter.fillRect(
                        QRectF(left + x * cell, top + y * cell, cell, cell), OBSTACLE
                    )
        if cell >= 5:
            painter.setPen(QPen(GRID_LINE, 1))
            for index in range(frame.size + 1):
                offset = index * cell
                painter.drawLine(
                    QPointF(left + offset, top), QPointF(left + offset, top + side)
                )
                painter.drawLine(
                    QPointF(left, top + offset), QPointF(left + side, top + offset)
                )
        for player, (x, y) in enumerate(frame.bases):
            rect = QRectF(left + x * cell, top + y * cell, cell, cell)
            painter.fillRect(rect, PLAYER_COLORS[player].darker(250))
            painter.setPen(QPen(PLAYER_COLORS[player], max(1.5, cell / 6)))
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
        painter.end()
        self._terrain, self._terrain_key = pixmap, key
        return pixmap

    @staticmethod
    def _paint_energy(
        painter: QPainter, frame: FrameView, cell: float, left: float, top: float
    ) -> None:
        inset = cell * 0.12
        for x, y, amount in frame.energy:
            painter.fillRect(
                QRectF(
                    left + x * cell + inset,
                    top + y * cell + inset,
                    cell - 2 * inset,
                    cell - 2 * inset,
                ),
                energy_color(amount, frame.max_energy),
            )

    @staticmethod
    def _paint_collisions(
        painter: QPainter, frame: FrameView, cell: float, left: float, top: float
    ) -> None:
        painter.setPen(QPen(COLLISION, max(1.5, cell / 5)))
        for x, y in frame.collisions:
            rect = QRectF(left + x * cell, top + y * cell, cell, cell)
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())

    def _paint_ships(
        self, painter: QPainter, frame: FrameView, cell: float, left: float, top: float
    ) -> None:
        upcoming: dict[int, ShipView] = {}
        if self._next is not None and self._progress > 0.0:
            upcoming = {ship.id: ship for ship in self._next.ships}
        radius = cell * 0.36
        for ship in frame.ships:
            x, y = float(ship.x), float(ship.y)
            after = upcoming.get(ship.id)
            if after is not None:
                x += (after.x - ship.x) * self._progress
                y += (after.y - ship.y) * self._progress
            centre = QPointF(left + (x + 0.5) * cell, top + (y + 0.5) * cell)
            color = PLAYER_COLORS[ship.owner]
            painter.setPen(
                QPen(QColor("#ffffff") if ship.mining else color.darker(), 1)
            )
            painter.setBrush(color)
            painter.drawEllipse(centre, radius, radius)
            if ship.cargo > 0 and cell >= 6:
                # Cargo gauge: an inner disc that grows with the load.
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(ENERGY_HIGH)
                inner = radius * 0.75 * (ship.cargo / SHIP_CAPACITY) ** 0.5
                painter.drawEllipse(centre, inner, inner)
