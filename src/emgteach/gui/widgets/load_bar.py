"""LoadBar — a compact muscle-load gauge with tiredness / fatigue zones.

Shows the current load (% MVC) as a filled horizontal bar, coloured by the
zone it falls in (green = normal, orange = warning / tiredness, red = danger /
fatigue), with faint zone bands behind it and dashed ticks at the thresholds.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from emgteach.i18n import tr

_GREEN = "#1a9850"
_ORANGE = "#E67E22"
_RED = "#cc0000"


class LoadBar(QWidget):
    """Horizontal muscle-load gauge (% MVC) with warning / danger zones."""

    _H = 20
    _VMAX = 120.0  # % MVC shown at full scale (a little headroom over 100)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._warning = 30.0
        self._danger = 50.0
        self._active = False  # greyed out until an MVC reference is calibrated
        self.setMinimumHeight(self._H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_zones(self, warning: float, danger: float) -> None:
        self._warning = float(warning)
        self._danger = float(danger)
        self.update()

    def set_value(self, value: float, active: bool = True) -> None:
        self._value = float(value)
        self._active = active
        self.update()

    def reset(self) -> None:
        self._value = 0.0
        self._active = False
        self.update()

    def _x(self, v: float, w: int) -> int:
        return int(max(0.0, min(v, self._VMAX)) / self._VMAX * w)

    def _colour(self) -> str:
        if self._value >= self._danger:
            return _RED
        if self._value >= self._warning:
            return _ORANGE
        return _GREEN

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(QPen(QColor("#999999"), 1))
        p.setBrush(QColor("#f0f0f0"))
        p.drawRect(0, 0, w - 1, h - 1)

        if not self._active:
            p.setPen(QColor("#999999"))
            p.setFont(QFont("Arial", 8))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("not calibrated"))
            p.end()
            return

        xw = self._x(self._warning, w)
        xd = self._x(self._danger, w)

        # Faint zone bands behind the fill.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(26, 152, 80, 40))
        p.drawRect(1, 1, max(0, xw - 1), h - 2)
        p.setBrush(QColor(230, 126, 34, 40))
        p.drawRect(xw, 1, max(0, xd - xw), h - 2)
        p.setBrush(QColor(204, 0, 0, 40))
        p.drawRect(xd, 1, max(0, w - 1 - xd), h - 2)

        # Solid fill up to the current value, coloured by zone.
        xv = self._x(self._value, w)
        p.setBrush(QColor(self._colour()))
        p.drawRect(1, 1, max(0, xv - 1), h - 2)

        # Threshold ticks.
        p.setPen(QPen(QColor("#555555"), 1, Qt.PenStyle.DashLine))
        p.drawLine(xw, 0, xw, h)
        p.drawLine(xd, 0, xd, h)

        # Value text (right-aligned).
        p.setPen(QColor("#000000"))
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.drawText(self.rect().adjusted(4, 0, -4, 0),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"{self._value:.0f} % MVC")
        p.end()
