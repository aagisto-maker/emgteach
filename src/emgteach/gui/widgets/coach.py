"""CoachMark — a floating explanation pinned to one control.

The same panel serves two purposes, which is why it is one widget and not two:
run a list of steps and it is a guided tour; show a single step and it is
contextual help for whatever the user just asked about.

Visually it follows :class:`~emgteach.gui.widgets.mvc_overlay.MvcOverlay` — a
near-opaque dark panel that reads clearly over the plots — but unlike that one
it takes mouse events, because it carries its own Back / Next / Skip buttons.

The rest of the window is dimmed and the control being explained is cut out of
the dimming and ringed, so the text and the thing it describes are visible at
the same time. Being told about a control you cannot see is how tours become
useless.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from emgteach.i18n import tr

_DIM = QColor(10, 12, 18, 170)      # veil over everything but the target
_BG = QColor(20, 20, 28, 240)       # panel, matching MvcOverlay
_ACCENT = QColor(46, 134, 222)

_PANEL_W = 430
_GAP = 14                            # panel-to-target clearance
_MARGIN = 10                         # panel-to-window clearance


class CoachStep:
    """One explanation: what the control is, and what it means physiologically.

    ``target`` is a callable rather than a widget so a step can point at
    something that does not exist yet, or is hidden in the current mode: it is
    resolved when the step is shown, and a step whose target has gone away
    still displays, centred, instead of crashing the tour.
    """

    def __init__(
        self,
        title: str,
        body: str,
        target: Callable[[], QWidget | None] | None = None,
        tab: int | None = None,
        on_enter: Callable[[], None] | None = None,
    ) -> None:
        self.title = title
        self.body = body
        self.target = target
        self.tab = tab
        # Run before the target is resolved, for a step that has to clear
        # something out of the way first — a panel covering the control it is
        # about to explain, say.
        self.on_enter = on_enter

    def enter(self) -> None:
        if self.on_enter is None:
            return
        try:
            self.on_enter()
        except Exception:
            pass

    def widget(self) -> QWidget | None:
        if self.target is None:
            return None
        try:
            w = self.target()
        except Exception:
            return None
        return w if w is not None and w.isVisible() else None


class CoachMark(QWidget):
    """Full-window overlay showing one CoachStep at a time."""

    finished = Signal()
    step_changed = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        # Kept explicitly: parentWidget() is Optional, and every geometry
        # calculation here needs the host window.
        self._host: QWidget = parent
        self._steps: list[CoachStep] = []
        self._index = 0
        self._hole: QRect | None = None
        self._on_tab: Callable[[int], None] | None = None

        self._panel = QFrame(self)
        self._panel.setObjectName("coachPanel")
        self._panel.setStyleSheet(
            "#coachPanel {"
            f"  background-color: rgba({_BG.red()},{_BG.green()},{_BG.blue()},{_BG.alpha()});"
            "  border: 1px solid #2E86DE;"
            "  border-radius: 8px;"
            "}"
            "#coachPanel QLabel { color: #F5F5F5; background: transparent; }"
            "#coachPanel QPushButton {"
            "  color: #F5F5F5; background-color: #2E86DE; border: none;"
            "  border-radius: 4px; padding: 5px 14px; font-size: 12px;"
            "}"
            "#coachPanel QPushButton:hover { background-color: #4A9BE8; }"
            "#coachPanel QPushButton:disabled { background-color: #3A4050; color: #8A90A0; }"
            "#coachPanel QPushButton#coachSkip {"
            "  background: transparent; color: #AEB6C4; text-decoration: underline;"
            "}"
            "#coachPanel QPushButton#coachSkip:hover { color: #F5F5F5; }"
        )
        lay = QVBoxLayout(self._panel)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(8)

        self._lbl_title = QLabel()
        self._lbl_title.setWordWrap(True)
        self._lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        lay.addWidget(self._lbl_title)

        self._lbl_body = QLabel()
        self._lbl_body.setWordWrap(True)
        self._lbl_body.setStyleSheet("font-size: 12px;")
        lay.addWidget(self._lbl_body)

        # A wrapped label reports its height through heightForWidth, and a
        # layout only asks when the size policy says to. Without this the
        # panel is sized from the unwrapped hint and clips the text.
        for lbl in (self._lbl_title, self._lbl_body):
            policy = lbl.sizePolicy()
            policy.setHeightForWidth(True)
            lbl.setSizePolicy(policy)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._lbl_count = QLabel()
        self._lbl_count.setStyleSheet("font-size: 11px; color: #AEB6C4;")
        row.addWidget(self._lbl_count)
        row.addStretch()
        self._btn_skip = QPushButton(tr("Skip"))
        self._btn_skip.setObjectName("coachSkip")
        self._btn_skip.clicked.connect(self.stop)
        row.addWidget(self._btn_skip)
        self._btn_back = QPushButton(tr("Back"))
        self._btn_back.clicked.connect(self.back)
        row.addWidget(self._btn_back)
        self._btn_next = QPushButton(tr("Next"))
        self._btn_next.clicked.connect(self.next)
        row.addWidget(self._btn_next)
        lay.addLayout(row)

        self.hide()

    # -- running a tour ------------------------------------------------------

    def start(
        self,
        steps: list[CoachStep],
        on_tab: Callable[[int], None] | None = None,
    ) -> None:
        """Show ``steps`` in order. ``on_tab`` switches tabs when a step asks."""
        if not steps:
            return
        self._steps = steps
        self._on_tab = on_tab
        self._index = 0
        self.setGeometry(self._host.rect())
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._host.installEventFilter(self)
        self._render()

    def stop(self) -> None:
        self._host.removeEventFilter(self)
        self.hide()
        self._steps = []
        self.finished.emit()

    def next(self) -> None:
        if self._index >= len(self._steps) - 1:
            self.stop()
            return
        self._index += 1
        self._render()

    def back(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._render()

    # -- rendering -----------------------------------------------------------

    def _render(self) -> None:
        step = self._steps[self._index]
        if step.tab is not None and self._on_tab is not None:
            self._on_tab(step.tab)
        step.enter()

        self._lbl_title.setText(step.title)
        self._lbl_body.setText(step.body)
        self._lbl_count.setText(
            tr("Step {i} of {n}").format(i=self._index + 1, n=len(self._steps))
        )
        self._btn_back.setEnabled(self._index > 0)
        self._btn_next.setText(
            tr("Finish") if self._index == len(self._steps) - 1 else tr("Next")
        )
        self.step_changed.emit(self._index)
        self._reposition()
        self.update()

    def _panel_height(self) -> int:
        """Height the panel needs for its text at the width it is pinned to.

        adjustSize() is not enough here. A word-wrapped QLabel only knows its
        height once its width is fixed, and the layout asks for that height
        through heightForWidth — which it skips unless the label's size policy
        advertises it. Without this the panel took the labels' unwrapped size
        hint and every step lost its last lines; the two-paragraph ones lost
        about six.
        """
        lay = self._panel.layout()
        m = lay.contentsMargins()
        # The styled border sits inside the panel but outside the layout, so
        # it has to be counted separately — leaving it out is what cost the
        # body its last line, two pixels at a time.
        frame = self._panel.contentsMargins()
        inner = _PANEL_W - frame.left() - frame.right() - m.left() - m.right()
        needed = (
            frame.top()
            + m.top()
            + self._lbl_title.heightForWidth(inner)
            + lay.spacing()
            + self._lbl_body.heightForWidth(inner)
            + lay.spacing()
            + self._btn_next.sizeHint().height()
            + m.bottom()
            + frame.bottom()
        )
        return max(needed, self._panel.sizeHint().height())

    def _reposition(self) -> None:
        """Put the hole over the target and the panel beside it."""
        self._hole = None
        target = self._steps[self._index].widget() if self._steps else None
        if target is not None:
            top_left = target.mapTo(self._host, QPoint(0, 0))
            self._hole = QRect(top_left, target.size()).adjusted(-4, -4, 4, 4)

        self._panel.setFixedWidth(_PANEL_W)
        self._panel.setFixedHeight(self._panel_height())
        pw, ph = self._panel.width(), self._panel.height()
        area = self.rect()

        if self._hole is None:
            self._panel.move(
                area.center().x() - pw // 2, area.center().y() - ph // 2
            )
            return

        # Below the target if it fits, otherwise above; then clamp to the
        # window so the panel is never partly off-screen.
        y = self._hole.bottom() + _GAP
        if y + ph > area.height() - _MARGIN:
            y = self._hole.top() - _GAP - ph
        y = max(_MARGIN, min(y, area.height() - ph - _MARGIN))
        x = self._hole.center().x() - pw // 2
        x = max(_MARGIN, min(x, area.width() - pw - _MARGIN))
        self._panel.move(x, y)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        veil = QPainterPath()
        veil.addRect(QRectF(self.rect()))
        if self._hole is not None:
            cut = QPainterPath()
            cut.addRoundedRect(QRectF(self._hole), 6, 6)
            veil = veil.subtracted(cut)
        p.fillPath(veil, _DIM)
        if self._hole is not None:
            p.setPen(QPen(_ACCENT, 2))
            p.drawRoundedRect(QRectF(self._hole), 6, 6)

    # -- keeping in step with the window ------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self._host and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.LayoutRequest,
        ):
            self.setGeometry(self._host.rect())
            if self._steps:
                self._reposition()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.stop()
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.next()
        elif event.key() == Qt.Key.Key_Left:
            self.back()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        """Swallow clicks: the veil is there to keep the tour in charge."""
        event.accept()
