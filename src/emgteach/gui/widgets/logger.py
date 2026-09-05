"""
LoggerWidget — shared log console for all tabs.

A QTextEdit in read-only mode. Each tab receives a reference to the single
instance created by MainWindow and calls append_log() / append_error().
Color-coded: normal messages in default color, errors in red.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtGui import QFont, QFontMetrics, QTextCursor
from PySide6.QtWidgets import QSizePolicy, QTextEdit

from emgteach.i18n import tr


class LoggerWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        font = QFont("Consolas")
        font.setPixelSize(11)
        self.setFont(font)
        fm = QFontMetrics(font)
        # Three lines was a ceiling, and the box around it is taller than
        # three lines in both tabs that carry one — so the log ended in the
        # top corner of an empty rectangle, showing the last three messages
        # of a session that had written twenty. It fills its box now: a
        # floor of three lines, no ceiling, and a size policy that takes
        # whatever height the box has without asking for any of its own (the
        # box beside it, the parameters, is what sets the row's height).
        self.setMinimumHeight(fm.lineSpacing() * 3 + 8)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")

    @Slot(str)
    def append_log(self, message: str) -> None:
        self.append(f"<span style='color:#202020;'>{message}</span>")
        self.moveCursor(QTextCursor.MoveOperation.End)

    @Slot(str)
    def append_error(self, message: str) -> None:
        self.append(
            f"<span style='color:#cc0000;'><b>{tr('Error:')}</b> {message}</span>"
        )
        self.moveCursor(QTextCursor.MoveOperation.End)
