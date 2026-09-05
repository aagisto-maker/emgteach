"""Qt's own strings — the standard dialog buttons above all.

"Yes", "No", "OK", "Cancel" and "Save" are drawn by Qt and translated from
its own catalogue, not from :mod:`emgteach.i18n`. With no translator installed
a Spanish interface still asks the user to press "Yes", which is exactly what
it did until this was added.

Marked ``gui`` (needs a QApplication).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui

_BUTTONS = ("Yes", "No", "Ok", "Cancel", "Save")


def _standard_button_texts() -> list[str]:
    from PySide6.QtWidgets import QMessageBox

    box = QMessageBox()
    flags = QMessageBox.StandardButton(0)
    for name in _BUTTONS:
        flags |= getattr(QMessageBox.StandardButton, name)
    box.setStandardButtons(flags)
    return [
        box.button(getattr(QMessageBox.StandardButton, name)).text().replace("&", "")
        for name in _BUTTONS
    ]


def test_spanish_translates_the_standard_buttons(qapp) -> None:
    from emgteach.gui.app import install_qt_translations

    translator = install_qt_translations(qapp, "es")
    assert translator is not None, "PySide6 should ship qtbase_es"
    try:
        assert _standard_button_texts() == [
            "Sí", "No", "Aceptar", "Cancelar", "Guardar",
        ]
    finally:
        qapp.removeTranslator(translator)


def test_english_installs_nothing(qapp) -> None:
    """Qt's untranslated strings are already English, so there is nothing to
    load — and nothing to leave installed for the next caller."""
    from emgteach.gui.app import install_qt_translations

    assert install_qt_translations(qapp, "en") is None
    assert _standard_button_texts() == ["Yes", "No", "OK", "Cancel", "Save"]
