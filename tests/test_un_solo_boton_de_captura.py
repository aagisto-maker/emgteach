"""«Captura» y «Auto» eran dos botones seguidos en la esquina.

Son la misma idea —una foto de la ventana— pedida de dos maneras, así que
pasan a ser un control: el cuerpo hace la foto de ahora y la flechita abre la
entrada que las hace solas. Lo que no se puede perder al juntarlos es **que se
vea si está armado**: el valor entero de esa función es armarla y olvidarse, y
con el menú cerrado el tic no se ve.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def ventana(qapp, tmp_path):
    from PySide6.QtCore import QSettings

    from emgteach.gui.app import MainWindow

    s = QSettings("emgteach-test", "un-solo-boton")
    s.clear()
    s.setValue("adquisicion/save_dir", str(tmp_path))
    s.setValue("app/tour_offer", False)
    win = MainWindow(s)
    win.resize(900, 600)
    win.show()
    qapp.processEvents()
    try:
        yield win
    finally:
        # El reloj vive mientras viva la ventana.
        win._act_auto_captura.setChecked(False)
        s.clear()
        win.close()
        win.deleteLater()
        qapp.processEvents()


class TestOneControlAndNotTwo:
    def test_the_corner_has_one_screenshot_button(self, ventana) -> None:
        from PySide6.QtWidgets import QToolButton

        from emgteach.i18n import tr

        esquina = ventana._tabs.cornerWidget()
        textos = [
            b.text() for b in esquina.findChildren(QToolButton)
        ]
        assert textos.count(tr("Screenshot")) == 1
        assert "Auto" not in textos

    def test_the_arrow_opens_the_automatic_one(self, ventana) -> None:
        from PySide6.QtWidgets import QToolButton

        menu = ventana._btn_captura.menu()
        assert menu is not None
        assert menu.actions() == [ventana._act_auto_captura]
        assert (
            ventana._btn_captura.popupMode()
            == QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )

    def test_the_body_does_not_arm_anything(self, ventana, tmp_path) -> None:
        """El cuerpo hace la foto de ahora, y solo eso: un botón marcable se
        habría armado al hacerla."""
        assert not ventana._btn_captura.isCheckable()
        ventana._btn_captura.click()
        assert len(list(tmp_path.glob("*.png"))) == 1
        assert not ventana._act_auto_captura.isChecked()
        assert not ventana._timer_captura.isActive()

    def test_the_entry_says_how_often(self, ventana) -> None:
        from emgteach.gui.app import AUTO_CAPTURA_MS

        assert (
            f"{AUTO_CAPTURA_MS / 1000:.0f}" in ventana._act_auto_captura.text()
        )


class TestTheArmedStateIsVisible:
    """Con el menú cerrado el tic no se ve, así que lo dice el botón."""

    def test_the_button_is_marked_while_armed(self, ventana) -> None:
        from emgteach.i18n import tr

        assert ventana._btn_captura.text() == tr("Screenshot")
        ventana._act_auto_captura.setChecked(True)
        assert ventana._btn_captura.text() != tr("Screenshot")
        assert ventana._btn_captura.text().startswith(tr("Screenshot"))
        ventana._act_auto_captura.setChecked(False)
        assert ventana._btn_captura.text() == tr("Screenshot")

    def test_the_corner_does_not_move_when_it_is_armed(self, ventana) -> None:
        """La marca tiene su sitio reservado desde el principio: si no, toda la
        fila se correría de lado cada vez que se arma."""
        ancho = ventana._btn_captura.width()
        esquina = ventana._tabs.cornerWidget().width()
        ventana._act_auto_captura.setChecked(True)
        assert ventana._btn_captura.sizeHint().width() <= ancho
        assert ventana._tabs.cornerWidget().sizeHint().width() == esquina

    def test_arming_it_still_starts_the_clock_and_says_so(
        self, ventana
    ) -> None:
        """El aviso del registro de eventos que ya existía se queda igual."""
        from emgteach.gui.app import AUTO_CAPTURA_MAX, AUTO_CAPTURA_MS
        from emgteach.i18n import tr

        ventana._act_auto_captura.setChecked(True)
        assert ventana._timer_captura.isActive()
        assert tr(
            "Automatic screenshots armed: one every {s:.0f} s while "
            "recording, at most {n} per recording."
        ).format(s=AUTO_CAPTURA_MS / 1000, n=AUTO_CAPTURA_MAX) in (
            ventana._logger.toPlainText())

    def test_the_key_still_works(self, ventana, tmp_path) -> None:
        """F12 desde cualquier pestaña no pasa por el botón."""
        ventana._atajo_captura.activated.emit()
        assert len(list(tmp_path.glob("*.png"))) == 1
