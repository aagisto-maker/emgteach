"""Lo que hace didáctica la aplicación: el bloque «añadir».

Una tabla por contracción (el puente entre la gráfica y la fisiología),
rangos habituales junto a cada número, una guía de cinco pasos con el resto
del texto en un «?» por caja, nombres de músculo en vez de «EMG1», el
retraso electromecánico donde hay acelerómetro en la extremidad, y el
espectro antes y después del filtro.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from matplotlib.figure import Figure
from PySide6.QtCore import QSettings
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Table

from emgteach import i18n
from emgteach.contractions import Contraction, contraction_table, mean_emd_ms
from emgteach.dsp import process_offline
from emgteach.figures import draw_emd_note, draw_spectrum_before_filter
from emgteach.gui import help_texts
from emgteach.gui.tabs.analysis import AnalysisTab
from emgteach.gui.tour import build_tour
from emgteach.gui.widgets.help_button import HelpButton
from emgteach.gui.widgets.logger import LoggerWidget
from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.modes import MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE, MODES
from emgteach.reports import _seccion_contracciones
from emgteach.workers.analysis import AnalysisWorker

tr = i18n.tr
FS = 1000


def _senal(bursts: list[tuple[float, float, float]], total_s: float = 8.0,
           seed: int = 1) -> np.ndarray:
    """A resting trace with sine bursts: (start_s, end_s, amplitude_mV)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(total_s * FS)) / FS
    amp = np.full(t.size, 0.01)
    for a, b, v in bursts:
        amp[int(a * FS):int(b * FS)] = v
    return np.sin(2 * np.pi * 80 * t) * amp + rng.normal(0, 0.002, t.size)


# ---------------------------------------------------------------------------
# One row per contraction
# ---------------------------------------------------------------------------


class TestTheContractionTable:
    def _tabla(self, raw, **kw):
        proc = process_offline(raw, FS)
        return contraction_table(
            fs=FS, emg_raw=raw, emg_filtered=proc["emg_filtered"],
            envelope=proc["emg_envelope"], name_1="FCR", **kw,
        )

    def test_two_efforts_give_two_rows(self) -> None:
        filas = self._tabla(_senal([(2.0, 3.0, 0.4), (5.0, 5.8, 0.3)]))
        assert [f.n for f in filas] == [1, 2]
        # The proposer opens each window where the envelope leaves the
        # floor, a little before the burst, and closes it as it settles.
        assert filas[0].start_s == pytest.approx(2.0, abs=0.35)
        assert filas[0].duration_s == pytest.approx(1.0, abs=0.5)
        assert filas[1].start_s == pytest.approx(5.0, abs=0.35)
        assert all(f.muscle == "FCR" for f in filas)
        # A firm burst is far above rest, and its MDF sits near the carrier.
        assert filas[0].rms_mv > 0.1
        assert filas[0].mdf_hz == pytest.approx(80.0, abs=10.0)
        # No reference, no percentage — and no invented one.
        assert all(f.peak_pct is None for f in filas)

    def test_a_reference_turns_the_peak_into_a_percentage(self) -> None:
        raw = _senal([(2.0, 3.0, 0.4)])
        proc = process_offline(raw, FS)
        ref = float(np.max(proc["emg_envelope"]))
        (fila,) = self._tabla(raw, mvc_ref=ref)
        assert fila.peak_pct is not None and 60.0 < fila.peak_pct <= 100.5

    def test_a_quiet_recording_has_no_rows(self) -> None:
        assert self._tabla(_senal([])) == []

    def test_two_muscles_name_the_one_that_led(self) -> None:
        raw1 = _senal([(2.0, 3.0, 0.4)])
        raw2 = _senal([(5.0, 6.0, 0.4)], seed=2)
        p1, p2 = process_offline(raw1, FS), process_offline(raw2, FS)
        filas = contraction_table(
            fs=FS, emg_raw=raw1, emg_filtered=p1["emg_filtered"],
            envelope=p1["emg_envelope"], emg_raw_2=raw2,
            emg_filtered_2=p2["emg_filtered"], envelope_2=p2["emg_envelope"],
            name_1="FCR", name_2="ECR", both_label="both",
        )
        assert [f.muscle for f in filas] == ["FCR", "ECR"]

    def test_the_electromechanical_delay_is_read_off_the_movement(self) -> None:
        raw = _senal([(2.0, 3.0, 0.4), (5.0, 6.0, 0.4)])
        proc = process_offline(raw, FS)
        # The limb moves 60 ms after the muscle fires.
        movimiento = np.roll(proc["emg_envelope"], 60)
        filas = self._tabla(raw, movement=movimiento)
        assert all(f.emd_ms is not None for f in filas)
        assert mean_emd_ms(filas) == pytest.approx(60.0, abs=25.0)

    def test_without_a_movement_there_is_no_delay(self) -> None:
        filas = self._tabla(_senal([(2.0, 3.0, 0.4)]))
        assert mean_emd_ms(filas) is None


# ---------------------------------------------------------------------------
# The worker exports them, and the spectrum before the filter
# ---------------------------------------------------------------------------


def _edf(path: Path, raw: np.ndarray) -> str:
    canales = [ChannelInfo("FCR", dimension="mV", sample_frequency=FS)]
    with BufferedEdfWriter(str(path), channels=canales) as w:
        w.add_samples(raw)
    return str(path)


class TestTheWorkerCarriesThem:
    def test_contractions_and_raw_spectrum_in_the_result(self, qapp, tmp_path: Path) -> None:
        edf = _edf(tmp_path / "r.edf", _senal([(2.0, 3.0, 0.4), (5.0, 5.8, 0.3)]))
        caja: list[dict] = []
        w = AnalysisWorker(edf_path=edf, channel_name="FCR", plot_duration_s=0)
        w.result_ready.connect(caja.append)
        w.run()
        assert caja, "the analysis did not finish"
        r = caja[0]
        assert [c.n for c in r["contractions"]] == [1, 2]
        assert r["emd_ms_mean"] is None
        # The raw spectrum spans the whole band the sampling allows; the
        # filtered one only the analysis band.
        assert float(r["frequencies_raw"][0]) == 0.0
        assert float(r["frequencies_raw"][-1]) == pytest.approx(FS / 2, abs=1.0)
        assert float(r["frequencies"][0]) >= 20.0


class TestTheSpectrumBeforeTheFilter:
    def test_drawn_faintly_and_the_axis_stays_on_the_filtered_one(self) -> None:
        ax = Figure().add_subplot(111)
        f = np.linspace(0, 500, 251)
        psd = np.exp(-((f - 90) ** 2) / 2000)
        bruto = psd + 40.0 * np.exp(-((f - 50) ** 2) / 2)   # a mains line
        draw_spectrum_before_filter(ax, {"frequencies_raw": f, "psd_raw": bruto, "psd": psd})
        assert len(ax.lines) == 1
        assert ax.get_ylim()[1] == pytest.approx(1.35, abs=0.01)

    def test_nothing_without_the_raw_spectrum(self) -> None:
        ax = Figure().add_subplot(111)
        draw_spectrum_before_filter(ax, {"psd": np.ones(4)})
        assert not ax.lines

    def test_the_delay_note_only_when_there_is_one(self) -> None:
        ax = Figure().add_subplot(111)
        draw_emd_note(ax, {"emd_ms_mean": None})
        assert not ax.texts
        draw_emd_note(ax, {
            "emd_ms_mean": 55.0,
            "contractions": [Contraction(1, 1.0, 2.0, "M", 0.2, None, None, 55.0)],
        })
        assert len(ax.texts) == 1 and "55" in ax.texts[0].get_text()


# ---------------------------------------------------------------------------
# The tab and the report show the table
# ---------------------------------------------------------------------------


@pytest.fixture
def tab(qapp):
    t = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "anadir"))
    yield t
    t.deleteLater()
    qapp.processEvents()


def _filas() -> list[Contraction]:
    return [
        Contraction(1, 2.0, 3.0, "FCR", 0.21, 64.0, 88.0),
        Contraction(2, 5.0, 5.8, "ECR", 0.15, 120.0, None),
    ]


class TestTheTableOnTheTab:
    def test_hidden_until_there_are_rows(self, tab) -> None:
        assert not tab._box_contr.isVisibleTo(tab)
        tab._refresh_contractions({"contractions": [], "channel_name": "FCR"})
        assert not tab._box_contr.isVisibleTo(tab)

    def test_one_row_per_contraction_and_the_muscle_column_only_with_two(self, tab) -> None:
        tab._refresh_contractions({"contractions": _filas(), "channel_name": "FCR"})
        assert tab._box_contr.isVisibleTo(tab)
        assert tab._tbl_contr.rowCount() == 2
        assert tab._tbl_contr.isColumnHidden(3)
        assert tab._tbl_contr.item(0, 5).text() == "64"
        assert tab._tbl_contr.item(1, 6).text() == "—"
        tab._refresh_contractions({
            "contractions": _filas(), "channel_name": "FCR", "channel_name_2": "ECR",
        })
        assert not tab._tbl_contr.isColumnHidden(3)
        assert tab._tbl_contr.item(1, 3).text() == "ECR"

    def test_the_cards_carry_their_usual_ranges(self, tab) -> None:
        from PySide6.QtWidgets import QLabel

        textos = {w.text() for w in tab.findChildren(QLabel)}
        assert tr("usual 60–150 Hz") in textos  # noqa: RUF001 - the UI's own dash
        assert tr("a task effort is usually 20–80 %") in textos  # noqa: RUF001


class TestTheTableInTheReport:
    def _historia(self, result: dict) -> list:
        st = getSampleStyleSheet()
        story: list = []
        _seccion_contracciones(story, result, st["Heading2"], st["Normal"])
        return story

    def test_nothing_without_rows(self) -> None:
        assert self._historia({}) == []

    def test_same_rows_as_the_screen(self) -> None:
        story = self._historia({
            "contractions": _filas(), "channel_name": "FCR",
            "channel_name_2": "ECR", "emd_ms_mean": None,
        })
        assert isinstance(story[0], Paragraph) and story[0].text == tr("Contractions")
        tabla = next(x for x in story if isinstance(x, Table))
        assert len(tabla._cellvalues) == 3
        assert "ECR" in [str(c) for c in tabla._cellvalues[2]]

    def test_the_delay_is_stated_when_there_is_one(self) -> None:
        filas = [Contraction(1, 2.0, 3.0, "M", 0.2, None, None, 48.0)]
        story = self._historia({"contractions": filas, "emd_ms_mean": 48.0})
        assert any(isinstance(x, Paragraph) and "48" in x.text for x in story)


# ---------------------------------------------------------------------------
# Five steps, and a «?» on every box
# ---------------------------------------------------------------------------


def _set_mode(win, qapp, mode: str) -> None:
    win._combo_mode.setCurrentIndex(MODES.index(mode))
    qapp.processEvents()


class TestTheTourIsShort:
    def test_five_steps_where_five_are_enough(self, main_window, qapp) -> None:
        for mode, n in ((MODE_SINGLE, 5), (MODE_PAIR, 5), (MODE_KINEMATICS, 7)):
            _set_mode(main_window, qapp, mode)
            assert len(build_tour(main_window)) == n, mode

    def test_every_box_has_a_help_button_with_a_registered_text(
        self, main_window, qapp
    ) -> None:
        botones = main_window.findChildren(HelpButton)
        claves = {b.objectName().removeprefix("help:") for b in botones}
        # Nine boxes: the panel chips lost their own box when they joined the
        # editors' line, and their text went to the «Panels:» tooltip.
        assert len(claves) >= 9
        assert claves <= set(help_texts.keys())

    def test_the_button_explains_over_its_own_box(self, main_window, qapp) -> None:
        boton = next(
            b for b in main_window.findChildren(HelpButton)
            if b.objectName() == "help:acq.control"
        )
        boton.click()
        qapp.processEvents()
        coach = main_window._coach
        assert coach.isVisible() and not coach.is_tour
        assert coach._steps[0].title == help_texts.text("acq.control")[0]
        coach.stop()


class TestMuscleLabels:
    def test_the_boxes_start_empty_with_a_hint(self, main_window, qapp) -> None:
        _set_mode(main_window, qapp, MODE_PAIR)
        adq = main_window._tab_adq
        for e in adq._edit_labels[:2]:
            e.setText("")
        assert tr("Agonist") in adq._edit_labels[0].placeholderText()
        assert tr("Antagonist") in adq._edit_labels[1].placeholderText()
        # Left empty, the recording is still named after what it is.
        assert adq._active_labels() == [tr("Agonist"), tr("Antagonist")]
        assert "EMG1" not in adq._active_labels()
