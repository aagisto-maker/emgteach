"""Que la CVM sea de verdad la máxima, y el resto de la ronda del 3-sep-2026.

El autor vio la tarea al 135 % de una «máxima»: la referencia se medía como
el medio segundo mantenido más fuerte, es decir, sobre la meseta de una
contracción sostenida, y los esfuerzos breves de la tarea alcanzan el pico
inicial, que la meseta no tiene. Ahora la ventana es de 0,2 s y la
calibración añade tres sacudidas máximas breves tras las tres mantenidas; la
referencia es la mejor de las seis. Además: PSD de los dos músculos, «Más
paneles…» en todas las prácticas, tres cuadros abajo con su «?» en la
esquina, sin ficha de archivo, y la guía sin la frase a medias.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel

from emgteach import i18n
from emgteach.gui.tabs.analysis import AnalysisTab
from emgteach.gui.tour import build_tour
from emgteach.gui.widgets.help_button import HelpButton
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.modes import MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE, MODES
from emgteach.mvc import mvc_from_reps
from emgteach.profiles import EMG_PROFILE
from emgteach.workers.analysis import AnalysisWorker

tr = i18n.tr
FS = 1000


# ---------------------------------------------------------------------------
# The reference is measured where the peak is
# ---------------------------------------------------------------------------


def _mantenida(peak: float = 1.0, plateau: float = 0.6, seconds: float = 4.0) -> np.ndarray:
    """A held maximum: a 0.25 s peak at the start, then a plateau."""
    env = np.full(int(seconds * FS), plateau)
    env[: int(0.25 * FS)] = peak
    return env


def _sacudida(peak: float = 1.0) -> np.ndarray:
    """A brief squeeze: 0.3 s at the peak and nothing else."""
    env = np.full(int(1.5 * FS), 0.05)
    env[int(0.4 * FS): int(0.7 * FS)] = peak
    return env


class TestTheReferenceIsTheRealMaximum:
    def test_a_half_second_window_sat_on_the_plateau(self) -> None:
        w = round(0.5 * FS)
        assert mvc_from_reps([_mantenida()], window_samples=w) == pytest.approx(0.8, abs=0.02)

    def test_the_profile_window_reaches_the_peak(self) -> None:
        w = round(EMG_PROFILE.mvc_peak_window_s * FS)
        assert mvc_from_reps([_mantenida()], window_samples=w) == pytest.approx(1.0, abs=0.05)

    def test_a_brief_squeeze_counts_in_full(self) -> None:
        w = round(EMG_PROFILE.mvc_peak_window_s * FS)
        assert mvc_from_reps([_sacudida()], window_samples=w) == pytest.approx(1.0, abs=0.01)
        # And the best of held and brief is the reference.
        assert mvc_from_reps([_mantenida(peak=0.9), _sacudida(1.0)], window_samples=w) == (
            pytest.approx(1.0, abs=0.01)
        )


# ---------------------------------------------------------------------------
# The wizard asks for the squeezes
# ---------------------------------------------------------------------------


class _FakeWorker:
    def __init__(self) -> None:
        self.markers: list[str] = []

    def isRunning(self) -> bool:
        return True

    def add_marker(self, label: str) -> None:
        self.markers.append(str(label))

    def stop(self) -> None:
        pass

    def is_streaming(self) -> bool:
        return True


@pytest.fixture
def adq(qapp):
    from emgteach.gui.tabs.acquisition import AcquisitionTab

    widget = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "cal-max"))
    widget._n_channels = 1
    widget._worker = _FakeWorker()
    yield widget
    widget._watchdog_timer.stop()
    widget._mvc_timer.stop()
    widget._prep_timer.stop()
    widget._load_timer.stop()
    widget.close()


class TestTheWizardAddsThreeSqueezes:
    def test_three_held_and_three_brief(self, adq) -> None:
        adq._iniciar_calibracion(auto_flow=False)
        try:
            assert adq._mvc_reps == 3 and adq._mvc_bursts == 3
        finally:
            adq._mvc_cancel()

    def test_a_squeeze_lasts_its_own_time_and_is_a_numbered_rep(self, adq) -> None:
        adq._iniciar_calibracion(auto_flow=False)
        try:
            adq._mvc_muscle = 0
            adq._mvc_rep = 3                       # first brief squeeze
            adq._mvc_phase = "contract"
            adq._mvc_cur_buf = list(_sacudida())
            adq._mvc_elapsed = EMG_PROFILE.mvc_burst_s - 0.3   # a tick adds 0.1 s
            adq._mvc_tick()
            assert adq._mvc_phase == "contract", "not over before its 1.5 s"
            adq._mvc_elapsed = EMG_PROFILE.mvc_burst_s
            adq._mvc_tick()
            assert "CAL end ch=1 rep=4" in adq._worker.markers
            assert adq._mvc_phase == "rest"          # two squeezes to go
        finally:
            adq._mvc_cancel()

    def test_the_last_squeeze_closes_the_muscle(self, adq) -> None:
        adq._iniciar_calibracion(auto_flow=False)
        try:
            adq._mvc_muscle = 0
            for _ in range(5):
                adq._mvc_capture[0].append(_mantenida(peak=0.8))
            adq._mvc_rep = 5                       # third and last squeeze
            adq._mvc_phase = "contract"
            adq._mvc_cur_buf = list(_sacudida(1.0))
            adq._mvc_elapsed = EMG_PROFILE.mvc_burst_s
            adq._mvc_tick()
            assert any(m.startswith("MVC ref ch=1") for m in adq._worker.markers)
            # The squeeze set the reference: it was the strongest 0.2 s.
            assert adq._mvc_ref[0] == pytest.approx(1.0, abs=0.02)
        finally:
            if adq._mvc_active:
                adq._mvc_cancel()


# ---------------------------------------------------------------------------
# Analysis: PSD of both muscles, more panels everywhere, three boxes below
# ---------------------------------------------------------------------------


def _dos_canales(path: Path) -> str:
    t = np.arange(8 * FS) / FS
    a1 = np.full(t.size, 0.01)
    a1[2 * FS: 3 * FS] = 0.4
    a2 = np.full(t.size, 0.01)
    a2[5 * FS: 6 * FS] = 0.35
    canales = [
        ChannelInfo("FCR", dimension="mV", sample_frequency=FS),
        ChannelInfo("ECR", dimension="mV", sample_frequency=FS),
    ]
    with BufferedEdfWriter(str(path), channels=canales) as w:
        w.add_samples(np.sin(2 * np.pi * 80 * t) * a1, np.sin(2 * np.pi * 90 * t) * a2)
    return str(path)


@pytest.fixture
def tab(qapp):
    t = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "cal-max-ana"))
    yield t
    t.deleteLater()
    qapp.processEvents()


class TestTheSpectrumOfBothMuscles:
    def test_the_worker_exports_the_second_spectrum(self, qapp, tmp_path: Path) -> None:
        caja: list[dict] = []
        w = AnalysisWorker(edf_path=_dos_canales(tmp_path / "d.edf"),
                           channel_name="FCR", channel_name_2="ECR", plot_duration_s=0)
        w.result_ready.connect(caja.append)
        w.run()
        r = caja[0]
        assert len(r["psd_2"]) == len(r["frequencies_2"])
        assert r["mdf_2"] == pytest.approx(90.0, abs=8.0)

    def test_the_pair_offers_the_spectrum_and_every_practical_can_reveal_more(
        self, main_window, qapp
    ) -> None:
        ana = main_window._tab_ana
        for mode in MODES:
            main_window._combo_mode.setCurrentIndex(MODES.index(mode))
            qapp.processEvents()
            assert ana._btn_mas_paneles.isVisibleTo(ana), mode
        main_window._combo_mode.setCurrentIndex(MODES.index(MODE_PAIR))
        qapp.processEvents()
        assert not ana._chk_paneles[ana._panel_pids.index(4)].isHidden()
        main_window._combo_mode.setCurrentIndex(MODES.index(MODE_SINGLE))
        qapp.processEvents()
        assert ana._chk_paneles[ana._panel_pids.index(4)].isHidden() is False


class TestThreeBoxesBelowWithACornerHelp:
    def test_coactivation_contractions_and_summary_share_the_band(self, tab) -> None:
        raiz = tab.layout()
        fila = None
        for i in range(raiz.count()):
            sub = raiz.itemAt(i).layout()
            if sub is not None and sub.indexOf(tab._grp_resumen) >= 0:
                fila = sub
        assert fila is not None
        assert 0 <= fila.indexOf(tab._box_coact) < fila.indexOf(tab._box_contr) < fila.indexOf(tab._grp_resumen)

    def test_each_has_the_same_corner_help_and_no_inline_button(self, tab) -> None:
        claves = {b.objectName() for b in tab.findChildren(HelpButton)}
        assert {"help:ana.coact", "help:ana.contr", "help:ana.summary"} <= claves
        assert not hasattr(tab, "_btn_ayuda_coact")
        assert not hasattr(tab, "_btn_ayuda_contr")

    def test_no_file_card(self, tab) -> None:
        textos = {w.text() for w in tab._grp_resumen.findChildren(QLabel)}
        assert tr("File") not in textos


class TestTheGuidedForceVelocityExplainsItself:
    """Every box on the acquisition tab has a «?» in its corner except the
    guided force-velocity flow, whose only explanation was the button's
    tooltip. It is the kinematics practical's whole procedure, so it gets a
    box of its own with the same corner help as the rest."""

    def test_the_box_carries_its_own_corner_help(self, main_window) -> None:
        adq = main_window._tab_adq
        claves = {b.objectName() for b in adq._box_fv_guided.findChildren(HelpButton)}
        assert claves == {"help:acq.fv"}

    def test_only_the_kinematics_practical_shows_it(self, main_window, qapp) -> None:
        adq = main_window._tab_adq
        for mode in MODES:
            main_window._combo_mode.setCurrentIndex(MODES.index(mode))
            qapp.processEvents()
            assert adq._box_fv_guided.isVisibleTo(adq) == (mode == MODE_KINEMATICS), mode

    def test_the_help_says_what_the_two_buttons_do(self) -> None:
        from emgteach.gui import help_texts

        cuerpo = help_texts.text("acq.fv")[1]
        assert tr("Guided F-V…") in cuerpo
        assert tr("Rehearse…") in cuerpo

    def test_the_device_help_names_the_test_identifier(self) -> None:
        from emgteach.gui import help_texts

        cuerpo = help_texts.text("acq.device")[1]
        assert "identifier" in cuerpo
        assert "student code" not in cuerpo


class TestSmallThings:
    def test_the_tour_no_longer_ends_mid_sentence(self, main_window) -> None:
        ultimo = build_tour(main_window)[-1].body
        assert "«?»" not in ultimo
        assert ultimo.rstrip().endswith(".")

    def test_the_normalisation_log_fills_its_box(self, main_window) -> None:
        """Five lines, where the widget's own cap is three."""
        log = main_window._tab_cvm._local_log
        assert log.maximumHeight() >= log.fontMetrics().lineSpacing() * 5
