"""A spin box that writes the decimal point, and reads the comma too.

Qt's widgets follow the operating system, not the application's language:
on the Spanish Windows of the laboratory every ``QDoubleSpinBox`` wrote
``4,4`` and refused the ``4.4`` a student typed into it, while the label
beside it, the report and the manual all wrote ``4.4``
(:func:`emgteach.i18n.cifra`). The number read and the number typed are
the same number, so they are written the same way.

Read either way on purpose: the numeric keypad of a Spanish keyboard
sends a comma, and refusing it would put a new fault in place of the old
one. A comma typed in becomes the point the field shows.
"""

from __future__ import annotations

from PySide6.QtCore import QLocale
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QDoubleSpinBox, QWidget

__all__ = ["DecimalSpinBox"]


class DecimalSpinBox(QDoubleSpinBox):
    """A ``QDoubleSpinBox`` with the point as decimal mark in any locale."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Its own locale, not the application's default: these are built
        # by the tools that draw the images and by the tests, outside the
        # start-up that could set a default.
        self.setLocale(QLocale.c())

    def validate(self, text: str, pos: int) -> tuple[QValidator.State, str, int]:
        """Take the comma as a decimal mark; the field keeps the point."""
        return super().validate(text.replace(",", "."), pos)

    def valueFromText(self, text: str) -> float:
        return super().valueFromText(text.replace(",", "."))
