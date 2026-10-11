"""The recording stops by itself when the guided session ends.

Decision of 11 Oct 2026, as in ecgteach and eegteach: when the pair practical's
guided task ends (the grip, after the manoeuvres) or the kinematics practical's
last load is lifted, the recording stops, and the event log says why. The
one-muscle practical has no guided end and keeps recording until the operator
stops it. «Cancel guide» stops the guide, never the recording. The «Task
recorded» panel stays its five seconds even though the recording has stopped.

The recordings are driven with the simulated BITalino: real worker, real EDF.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from emgteach.gui.tabs.acquisition import events_path
from emgteach.i18n import tr
from emgteach.modes import MODE_KINEMATICS, MODE_PAIR

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


@pytest.fixture
def grabando(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request):
    """A tab of the given practical, recording the simulated board."""
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    modo = request.param
    settings = QSettings("emgteach-test", "sesion-guiada-termina")
    settings.clear()
    settings.setValue("app/mode", modo)
    settings.setValue("adquisicion/device_type", 0)
    settings.setValue("adquisicion/save_dir", str(tmp_path))
    settings.setValue("adquisicion/fv_loads", "2, 4")
    destino = tmp_path / "sesion.edf"
    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(destino), "")))
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab.apply_mode(modo, False)
    tab.resize(1200, 760)
    tab.show()
    tab._edit_mac.setText("simulada")
    tab._btn_conectar.setChecked(True)
    tab._toggle_conexion()
    tab._btn_grabar.setChecked(True)
    tab._toggle_grabacion()
    assert _hasta(lambda: tab._total_samples > 300, 8.0), "the simulated board did not start"
    # The session's own flow (calibration first) is not what is tested here.
    tab._mvc_cancel()
    tab.destino = destino
    yield tab
    if tab._worker is not None:
        tab._worker.stop()
        tab._worker.wait(5000)
    tab.cleanup()
    settings.clear()


@pytest.mark.parametrize("grabando", [MODE_PAIR], indirect=True)
def test_the_end_of_the_pair_task_stops_the_recording(grabando) -> None:
    tab = grabando
    tab._guia_fin()
    assert _hasta(lambda: not tab.is_recording(), 5.0), "the recording went on"
    assert _hasta(lambda: tab._eventos is None, 5.0)
    # The panel says the task is recorded, and stays.
    assert tab._mvc_overlay.isVisible()
    assert tab._mvc_overlay._title == tr("Task recorded")
    log = events_path(tab.destino).read_text(encoding="utf-8")
    assert tr("Recording stopped automatically: guided session finished.") in log
    assert tab.destino.exists()


@pytest.mark.parametrize("grabando", [MODE_KINEMATICS], indirect=True)
def test_the_last_load_stops_the_recording(grabando) -> None:
    tab = grabando
    tab._fv_loads = [2.0, 4.0]
    tab._fv_active = True
    tab._fv_finish_all()
    assert _hasta(lambda: not tab.is_recording(), 5.0), "the recording went on"
    assert _hasta(lambda: tab._eventos is None, 5.0)
    assert tab._mvc_overlay.isVisible()
    assert tab._mvc_overlay._title == tr("Loads recorded")
    log = events_path(tab.destino).read_text(encoding="utf-8")
    assert tr("Recording stopped automatically: guided session finished.") in log


@pytest.mark.parametrize("grabando", [MODE_PAIR], indirect=True)
def test_the_panel_stays_its_five_seconds(grabando) -> None:
    """The stop does not take the «Task recorded» panel away before its time."""
    tab = grabando
    tab._guia_fin()
    assert _hasta(lambda: not tab.is_recording(), 5.0)
    _hasta(lambda: False, 2.0)
    assert tab._mvc_overlay.isVisible(), "the panel went with the recording"
    assert _hasta(lambda: not tab._mvc_overlay.isVisible(), 6.0), "the panel never went"


@pytest.mark.parametrize("grabando", [MODE_PAIR], indirect=True)
def test_cancel_guide_does_not_stop_the_recording(grabando) -> None:
    tab = grabando
    tab._mvc_ref[0] = tab._mvc_ref[1] = 1.0
    tab._guia_maniobras(0)
    tab._cancelar_guiado()
    _hasta(lambda: False, 1.0)
    assert tab.is_recording(), "«Cancel guide» stopped the recording"
