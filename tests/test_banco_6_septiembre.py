"""Lo que salió mal en el banco del 6 de septiembre, práctica del par.

Dos cosas, las dos de la aplicación y ninguna de la señal:

1. Los fragmentos se nombraron, la tabla de coactivación salió por maniobra
   — Flexion 31 %, Grip 81 % — y **no había forma de guardar nada de eso**:
   «Save tuned EDF…» solo se mostraba en la práctica de cinemática.
2. El identificador de prueba estaba escrito en su casilla y el archivo salió
   igualmente como `emg_<fecha>.edf`, así que hubo que renombrarlo a mano.
"""
from __future__ import annotations

import pytest


class TestTheDefaultFileName:
    """«tampoco guarda el archivo con p01, he tenido que añadirlo»."""

    @pytest.fixture
    def nombre(self):
        from emgteach.gui.tabs.acquisition import nombre_por_defecto

        return nombre_por_defecto

    def test_the_identifier_leads_the_name(self, nombre) -> None:
        assert nombre("P01", "2026-09-06_09-15") == "P01_2026-09-06_09-15.edf"

    def test_without_an_identifier_nothing_changes(self, nombre) -> None:
        """Quien no rellena la casilla sigue teniendo el nombre de siempre."""
        assert nombre("", "2026-09-06_09-15") == "emg_2026-09-06_09-15.edf"
        assert nombre("   ", "2026-09-06_09-15") == "emg_2026-09-06_09-15.edf"

    def test_it_is_free_text_so_it_is_cleaned(self, nombre) -> None:
        """La casilla propone «e.g. bench 3, attempt 2», que lleva coma y
        espacios; y en Windows unos cuantos caracteres no valen en un nombre."""
        assert nombre("bench 3, attempt 2", "S") == "bench-3-attempt-2_S.edf"
        assert nombre('a/b\\c:d*e?f"g<h>i|j', "S") == "a-b-c-d-e-f-g-h-i-j_S.edf"

    def test_punctuation_only_falls_back(self, nombre) -> None:
        """Un identificador que no deja nada utilizable no puede dar un nombre
        que empiece por guion o por punto."""
        assert nombre("///", "S") == "emg_S.edf"
        assert nombre("...", "S") == "emg_S.edf"
        assert nombre("-_-", "S") == "emg_S.edf"

    def test_a_long_identifier_does_not_bury_the_date(self, nombre) -> None:
        from emgteach.gui.tabs.acquisition import MAX_ID_EN_NOMBRE

        salida = nombre("X" * 80, "2026-09-06_09-15")
        assert salida == "X" * MAX_ID_EN_NOMBRE + "_2026-09-06_09-15.edf"

    def test_the_dialogue_opens_with_it(self, qapp, monkeypatch, tmp_path) -> None:
        """Y no solo la función: el diálogo de guardar tiene que abrirse con
        ese nombre, que es donde se vio el fallo."""
        from PySide6.QtCore import QSettings

        from emgteach.gui.app import MainWindow

        s = QSettings("emgteach-test", "nombre-por-defecto")
        s.clear()
        s.setValue("adquisicion/save_dir", str(tmp_path))
        s.setValue("app/tour_offer", False)
        win = MainWindow(s)
        try:
            adq = win._tab_adq
            adq._edit_student_code.setText("P01")
            visto = {}

            def falso_dialogo(parent, titulo, ruta, filtro):
                visto["ruta"] = ruta
                return "", ""      # cancelar: no arranca ninguna grabación

            monkeypatch.setattr(
                "emgteach.gui.tabs.acquisition.QFileDialog.getSaveFileName",
                falso_dialogo,
            )
            adq._btn_grabar.setChecked(True)
            adq._toggle_grabacion()
            assert "ruta" in visto, "no se llegó a abrir el diálogo de guardar"
            assert visto["ruta"].split("\\")[-1].split("/")[-1].startswith("P01_")
        finally:
            s.clear()
            win.close()
            win.deleteLater()
            qapp.processEvents()


class TestTheAutomaticScreenshot:
    """«me lío con grabar, contraer, capturar, tiempo».

    El sujeto y el operador son la misma persona, así que una tecla que hay
    que pulsar en el instante justo es una cosa de más — y lo que se pierde es
    siempre la foto, nunca la contracción.
    """

    @pytest.fixture
    def ventana(self, qapp, tmp_path):
        from PySide6.QtCore import QSettings

        from emgteach.gui.app import MainWindow

        s = QSettings("emgteach-test", "auto-captura")
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
            s.clear()
            win.close()
            win.deleteLater()
            qapp.processEvents()

    def test_it_is_a_button_and_starts_disarmed(self, ventana) -> None:
        """Un botón y no un ajuste: no siempre se quiere capturar."""
        assert ventana._btn_auto_captura.isCheckable()
        assert not ventana._btn_auto_captura.isChecked()
        assert not ventana._timer_captura.isActive()

    def test_arming_it_starts_the_clock(self, ventana) -> None:
        from emgteach.gui.app import AUTO_CAPTURA_MS

        ventana._btn_auto_captura.setChecked(True)
        assert ventana._timer_captura.isActive()
        assert ventana._timer_captura.interval() == AUTO_CAPTURA_MS
        ventana._btn_auto_captura.setChecked(False)
        assert not ventana._timer_captura.isActive()

    def test_armed_but_not_recording_writes_nothing(
        self, ventana, tmp_path
    ) -> None:
        """Puede quedarse pulsado toda la tarde: fuera de una grabación no
        escribe nada, que es lo que lo hace no tener que desactivarse."""
        ventana._btn_auto_captura.setChecked(True)
        for _ in range(5):
            ventana._tic_captura()
        assert list(tmp_path.glob("*.png")) == []

    def test_while_recording_it_takes_them_on_its_own(
        self, ventana, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(ventana._tab_adq, "is_recording", lambda: True)
        ventana._btn_auto_captura.setChecked(True)
        for _ in range(3):
            ventana._tic_captura()
        assert len(list(tmp_path.glob("*.png"))) == 3

    def test_it_does_not_write_a_line_per_picture(
        self, ventana, monkeypatch
    ) -> None:
        """Treinta líneas enterrarían los marcadores, que es para lo que está
        el registro de eventos. Lo que se dice es el total, al terminar."""
        monkeypatch.setattr(ventana._tab_adq, "is_recording", lambda: True)
        ventana._btn_auto_captura.setChecked(True)
        for _ in range(3):
            ventana._tic_captura()
        assert "Captura guardada" not in ventana._logger.toPlainText()
        assert "Screenshot saved" not in ventana._logger.toPlainText()

        monkeypatch.setattr(ventana._tab_adq, "is_recording", lambda: False)
        ventana._tic_captura()
        texto = ventana._logger.toPlainText()
        assert "3" in texto.splitlines()[-1]

    def test_the_key_still_says_where_the_picture_went(self, ventana) -> None:
        """La captura que pide una persona sí se anota: la pide para llevársela
        y tiene que saber a dónde fue."""
        assert ventana._guardar_captura() is True
        assert "emgteach_captura_" in ventana._logger.toPlainText()

    def test_a_failure_is_reported_even_when_automatic(
        self, ventana, monkeypatch
    ) -> None:
        from pathlib import Path

        def revienta(*_a, **_k):
            raise OSError("disco lleno")

        monkeypatch.setattr(Path, "mkdir", revienta)
        assert ventana._guardar_captura(silenciosa=True) is False
        assert "disco lleno" in ventana._logger.toPlainText()


class TestSavingTheTunedRecording:
    """«se ha perdido el botón de save tuned edf».

    No se perdió: no se ofrecía. Estaba condicionado a la práctica avanzada,
    con el argumento de que un EDF derivado es para quien cura los registros y
    no para el alumno que lee uno. Eso vale para el alumno y no para la
    práctica: el resultado por maniobra del par es justo lo que hay que poder
    sacar de la pantalla.
    """

    @pytest.fixture
    def tab(self, qapp, tmp_path):
        from PySide6.QtCore import QSettings

        from emgteach.gui.app import MainWindow

        s = QSettings("emgteach-test", "afinado-visible")
        s.clear()
        s.setValue("app/mode", "pair")
        s.setValue("app/tour_offer", False)
        win = MainWindow(s)
        win.show()
        qapp.processEvents()
        try:
            yield win._tab_ana
        finally:
            s.clear()
            win.close()
            win.deleteLater()
            qapp.processEvents()

    # `isHidden()` y no `isVisible()`: la pestaña de Análisis no es la que está
    # al frente en estas pruebas, y un hijo de una pestaña de atrás nunca es
    # «visible» aunque nadie lo haya ocultado. Lo que se comprueba aquí es la
    # decisión de la propia pestaña, que es lo que la corrección cambia.

    def test_it_stays_out_of_the_way_until_there_is_one(self, tab) -> None:
        """Sin fragmentos elegidos no hay registro afinado que guardar, y el
        alumno que solo abre un archivo no ve el botón."""
        assert tab._selected_segments == []
        assert tab._btn_afinado.isHidden()

    def test_choosing_fragments_offers_it(self, tab, qapp) -> None:
        from emgteach.selection import Segment

        tab._selected_segments = [Segment(0.0, 1.0, "Flexion")]
        tab._actualizar_etiqueta_fragmentos()
        qapp.processEvents()
        assert not tab._btn_afinado.isHidden()
        # Y su fila con él: el botón vive dentro de ella.
        assert not tab._box_tools.isHidden()

    def test_dropping_them_takes_it_away_again(self, tab, qapp) -> None:
        from emgteach.selection import Segment

        tab._selected_segments = [Segment(0.0, 1.0, "Flexion")]
        tab._actualizar_etiqueta_fragmentos()
        tab._selected_segments = []
        tab._actualizar_etiqueta_fragmentos()
        qapp.processEvents()
        assert tab._btn_afinado.isHidden()

    def test_the_envelope_cutoff_stays_advanced_only(self, tab, qapp) -> None:
        """La fila que lo contiene lleva además el corte de la envolvente, que
        sí es un ajuste fino: enseñar la fila no puede sacarlo a la vista."""
        from emgteach.selection import Segment

        tab._selected_segments = [Segment(0.0, 1.0, "Flexion")]
        tab._actualizar_etiqueta_fragmentos()
        qapp.processEvents()
        assert tab._box_fenv.isHidden()

    def test_the_advanced_practical_keeps_offering_it_from_the_start(
        self, qapp, tmp_path
    ) -> None:
        from PySide6.QtCore import QSettings

        from emgteach.gui.app import MainWindow

        s = QSettings("emgteach-test", "afinado-cinematica")
        s.clear()
        s.setValue("app/mode", "kinematics")
        s.setValue("app/tour_offer", False)
        win = MainWindow(s)
        win.show()
        qapp.processEvents()
        try:
            assert not win._tab_ana._btn_afinado.isHidden()
        finally:
            s.clear()
            win.close()
            win.deleteLater()
            qapp.processEvents()
