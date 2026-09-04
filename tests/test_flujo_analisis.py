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


class TestTheAnalyseButtonIsNoLongerAStep:
    """It could not be removed, and it should not be a step either.

    Five things still feed the analysis without re-running it — the channel,
    the second channel, the accelerometer panels, the envelope smoothing and
    the region of interest — so the button survives for exactly those. What it
    stops being is part of the sequence: in a session that opens a recording
    and then the two editors, it never lights up.
    """

    def test_it_starts_dark(self, tab) -> None:
        assert not tab._btn_analizar.isEnabled()

    def test_a_loaded_file_alone_does_not_light_it(self, tab, tmp_path) -> None:
        tab._edit_path.setText(_registro(tmp_path / "r.edf"))
        tab._actualizar_boton_analizar()
        assert not tab._btn_analizar.isEnabled()

    def test_changing_the_channel_lights_it(self, tab, tmp_path) -> None:
        tab._edit_path.setText(_registro(tmp_path / "r.edf"))
        tab._marcar_pendiente()
        assert tab._btn_analizar.isEnabled()

    def test_a_finished_analysis_puts_it_out(
        self, tab, qapp, tmp_path
    ) -> None:
        """Run for real: a hand-made result dict would only prove that the
        line assigning the flag exists."""
        pytest.importorskip("mne")
        from PySide6.QtCore import QElapsedTimer

        tab._edit_path.setText(_registro(tmp_path / "r.edf"))
        tab._populate_channels(tab._edit_path.text())
        tab._marcar_pendiente()
        assert tab._btn_analizar.isEnabled()

        tab._iniciar_analisis()
        # wait() first (it releases the GIL), then pump the queued signals:
        # a processEvents() spin while the thread runs starved it on CI. See
        # test_analysis_phases._analizar.
        if tab._worker is not None:
            tab._worker.wait(120000)
        reloj = QElapsedTimer()
        reloj.start()
        while tab._last_result is None and reloj.elapsed() < 5000:
            qapp.processEvents()
        for _ in range(30):
            qapp.processEvents()
        assert tab._last_result is not None, "el análisis no produjo resultado"
        assert not tab._btn_analizar.isEnabled()

    def test_with_no_file_nothing_lights_it(self, tab) -> None:
        tab._marcar_pendiente()
        assert not tab._btn_analizar.isEnabled()


class TestTheGuidanceAlsoFloats:
    """A line of small print under two buttons is read by whoever was already
    looking there. The floating panel dims the rest and rings the button."""

    def _pasos(self, tab):
        vistos = []
        tab.coach_step.connect(lambda t, b, w: vistos.append((t, b, w)))
        return vistos

    def test_the_first_step_floats_over_the_repetitions(self, tab) -> None:
        vistos = self._pasos(tab)
        tab._last_result = {"cal_rep_values": {0: [1.0, 1.2]}}
        tab._actualizar_siguiente_paso()
        assert len(vistos) == 1
        assert vistos[0][2] is tab._btn_reps

    def test_it_does_not_come_back_on_every_re_analysis(self, tab) -> None:
        """Otherwise the panel reappears after each accept, over and over."""
        vistos = self._pasos(tab)
        tab._last_result = {"cal_rep_values": {0: [1.0]}}
        tab._actualizar_siguiente_paso()
        tab._actualizar_siguiente_paso()
        tab._actualizar_siguiente_paso()
        assert len(vistos) == 1

    def test_the_next_step_floats_over_the_fragments(self, tab) -> None:
        vistos = self._pasos(tab)
        tab._last_result = {"cal_rep_values": {0: [1.0]}}
        tab._actualizar_siguiente_paso()
        tab._cal_keep = {0: {0}}
        tab._actualizar_siguiente_paso()
        assert [v[2] for v in vistos] == [tab._btn_reps, tab._btn_fragmentos]

    def test_nothing_floats_once_both_are_done(self, tab) -> None:
        vistos = self._pasos(tab)
        tab._last_result = {"cal_rep_values": {0: [1.0]}}
        tab._cal_keep = {0: {0}}
        tab._selected_segments = [(1.0, 2.0)]
        tab._actualizar_siguiente_paso()
        assert vistos == []


class TestTheCoactivationTableWaitsForItsWindows:
    """The first analysis now runs on its own when the file is opened, so the
    single whole-recording row was the *first* thing the student saw of this
    panel: a co-activation index, in bold, computed over rest and flexion and
    extension together. The module's own docstring says that number is not a
    measurement of anything."""

    def _resultado(self, desde_marcas: bool) -> dict:
        from emgteach.coactivation import CoactivationResult

        return {
            "channel_name": "FCR",
            "channel_name_2": "ECR",
            "coactivation": [
                CoactivationResult(index=42.0, mean_1=10.0, mean_2=9.0,
                                   window_s=(0.0, 10.0), label="x")
            ],
            "coactivation_from_markers": desde_marcas,
        }

    def test_without_windows_the_table_is_hidden(self, tab) -> None:
        # isVisibleTo, not isVisible: the tab itself is never shown in a
        # headless run, so isVisible() is False either way and would pass
        # over the bug it is meant to catch.
        tab._refresh_coactivation(self._resultado(False))
        # The stack holds the chart and, one click behind, the table.
        assert not tab._stack_coact.isVisibleTo(tab._box_coact)

    def test_before_the_student_has_done_anything_the_panel_is_not_there(
        self, tab
    ) -> None:
        """No table and no red line either.

        The line warns that a number does not measure anything, about a number
        that is no longer shown, at the one moment the student has done nothing
        wrong: the file has just been opened and analysed by itself. What to do
        next is said twice already — under the two editors, and in the panel
        that floats over the button.
        """
        tab._selected_segments = []
        tab._refresh_coactivation(self._resultado(False))
        assert not tab._lbl_coact_aviso.text()
        assert not tab._box_coact.isVisibleTo(tab)

    def test_but_clearing_every_name_by_hand_is_still_worth_saying(
        self, tab
    ) -> None:
        """The one case the warning still answers: fragments were chosen and
        every name was cleared, which is deliberate and has a consequence."""
        tab._selected_segments = [(1.0, 2.0)]
        tab._refresh_coactivation(self._resultado(False))
        assert tab._lbl_coact_aviso.text()
        assert tab._box_coact.isVisibleTo(tab)

    def test_with_windows_the_table_is_there(self, tab) -> None:
        tab._refresh_coactivation(self._resultado(True))
        assert tab._stack_coact.isVisibleTo(tab._box_coact)
        assert tab._tbl_coact.rowCount() == 1
        # And the chart in front of it has its two bars and its index.
        assert len(tab._ax_coact.patches) >= 2
