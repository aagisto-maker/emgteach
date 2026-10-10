"""After a recording with the real board, the status says to switch it off and on.

Ported from ecgteach 0.4.0 (bench of 5 October 2026, points 16 and 31): every
new recording needed the BITalino switched off and on, or Windows answered
with errors 1168 or 121. By Ángel's decision the cause is not investigated;
it is said, where the operator looks. Short on screen («Estado: apague y
encienda la placa»), whole in the tooltip. Not with the simulated board, and
not when the board did not answer (that status stays). The kit of the 3.7.2
already says it in its LEEME.txt.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from emgteach.devices import AcquisitionDevice
from emgteach.i18n import tr

pytestmark = pytest.mark.gui

_LARGA = "Status: for the next recording, switch the BITalino board off and on"
_CORTA = "Status: switch the board off and on"


class _Placa(AcquisitionDevice):
    """A board that answers at once, as the real one on the bench."""

    @property
    def fs(self) -> float:
        return 1000.0

    @property
    def name(self) -> str:
        return "BITalino"

    @property
    def n_channels(self) -> int:
        return 1

    def open(self) -> None:
        pass

    def read(self, n_samples: int) -> np.ndarray:
        time.sleep(0.01)
        return np.zeros((int(n_samples), 1))

    def close(self) -> None:
        pass

    def force_close(self) -> None:
        pass


def _hasta(condicion, segundos: float) -> bool:
    app = QApplication.instance()
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        app.processEvents()
        if condicion():
            return True
        time.sleep(0.01)
    return False


@pytest.mark.parametrize(("direccion", "lo_dice"), [("98:D3:91:FE:44:E4", True),
                                                    ("simulada", False)])
def test_after_a_recording_with_the_board_it_says_to_restart_it(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, direccion: str, lo_dice: bool
) -> None:
    from emgteach.gui.tabs import acquisition as acq_mod
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "apague-y-encienda")
    settings.clear()
    settings.setValue("app/mode", "single")
    settings.setValue("adquisicion/device_type", 0)
    settings.setValue("adquisicion/save_dir", str(tmp_path))
    monkeypatch.setattr(acq_mod.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tmp_path / "a.edf"), "")))
    if direccion != "simulada":
        monkeypatch.setattr(acq_mod, "create_device", lambda *a, **k: _Placa())
    tab = AcquisitionTab(LoggerWidget(), settings)
    try:
        tab.apply_mode("single", False)
        tab._edit_mac.setText(direccion)
        tab._btn_conectar.setChecked(True)
        tab._toggle_conexion()
        tab._btn_grabar.setChecked(True)
        tab._toggle_grabacion()
        assert _hasta(lambda: tab._lbl_estado.text() == tr("Status: recording…"), 8.0)
        tab._btn_grabar.setChecked(False)
        tab._toggle_grabacion()
        assert _hasta(lambda: not tab._worker.isRunning(), 8.0)
        _hasta(lambda: False, 0.3)
        assert (tab._lbl_estado.text() == tr(_CORTA)) is lo_dice, tab._lbl_estado.text()
        assert (tr(_LARGA) in tab._lbl_estado.toolTip()) is lo_dice
        # The next recording, or a new connection, clears it.
        tab._btn_conectar.setChecked(False)
        tab._toggle_conexion()
        tab._btn_conectar.setChecked(True)
        tab._toggle_conexion()
        assert tab._lbl_estado.text() == tr("Status: connected (ready to record)")
        assert tab._lbl_estado.toolTip() == ""
    finally:
        tab.cleanup()
        if tab._worker is not None:
            tab._worker.wait(5000)
        settings.clear()


def test_the_restart_status_is_short_and_the_tooltip_says_it_all(qapp) -> None:
    """ecgteach, annex of 6 Oct 2026, point 31: the long sentence came out
    clipped; on screen it is short, and the whole sentence is in the tooltip."""
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget
    from emgteach.i18n import get_language, set_language

    settings = QSettings("emgteach-test", "apague-corto")
    settings.clear()
    antes = get_language()
    set_language("es")
    tab = AcquisitionTab(LoggerWidget(), settings)
    try:
        tab._btn_conectar.setChecked(True)
        tab._placa_reiniciar = True
        tab._lbl_estado.setText(tab._estado_en_reposo())
        assert tab._lbl_estado.text() == "Estado: apague y encienda la placa"
        assert tab._lbl_estado.toolTip() == (
            "Estado: para la siguiente grabación, apague y encienda la placa BITalino")
    finally:
        set_language(antes)
        tab.cleanup()
        settings.clear()
