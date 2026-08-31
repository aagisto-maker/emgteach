"""MvcOverlay — a floating, prominent guide for the MVC-calibration wizard.

A semi-transparent panel drawn over the live plots that tells the subject,
one muscle at a time, exactly what to do: a big "get ready" countdown, then a
"contract at maximum" phase with a window-progress bar and a **live effort
bar** that rises and falls with the contraction force (with a peak marker),
then a relax pause. It is purely a view: the wizard state machine in the
acquisition tab drives it through the ``show_*`` methods.

**The panel is sized from its text, not the other way round.** It used to be
460x210 fixed with only the "done" message word-wrapped; every other subtitle
was drawn as a single centred line into a strip 28 px tall, so a long
instruction simply ran off both edges. That is not a cosmetic problem here —
the messages that overflow are the long ones, and the long ones are the ones
that explain what went wrong. Now every message wraps, and the panel measures
what it is about to draw and grows to hold it.
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QFrame

from emgteach.i18n import tr

_BG = QColor(20, 20, 28, 225)      # near-opaque dark panel
_FG = QColor(245, 245, 245)
_ACCENT = QColor(46, 134, 222)     # blue (ready / progress)
_EFFORT = QColor(39, 174, 96)      # green (effort fill)
_PEAK = QColor(241, 196, 15)       # amber (peak marker)
_OK = QColor(46, 204, 113)
_MUTED = QColor(190, 190, 200)


class MvcOverlay(QFrame):
    """Floating guide panel for the guided MVC-calibration wizard."""

    _W = 460
    _H = 210                  #: minimum height; the panel grows past it

    #: Type size of the message band, and the room around it.
    _SUB_PT = 12
    _SUB_MARGIN = 18          # px each side
    _BOTTOM = 16              # px below the last line

    #: Where the message band starts in each mode — i.e. how much room the
    #: countdown, the bars or the title need above it.
    _TOP: ClassVar[dict[str, int]] = {
        "ready": 152,
        "contract": 160,
        "relax": 126,
        "action": 126,
        "done": 76,
    }

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
        self._present()

    def show_contract(
        self, title: str, secs_left: float, progress: float, effort: float
    ) -> None:
        self._mode = "contract"
        self._title = title
        self._count = f"{secs_left:.0f}"
        self._progress = max(0.0, min(1.0, progress))
        self._effort = max(0.0, min(1.0, effort))
        self._subtitle = self._hint_contract()
        self._present()

    def show_relax(self, subtitle: str = "") -> None:
        self._mode = "relax"
        self._title = ""
        self._subtitle = subtitle
        self._present()

    def show_action(self, word: str, subtitle: str = "") -> None:
        """A single big 'go now' cue (e.g. Lift!) — no bars, no countdown.

        Used for a quick concentric action where a hold timer or effort bar
        would only distract (and could read as 'something is missing')."""
        self._mode = "action"
        self._title = word
        self._subtitle = subtitle
        self._present()

    def show_done(self, title: str, subtitle: str) -> None:
        self._mode = "done"
        self._title = title
        self._subtitle = subtitle
        self._present()

    def hide_overlay(self) -> None:
        self._mode = "hidden"
        self.hide()

    # -- sizing --------------------------------------------------------------

    def _present(self) -> None:
        """Grow to fit the message, then show and repaint.

        The width stays fixed so the acquisition tab's horizontal centring
        keeps working without being told anything; only the height moves, and
        the panel is anchored at its top, so it grows downwards over the plots.
        """
        self.resize(self._W, self.height_for_text())
        self.show()
        self.raise_()
        self.update()

    def message_rect(self) -> tuple[int, int, int, int]:
        """``(x, y, w, h)`` of the band the message is drawn in."""
        top = self._TOP.get(self._mode, 152)
        ancho = self._W - 2 * self._SUB_MARGIN
        return (
            self._SUB_MARGIN, top, ancho,
            max(0, self.height() - top - self._BOTTOM),
        )

    def text_height(self, text: str | None = None) -> int:
        """Height the message needs, wrapped, at the panel's own width."""
        texto = self._subtitle if text is None else text
        if not texto:
            return 0
        fm = QFontMetrics(QFont("Arial", self._SUB_PT))
        flags = int(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
        )
        rect = fm.boundingRect(
            0, 0, self._W - 2 * self._SUB_MARGIN, 10_000, flags, texto
        )
        return rect.height()

    def height_for_text(self) -> int:
        """The height this panel needs for what it is about to draw."""
        top = self._TOP.get(self._mode, 152)
        return max(self._H, top + self.text_height() + self._BOTTOM)

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
        elif self._mode == "contract":
            self._text(p, self._title, 0, 14, w, 30, 16, bold=True, colour=_EFFORT)
            self._text(p, self._count + " s", 0, 44, w, 34, 22, bold=True)
            # Window progress (thin) and live effort (tall) bars.
            self._bar(p, 24, 92, w - 48, 8, self._progress, _ACCENT, peak=None)
            self._text(p, self._effort_label(), 24, 108, w - 48, 16, 9,
                       align=Qt.AlignmentFlag.AlignLeft)
            self._bar(p, 24, 126, w - 48, 26, self._effort, _EFFORT, peak=1.0)
        elif self._mode == "relax":
            self._text(p, self._relax_word(), 0, 40, w, 60, 40, bold=True,
                       colour=_ACCENT)
        elif self._mode == "action":
            # Just the cue word, large and green — no bars or countdown.
            self._text(p, self._title, 0, 40, w, 60, 38, bold=True, colour=_EFFORT)
        elif self._mode == "done":
            self._text(p, self._title, 0, 26, w, 36, 20, bold=True, colour=_OK)

        # One path for every message, wrapped, in the band measured above. The
        # single-line strips this replaces are what let the long warnings —
        # which are the ones worth reading — run off the edges of the panel.
        if self._mode != "hidden" and self._subtitle:
            x, y, bw, bh = self.message_rect()
            colour = _FG if self._mode == "done" else _MUTED
            self._text(p, self._subtitle, x, y, bw, bh, self._SUB_PT,
                       colour=colour, wrap=True)
        p.end()

    # -- helpers -------------------------------------------------------------

    def _effort_label(self) -> str:
        return tr("Effort {pct:.0f} %").format(pct=self._effort * 100)

    def _hint_contract(self) -> str:
        return tr("Contract as hard as you can until the count reaches 0")

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
            flags = (
                Qt.AlignmentFlag.AlignHCenter
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap
            )
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
