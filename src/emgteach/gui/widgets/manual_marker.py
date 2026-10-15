"""ManualMarker — the label selector, the «Mark» button and the M key.

The acquisition tab holds one and only says when a recording is running: the
widget does the rest, and emits :attr:`ManualMarker.marked` with the label as
the interface writes it at that moment. What the label means, and how the
analysis tells a manual mark from the others, is in
:mod:`emgteach.manual_marks`.

The M key is a shortcut of the tab that holds the widget. A text field with
the focus keeps its letters — Qt hands a plain key to the field before any
shortcut — so typing a name with an «m» in it while recording marks nothing.
The other half is getting out of the field: :func:`give_back_focus` makes
Enter or Esc in any text field of the tab, or a click anywhere in it that is
not a text field (the live plots included), hand the focus back to the tab,
and the M marks again. At the bench of 15 October 2026 the operator typed the
test identifier, clicked on the live plot and the M still typed into the field.

The live plots are the case apart (:func:`hand_the_m_over`). A click inside one
gave it the focus — pyqtgraph makes its views StrongFocus — and on that bench,
with Windows' own platform, the M then marked nothing. Offscreen, the M goes
through the plot to the shortcut, so the cause could not be reproduced here;
the plots take no focus now, so a click in them hands it to the tab, and a M
that still reaches one of them marks all the same.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget

from emgteach.i18n import tr
from emgteach.manual_marks import MANUAL_MARK_LABELS, MARK_KEY


class ManualMarker(QWidget):
    """A label to choose and two ways to mark with it, only while recording."""

    #: The selected label, in the language of the interface.
    marked = Signal(str)

    def __init__(self, shortcut_owner: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.combo = QComboBox()
        for label in MANUAL_MARK_LABELS:
            self.combo.addItem(tr(label), label)
        self.combo.setToolTip(tr("Label of the next mark."))
        layout.addWidget(self.combo)

        # The key on the button itself: said once in the log when the
        # recording starts, it scrolled out of sight before anyone needed it.
        self.button = QPushButton(tr("Mark (M)"))
        self.button.setToolTip(tr(
            "Marks this moment of the recording with the selected label (key M). "
            "Only while recording."
        ))
        self.button.clicked.connect(self.mark)
        layout.addWidget(self.button)

        self.shortcut = QShortcut(QKeySequence(MARK_KEY), shortcut_owner)
        self.shortcut.activated.connect(self.mark)

        self.set_recording(False)

    def set_recording(self, recording: bool) -> None:
        """Offer the marking while a recording runs, and only then."""
        self._recording = bool(recording)
        self.combo.setEnabled(self._recording)
        self.button.setEnabled(self._recording)
        self.shortcut.setEnabled(self._recording)

    def is_recording(self) -> bool:
        return self._recording

    def label(self) -> str:
        """The selected label, as the interface writes it now."""
        return tr(str(self.combo.currentData()))

    @Slot()
    def mark(self) -> None:
        """Mark with the selected label; nothing outside a recording."""
        if self._recording:
            self.marked.emit(self.label())


_KEYS_THAT_LEAVE = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape)


class _FocusBack(QObject):
    """Enter or Esc in a text field hands the focus back to *owner*.

    The key is not consumed: Enter still confirms the field and Esc still
    reaches the tab's own Esc shortcut. Esc is seen as a shortcut override
    too, since a shortcut on the same key can take it before the key press.
    """

    def __init__(self, owner: QWidget) -> None:
        super().__init__(owner)
        self._owner = owner

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if (event.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride)
                and isinstance(event, QKeyEvent)
                and event.key() in _KEYS_THAT_LEAVE):
            QTimer.singleShot(0, self._owner.setFocus)
        return False


def give_back_focus(owner: QWidget) -> None:
    """Make every way out of a text field of *owner* hand the focus to *owner*.

    Enter or Esc in any of its text fields, and a click on any part of it
    that does not take the focus itself — the live plots, the empty space
    between boxes: *owner* takes the click's focus, so the field loses it.
    Called once the tab is built, so it reaches every field.
    """
    owner.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    back = _FocusBack(owner)
    for field in owner.findChildren(QLineEdit):
        field.installEventFilter(back)


class _MarkFromPlot(QObject):
    """A plain M reaching a live plot marks, while recording.

    The shortcut takes the M before the key press when it can; this is for a
    platform where the plot gets it anyway. The key is consumed only when it
    marks, so a plot outside a recording behaves as before.
    """

    def __init__(self, marker: ManualMarker) -> None:
        super().__init__(marker)
        self._marker = marker

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if (event.type() == QEvent.Type.KeyPress
                and isinstance(event, QKeyEvent)
                and event.key() == Qt.Key.Key_M
                and event.modifiers() in (Qt.KeyboardModifier.NoModifier,
                                          Qt.KeyboardModifier.ShiftModifier)
                and self._marker.is_recording()):
            self._marker.mark()
            return True
        return False


def hand_the_m_over(plots: list[QWidget], marker: ManualMarker) -> None:
    """Keep the live *plots* from holding the focus the M needs.

    They take no focus of their own: a click in one goes to the first parent
    that takes it — the tab, after :func:`give_back_focus` — and the shortcut
    fires from there. Zoom, drag and the wheel are mouse events and do not
    need the focus; what goes is pyqtgraph's keyboard zoom (-, +, Backspace),
    which the application never offered. Should a M reach a plot all the
    same, it marks (:class:`_MarkFromPlot`).
    """
    to_marker = _MarkFromPlot(marker)
    for plot in plots:
        widgets = [plot]
        viewport = getattr(plot, "viewport", None)
        if callable(viewport):
            widgets.append(viewport())
        for w in widgets:
            w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            w.installEventFilter(to_marker)
