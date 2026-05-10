"""TimeRangeSelector — minimapa temporal interactivo.

Muestra la duración total del registro como una barra y permite seleccionar
visualmente un sub-rango [inicio, inicio+duracion] arrastrando con el ratón.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class TimeRangeSelector(QWidget):
    range_changed = Signal(float, float)   # (inicio, duracion) al soltar el ratón
    range_preview = Signal(float, float)   # (inicio, duracion) durante el arrastre

    _BAR_H   = 30   # px — altura del rectángulo de selección
    _SCALE_H = 18   # px — altura de la escala temporal
    _EDGE    = 6    # px — zona sensible en bordes izquierdo/derecho
    _MIN_DUR = 0.5  # s  — duración mínima seleccionable

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

    # ------------------------------------------------------------------ API pública

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

    # ------------------------------------------------------------------ helpers internos

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
        x1, x2 = self._rect_x1x2()
        if abs(x - x1) <= self._EDGE:
            return "resize_left"
        if abs(x - x2) <= self._EDGE:
            return "resize_right"
        if x1 < x < x2:
            return "move"
        return "outside"

    # ------------------------------------------------------------------ pintado

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w  = self.width()
        bh = self._BAR_H

        # Pista exterior
        p.setPen(QPen(QColor("#666666"), 1))
        p.setBrush(QColor("#f5f5f5"))
        p.drawRect(0, 0, w - 1, bh - 1)

        # Rectángulo de selección
        x1, x2 = self._rect_x1x2()
        fill = QColor("#1f77b4")
        fill.setAlpha(100)
        p.setBrush(fill)
        p.setPen(QPen(QColor("#1f77b4"), 2))
        p.drawRect(x1, 1, x2 - x1, bh - 3)

        # Escala temporal — tics cada 10%, con supresión de solapamiento
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

    # ------------------------------------------------------------------ ratón

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x    = int(event.position().x())
        mode = self._hit_mode(x)
        self._drag_mode           = mode
        self._drag_start_x        = x
        self._drag_start_inicio   = self._inicio
        self._drag_start_duracion = self._duracion

        if mode == "outside":
            t = self._to_time(x)
            self._inicio = max(0.0, min(self._total - self._duracion,
                                        t - self._duracion / 2))
            self._clamp()
            self.update()
            self.range_preview.emit(self._inicio, self._duracion)

    def mouseMoveEvent(self, event) -> None:
        x = int(event.position().x())

        if self._drag_mode is None:
            mode = self._hit_mode(x)
            cur  = (Qt.CursorShape.SizeHorCursor
                    if mode in ("resize_left", "resize_right", "move")
                    else Qt.CursorShape.ArrowCursor)
            self.setCursor(cur)
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
