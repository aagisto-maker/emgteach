"""El cuadro de fragmentos se ajusta mirando, y las tablas de abajo son gráficos.

Lo que pidió el autor el 4 de septiembre de 2026: un manejo sencillo del cuadro
de fragmentos, con pocos ajustes cuyo efecto se vea al momento en el gráfico y
en el sombreado —dos niveles, básico y fino—, y las dos tablas de datos de
abajo convertidas en gráficos que resuman contracciones y coactivación. Y un
solo término: coactivación.
"""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure
from PySide6.QtCore import QSettings

from emgteach.charts import draw_coactivation_chart, draw_contraction_chart
from emgteach.coactivation import CoactivationResult
from emgteach.contractions import Contraction, contraction_table
from emgteach.dsp import process_offline
from emgteach.gui.widgets.fragment_selection import (
    FragmentSelectionDialog,
    default_detection,
)
from emgteach.i18n import tr
from emgteach.selection import DEFAULT_DETECTION, activity_threshold

FS = 1000
FK = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}


def _bursts(scale: float = 1.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    sig = rng.normal(0.0, 0.01, size=10 * FS)
    for a, b in ((2.0, 3.5), (6.0, 7.5)):
        i0, i1 = int(a * FS), int(b * FS)
        t = np.arange(i1 - i0) / FS
        sig[i0:i1] += 0.5 * np.sin(2 * np.pi * 90.0 * t)
    return sig * scale


# ---------------------------------------------------------------------------
# The dialogue: two sliders whose effect is seen as they move
# ---------------------------------------------------------------------------


@pytest.mark.gui
class TestTheSlidersMoveTheProposal:
    def test_it_opens_on_the_core_defaults(self, qapp) -> None:
        dlg = FragmentSelectionDialog(_bursts(), FS, FK)
        assert dlg.detection_kwargs() == default_detection()
        assert dlg.detection_kwargs()["k"] == DEFAULT_DETECTION["k"]
        assert not dlg._box_fino.isVisibleTo(dlg)
        dlg.deleteLater()

    def test_the_sensitivity_slider_rebuilds_the_rows(self, qapp) -> None:
        """A move arms the timer; when it fires the proposal is rebuilt with
        the new k, and a clean two-burst signal still gives two rows."""
        dlg = FragmentSelectionDialog(_bursts(), FS, FK)
        dlg._sld_k.setValue(55)
        assert dlg._timer.isActive()
        dlg._auto_suggest()
        assert dlg.detection_kwargs()["k"] == pytest.approx(5.5)
        assert dlg._table.rowCount() == 2
        assert dlg._lbl_k.text() == "k = 5.5"
        dlg.deleteLater()

    def test_the_threshold_line_is_drawn_and_follows_k(self, qapp) -> None:
        dlg = FragmentSelectionDialog(_bursts(), FS, FK)
        dashed = [ln for ln in dlg._ax.get_lines() if ln.get_linestyle() == "--"]
        assert dashed, "no threshold line on the preview"
        y_antes = dashed[0].get_ydata()[0]
        env = process_offline(_bursts(), FS, **FK)["emg_envelope"]
        assert y_antes == pytest.approx(activity_threshold(env, 3.0)[1])
        dlg._sld_k.setValue(55)
        dlg._auto_suggest()
        dashed = [ln for ln in dlg._ax.get_lines() if ln.get_linestyle() == "--"]
        assert dashed[0].get_ydata()[0] > y_antes
        dlg.deleteLater()

    def test_the_co_activation_rule_renames_without_rebuilding(self, qapp) -> None:
        """The second muscle at 30 % of the first: below the default rule one
        muscle led, and the slider moved under it says both did. Same rows."""
        dlg = FragmentSelectionDialog(
            _bursts(), FS, FK, raw_2=_bursts(0.3, seed=1), name_1="FCR", name_2="ECR",
        )
        assert dlg._sld_ratio.isVisibleTo(dlg)
        nombres = [w["label"].currentText() for w in dlg._row_widgets]
        assert nombres and all(n == "FCR" for n in nombres)
        filas = dlg._table.rowCount()
        dlg._sld_ratio.setValue(20)
        assert not dlg._timer.isActive()
        nombres = [w["label"].currentText() for w in dlg._row_widgets]
        assert all(n == tr("Co-activation") for n in nombres)
        assert dlg._table.rowCount() == filas
        assert dlg.detection_kwargs()["both_ratio"] == pytest.approx(0.2)
        dlg.deleteLater()

    def test_with_one_muscle_there_is_no_co_activation_slider(self, qapp) -> None:
        dlg = FragmentSelectionDialog(_bursts(), FS, FK)
        assert not dlg._sld_ratio.isVisibleTo(dlg)
        dlg.deleteLater()

    def test_the_fine_row_unfolds_on_request(self, qapp) -> None:
        dlg = FragmentSelectionDialog(_bursts(), FS, FK)
        dlg._btn_fino.setChecked(True)
        assert dlg._box_fino.isVisibleTo(dlg)
        dlg._spin_min.setValue(1.0)
        assert dlg._timer.isActive()
        dlg._auto_suggest()
        assert dlg.detection_kwargs()["min_duration_s"] == pytest.approx(1.0)
        dlg.deleteLater()

    def test_reset_returns_every_setting_to_its_default(self, qapp) -> None:
        dlg = FragmentSelectionDialog(_bursts(), FS, FK)
        dlg._sld_k.setValue(20)
        dlg._sld_prom.setValue(50)
        dlg._reset_detection()
        assert dlg.detection_kwargs() == default_detection()
        assert dlg._sld_k.value() == 30
        dlg.deleteLater()

    def test_a_click_on_a_stretch_drops_it_and_another_brings_it_back(
        self, qapp
    ) -> None:
        dlg = FragmentSelectionDialog(_bursts(), FS, FK)
        assert len(dlg.selected_segments()) == 2
        dlg._toggle_at(2.5)
        assert len(dlg.selected_segments()) == 1
        dlg._toggle_at(2.5)
        assert len(dlg.selected_segments()) == 2
        dlg.deleteLater()

    def test_it_reopens_where_it_was_left(self, qapp) -> None:
        dlg = FragmentSelectionDialog(
            _bursts(), FS, FK, detection={"k": 4.0, "prominence": 0.4},
        )
        assert dlg._sld_k.value() == 40
        assert dlg._sld_prom.value() == 40
        dlg.deleteLater()

    def test_the_label_for_both_is_co_activation(self, qapp) -> None:
        dlg = FragmentSelectionDialog(_bursts(), FS, FK, raw_2=_bursts(), name_1="A", name_2="B")
        opciones = [dlg._row_widgets[0]["label"].itemText(i)
                    for i in range(dlg._row_widgets[0]["label"].count())]
        assert tr("Co-activation") in opciones
        assert "Co-contraction" not in opciones
        dlg.deleteLater()


class TestTheSettingsReachTheTable:
    """What the student tuned by eye is what the rows are made of."""

    def test_the_contraction_table_takes_the_same_settings(self) -> None:
        raw = _bursts()
        proc = process_offline(raw, FS, **FK)
        filas = contraction_table(
            fs=FS, emg_raw=raw, emg_filtered=proc["emg_filtered"],
            envelope=proc["emg_envelope"], name_1="FCR",
            k=5.5, min_duration_s=0.5, merge_gap_s=0.3, prominence=0.4,
            both_ratio=0.5,
        )
        assert len(filas) == 2
        assert all(f.channel == 1 and f.rms_mv_other is None for f in filas)

    def test_the_other_muscle_travels_with_the_row(self) -> None:
        raw, raw2 = _bursts(), _bursts(0.3, seed=1)
        p1, p2 = process_offline(raw, FS, **FK), process_offline(raw2, FS, **FK)
        filas = contraction_table(
            fs=FS, emg_raw=raw, emg_filtered=p1["emg_filtered"], envelope=p1["emg_envelope"],
            emg_raw_2=raw2, emg_filtered_2=p2["emg_filtered"], envelope_2=p2["emg_envelope"],
            name_1="FCR", name_2="ECR", both_label="both",
        )
        assert filas
        for f in filas:
            assert f.channel == 1 and f.muscle == "FCR"
            assert f.rms_mv_other is not None and f.rms_mv_other < f.rms_mv
            assert f.by_muscle(2)[0] == pytest.approx(f.rms_mv_other)


# ---------------------------------------------------------------------------
# The two charts
# ---------------------------------------------------------------------------


def _rows(dos: bool) -> list[Contraction]:
    return [
        Contraction(n=1, start_s=1.0, end_s=2.0, muscle="FCR", rms_mv=0.2, peak_pct=60.0,
                    mdf_hz=95.0, channel=1,
                    rms_mv_other=0.05 if dos else None, peak_pct_other=12.0 if dos else None),
        Contraction(n=2, start_s=3.0, end_s=4.0, muscle="FCR", rms_mv=0.25, peak_pct=110.0,
                    mdf_hz=90.0, channel=1,
                    rms_mv_other=0.06 if dos else None, peak_pct_other=15.0 if dos else None),
        Contraction(n=3, start_s=5.0, end_s=6.0, muscle="both", rms_mv=0.22, peak_pct=70.0,
                    mdf_hz=None, emd_ms=42.0, channel=2,
                    rms_mv_other=0.2 if dos else None, peak_pct_other=65.0 if dos else None),
    ]


class TestTheCharts:
    def test_two_bars_per_contraction_with_two_muscles(self) -> None:
        fig = Figure()
        ax = fig.add_subplot(111)
        draw_contraction_chart(ax, _rows(True), name_1="FCR", name_2="ECR")
        assert len(ax.patches) == 6
        # The median frequency rides on its own axis.
        assert len(fig.axes) == 2
        # And the electromechanical delay is written over its bar.
        assert any("42 ms" in t.get_text() for t in ax.texts)

    def test_one_bar_per_contraction_with_one_muscle(self) -> None:
        fig = Figure()
        ax = fig.add_subplot(111)
        draw_contraction_chart(ax, _rows(False), name_1="FCR")
        assert len(ax.patches) == 3

    def test_no_rows_no_axes(self) -> None:
        fig = Figure()
        ax = fig.add_subplot(111)
        draw_contraction_chart(ax, [], name_1="FCR")
        assert not ax.axison

    def test_the_co_activation_chart_says_when_it_does_not_report(self) -> None:
        fig = Figure()
        ax = fig.add_subplot(111)
        res = [
            CoactivationResult(index=85.0, mean_1=60.0, mean_2=55.0, window_s=(0.0, 5.0), label="Grip"),
            CoactivationResult(index=None, mean_1=45.0, mean_2=3.0, window_s=(5.0, 9.0),
                               label="FCR", reason="not reported — x"),
        ]
        draw_coactivation_chart(ax, res, name_1="FCR", name_2="ECR")
        assert len(ax.patches) == 4
        textos = [t.get_text() for t in ax.texts]
        assert "85 %" in textos
        assert tr("not reported") in textos


@pytest.mark.gui
class TestTheTabShowsChartsFirst:
    @pytest.fixture
    def tab(self, qapp):
        from emgteach.gui.tabs.analysis import AnalysisTab
        from emgteach.gui.widgets.logger import LoggerWidget

        t = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "charts"))
        yield t
        t.deleteLater()

    def test_the_contraction_box_draws_bars_and_keeps_the_table(self, tab) -> None:
        tab._refresh_contractions({
            "contractions": _rows(True), "channel_name": "FCR",
            "channel_name_2": "ECR", "emd_ms_mean": 42.0,
        })
        assert tab._stack_contr.currentIndex() == 0
        assert len(tab._ax_contr.patches) == 6
        assert tab._tbl_contr.rowCount() == 3

    def test_the_table_is_one_click_behind_in_both_boxes(self, tab) -> None:
        tab._btn_tabla_contr.setChecked(True)
        assert tab._stack_contr.currentIndex() == 1
        assert tab._stack_coact.currentIndex() == 1
        assert tab._btn_tabla_contr.text() == tr("Chart")
        tab._btn_tabla_coact.setChecked(False)
        assert tab._stack_contr.currentIndex() == 0
        assert tab._btn_tabla_contr.text() == tr("Table")
