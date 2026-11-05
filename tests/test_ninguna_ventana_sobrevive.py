"""The fixture that closes what a test leaves on screen
(tests/conftest.py, ``no_window_outlives_its_test``).

What it must do with what it finds: stop an acquisition tab the way the
application stops it on closing — not just hide it, which would leave its
timers ticking into the tests that follow — and close a dialog without
answering it, so no «Retry» runs the application's code on the way out.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from tests.conftest import _close_for_good, _shown_windows, _widget_of

pytestmark = pytest.mark.gui


def test_a_tab_left_on_screen_is_stopped_before_it_is_closed(qapp) -> None:
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    logger = LoggerWidget()
    tab = AcquisitionTab(logger, QSettings("emgteach-test", "ninguna-ventana"))
    tab.show()
    qapp.processEvents()
    tab._trazado._render_timer.start()
    tab._conexion._watchdog_timer.start()
    tab._conexion._conexion_timer.start()
    llamadas: list[str] = []
    limpieza = tab.cleanup

    def cleanup() -> None:
        llamadas.append("cleanup")
        limpieza()

    tab.cleanup = cleanup
    assert tab.windowHandle() in _shown_windows(qapp).values()

    _close_for_good(tab)

    assert llamadas == ["cleanup"]
    assert not tab._trazado._render_timer.isActive()
    assert not tab._conexion._watchdog_timer.isActive()
    assert not tab._conexion._conexion_timer.isActive()
    assert not tab.isVisible()
    qapp.processEvents()
    logger.deleteLater()


def test_a_dialog_left_open_is_closed_without_an_answer(qapp) -> None:
    caja = QMessageBox(
        QMessageBox.Icon.Warning, "The board did not answer", "…",
        QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Close)
    respuestas: list[int] = []
    caja.finished.connect(respuestas.append)
    caja.open()
    qapp.processEvents()
    assert caja.windowHandle() in _shown_windows(qapp).values()

    _close_for_good(caja)

    assert not caja.isVisible()
    assert respuestas == []           # nobody was told it was answered


def test_a_window_on_screen_is_traced_back_to_its_widget(qapp) -> None:
    """Only the windows on screen are looked at; the widget behind one is
    found for what is left over."""
    from PySide6.QtWidgets import QWidget

    nunca_mostrado = QWidget()
    mostrado = QWidget()
    mostrado.show()
    qapp.processEvents()
    try:
        ventanas = list(_shown_windows(qapp).values())
        assert nunca_mostrado.windowHandle() is None
        assert [_widget_of(v) for v in ventanas] == [mostrado]
    finally:
        mostrado.close()
        mostrado.deleteLater()
        nunca_mostrado.deleteLater()
        qapp.processEvents()


def test_a_window_whose_object_is_gone_is_passed_over(qapp, monkeypatch) -> None:
    """Qt can list an address shiboken still knows by the wrapper of what was
    deleted there; reading it raises, and in CI that failed the set-up of an
    unrelated test. The scan passes it over."""
    import shiboken6
    from PySide6.QtGui import QGuiApplication, QWindow

    muerta = QWindow()
    shiboken6.delete(muerta)               # the wrapper outlives its object
    assert not shiboken6.isValid(muerta)
    monkeypatch.setattr(QGuiApplication, "topLevelWindows", staticmethod(lambda: [muerta]))
    assert _shown_windows(qapp) == {}
    assert _widget_of(muerta) is None
