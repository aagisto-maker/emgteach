"""A «?» in the corner of a box, answering where the question arises.

The guided tour used to carry fourteen to seventeen steps, most of them
about a control the student could already see and would only wonder about
when they got to it. The tour is now five steps; the rest of that text lives
here, one button per box, shown over the box it is about with the same
panel the tour uses — so the explanation looks like the explanation, and it
closes with a click.

The button finds the window's coach by walking up the widget tree. That
keeps every tab free of a signal per box, and lets a tab built on its own
(in a test, say) still answer: without a coach it opens a plain message box
with the same text.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QGroupBox, QMessageBox, QToolButton, QWidget

from emgteach.gui.help_texts import text as help_text
from emgteach.gui.widgets.coach import CoachStep


class HelpButton(QToolButton):
    """A small «?» that explains the group box it sits on."""

    _SIZE = 18

    def __init__(self, box: QGroupBox, title: str, body: str) -> None:
        super().__init__(box)
        self._box = box
        self._title = title
        self._body = body
        self.setText("?")
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setToolTip(title)
        self.setStyleSheet(
            "QToolButton { font-weight: bold; color: #2E86DE; border: 1px solid "
            "#2E86DE; border-radius: 9px; background: white; }"
            "QToolButton:hover { background: #E3F0FB; }"
        )
        self.clicked.connect(self.explain)
        box.installEventFilter(self)
        self._colocar()
        self.raise_()

    # -- placement --------------------------------------------------------

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        # Only the box's own resize. Reacting to LayoutRequest as well, and
        # raising the button each time, risked feeding the event queue from
        # inside its own handler; a resize is the one thing that moves the
        # corner, and a move of a child outside the layout posts nothing back.
        if obj is self._box and event.type() == QEvent.Type.Resize:
            self._colocar()
        return False

    def _colocar(self) -> None:
        # Top-right corner, on the title line of the group box.
        self.move(self._box.width() - self._SIZE - 6, 0)

    # -- behaviour --------------------------------------------------------

    def explain(self) -> None:
        """Show the text over the box, with the coach when the window has one."""
        ventana = self.window()
        coach = getattr(ventana, "_coach", None)
        if coach is not None and hasattr(coach, "start"):
            if coach.isVisible() and getattr(coach, "is_tour", False):
                return          # never over the tour itself
            if coach.isVisible():
                coach.stop()
            caja = self._box
            coach.start([CoachStep(self._title, self._body, target=lambda: caja)])
            return
        QMessageBox.information(self, self._title, self._body)


def add_help(box: QGroupBox, key: str) -> HelpButton:
    """Put a «?» on ``box`` with the text registered under ``key``.

    The text is looked up when the button is built, so an unknown key fails
    at construction — on the developer's screen — and not on a click in the
    laboratory.
    """
    title, body = help_text(key)
    boton = HelpButton(box, title, body)
    boton.setObjectName(f"help:{key}")
    return boton


def help_buttons(parent: QWidget) -> list[HelpButton]:
    """Every «?» under ``parent`` — for tests, and for nothing else."""
    return parent.findChildren(HelpButton)
