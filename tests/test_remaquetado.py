"""La remaquetación que pidió el autor tras ver las capturas (3-sep-2026).

Adquisición: el selector de dispositivo solo en la práctica de un músculo
(las otras dos son BITalino); «Ruta y archivo de salida»; el identificador
de prueba comparte línea con la difusión a móviles; k a la vista con su
explicación. Análisis: sin campo de identificador (viene del EDF); una sola
línea con repeticiones → fragmentos → canales → paneles; el resumen y las
contracciones abajo, lado a lado; la rueda desplaza y la escala tiene
botones en la barra lateral; el panel de fatiga lleva los dos músculos. Y
la pestaña CVM sigue la misma pauta.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QLabel, QToolButton

from emgteach import i18n
from emgteach.gui.tabs.analysis import AnalysisTab
from emgteach.gui.tour import build_tour
from emgteach.gui.widgets.canvas import ScrollingCanvas
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.modes import MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE, MODES
from emgteach.workers.analysis import AnalysisWorker

tr = i18n.tr
FS = 1000


def _set_mode(win, qapp, mode: str) -> None:
    win._combo_mode.setCurrentIndex(MODES.index(mode))
    qapp.processEvents()


@pytest.fixture
def tab(qapp):
    t = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "remaquetado"))
    yield t
    t.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Acquisition
# ---------------------------------------------------------------------------


class TestTheDeviceChoiceBelongsToOnePractical:
    def test_only_the_single_muscle_practical_offers_it(self, main_window, qapp) -> None:
        adq = main_window._tab_adq
        _set_mode(main_window, qapp, MODE_SINGLE)
        assert adq._combo_device_type.isVisibleTo(adq)
        for mode in (MODE_PAIR, MODE_KINEMATICS):
            _set_mode(main_window, qapp, mode)
            assert not adq._combo_device_type.isVisibleTo(adq), mode
            # The port or address stays editable: it differs from board to board.
            assert adq._box_device.isVisibleTo(adq)

    def test_the_other_practicals_get_the_bitalino(self, main_window, qapp) -> None:
        adq = main_window._tab_adq
        _set_mode(main_window, qapp, MODE_SINGLE)
        adq._combo_device_type.setCurrentIndex(1)      # Arduino + MyoWare
        _set_mode(main_window, qapp, MODE_PAIR)
        assert adq._combo_device_type.currentIndex() == 0


class TestTheConfigurationBoxSaysWhatItAsks:
    def test_output_path_and_test_identifier(self, main_window) -> None:
        adq = main_window._tab_adq
        textos = {w.text() for w in adq.findChildren(QLabel)}
        assert tr("Output path and file:") in textos
        assert tr("Test identifier:") in textos
        assert tr("Student code:") not in textos
        assert tr("Folder:") not in textos
        # On the broadcast row, not on a row of its own.
        assert adq._box_aula.isAncestorOf(adq._edit_student_code)
        assert adq._edit_student_code.placeholderText()

    @pytest.mark.parametrize("mode", MODES)
    def test_k_is_on_screen_in_every_practical_with_its_meaning(
        self, main_window, qapp, mode
    ) -> None:
        adq = main_window._tab_adq
        _set_mode(main_window, qapp, mode)
        assert adq._box_k.isVisibleTo(adq)
        assert adq._lbl_k_explica.isVisibleTo(adq)
        assert adq._lbl_k_explica.text() == tr("threshold = rest + k × noise (3 is usual)")  # noqa: RUF001


class TestTheTourNamesTheChannelOrder:
    def test_muscle_one_is_a1(self, main_window, qapp) -> None:
        _set_mode(main_window, qapp, MODE_PAIR)
        cuerpos = " ".join(s.body for s in build_tour(main_window))
        assert "A1" in cuerpos


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def _registro(path: Path, dos: bool = False) -> str:
    t = np.arange(8 * FS) / FS
    amp = np.full(t.size, 0.01)
    amp[2 * FS: 3 * FS] = 0.4
    amp[5 * FS: 6 * FS] = 0.3
    canales = [ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]
    datos = [np.sin(2 * np.pi * 80 * t) * amp]
    if dos:
        canales.append(ChannelInfo("ECR", dimension="mV", sample_frequency=FS))
        amp2 = np.full(t.size, 0.01)
        amp2[int(3.5 * FS): int(4.5 * FS)] = 0.35
        datos.append(np.sin(2 * np.pi * 90 * t) * amp2)
    with BufferedEdfWriter(str(path), channels=canales) as w:
        w.add_samples(*datos)
    return str(path)


class TestTheIdentifierComesFromTheRecording:
    def test_no_field_on_the_tab(self, tab) -> None:
        assert not hasattr(tab, "_edit_student_code")
        textos = {w.text() for w in tab.findChildren(QLabel)}
        assert tr("Student code:") not in textos

    def test_read_from_the_header_when_a_file_is_opened(
        self, tab, tmp_path: Path, monkeypatch
    ) -> None:
        edf = _registro(tmp_path / "r.edf")
        monkeypatch.setattr(
            "emgteach.gui.tabs.analysis.read_edf_metadata",
            lambda _p: SimpleNamespace(student_code="MESA-3", protocol=""),
        )
        tab._populate_channels(edf)
        assert tab._student_code == "MESA-3"
        tab.reset()
        assert tab._student_code == ""


class TestOneLineInTheOrderThingsAreDone:
    def test_repetitions_then_fragments_then_channels_then_panels(self, tab) -> None:
        fila = tab._box_fragmentos.layout()
        i_reps = fila.indexOf(tab._btn_reps)
        i_frag = fila.indexOf(tab._btn_fragmentos)
        assert 0 <= i_reps < i_frag
        # The channel picker and the panel chips live on that same line.
        assert tab._box_fragmentos.isAncestorOf(tab._combo_canal)
        assert tab._box_fragmentos.isAncestorOf(tab._chk_paneles[0])
        assert tab._box_fragmentos.isAncestorOf(tab._btn_mas_paneles)

    def test_the_fragment_message_is_a_count(self, tab) -> None:
        tab._selected_segments = [(0.0, 1.0), (2.0, 3.0)]
        tab._segment_labels = ["FCR", ""]
        tab._actualizar_etiqueta_fragmentos()
        assert tab._lbl_fragmentos.text() == tr("{n} fragments selected").format(n=2)
        tab._selected_segments = [(0.0, 1.0)]
        tab._segment_labels = [""]
        tab._actualizar_etiqueta_fragmentos()
        assert tab._lbl_fragmentos.text() == tr("1 fragment selected")


class TestTheBottomBand:
    def test_summary_and_contractions_share_a_row(self, tab) -> None:
        raiz = tab.layout()
        compartida = None
        for i in range(raiz.count()):
            sub = raiz.itemAt(i).layout()
            if sub is not None and sub.indexOf(tab._grp_resumen) >= 0:
                compartida = sub
        assert compartida is not None
        assert compartida.indexOf(tab._box_contr) >= 0
        assert compartida.indexOf(tab._box_contr) < compartida.indexOf(tab._grp_resumen)


class TestTheWheelScrollsAndTheScaleIsAButton:
    def test_the_canvas_lets_the_wheel_through(self, tab, qapp) -> None:
        assert isinstance(tab._canvas, ScrollingCanvas)
        ev = QWheelEvent(
            QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, 120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False,
        )
        ev.setAccepted(True)
        QApplication.sendEvent(tab._canvas, ev)
        assert not ev.isAccepted()

    def test_time_scale_buttons_beside_the_amplitude_ones(self, tab) -> None:
        tab._axes_list = [tab._fig.add_subplot(111)]
        tab._rebuild_y_sidebar([0])
        textos = [b.text() for b in tab._y_scale_sidebar.findChildren(QToolButton)]
        assert textos.count("▲") == 1 and textos.count("▼") == 1
        assert textos.count("▶◀") == 1 and textos.count("◀▶") == 1


class TestFatigueForBothMuscles:
    def test_the_worker_fits_the_second_muscle_too(self, qapp, tmp_path: Path) -> None:
        edf = _registro(tmp_path / "dos.edf", dos=True)
        caja: list[dict] = []
        w = AnalysisWorker(edf_path=edf, channel_name="FCR", channel_name_2="ECR",
                           plot_duration_s=0)
        w.result_ready.connect(caja.append)
        w.run()
        assert caja, "the analysis did not finish"
        r = caja[0]
        assert len(r["mdf_seg_2"]) == len(r["t_seg_2"]) == len(r["fat_fitted_2"])
        assert "mdf_slope_2" in r

    def test_the_pair_practical_offers_the_panel(self, main_window, qapp) -> None:
        ana = main_window._tab_ana
        _set_mode(main_window, qapp, MODE_PAIR)
        pos = ana._panel_pids.index(6)
        assert not ana._chk_paneles[pos].isHidden()


# ---------------------------------------------------------------------------
# MVC normalisation follows the same pattern
# ---------------------------------------------------------------------------


class TestTheNormalisationTabFollows:
    def test_fragments_before_the_channel_and_a_scrolling_canvas(self, main_window) -> None:
        cvm = main_window._tab_cvm
        assert isinstance(cvm._canvas, ScrollingCanvas)
        fila = cvm._btn_fragmentos.parentWidget().layout()
        # Both sit in the same row layout, the editor first.
        capa = None
        for i in range(fila.count()):
            sub = fila.itemAt(i).layout()
            if sub is not None and sub.indexOf(cvm._btn_fragmentos) >= 0:
                capa = sub
        capa = capa or fila
        assert 0 <= capa.indexOf(cvm._btn_fragmentos) < capa.indexOf(cvm._combo_canal)

    def test_time_scale_buttons_in_its_sidebar(self, main_window) -> None:
        cvm = main_window._tab_cvm
        cvm._axes_list = [cvm._fig.add_subplot(111)]
        cvm._rebuild_y_sidebar()
        textos = [b.text() for b in cvm._y_scale_sidebar.findChildren(QToolButton)]
        assert "▶◀" in textos and "◀▶" in textos

    def test_the_fragment_message_is_a_count(self, main_window) -> None:
        cvm = main_window._tab_cvm
        cvm._selected_segments = [(0.0, 1.0), (2.0, 3.0), (4.0, 5.0)]
        cvm._actualizar_etiqueta_fragmentos()
        assert cvm._lbl_fragmentos.text() == tr("{n} fragments selected").format(n=3)


# ---------------------------------------------------------------------------
# Lo visto en el banco del 3 de septiembre, segunda tanda
# ---------------------------------------------------------------------------


class TestWhatTheSecondBenchSessionShowed:
    def test_the_legend_names_the_muscles_of_the_chosen_practical(
        self, main_window, qapp
    ) -> None:
        """It read «Muscle · ECR» beside two boxes saying FCR and ECR.

        The legend and the lane labels are painted while the tab is built,
        before any mode has been applied, so they carried the names of the
        default practical; with the channel count already at two, nothing
        changed afterwards and the first one never got its name.
        """
        adq = main_window._tab_adq
        _set_mode(main_window, qapp, MODE_PAIR)
        adq._edit_labels[0].setText("FCR")
        adq._edit_labels[1].setText("ECR")
        qapp.processEvents()
        # Re-applying the mode with the count already right used to leave it.
        adq.apply_mode(MODE_PAIR, advanced=False)
        qapp.processEvents()
        assert adq._active_labels() == ["FCR", "ECR"]
        assert "FCR" in adq._lbl_legend.text()
        assert tr("Muscle") not in adq._lbl_legend.text()

    def test_the_next_step_waits_for_the_analysis_tab(self, main_window, qapp) -> None:
        """The recording is analysed as soon as it is opened, which happens
        while the student is still on Acquisition — so the step saying what to
        do next was raised over a tab nobody was looking at and dropped, and
        the analysis tab, which only emits on a *change* of step, never
        offered it again."""
        main_window._tabs.setCurrentWidget(main_window._tab_adq)
        qapp.processEvents()
        main_window._mostrar_paso_guiado(
            "t", "b", main_window._tab_ana._btn_reps
        )
        assert not main_window._coach.isVisible()
        assert main_window._paso_pendiente is not None

        main_window._tabs.setCurrentWidget(main_window._tab_ana)
        qapp.processEvents()
        assert main_window._coach.isVisible()
        assert main_window._paso_pendiente is None
        main_window._coach.stop()

    def test_the_contraction_table_fills_its_box(self, tab) -> None:
        """Pinned to a fixed height it sat at the bottom of a taller box with
        a strip of empty box above it."""
        from emgteach.contractions import Contraction

        def filas(n: int) -> list[Contraction]:
            return [
                Contraction(i, float(i), float(i) + 0.7, "FCR", 0.2, 60.0, 120.0)
                for i in range(1, n + 1)
            ]

        tab._refresh_contractions({"contractions": filas(2), "channel_name": "FCR"})
        assert tab._tbl_contr.maximumHeight() > 1000
        con_dos = tab._tbl_contr.minimumHeight()
        tab._refresh_contractions({"contractions": filas(8), "channel_name": "FCR"})
        assert tab._tbl_contr.minimumHeight() > con_dos

    def test_the_normalisation_greeting_does_not_come_back(
        self, main_window, qapp
    ) -> None:
        """Dismissed stays dismissed: «New session» used to raise it again
        over a tab the operator was already using."""
        cvm = main_window._tab_cvm
        cvm._dismiss_entry_screen()
        qapp.processEvents()
        assert not cvm._entry_panel.isVisibleTo(cvm)
        cvm.reset()
        qapp.processEvents()
        assert not cvm._entry_panel.isVisibleTo(cvm)

    def test_a_new_recording_forgets_what_the_last_one_chose(
        self, tab, qapp, tmp_path: Path
    ) -> None:
        """Bench, 3 September, fourth recording: no guided box at all.

        Opening a file cleared the fragments but kept the discarded
        calibration repetitions and the record of which step had been shown,
        so the new file opened as if its calibration were reviewed, offered
        «select fragments» — the step the previous file had ended on — and a
        step that has not changed is not offered again. Worse, the discards
        went to the worker by number, against a different recording.
        """
        import time

        tab._cal_keep = {0: {1, 2}}
        tab._selected_segments = [(0.0, 1.0)]
        tab._paso_mostrado = "frags"
        pasos: list[str] = []
        tab.coach_step.connect(lambda _t, cuerpo, _b: pasos.append(cuerpo))
        # One channel: with two, adopting a recording asks which muscle to
        # analyse in a modal dialogue, and headless that question waits for
        # an answer that never comes.
        tab.adopt_recording(_registro(tmp_path / "n.edf"))
        tab._worker.wait(120000)
        t0 = time.time()
        while time.time() - t0 < 5 and tab._worker.isRunning():
            qapp.processEvents()
        for _ in range(20):
            qapp.processEvents()
        assert tab._cal_keep == {} and tab._selected_segments == []
        assert pasos and tr("Select fragments…") in pasos[-1]

    def test_a_step_replaces_the_one_still_on_screen(self, main_window, qapp) -> None:
        """The previous «open this next» left on screen used to swallow the
        next one, and a step is only ever offered once."""
        main_window._tabs.setCurrentWidget(main_window._tab_ana)
        qapp.processEvents()
        main_window._mostrar_paso_guiado("t", "primero", main_window._tab_ana._btn_reps)
        assert main_window._coach.isVisible()
        main_window._mostrar_paso_guiado(
            "t", "segundo", main_window._tab_ana._btn_fragmentos
        )
        assert main_window._coach.isVisible()
        assert "segundo" in main_window._coach._lbl_body.text()
        main_window._coach.stop()
