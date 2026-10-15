"""ManualMarker — the label selector, the «Mark» button and the M key.

The acquisition tab holds one and only says when a recording is running: the
widget does the rest, and emits :attr:`ManualMarker.marked` with the label as
the interface writes it at that moment. What the label means, and how the
analysis tells a manual mark from the others, is in
:mod:`emgteach.manual_marks`.

The M key is a shortcut of the tab that holds the widget. A text field with
the focus keeps its letters — Qt hands a plain key to the field before any
shortcut — so typing a name with an «m» in it while recording marks nothing.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

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

        self.button = QPushButton(tr("Mark"))
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
