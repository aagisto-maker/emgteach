"""
LoggerWidget — shared log console for all tabs.

A QTextEdit in read-only mode. Each tab receives a reference to the single
instance created by MainWindow and calls append_log() / append_error().
Color-coded: normal messages in default color, errors in red.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtGui import QFont, QFontMetrics, QTextCursor
from PySide6.QtWidgets import QTextEdit


class LoggerWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        font = QFont("Consolas")
        font.setPixelSize(11)
        self.setFont(font)
        fm = QFontMetrics(font)
        self.setMaximumHeight(fm.lineSpacing() * 5 + 8)
        self.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")

    @Slot(str)
    def append_log(self, message: str) -> None:
        self.append(f"<span style='color:#202020;'>{message}</span>")
        self.moveCursor(QTextCursor.MoveOperation.End)

    @Slot(str)
    def append_error(self, message: str) -> None:
        self.append(f"<span style='color:#cc0000;'><b>Error:</b> {message}</span>")
        self.moveCursor(QTextCursor.MoveOperation.End)
