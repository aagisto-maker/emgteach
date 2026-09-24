"""A board that does not answer is said to not answer.

On the bench, after changing practical inside one run of the application,
the connection hung without a word: the log stopped at «Connecting to
BITalino…», the status line said «recording…» over empty plots and, once
stopped, «connected (ready to record)», and no file was written. A student
believes the status line.

- Until the first block the status says it is connecting, and after
  ``CONEXION_MAX_S`` with nothing it stops, says the board did not answer,
  and offers to try again.
- A stop asked for while the board is being reached survives the opening:
  the thread used to set itself back to running once the device answered,
  and a recording stopped at the bench would have started later, holding
  the port.
- A handshake that hangs half-way can be released from another thread, and
  no write of the opening waits forever.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from emgteach.devices import AcquisitionDevice
from emgteach.i18n import tr


class _Colgada(AcquisitionDevice):
    """A board whose opening does not return until the test says so."""

    def __init__(self) -> None:
        self.soltar = threading.Event()
        self.abierta = False
        self.lecturas = 0

    @property
    def fs(self) -> float:
        return 1000.0

    @property
    def name(self) -> str:
        return "Colgada"

    @property
    def n_channels(self) -> int:
        return 1

    def open(self) -> None:
        self.soltar.wait(10.0)
        self.abierta = True

    def read(self, n_samples: int) -> np.ndarray:
        self.lecturas += 1
        time.sleep(0.01)
        return np.zeros((int(n_samples), 1))

    def close(self) -> None:
        self.abierta = False

    def force_close(self) -> None:
        self.abierta = False


def _hasta(condicion, segundos: float) -> bool:
    app = QApplication.instance()
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        app.processEvents()
        if condicion():
            return True
        time.sleep(0.01)
    return False


@pytest.mark.gui
class TestAStopWhileOpeningSurvivesTheOpening:
    def test_the_thread_ends_without_recording(self, qapp, tmp_path: Path) -> None:
        from emgteach.workers.acquisition import AcquisitionWorker

        placa = _Colgada()
        worker = AcquisitionWorker(device=placa, save_path=str(tmp_path / "x.edf"))
        datos, fin = [], []
        worker.data_ready.connect(datos.append)
        worker.finished_ok.connect(fin.append)
        worker.start()
        assert _hasta(worker.is_opening, 2.0)
        worker.stop()
        placa.soltar.set()                       # the board answers, late
        assert worker.wait(5000)
        assert _hasta(lambda: bool(fin), 2.0)
        assert fin == [""]
        assert datos == [] and placa.lecturas == 0
        assert not placa.abierta, "the port is released, not kept"
        assert not (tmp_path / "x.edf").exists()


@pytest.fixture
def pestana(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The acquisition tab with a board that hangs on opening."""
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "placa-que-no-responde")
    settings.clear()
    settings.setValue("app/mode", "single")
    settings.setValue("adquisicion/device_type", 0)
    settings.setValue("adquisicion/save_dir", str(tmp_path))
    placa = _Colgada()
    monkeypatch.setattr(acq_mod, "create_device", lambda *a, **k: placa)
    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tmp_path / "a.edf"), "")))
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab.apply_mode("single", False)
    tab._edit_mac.setText("98:D3:91:FE:44:E4")
    tab._conexion_timer.setInterval(300)
    tab.placa = placa
    tab._btn_conectar.setChecked(True)
    tab._toggle_conexion()
    yield tab
    placa.soltar.set()
    if tab._aviso_conexion is not None:
        tab._aviso_conexion.close()
    tab.cleanup()
    if tab._worker is not None:
        tab._worker.wait(5000)


def _grabar(tab) -> None:
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()


@pytest.mark.gui
class TestTheTabSaysWhatIsHappening:
    def test_it_says_connecting_until_the_first_block(self, qapp, pestana) -> None:
        _grabar(pestana)
        assert pestana._lbl_estado.text() == tr("Status: connecting to the board…")
        pestana.placa.soltar.set()
        assert _hasta(lambda: pestana._lbl_estado.text() == tr("Status: recording…"), 5.0)

    def test_after_the_limit_it_stops_and_says_the_board_did_not_answer(
        self, qapp, pestana
    ) -> None:
        _grabar(pestana)
        assert _hasta(lambda: pestana._aviso_conexion is not None, 3.0)
        assert pestana._lbl_estado.text() == tr("Status: the board did not answer")
        assert not pestana._btn_grabar.isChecked()
        assert pestana._btn_grabar.text() == tr("Start recording")
        assert "20" in tr(
            "No data arrived from the board in {s:.0f} s, so nothing is being "
            "recorded. Check that the BITalino is switched on, switch it off "
            "and on again, and try again. If it happens again, close emgteach "
            "and open it again.").format(s=20.0)

    def test_a_stop_before_the_first_block_does_not_say_connected(
        self, qapp, pestana
    ) -> None:
        _grabar(pestana)
        pestana._btn_grabar.setChecked(False)
        pestana._toggle_grabacion()
        assert pestana._lbl_estado.text() == tr("Status: the board did not answer")
        pestana.placa.soltar.set()
        assert _hasta(lambda: not pestana.is_recording(), 5.0)
        QApplication.instance().processEvents()
        assert pestana._lbl_estado.text() == tr("Status: the board did not answer")


class TestTheOpeningCanBeReleased:
    def test_force_close_closes_a_port_still_in_its_handshake(self) -> None:
        from emgteach.devices.bitalino import BitalinoDevice

        class _Puerto:
            cerrado = False

            def close(self) -> None:
                self.cerrado = True

        dev = BitalinoDevice(port="COM9")
        puerto = _Puerto()
        dev._opening_serial = puerto
        dev.force_close()
        assert puerto.cerrado

    def test_the_writes_of_the_opening_are_bounded(self) -> None:
        from emgteach.devices.bitalino import BitalinoDevice

        pedidos = []

        class _Serial:
            def Serial(self, **kwargs):  # pyserial's name
                pedidos.append(kwargs)
                return object()

        BitalinoDevice(port="COM9")._open_serial(_Serial(), "COM9")
        assert pedidos[0]["write_timeout"] is not None


# ---------------------------------------------------------------------------
# The opening that holds the lock: Windows' CreateFile on a Bluetooth port
# whose board is off. On the bench it took 52 s, and the 20-second warning
# froze the window for all of them.
# ---------------------------------------------------------------------------

class _PuertoFalso:
    """What serial.Serial returns once CreateFile lets go."""

    def __init__(self) -> None:
        self.cerrado = False
        self.timeout = None

    def close(self) -> None:
        self.cerrado = True

    def write(self, data: bytes) -> int:
        return len(data)

    def read(self, n: int = 1) -> bytes:
        return b""


def _bitalino_que_tarda(segundos: float = 60.0):
    """A real BitalinoDevice whose port takes *segundos* to open, lock held."""
    from emgteach.devices.bitalino import BitalinoDevice

    class _Tarda(BitalinoDevice):
        def __init__(self) -> None:
            super().__init__(port="COM9")
            self.soltar = threading.Event()
            self.dentro = threading.Event()
            self.puertos: list[_PuertoFalso] = []

        def _resolve_port(self) -> str:
            return "COM9"

        def _open_serial(self, serial_mod, port):
            self.dentro.set()
            self.soltar.wait(segundos)            # inside CreateFile
            puerto = _PuertoFalso()
            self.puertos.append(puerto)
            return puerto

    return _Tarda()


class TestForceCloseNeverWaits:
    def test_it_returns_at_once_while_open_holds_the_lock(self) -> None:
        dev = _bitalino_que_tarda()
        errores: list[BaseException] = []

        def abrir() -> None:
            try:
                dev.open()
            except BaseException as exc:          # recorded, then asserted
                errores.append(exc)

        hilo = threading.Thread(target=abrir)
        hilo.start()
        assert dev.dentro.wait(2.0)
        t0 = time.monotonic()
        dev.force_close()
        assert time.monotonic() - t0 < 0.2, "force_close waited for the opening"
        dev.soltar.set()                          # Windows lets go, late
        hilo.join(5.0)
        assert not hilo.is_alive()
        assert errores and isinstance(errores[0], RuntimeError)
        assert dev.puertos[0].cerrado, "the port that arrived late is closed"
        assert not dev.is_connected


@pytest.fixture
def pestana_que_tarda(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The tab whose first board takes a minute to open and whose next one answers."""
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "placa-que-tarda")
    settings.clear()
    settings.setValue("app/mode", "single")
    settings.setValue("adquisicion/device_type", 0)
    settings.setValue("adquisicion/save_dir", str(tmp_path))
    primera = _bitalino_que_tarda()
    rapida = _Colgada()
    rapida.soltar.set()
    placas = [primera, rapida]
    monkeypatch.setattr(acq_mod, "create_device", lambda *a, **k: placas.pop(0))
    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tmp_path / "a.edf"), "")))
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab.apply_mode("single", False)
    tab._edit_mac.setText("98:D3:91:FE:44:E4")
    tab._conexion_timer.setInterval(300)
    tab.primera, tab.rapida = primera, rapida
    tab._btn_conectar.setChecked(True)
    tab._toggle_conexion()
    yield tab
    primera.soltar.set()
    if tab._aviso_conexion is not None:
        tab._aviso_conexion.close()
    tab.cleanup()
    for w in (getattr(tab, "_worker", None),):
        if w is not None:
            w.wait(5000)


@pytest.mark.gui
class TestTheWarningDoesNotFreezeTheWindow:
    def test_the_warning_comes_on_time_while_the_port_is_still_opening(
        self, qapp, pestana_que_tarda
    ) -> None:
        tab = pestana_que_tarda
        t0 = time.monotonic()
        _grabar(tab)
        assert _hasta(lambda: tab._aviso_conexion is not None, 3.0), \
            "the warning waited for the port"
        assert time.monotonic() - t0 < 2.0
        assert tab.primera.dentro.is_set() and not tab.primera.soltar.is_set()
        assert tab._lbl_estado.text() == tr("Status: the board did not answer")

    def test_retry_waits_for_the_port_and_then_records(
        self, qapp, pestana_que_tarda
    ) -> None:
        from PySide6.QtWidgets import QMessageBox

        tab = pestana_que_tarda
        _grabar(tab)
        assert _hasta(lambda: tab._aviso_conexion is not None, 3.0)
        viejo = tab._worker
        t0 = time.monotonic()
        tab._tras_aviso_conexion(QMessageBox.StandardButton.Retry)
        assert time.monotonic() - t0 < 0.5, "Retry froze the window"
        assert tab._worker is viejo, "no second connection while the port is taken"
        assert tab._lbl_estado.text() == tr(
            "Status: waiting for Windows to release the port…")
        assert not tab._btn_grabar.isEnabled()
        tab.primera.soltar.set()                  # Windows lets go
        assert _hasta(lambda: tab._worker is not viejo and tab.is_recording(), 5.0)
        assert _hasta(lambda: tab._lbl_estado.text() == tr("Status: recording…"), 5.0)
        assert tab.primera.puertos[0].cerrado
