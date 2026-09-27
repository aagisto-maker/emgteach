"""Guardar el registro afinado: cuando no se puede, se dice por qué.

En el banco de la 3.7.1 (CRC02, 27 de septiembre), guardar el afinado de un
registro de un músculo —que no tiene fase que afinar— sacó «Error inesperado»:
las dos negativas de ``_guardar_afinado`` llamaban a ``self._err``, que la
pestaña de análisis nunca tuvo. La negativa tiene que llegar como aviso, con
su motivo, y sin excepción.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from emgteach.gui.tabs.analysis import AnalysisTab
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.io import BufferedEdfWriter, ChannelInfo

FS = 1000


def _edf_de_un_musculo(path: Path) -> str:
    """Two contractions and nothing else: no «REC start», no calibration."""
    t = np.arange(8 * FS) / FS
    raw = 0.01 * np.sin(2 * np.pi * 80 * t)
    for a in (2.0, 5.0):
        raw[int(a * FS):int((a + 1) * FS)] *= 20
    with BufferedEdfWriter(str(path), channels=[
            ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]) as w:
        w.add_samples(raw)
    return str(path)


@pytest.fixture
def tab(qapp):
    t = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "guardar-afinado"))
    yield t
    t.deleteLater()
    qapp.processEvents()


def test_a_recording_with_nothing_to_tune_gets_a_warning_not_a_crash(
    tab, tmp_path: Path
) -> None:
    origen = _edf_de_un_musculo(tmp_path / "CRC02.edf")
    tab._edit_path.setText(origen)
    tab._last_result = {"channel_name": "FCR"}
    destino = str(tmp_path / "CRC02_tuned.edf")
    with patch("emgteach.gui.tabs.analysis.QFileDialog.getSaveFileName",
               return_value=(destino, "")), \
         patch("emgteach.gui.tabs.analysis.QMessageBox.warning") as aviso:
        tab._guardar_afinado()                   # used to raise AttributeError
    aviso.assert_called_once()
    assert "REC start" in aviso.call_args.args[2]
    assert not Path(destino).exists()


def test_the_tuned_recording_cannot_replace_its_source(tab, tmp_path: Path) -> None:
    origen = _edf_de_un_musculo(tmp_path / "CRC02.edf")
    tab._edit_path.setText(origen)
    tab._last_result = {"channel_name": "FCR"}
    with patch("emgteach.gui.tabs.analysis.QFileDialog.getSaveFileName",
               return_value=(origen, "")), \
         patch("emgteach.gui.tabs.analysis.QMessageBox.warning") as aviso:
        tab._guardar_afinado()
    aviso.assert_called_once()
    assert "cannot replace" in aviso.call_args.args[2]
