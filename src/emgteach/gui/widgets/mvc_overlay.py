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

The title got the same treatment later, for the same reason. Wrapping the
message left the title as a single bold line, and the brief-squeeze
instruction the author asked for word for word («Haga una contracción o
sacudida muscular simple (breve) de FCR con la máxima fuerza posible») is
twice the panel's width at that size. So the title band is measured too, and
everything under it — the countdown, the bars, the message — moves down by
whatever the title grew.

**The row of steps along the bottom is the map of the phase**: one empty box
per action the phase asks for, in the colour of the muscle it belongs to,
filled as each one is done. It answers a different question from the
countdown — the count says *now*, the row says *where I am and how much is
left* — so the two live together. It is drawn as a footer band, under
everything else, which is why adding it moved none of the layout above it.
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame

from emgteach.i18n import tr

_BG = QColor(20, 20, 28, 225)      # near-opaque dark panel
_FG = QColor(245, 245, 245)
_ACCENT = QColor(46, 134, 222)     # blue (ready / progress)
_EFFORT = QColor(39, 174, 96)      # green (effort fill)
_PEAK = QColor(241, 196, 15)       # amber (peak marker)
_OK = QColor(46, 204, 113)
_MUTED = QColor(190, 190, 200)
_STEP_EMPTY = QColor(38, 38, 48)   # the box before its action is done

_WRAP_TOP = int(
    Qt.AlignmentFlag.AlignHCenter
    | Qt.AlignmentFlag.AlignTop
    | Qt.TextFlag.TextWordWrap
)


class MvcOverlay(QFrame):
    """Floating guide panel for the guided MVC-calibration wizard."""

    _W = 460
    _H = 210                  #: minimum height; the panel grows past it

    #: How much of the window the picture may take, and the air under it.
    #: Capped like the tour's (``coach._IMG_MAX_FRAC``) so a tall picture
    #: on a small screen still leaves the plots and the message in view.
    _IMG_MAX_FRAC = 0.28
    _IMG_GAP = 10

    #: The footer row: one box per action of the phase. Vertical, because a
    #: row of uprights reads as a row of things to do; the horizontal bars
    #: in this panel already mean «time running».
    _STEP_H = 22
    _STEP_W = 13
    _STEP_GAP = 5
    _STEP_TOP_GAP = 12

    #: The bar that runs a hold, in the phase box.
    _RUN_H = 14
    _RUN_GAP = 12

    #: Type size of the message band, and the room around it.
    _SUB_PT = 12
    _SUB_MARGIN = 18          # px each side
    _BOTTOM = 16              # px below the last line

    #: The title band per mode: point size, top of the band, and the height
    #: of the single-line strip the layout below was designed around. A
    #: title that needs more than that strip pushes everything down.
    _TITLE: ClassVar[dict[str, tuple[int, int, int]]] = {
        "ready": (15, 18, 30),
        "contract": (16, 14, 30),
        "done": (20, 26, 36),
        "phase": (15, 14, 26),
    }

    #: How much taller the countdown box is for the bar under its number.
    _WAIT_EXTRA = 22

    #: Where the message band starts in each mode with a single-line title —
    #: i.e. how much room the countdown, the bars or the title need above it.
    _TOP: ClassVar[dict[str, int]] = {
        "ready": 152,
        "contract": 160,
        "relax": 126,
        "action": 126,
        "done": 76,
        "phase": 52,
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mode = "hidden"      # ready | contract | relax | done | hidden
        self._title = ""
        self._subtitle = ""
        self._count = ""
        self._progress = 0.0       # window progress 0..1
        self._effort = 0.0         # live effort 0..1 (of the running peak)
        self._pixmap = QPixmap()   # the gesture being asked for, or nothing
        #: ``[colour, done]`` per action of the phase; empty for no footer.
        self._steps: list[list] = []
        self._running: float | None = None   # a hold in progress, 0..1
        self._waiting: float | None = None   # a countdown in progress, 0..1
        self.resize(self._W, self._H)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

    # -- the map of the phase ------------------------------------------------

    def set_steps(self, colours) -> None:
        """Lay out one empty box per action, in the order they are asked for.

        *colours* is one ``(r, g, b)`` per action — the muscle's own, so the
        colour in the row is the colour of its trace — or empty for a phase
        that has no actions to count, like the warm-up.
        """
        self._steps = [[QColor(*c), False] for c in (colours or [])]

    def mark_step(self, index: int) -> None:
        """Fill one box. Out of range is ignored on purpose: the row informs,
        it does not govern, so more actions than boxes is not an error —
        the count that matters is the one the analysis makes afterwards.
        """
        if 0 <= index < len(self._steps):
            self._steps[index][1] = True

    def steps_done(self) -> list[bool]:
        """Which boxes are filled, in order."""
        return [bool(hecho) for _colour, hecho in self._steps]

    def steps_rect(self) -> tuple[int, int, int, int]:
        """``(x, y, w, h)`` of the footer row; empty when there is none."""
        if not self._steps:
            return (0, 0, 0, 0)
        n = len(self._steps)
        ancho = n * self._STEP_W + (n - 1) * self._STEP_GAP
        return ((self._W - ancho) // 2,
                self.height() - self._BOTTOM - self._STEP_H,
                ancho, self._STEP_H)

    # -- driven by the wizard ------------------------------------------------

    def show_ready(self, title: str, count: int, subtitle: str = "",
                   image: str | None = None, *,
                   waiting: float | None = None) -> None:
        """The countdown before an effort, with the gesture it asks for.

        *image* is a path, or ``None`` for the panel of always: without
        one nothing about the layout changes. The picture belongs with the
        instruction, not with the effort — while the student is squeezing
        they are watching the bar, and a taller panel would cover the
        plots just then.

        *waiting* is the same seconds as a bar, 0..1. The number says
        *now* and is the signal to start; the bar says *how much is left*,
        which is read without counting. It is drawn in the panel's blue —
        time running — and never in the green of the effort bar, so two
        bars never mean two different things in one colour.
        """
        self._mode = "ready"
        self._running = None
        self._waiting = (None if waiting is None
                         else max(0.0, min(1.0, float(waiting))))
        self._title = title
        self._count = str(count)
        self._subtitle = subtitle
        self._set_image(image)
        self._present()

    def show_contract(
        self, title: str, secs_left: float, progress: float, effort: float
    ) -> None:
        self._set_image(None)          # the effort is watched on the bar
        self._mode = "contract"
        self._waiting = None
        self._running = None
        self._title = title
        self._count = f"{secs_left:.0f}"
        self._progress = max(0.0, min(1.0, progress))
        self._effort = max(0.0, min(1.0, effort))
        self._subtitle = self._hint_contract()
        self._present()

    def show_relax(self, subtitle: str = "") -> None:
        self._set_image(None)
        self._mode = "relax"
        self._waiting = None
        self._running = None
        self._title = ""
        self._subtitle = subtitle
        self._present()

    def show_action(self, word: str, subtitle: str = "") -> None:
        """A single big 'go now' cue (e.g. Lift!) — no bars, no countdown.

        Used for a quick concentric action where a hold timer or effort bar
        would only distract (and could read as 'something is missing')."""
        self._set_image(None)
        self._mode = "action"
        self._waiting = None
        self._running = None
        self._title = word
        self._subtitle = subtitle
        self._present()

    def show_phase(self, title: str, subtitle: str = "", *,
                   running: float | None = None) -> None:
        """A phase of the session: what to do, the map, and a hold if there is one.

        The box the free manoeuvres and the grip are guided by. It is short
        on purpose — the student is watching their own load bars and traces
        while they work, and those are exactly what a tall panel covers.

        *running* is a hold in progress, 0..1, drawn as a bar that fills with
        the clock; ``None`` for a phase nobody is timing.
        """
        self._set_image(None)
        self._mode = "phase"
        self._waiting = None
        self._title = title
        self._subtitle = subtitle
        self._running = (None if running is None
                         else max(0.0, min(1.0, float(running))))
        self._present()

    def show_done(self, title: str, subtitle: str) -> None:
        self._set_image(None)
        self._mode = "done"
        self._waiting = None
        self._running = None
        self._title = title
        self._subtitle = subtitle
        self._present()

    def hide_overlay(self) -> None:
        self._mode = "hidden"
        self.hide()

    # -- sizing --------------------------------------------------------------

    def _present(self) -> None:
        """Grow to fit the title and the message, then show and repaint.

        The width stays fixed so the acquisition tab's horizontal centring
        keeps working without being told anything; only the height moves, and
        the panel is anchored at its top, so it grows downwards over the plots.
        """
        self.resize(self._W, self.height_for_text())
        self.show()
        self.raise_()
        self.update()

    def title_height(self, text: str | None = None) -> int:
        """Height the title needs, wrapped, at the panel's own width.

        Never less than the strip the layout was drawn around, so a short
        title changes nothing; modes without a title band report 0.
        """
        if self._mode not in self._TITLE:
            return 0
        pt, _y, strip = self._TITLE[self._mode]
        texto = self._title if text is None else text
        if not texto:
            return strip
        f = QFont("Arial", pt)
        f.setBold(True)
        rect = QFontMetrics(f).boundingRect(
            0, 0, self._W - 2 * self._SUB_MARGIN, 10_000, _WRAP_TOP, texto
        )
        return max(strip, rect.height())

    def title_rect(self) -> tuple[int, int, int, int]:
        """``(x, y, w, h)`` of the band the title is drawn in; empty without one."""
        if self._mode not in self._TITLE:
            return (0, 0, 0, 0)
        _pt, y, _strip = self._TITLE[self._mode]
        return (self._SUB_MARGIN, y, self._W - 2 * self._SUB_MARGIN,
                self.title_height())

    def _title_extra(self) -> int:
        """How far everything under the title moves down for a wrapped one."""
        if self._mode not in self._TITLE:
            return 0
        return self.title_height() - self._TITLE[self._mode][2]

    def _set_image(self, ruta: str | None) -> None:
        """Load the picture for the panel's width, or clear it.

        The width is fixed — the tab centres the panel by it — so the
        picture is scaled to the text's own width and capped in height by
        a share of the window it floats over.
        """
        pix = QPixmap(ruta) if ruta else QPixmap()
        if pix.isNull():
            self._pixmap = QPixmap()
            return
        ancho = self._W - 2 * self._SUB_MARGIN
        alto_max = max(90, int(self._alto_disponible() * self._IMG_MAX_FRAC))
        escala = min(ancho / pix.width(), alto_max / pix.height())
        self._pixmap = pix.scaled(
            max(1, int(pix.width() * escala)), max(1, int(pix.height() * escala)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _alto_disponible(self) -> int:
        """The window the panel floats over, or a sane number without one."""
        padre = self.parentWidget()
        return padre.height() if padre is not None else 600

    def _steps_extra(self) -> int:
        """How much taller the panel is for its footer row."""
        return 0 if not self._steps else self._STEP_H + self._STEP_TOP_GAP

    def _waiting_extra(self) -> int:
        """How far the message moves down for the countdown bar."""
        return 0 if self._waiting is None else self._WAIT_EXTRA

    def _running_extra(self) -> int:
        """How far the message moves down for the hold bar, if there is one."""
        return 0 if self._running is None else self._RUN_H + self._RUN_GAP

    def _image_extra(self) -> int:
        """How far the message moves down for the picture, if there is one."""
        return 0 if self._pixmap.isNull() else self._pixmap.height() + self._IMG_GAP

    def image_rect(self) -> tuple[int, int, int, int]:
        """``(x, y, w, h)`` of the picture; empty when there is none."""
        if self._pixmap.isNull():
            return (0, 0, 0, 0)
        top = (self._TOP.get(self._mode, 152) + self._title_extra()
               + self._waiting_extra())
        x = (self._W - self._pixmap.width()) // 2
        return (x, top, self._pixmap.width(), self._pixmap.height())

    def message_rect(self) -> tuple[int, int, int, int]:
        """``(x, y, w, h)`` of the band the message is drawn in."""
        top = self._mensaje_top()
        ancho = self._W - 2 * self._SUB_MARGIN
        return (
            self._SUB_MARGIN, top, ancho,
            max(0, self.height() - top - self._BOTTOM - self._steps_extra()),
        )

    def _mensaje_top(self) -> int:
        return (self._TOP.get(self._mode, 152) + self._title_extra()
                + self._waiting_extra() + self._image_extra()
                + self._running_extra())

    def text_height(self, text: str | None = None) -> int:
        """Height the message needs, wrapped, at the panel's own width."""
        texto = self._subtitle if text is None else text
        if not texto:
            return 0
        fm = QFontMetrics(QFont("Arial", self._SUB_PT))
        rect = fm.boundingRect(
            0, 0, self._W - 2 * self._SUB_MARGIN, 10_000, _WRAP_TOP, texto
        )
        return rect.height()

    def height_for_text(self) -> int:
        """The height this panel needs for what it is about to draw.

        The phase box is not held to the minimum the calibration needs: it
        floats while the student is working and the two plots and the load
        bars under it are what they are working from.
        """
        alto = (self._mensaje_top() + self.text_height() + self._BOTTOM
                + self._steps_extra())
        return alto if self._mode == "phase" else max(self._H, alto)

    # -- painting ------------------------------------------------------------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_BG)
        p.drawRoundedRect(0, 0, w, h, 16, 16)

        # Everything below the title shifts by what the title grew.
        d = self._title_extra()
        if self._mode == "ready":
            self._title_band(p, colour=_FG)
            self._text(p, self._count, 0, 55 + d, w, 90, 64, bold=True, colour=_ACCENT)
            if self._waiting is not None:
                self._bar(p, 24, 145 + d, w - 48, 10, self._waiting, _ACCENT)
        elif self._mode == "contract":
            self._title_band(p, colour=_EFFORT)
            self._text(p, self._count + " s", 0, 44 + d, w, 34, 22, bold=True)
            # Window progress (thin) and live effort (tall) bars.
            self._bar(p, 24, 92 + d, w - 48, 8, self._progress, _ACCENT, peak=None)
            self._text(p, self._effort_label(), 24, 108 + d, w - 48, 16, 9,
                       align=Qt.AlignmentFlag.AlignLeft)
            self._bar(p, 24, 126 + d, w - 48, 26, self._effort, _EFFORT, peak=1.0)
        elif self._mode == "relax":
            self._text(p, self._relax_word(), 0, 40, w, 60, 40, bold=True,
                       colour=_ACCENT)
        elif self._mode == "action":
            # Just the cue word, large and green — no bars or countdown.
            self._text(p, self._title, 0, 40, w, 60, 38, bold=True, colour=_EFFORT)
        elif self._mode == "done":
            self._title_band(p, colour=_OK)
        elif self._mode == "phase":
            self._title_band(p, colour=_FG)
            if self._running is not None:
                y = self._TOP["phase"] + d + self._RUN_GAP // 2
                self._bar(p, 24, y, w - 48, self._RUN_H, self._running,
                          _EFFORT, peak=None)

        # The footer row, last of the layout and first of what is looked at
        # while the work is being done.
        if self._steps:
            x, y, _w, _h = self.steps_rect()
            for colour, hecho in self._steps:
                p.setPen(QPen(colour, 2))
                p.setBrush(colour if hecho else _STEP_EMPTY)
                p.drawRoundedRect(x, y, self._STEP_W, self._STEP_H, 3, 3)
                x += self._STEP_W + self._STEP_GAP

        if not self._pixmap.isNull():
            x, y, _w, _h = self.image_rect()
            p.drawPixmap(x, y, self._pixmap)

        # One path for every message, wrapped, in the band measured above. The
        # single-line strips this replaces are what let the long warnings —
        # which are the ones worth reading — run off the edges of the panel.
        if self._mode != "hidden" and self._subtitle:
            x, y, bw, bh = self.message_rect()
            colour = _FG if self._mode == "done" else _MUTED
            self._text(p, self._subtitle, x, y, bw, bh, self._SUB_PT,
                       colour=colour, wrap=True,
                       align=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        p.end()

    # -- helpers -------------------------------------------------------------

    def _effort_label(self) -> str:
        return tr("Effort {pct:.0f} %").format(pct=self._effort * 100)

    def _hint_contract(self) -> str:
        return tr("One explosive jerk at maximal power — brief, not held")

    def _relax_word(self) -> str:
        return tr("Relax")

    def _title_band(self, p, *, colour) -> None:
        """The title, wrapped and centred in the band it was measured for."""
        x, y, w, h = self.title_rect()
        pt = self._TITLE[self._mode][0]
        self._text(p, self._title, x, y, w, h, pt, bold=True, colour=colour,
                   wrap=True)

    def _text(self, p, text, x, y, w, h, pt, *, bold=False, colour=None,
              align=Qt.AlignmentFlag.AlignCenter, wrap=False) -> None:
        if not text:
            return
        p.setPen(colour or _FG)
        f = QFont("Arial", pt)
        f.setBold(bold)
        p.setFont(f)
        flags = int(align)
        if wrap:
            flags |= int(Qt.TextFlag.TextWordWrap)
        else:
            flags |= int(Qt.AlignmentFlag.AlignVCenter)
        p.drawText(x, y, w, h, flags, text)

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
