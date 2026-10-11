"""A file that disappears mid-recording stops it at once, and a box says so.

3.8.0, from ecgteach 0.4.0 (bench of 5 October 2026, E10): with the memory
stick taken out while recording, nothing was said. In emgteach the worker
already stopped and said it when ``add_samples`` raised; what was not known
is whether it raises at all when the folder goes. Reproduced first, on this
machine (Linux), with the real writer and the simulated board: the folder
deleted, the recording went on for ten seconds and more without a word, and
at the end the log said «EDF file saved» for a file that was no longer there.
The EDF library buffers whole records in its own FILE*, and a write to a file
whose folder is gone need not fail for a long while.

The fix is ecgteach's: once a second the worker checks that the file is still
in its folder; if not, it stops, says it in the log and, through
``escritura_fallida``, the tab says it in a non-modal box.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from emgteach.i18n import tr

pytestmark = pytest.mark.gui


def _hasta(condicion, segundos: float) -> bool:
    app = QApplication.instance()
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        app.processEvents()
        if condicion():
            return True
        time.sleep(0.01)
    return False


class _EscritorQueSeVa:
    """A writer whose file is on a stick that is then taken out.

    Every write succeeds, as one buffered by the C library does; the file
    simply stops being there.
    """

    def __init__(self, path, channels, metadata=None):
        self.path = Path(path)
        self.path.write_bytes(b"0")
        self.bloques = 0
        self.header_notices: list[str] = []

    def add_samples(self, *blocks) -> None:
        self.bloques += 1
        if self.bloques == 5 and self.path.exists():
            self.path.unlink()                      # the stick is taken out

    def add_annotation(self, *_a) -> None:
        pass

    def close(self) -> None:
        pass


def test_a_file_that_vanishes_mid_recording_stops_it_at_once(qapp, tmp_path, monkeypatch) -> None:
    import emgteach.workers.acquisition as wmod
    from emgteach.devices import BACKEND_BITALINO, create_device

    monkeypatch.setattr(wmod, "BufferedEdfWriter", _EscritorQueSeVa)
    device = create_device(BACKEND_BITALINO, port="simulada", fs=1000, channels=[0])
    worker = wmod.AcquisitionWorker(
        device=device, save_path=str(tmp_path / "usb.edf"), n_per_read=100,
        sensor_labels=["Bíceps"],
    )
    fallos: list[str] = []
    errores: list[str] = []
    fin: list[str] = []
    worker.escritura_fallida.connect(fallos.append)
    worker.error.connect(errores.append)
    worker.finished_ok.connect(fin.append)
    try:
        worker.start()
        # The file goes after half a second; within about a second more the
        # recording has stopped, said why, and announced nothing.
        assert _hasta(lambda: bool(fin), 5.0), "the recording went on"
        assert worker.wait(5000)
        assert fallos and "usb.edf" in fallos[0]
        assert tr("the file is no longer in its folder") in fallos[0]
        assert errores == fallos, "the log says it too"
        assert fin == [""], "a file that is not there is not announced as saved"
    finally:
        if worker.isRunning():
            worker.stop()
            worker.wait(5000)


@pytest.fixture
def pestana(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "archivo-que-desaparece")
    settings.clear()
    settings.setValue("app/mode", "single")
    settings.setValue("adquisicion/device_type", 0)
    settings.setValue("adquisicion/save_dir", str(tmp_path))
    carpeta = tmp_path / "usb"
    carpeta.mkdir()
    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(carpeta / "a.edf"), "")))
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab.apply_mode("single", False)
    tab._edit_mac.setText("simulada")
    tab._btn_conectar.setChecked(True)
    tab._toggle_conexion()
    tab.carpeta = carpeta
    yield tab
    if tab._worker is not None:
        tab._worker.stop()
        tab._worker.wait(5000)
    tab.cleanup()
    settings.clear()


def _caja(tab) -> str | None:
    caja = getattr(tab, "_aviso_guardado", None)
    return caja.text() if caja is not None else None


def test_the_tab_says_it_in_a_box_and_is_ready_again(pestana, monkeypatch) -> None:
    import emgteach.workers.acquisition as wmod

    monkeypatch.setattr(wmod, "BufferedEdfWriter", _EscritorQueSeVa)
    tab = pestana
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    assert _hasta(lambda: not tab.is_recording(), 8.0), "the recording went on"
    assert _hasta(lambda: _caja(tab) is not None, 2.0), "no box said it"
    assert "a.edf" in _caja(tab)
    assert not tab._aviso_guardado.isModal(), "the window has to stay usable"
    assert not tab._btn_grabar.isChecked()
    assert tab._lbl_estado.text() == tr("Status: connected (ready to record)")


@pytest.mark.skipif(sys.platform == "win32",
                    reason="Windows does not delete a folder with an open file in it; "
                           "the stick taken out is tried on the PC")
def test_the_real_writer_with_its_folder_deleted(pestana) -> None:
    """The reproduction itself, with the real writer: the folder deleted with
    the recording running. Before the fix it went on recording."""
    tab = pestana
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    assert _hasta(lambda: tab._total_samples > 1500, 8.0)
    shutil.rmtree(tab.carpeta)
    t0 = time.monotonic()
    assert _hasta(lambda: not tab.is_recording(), 5.0), "the recording went on"
    assert time.monotonic() - t0 < 3.0
    assert _hasta(lambda: _caja(tab) is not None, 2.0), "no box said it"
    dicho = tab._local_log.toPlainText()
    assert tr("EDF file saved: {path}").format(path=tab.carpeta / "a.edf") not in dicho


def test_a_folder_that_is_gone_is_not_where_the_dialog_opens(pestana, monkeypatch) -> None:
    """3.8.0, from ecgteach 0.4.0 (ecg 1): the stick taken out after a
    recording that went to it. The next save dialog opened on a folder that
    was not there; it opens in Documents now, and the log says so."""
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.tabs.acquisition import carpeta_por_defecto

    tab = pestana
    pedido: list[str] = []

    def dialogo(_padre, _titulo, inicio, _filtro):
        pedido.append(inicio)
        return "", ""                               # cancelled

    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName", staticmethod(dialogo))
    ida = tab.carpeta / "la_memoria_que_se_saco"
    tab._edit_dir.setText(str(ida))
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    assert pedido, "the save dialog was not opened"
    assert Path(pedido[-1]).parent == Path(carpeta_por_defecto())
    assert tab._edit_dir.text() == carpeta_por_defecto()
    assert str(ida) in tab._local_log.toPlainText()
    assert not tab.is_recording()


def test_a_file_that_cannot_be_created_is_not_a_board_that_did_not_answer(
    pestana, monkeypatch
) -> None:
    """Decision of 11 Oct 2026 (point 3, ecgteach 9a33ef3): the board answered
    and the file could not be created. The status must not say the board did
    not answer, a box must say the file could not be made, and the tab must
    record again once there is somewhere to write."""
    import emgteach.workers.acquisition as wmod

    real = wmod.BufferedEdfWriter

    def no_se_puede(*_a, **_k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(wmod, "BufferedEdfWriter", no_se_puede)
    tab = pestana
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    assert _hasta(lambda: tab._worker is not None and not tab._worker.isRunning(), 8.0)
    _hasta(lambda: False, 0.3)
    assert _caja(tab) is not None and "a.edf" in _caja(tab), "no box said it"
    assert tab._lbl_estado.text() == tr("Status: connected (ready to record)")
    monkeypatch.setattr(wmod, "BufferedEdfWriter", real)
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    assert _hasta(lambda: tab._lbl_estado.text() == tr("Status: recording…"), 8.0)
