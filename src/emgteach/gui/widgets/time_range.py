"""TimeRangeSelector — interactive time minimap.

Shows the recording's total duration as a bar and lets the user visually
select a sub-range [start, start+duration] by dragging with the mouse.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class TimeRangeSelector(QWidget):
    range_changed = Signal(float, float)   # (start, duration) on mouse release
    range_preview = Signal(float, float)   # (start, duration) while dragging

    _BAR_H    = 30   # px — height of the selection rectangle
    _SCALE_H  = 18   # px — height of the time scale
    _EDGE     = 7    # px — max width of each resize handle (capped to w/3)
    _MIN_GRAB = 18   # px — below this width the whole selection moves (no edge resize)
    _GRAB_PAD = 3    # px — extra catch margin around a thin selection, for moving
    _MIN_DUR  = 0.5  # s  — minimum selectable duration

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total: float    = 60.0
        self._inicio: float   = 0.0
        self._duracion: float = 10.0

        self._drag_mode: str | None = None
        self._drag_start_x: int     = 0
        self._drag_start_inicio: float   = 0.0
        self._drag_start_duracion: float = 10.0

        self.setFixedHeight(self._BAR_H + self._SCALE_H + 2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------ public API

    def set_total_duration(self, seconds: float) -> None:
        self._total = max(float(seconds), 1.0)
        self._clamp()
        self.update()

    def set_range(self, inicio: float, duracion: float) -> None:
        self._inicio   = float(inicio)
        self._duracion = float(duracion)
        self._clamp()
        self.update()

    def get_range(self) -> tuple[float, float]:
        return self._inicio, self._duracion

    # ------------------------------------------------------------------ internal helpers

    def _clamp(self) -> None:
        self._duracion = max(self._MIN_DUR, min(self._duracion, self._total))
        self._inicio   = max(0.0, min(self._inicio, self._total - self._duracion))

    def _usable_w(self) -> int:
        return max(1, self.width() - 2)

    def _to_px(self, t: float) -> int:
        return 1 + int(t / self._total * self._usable_w())

    def _to_time(self, px: int) -> float:
        return max(0.0, min(self._total, (px - 1) / self._usable_w() * self._total))

    def _rect_x1x2(self) -> tuple[int, int]:
        x1 = self._to_px(self._inicio)
        x2 = self._to_px(self._inicio + self._duracion)
        return x1, max(x1 + 2, x2)

    def _hit_mode(self, x: int) -> str:
        """Classify a cursor x over the selection: resize_left/right, move, outside.

        Resize handles sit at the outer edges but never swallow the whole
        rectangle: each is capped to a third of the width and is only offered
        when the selection is wide enough (>= _MIN_GRAB) to keep a central move
        zone. A narrow selection is therefore always "move" (resize it with the
        ◀▶ / zoom controls) — this fixes the old behaviour where moving a thin
        window accidentally grabbed an edge and resized it. A small pad around
        the rectangle still counts as "move" so a thin bar is easy to catch.
        """
        x1, x2 = self._rect_x1x2()
        if (x2 - x1) >= self._MIN_GRAB:
            edge = min(self._EDGE, (x2 - x1) // 3)
            if x1 <= x < x1 + edge:
                return "resize_left"
            if x2 - edge < x <= x2:
                return "resize_right"
        if x1 - self._GRAB_PAD <= x <= x2 + self._GRAB_PAD:
            return "move"
        return "outside"

    def _cursor_for(self, mode: str, pressed: bool = False):
        if mode in ("resize_left", "resize_right"):
            return Qt.CursorShape.SizeHorCursor
        if mode == "move":
            return (Qt.CursorShape.ClosedHandCursor if pressed
                    else Qt.CursorShape.OpenHandCursor)
        return Qt.CursorShape.ArrowCursor

    # ------------------------------------------------------------------ painting

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w  = self.width()
        bh = self._BAR_H

        # Outer track
        p.setPen(QPen(QColor("#666666"), 1))
        p.setBrush(QColor("#f5f5f5"))
        p.drawRect(0, 0, w - 1, bh - 1)

        # Selection rectangle
        x1, x2 = self._rect_x1x2()
        fill = QColor("#1f77b4")
        fill.setAlpha(100)
        p.setBrush(fill)
        p.setPen(QPen(QColor("#1f77b4"), 2))
        p.drawRect(x1, 1, x2 - x1, bh - 3)

        # Resize-handle grips at the edges (only when the selection is wide
        # enough to offer edge-resize; a thin selection is move-only).
        if (x2 - x1) >= self._MIN_GRAB:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#1f77b4"))
            p.drawRect(x1, 1, 3, bh - 3)
            p.drawRect(x2 - 3, 1, 3, bh - 3)

        # Time scale — ticks every 10%, with overlap suppression
        font = QFont("Arial", 7)
        p.setFont(font)
        p.setPen(QColor("#444444"))
        fm = p.fontMetrics()
        n_ticks = 11  # 0%, 10%, …, 100%
        last_label_end = -1
        for i in range(n_ticks):
            frac = i / (n_ticks - 1)
            t    = frac * self._total
            px   = self._to_px(t)
            p.drawLine(px, bh, px, bh + 4)
            lbl  = f"{t:.0f}s"
            lw   = fm.horizontalAdvance(lbl)
            lx   = max(0, min(w - lw, px - lw // 2))
            if lx >= last_label_end:
                p.drawText(lx, bh + 4 + fm.ascent(), lbl)
                last_label_end = lx + lw + 4

        p.end()

    # ------------------------------------------------------------------ mouse

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x    = int(event.position().x())
        mode = self._hit_mode(x)

        if mode == "outside":
            # Click on the empty track: centre the window on the click, then
            # continue as a move so the same drag can pan it.
            t = self._to_time(x)
            self._inicio = max(0.0, min(self._total - self._duracion,
                                        t - self._duracion / 2))
            self._clamp()
            self.update()
            self.range_preview.emit(self._inicio, self._duracion)
            mode = "move"

        self._drag_mode           = mode
        self._drag_start_x        = x
        self._drag_start_inicio   = self._inicio
        self._drag_start_duracion = self._duracion
        self.setCursor(self._cursor_for(mode, pressed=True))

    def mouseMoveEvent(self, event) -> None:
        x = int(event.position().x())

        if self._drag_mode is None:
            self.setCursor(self._cursor_for(self._hit_mode(x)))
            return

        dx_t = (x - self._drag_start_x) / self._usable_w() * self._total
        i0   = self._drag_start_inicio
        d0   = self._drag_start_duracion

        if self._drag_mode == "move":
            self._inicio   = max(0.0, min(self._total - d0, i0 + dx_t))
            self._duracion = d0

        elif self._drag_mode == "resize_left":
            new_i = i0 + dx_t
            new_d = d0 - dx_t
            if new_d < self._MIN_DUR:
                new_i = i0 + d0 - self._MIN_DUR
                new_d = self._MIN_DUR
            if new_i < 0.0:
                new_d = max(self._MIN_DUR, i0 + d0)
                new_i = 0.0
            self._inicio   = new_i
            self._duracion = new_d

        elif self._drag_mode == "resize_right":
            new_d = max(self._MIN_DUR, d0 + dx_t)
            if i0 + new_d > self._total:
                new_d = self._total - i0
            self._duracion = new_d

        self._clamp()
        self.update()
        self.range_preview.emit(self._inicio, self._duracion)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drag_mode is not None:
            self._clamp()
            self.range_changed.emit(self._inicio, self._duracion)
        self._drag_mode = None
        self.setCursor(self._cursor_for(self._hit_mode(int(event.position().x()))))
