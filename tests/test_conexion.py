"""The device and its link as a piece of their own (step 2 of
docs/PLAN-partir-AcquisitionTab.md): `ConnectionBox` is built with the
settings and a way to ask for the current worker, and nothing else. It
holds the device row, the Connect button and the LED, and watches the link
while a recording runs; what reaches the recording it hands back to the tab
through signals. The tab's side — the record button, the status line, the
recording itself — is covered by the tests that start one
(tests/test_la_placa_que_no_responde.py and others).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from emgteach import station
from emgteach.gui.acquisition.connection import (
    CONEXION_MAX_S,
    DEFAULT_BITALINO_ADDR,
    LED_IDLE_MS,
    ConnectionBox,
)
from emgteach.i18n import tr

pytestmark = pytest.mark.gui


class _Hilo:
    """A worker that runs nothing: it answers what it is asked."""

    def __init__(self, *, transmitiendo: bool = True, silencio: float = 0.0,
                 respondio: bool = True) -> None:
        self.corriendo = True
        self.transmitiendo = transmitiendo
        self.silencio = silencio
        self.respondio = respondio
        self.forzado = 0
        self.esperas: list[int] = []

    def isRunning(self) -> bool:
        return self.corriendo

    def is_streaming(self) -> bool:
        return self.transmitiendo

    def time_since_last_sample(self) -> float:
        return self.silencio

    def placa_respondio(self) -> bool:
        return self.respondio

    def stop_forced(self) -> None:
        self.forzado += 1

    def wait(self, ms: int) -> bool:
        self.esperas.append(ms)
        self.corriendo = False
        return True


@pytest.fixture
def caja(qapp, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(station, "app_folder", lambda: tmp_path)   # no bitalino.txt
    ajustes = QSettings("emgteach-test", "conexion")
    ajustes.clear()
    hilo: list[_Hilo | None] = [None]
    box = ConnectionBox(ajustes, worker=lambda: hilo[0])
    box.registro: list[str] = []
    box.avisos: list[str] = []
    box.tipos: list[int] = []
    box.senales: list[str] = []
    box.logged.connect(box.registro.append)
    box.warned.connect(box.avisos.append)
    box.device_type_changed.connect(box.tipos.append)
    box.link_lost.connect(lambda: box.senales.append("perdida"))
    box.no_answer.connect(lambda: box.senales.append("sin respuesta"))
    box.retry_requested.connect(lambda: box.senales.append("reintentar"))
    yield box, ajustes, hilo
    box.stop()
    box.close()
    box.deleteLater()
    qapp.processEvents()


def test_it_starts_on_the_saved_device_with_the_lab_s_address(caja) -> None:
    box, _ajustes, _hilo = caja
    assert box.device_index() == 0 and box.address() == DEFAULT_BITALINO_ADDR
    assert not box._widget_mac.isHidden() and box._widget_arduino.isHidden()
    assert box.connect_button.text() == tr("Connect") and box.connect_button.isCheckable()
    assert not box.is_connected()
    assert "#C0392B" in box.led.styleSheet()          # red: disconnected
    assert box.idle_status() == (tr("Status: disconnected"), "")


def test_choosing_the_arduino_shows_its_port_and_asks_for_the_scale(caja) -> None:
    box, _ajustes, _hilo = caja
    box._combo_device_type.setCurrentIndex(1)
    assert box._widget_mac.isHidden() and not box._widget_arduino.isHidden()
    assert box.tipos == [1]
    box.select_bitalino("simulada")
    assert box.device_index() == 0 and box.address() == "simulada"
    assert box.tipos == [1, 0]


def test_connecting_locks_the_device_and_saves_it(caja) -> None:
    box, ajustes, _hilo = caja
    box.select_bitalino("  simulada ")
    box.connect_button.setChecked(True)
    assert box.connect_device() == "simulada"
    assert ajustes.value("adquisicion/port") == "simulada"
    assert int(ajustes.value("adquisicion/device_type")) == 0
    assert box.connect_button.text() == tr("Disconnect")
    assert not box._combo_device_type.isEnabled() and not box._widget_mac.isEnabled()
    assert "#F1C40F" in box.led.styleSheet()          # yellow: connected, no traffic
    assert box.idle_status() == (tr("Status: connected (ready to record)"), "")
    box.disconnect_device()
    assert not box.is_connected() and box.connect_button.text() == tr("Connect")
    assert box._combo_device_type.isEnabled() and box._widget_mac.isEnabled()
    assert "#C0392B" in box.led.styleSheet()


def test_an_arduino_without_a_port_is_not_connected(caja) -> None:
    box, _ajustes, _hilo = caja
    box._combo_device_type.setCurrentIndex(1)
    box._combo_port.clear()
    box.connect_button.setChecked(True)
    assert box.connect_device() is None
    assert box.avisos == [tr("Select a COM port for the Arduino before connecting.")]
    assert not box.is_connected() and box._combo_device_type.isEnabled()


def test_the_first_block_ends_the_wait_and_starts_the_watchdog(caja) -> None:
    box, _ajustes, hilo = caja
    box.select_bitalino(DEFAULT_BITALINO_ADDR)          # the real board
    box.connect_button.setChecked(True)
    box.connect_device()
    hilo[0] = _Hilo()
    box.recording_started()
    assert not box.connect_button.isEnabled()
    assert box._conexion_timer.isActive()
    assert box._conexion_timer.interval() == int(CONEXION_MAX_S * 1000)
    assert box.block_arrived() is True
    assert not box._conexion_timer.isActive() and box._watchdog_timer.isActive()
    assert box.block_arrived() is False                   # only the first one is
    box.traffic()
    assert "#27AE60" in box.led.styleSheet()              # green
    assert box._led_idle_timer.isActive() and box._led_idle_timer.interval() == LED_IDLE_MS
    box.stop_watchdog()
    box.recording_finished()
    assert box.connect_button.isEnabled() and not box._watchdog_timer.isActive()
    # The real BITalino answered: the next recording needs it restarted.
    texto, ayuda = box.idle_status()
    assert texto == tr("Status: switch the board off and on, wait about 20 s and press Start")
    assert "BITalino" in ayuda
    box.recording_requested()
    assert box.idle_status() == (tr("Status: connected (ready to record)"), "")


def test_the_simulated_board_needs_no_restart(caja) -> None:
    box, _ajustes, hilo = caja
    box.select_bitalino("simulada")
    box.connect_button.setChecked(True)
    box.connect_device()
    hilo[0] = _Hilo()
    box.recording_started()
    box.block_arrived()
    assert box.idle_status() == (tr("Status: connected (ready to record)"), "")


def test_a_recording_stopped_before_its_first_block_says_the_board_did_not_answer(caja) -> None:
    box, _ajustes, hilo = caja
    box.connect_button.setChecked(True)
    box.connect_device()
    hilo[0] = _Hilo(respondio=False)
    box.recording_started()
    box.mark_if_no_answer()
    assert box.idle_status() == (tr("Status: the board did not answer"), "")
    assert "#C0392B" in box.led.styleSheet()
    # A board that answered, with a file that could not be made, did answer.
    hilo[0] = _Hilo(respondio=True)
    box.recording_started()
    box.mark_if_no_answer()
    assert box.idle_status() == (tr("Status: connected (ready to record)"), "")


def test_no_block_in_time_stops_and_offers_to_retry(caja, qapp) -> None:
    box, _ajustes, hilo = caja
    box.connect_button.setChecked(True)
    box.connect_device()
    hilo[0] = _Hilo(transmitiendo=False)                  # still reaching the board
    box.recording_started()
    box._conexion_sin_datos()
    assert hilo[0].forzado == 1
    assert box.senales == ["sin respuesta"]
    assert len(box.avisos) == 1 and "20 s" in box.avisos[0]
    assert box.idle_status()[0] == tr("Status: the board did not answer")
    assert isinstance(box._aviso_conexion, QMessageBox)
    box._aviso_conexion.done(int(QMessageBox.StandardButton.Retry))
    qapp.processEvents()
    assert box._aviso_conexion is None
    assert box.senales == ["sin respuesta", "reintentar"]
    # «Close» asks for nothing.
    box._conexion_sin_datos()
    box._aviso_conexion.done(int(QMessageBox.StandardButton.Close))
    qapp.processEvents()
    assert box.senales == ["sin respuesta", "reintentar", "sin respuesta"]


def test_a_board_that_streams_is_never_told_it_did_not_answer(caja) -> None:
    box, _ajustes, hilo = caja
    hilo[0] = _Hilo(transmitiendo=True)
    box._conexion_sin_datos()
    assert hilo[0].forzado == 0 and box.senales == [] and box._aviso_conexion is None


def test_the_watchdog_disconnects_when_the_samples_stop(caja) -> None:
    box, _ajustes, hilo = caja
    hilo[0] = _Hilo(silencio=1.0)
    box._watchdog_timer.start()
    box._check_watchdog()
    assert box.senales == [] and box._watchdog_timer.isActive()
    hilo[0].silencio = 4.2
    box._check_watchdog()
    assert box.avisos == [
        tr("No data from the device for {s:.1f} s — forcing disconnection.").format(s=4.2)]
    assert hilo[0].forzado == 1 and hilo[0].esperas == [2000]
    assert not box._watchdog_timer.isActive()
    assert box.senales == ["perdida"]


def test_the_station_s_address_is_the_default_and_is_said(qapp, monkeypatch, tmp_path) -> None:
    (tmp_path / station.ADDRESS_FILE).write_text("AA:BB:CC:DD:EE:FF\n", encoding="utf-8")
    monkeypatch.setattr(station, "app_folder", lambda: tmp_path)
    ajustes = QSettings("emgteach-test", "conexion-puesto")
    ajustes.clear()
    box = ConnectionBox(ajustes, worker=lambda: None)
    try:
        registro: list[str] = []
        box.logged.connect(registro.append)
        qapp.processEvents()
        assert box.address() == "AA:BB:CC:DD:EE:FF"
        assert len(registro) == 1 and station.ADDRESS_FILE in registro[0]
        box.set_practical(single_muscle=True)
        assert box._lbl_first_setup.isHidden()      # a station with the file is set up
    finally:
        # set_practical shows the row; with no tab around it, that is a
        # window of its own, and a window left open takes the activation
        # the keyboard tests after this one need.
        box.close()
        box.deleteLater()
        qapp.processEvents()


def test_the_tab_lays_it_out_where_it_was(qapp) -> None:
    """The device row in the configuration; the button first in the control
    row and the LED just before the status line, as before the split."""
    from tests.test_arreglos_pantalla import _cierra, _ventana

    win = _ventana(qapp, "single")
    try:
        adq = win._tab_adq
        assert isinstance(adq._conexion, ConnectionBox)
        fila = adq._conexion.connect_button.parentWidget().layout()
        assert fila.itemAt(0).widget() is adq._conexion.connect_button
        indice_led = fila.indexOf(adq._conexion.led)
        assert fila.itemAt(indice_led + 1).widget() is adq._lbl_estado
        adq.connect_to("simulada")
        assert adq._conexion.is_connected()
        assert adq._lbl_estado.text() == tr("Status: connected (ready to record)")
        assert adq._btn_grabar.isEnabled()
    finally:
        _cierra(qapp, win)
