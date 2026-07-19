"""MvcOverlay — a floating, prominent guide for the MVC-calibration wizard.

A semi-transparent panel drawn over the live plots that tells the subject,
one muscle at a time, exactly what to do: a big "get ready" countdown, then a
"contract at maximum" phase with a window-progress bar and a **live effort
bar** that rises and falls with the contraction force (with a peak marker),
then a relax pause. It is purely a view: the wizard state machine in the
acquisition tab drives it through the ``show_*`` methods.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame

from emgteach.i18n import tr

_BG = QColor(20, 20, 28, 225)      # near-opaque dark panel
_FG = QColor(245, 245, 245)
_ACCENT = QColor(46, 134, 222)     # blue (ready / progress)
_EFFORT = QColor(39, 174, 96)      # green (effort fill)
_PEAK = QColor(241, 196, 15)       # amber (peak marker)
_OK = QColor(46, 204, 113)


class MvcOverlay(QFrame):
    """Floating guide panel for the guided MVC-calibration wizard."""

    _W = 460
    _H = 210

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mode = "hidden"      # ready | contract | relax | done | hidden
        self._title = ""
        self._subtitle = ""
        self._count = ""
        self._progress = 0.0       # window progress 0..1
        self._effort = 0.0         # live effort 0..1 (of the running peak)
        self.resize(self._W, self._H)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

    # -- driven by the wizard ------------------------------------------------

    def show_ready(self, title: str, count: int, subtitle: str = "") -> None:
        self._mode = "ready"
        self._title = title
        self._count = str(count)
        self._subtitle = subtitle
        self.show()
        self.raise_()
        self.update()

    def show_contract(
        self, title: str, secs_left: float, progress: float, effort: float
    ) -> None:
        self._mode = "contract"
        self._title = title
        self._count = f"{secs_left:.0f}"
        self._progress = max(0.0, min(1.0, progress))
        self._effort = max(0.0, min(1.0, effort))
        self.show()
        self.raise_()
        self.update()

    def show_relax(self, subtitle: str = "") -> None:
        self._mode = "relax"
        self._title = ""
        self._subtitle = subtitle
        self.show()
        self.raise_()
        self.update()

    def show_action(self, word: str, subtitle: str = "") -> None:
        """A single big 'go now' cue (e.g. Lift!) — no bars, no countdown.

        Used for a quick concentric action where a hold timer or effort bar
        would only distract (and could read as 'something is missing')."""
        self._mode = "action"
        self._title = word
        self._subtitle = subtitle
        self.show()
        self.raise_()
        self.update()

    def show_done(self, title: str, subtitle: str) -> None:
        self._mode = "done"
        self._title = title
        self._subtitle = subtitle
        self.show()
        self.raise_()
        self.update()

    def hide_overlay(self) -> None:
        self._mode = "hidden"
        self.hide()

    # -- painting ------------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_BG)
        p.drawRoundedRect(0, 0, w, h, 16, 16)

        if self._mode == "ready":
            self._text(p, self._title, 0, 18, w, 30, 15, bold=True)
            self._text(p, self._count, 0, 55, w, 90, 64, bold=True, colour=_ACCENT)
            if self._subtitle:
                self._text(p, self._subtitle, 0, h - 38, w, 28, 11, colour=QColor(190, 190, 200))
        elif self._mode == "contract":
            self._text(p, self._title, 0, 14, w, 30, 16, bold=True, colour=_EFFORT)
            self._text(p, self._count + " s", 0, 44, w, 34, 22, bold=True)
            # Window progress (thin) and live effort (tall) bars.
            self._bar(p, 24, 92, w - 48, 8, self._progress, _ACCENT, peak=None)
            self._text(p, self._effort_label(), 24, 108, w - 48, 16, 9,
                       align=Qt.AlignmentFlag.AlignLeft)
            self._bar(p, 24, 126, w - 48, 26, self._effort, _EFFORT, peak=1.0)
            self._text(p, self._hint_contract(), 0, h - 30, w, 22, 10,
                       colour=QColor(190, 190, 200))
        elif self._mode == "relax":
            self._text(p, self._relax_word(), 0, 60, w, 60, 40, bold=True, colour=_ACCENT)
            if self._subtitle:
                self._text(p, self._subtitle, 0, h - 40, w, 28, 12,
                           colour=QColor(190, 190, 200))
        elif self._mode == "action":
            # Just the cue word, large and green — no bars or countdown.
            self._text(p, self._title, 0, 60, w, 60, 38, bold=True, colour=_EFFORT)
            if self._subtitle:
                self._text(p, self._subtitle, 0, h - 40, w, 28, 12,
                           colour=QColor(190, 190, 200))
        elif self._mode == "done":
            self._text(p, self._title, 0, 28, w, 36, 20, bold=True, colour=_OK)
            self._text(p, self._subtitle, 12, 78, w - 24, h - 96, 12, wrap=True)
        p.end()

    # -- helpers -------------------------------------------------------------

    def _effort_label(self) -> str:
        return tr("Effort {pct:.0f} %").format(pct=self._effort * 100)

    def _hint_contract(self) -> str:
        return tr("Push as hard as you can until it reaches 0")

    def _relax_word(self) -> str:
        return tr("Relax")

    def _text(self, p, text, x, y, w, h, pt, *, bold=False, colour=None,
              align=Qt.AlignmentFlag.AlignCenter, wrap=False) -> None:
        if not text:
            return
        p.setPen(colour or _FG)
        f = QFont("Arial", pt)
        f.setBold(bold)
        p.setFont(f)
        flags = align | Qt.AlignmentFlag.AlignVCenter
        if wrap:
            flags = align | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        p.drawText(x, y, w, h, int(flags), text)

    def _bar(self, p, x, y, w, h, frac, colour, peak=None) -> None:
        frac = max(0.0, min(1.0, frac))
        p.setPen(QPen(QColor(110, 110, 120), 1))
        p.setBrush(QColor(45, 45, 55))
        p.drawRoundedRect(x, y, w, h, 4, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        fill_w = int((w - 2) * frac)
        if fill_w > 0:
            p.drawRoundedRect(x + 1, y + 1, fill_w, h - 2, 3, 3)
        if peak is not None:
            px = x + 1 + int((w - 2) * max(0.0, min(1.0, peak)))
            p.setPen(QPen(_PEAK, 2))
            p.drawLine(px, y, px, y + h)
