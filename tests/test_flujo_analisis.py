"""El orden de las cosas en la pestaña de análisis.

«La mecánica del proceso no está clara»: se carga un registro, hay que pulsar
Analizar, y **luego hay que volver a pulsarlo** después de elegir fragmentos.
El mismo botón con dos significados —la primera vez «enséñame el registro», las
siguientes «aplica lo que acabo de elegir»— es lo que hacía difícil de seguir
la secuencia. Y los dos editores se encienden a la vez sin que nada diga que
uno va antes que el otro.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from emgteach.gui.tabs.analysis import AnalysisTab
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.io import BufferedEdfWriter, ChannelInfo

FS = 1000


@pytest.fixture
def tab(qapp):
    t = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "flujo"))
    yield t
    t.deleteLater()
    qapp.processEvents()


def _registro(path: Path) -> str:
    t = np.arange(6 * FS) / FS
    amp = np.full(t.size, 0.01)
    amp[2 * FS : 3 * FS] = 0.4
    canales = [ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]
    with BufferedEdfWriter(str(path), channels=canales) as w:
        w.add_samples(np.sin(2 * np.pi * 80 * t) * amp)
    return str(path)


class TestOpeningARecordingAnalysesIt:
    """Opening a recording in order *not* to analyse it is not a thing anyone
    does, and making the first run a button press is what gave that button its
    second meaning."""

    def test_the_first_analysis_starts_by_itself(
        self, tab, qapp, tmp_path: Path, monkeypatch
    ) -> None:
        edf = _registro(tmp_path / "r.edf")
        lanzados: list[str] = []
        monkeypatch.setattr(
            tab, "_iniciar_analisis", lambda: lanzados.append("va")
        )
        monkeypatch.setattr(
            "emgteach.gui.tabs.analysis.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (edf, "")),
        )
        tab._seleccionar_archivo()
        assert lanzados == ["va"]

    def test_it_says_so_in_the_log(
        self, tab, qapp, tmp_path: Path, monkeypatch
    ) -> None:
        """Announced, not silent: a progress bar that starts on its own with
        no line explaining it reads as the program doing something else."""
        edf = _registro(tmp_path / "r.edf")
        monkeypatch.setattr(tab, "_iniciar_analisis", lambda: None)
        monkeypatch.setattr(
            "emgteach.gui.tabs.analysis.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (edf, "")),
        )
        tab._seleccionar_archivo()
        assert "análisis" in tab._logger.toPlainText().lower() or \
               "analysis" in tab._logger.toPlainText().lower()


class TestItSaysWhichEditorComesFirst:
    """Both light up together at the end of the first analysis, side by side,
    and nothing said that the calibration comes first. It does, and not by
    convention: the reference it fixes is the yardstick for every % MVC the
    fragments are then measured in."""

    def test_with_a_calibration_it_points_at_the_repetitions(self, tab) -> None:
        tab._last_result = {"cal_rep_values": {0: [1.0, 1.2]}}
        tab._actualizar_siguiente_paso()
        assert tab._lbl_siguiente.isVisible() or tab._lbl_siguiente.text()
        assert "repeticiones" in tab._lbl_siguiente.text().lower() or \
               "repetitions" in tab._lbl_siguiente.text().lower()

    def test_once_they_are_chosen_it_points_at_the_fragments(self, tab) -> None:
        tab._last_result = {"cal_rep_values": {0: [1.0, 1.2]}}
        tab._cal_keep = {0: {0}}
        tab._actualizar_siguiente_paso()
        assert "fragment" in tab._lbl_siguiente.text().lower()

    def test_with_no_calibration_it_goes_straight_to_the_fragments(
        self, tab
    ) -> None:
        tab._last_result = {"channel_name": "FCR"}
        tab._actualizar_siguiente_paso()
        assert "fragment" in tab._lbl_siguiente.text().lower()

    def test_when_both_are_done_it_says_nothing(self, tab) -> None:
        tab._last_result = {"cal_rep_values": {0: [1.0]}}
        tab._cal_keep = {0: {0}}
        tab._selected_segments = [(1.0, 2.0)]
        tab._actualizar_siguiente_paso()
        assert tab._lbl_siguiente.text() == ""

    def test_before_any_analysis_it_says_nothing(self, tab) -> None:
        tab._last_result = None
        tab._actualizar_siguiente_paso()
        assert not tab._lbl_siguiente.isVisible()
