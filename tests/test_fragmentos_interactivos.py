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
from matplotlib import colors as mcolors
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


class TestTheLoadOfEachContraction:
    """The guided wizard marks the start of each load's window; a
    contraction belongs to the last marker before it, if close enough.
    The worker hands the parsed ``(onset_s, kg)`` pairs over as
    ``fv_loads``, already in the analysed span's time."""

    def test_each_contraction_takes_the_marker_before_it(self) -> None:
        from emgteach.contractions import load_of_each

        marcas = [(12.4, 2.0), (20.2, 3.0)]
        filas = [
            Contraction(1, 5.0, 6.0, "FCR", 0.1, None, None),
            Contraction(2, 13.0, 15.0, "FCR", 0.1, None, None),
            Contraction(3, 21.0, 22.5, "FCR", 0.1, None, None),
            Contraction(4, 40.0, 41.0, "FCR", 0.1, None, None),
        ]
        assert load_of_each(filas, marcas) == [None, 2.0, 3.0, None]

    def test_no_markers_no_loads(self) -> None:
        from emgteach.contractions import load_of_each

        assert load_of_each(_rows(False), []) == [None, None, None]


class TestTheCharts:
    """A chart earns its place by showing a relation a conclusion can be read
    off. The first version was the table drawn as bars, and the author's
    verdict was exact: nothing came out of it."""

    def test_two_muscles_get_the_series_and_the_activation_plane(self) -> None:
        fig = Figure()
        draw_contraction_chart(fig, _rows(True), name_1="FCR", name_2="ECR")
        # The series (plus the MDF axis twinned on it) and the relation.
        assert len(fig.axes) == 3
        serie, relacion = fig.axes[0], fig.axes[1]
        # Two lines with markers along the series, one per muscle.
        assert len([ln for ln in serie.get_lines() if len(ln.get_xdata()) == 3]) == 2
        # The plane carries the co-activation wedge and one point per contraction.
        assert len(relacion.patches) >= 1
        assert len([ln for ln in relacion.get_lines() if len(ln.get_xdata()) == 1]) == 3
        # The electromechanical delay is written over its point.
        assert any("42 ms" in t.get_text() for t in serie.texts)
        assert relacion.get_title() == tr("Who leads each contraction")

    def test_the_wedge_follows_the_rule_it_was_labelled_under(self) -> None:
        """The slider that sets the rule is seen setting the wedge: a wider
        ratio narrows it."""
        def ancho(ratio):
            fig = Figure()
            draw_contraction_chart(fig, _rows(True), name_1="FCR", name_2="ECR",
                                   both_ratio=ratio)
            cuña = fig.axes[1].patches[0]
            xs, ys = cuña.get_xy()[:, 0], cuña.get_xy()[:, 1]
            return float(ys[1] / xs[1])  # the lower edge's slope is the ratio
        assert ancho(0.3) == pytest.approx(0.3)
        assert ancho(0.7) == pytest.approx(0.7)

    def test_one_muscle_gets_the_series_with_its_trend_and_the_jasa_plane(self) -> None:
        filas = [
            Contraction(n=k, start_s=float(k), end_s=k + 0.8, muscle="FCR",
                        rms_mv=0.2 + 0.02 * k, peak_pct=50.0 + 5.0 * k,
                        mdf_hz=100.0 - 4.0 * k)
            for k in range(1, 7)
        ]
        fig = Figure()
        draw_contraction_chart(fig, filas, name_1="FCR")
        assert len(fig.axes) == 3
        serie, relacion, mdf = fig.axes[0], fig.axes[1], fig.axes[2]
        etiquetas = [t.get_text() for t in serie.get_legend().get_texts()]
        # Six contractions are enough for a fitted trend, and the slope is
        # written in the legend, for the amplitude and for the MDF.
        assert any("/" in e and "%" in e for e in etiquetas)
        assert any(e.startswith("MDF") and "Hz/" in e for e in etiquetas)
        assert mdf.get_ylabel() == tr("MDF (Hz)")
        # The JASA plane names its four quadrants.
        textos = [t.get_text() for t in relacion.texts]
        for palabra in ("fatigue", "more force", "less force", "recovery"):
            assert tr(palabra) in textos
        assert relacion.get_title() == tr("Amplitude against MDF (JASA)")

    def test_the_category_view_groups_by_who_led(self) -> None:
        fig = Figure()
        draw_contraction_chart(fig, _rows(True), name_1="FCR", name_2="ECR",
                               view="category")
        ax = fig.axes[0]
        # One bar per muscle per category present.
        categorias = {r.muscle for r in _rows(True)}
        assert len(ax.patches) == 2 * len(categorias)
        etiquetas = [t.get_text() for t in ax.get_xticklabels()]
        assert any(e.startswith("FCR") for e in etiquetas)
        assert any(e.startswith(tr("Co-activation")) for e in etiquetas)
        assert ax.get_title() == tr("Mean per category, and each contraction")

    def test_the_dominance_view_is_one_bar_per_contraction_in_a_band(self) -> None:
        fig = Figure()
        draw_contraction_chart(fig, _rows(True), name_1="FCR", name_2="ECR",
                               view="dominance", both_ratio=0.5)
        ax = fig.axes[0]
        # Three bars plus the band.
        assert len(ax.patches) == 4
        banda = ax.patches[0]
        assert banda.get_x() + banda.get_width() == pytest.approx((1 - 0.5) / (1 + 0.5))
        etiquetas = [t.get_text() for t in ax.get_xticklabels()]
        assert tr("only {name}").format(name="FCR") in etiquetas
        assert tr("equal") in etiquetas

    def test_the_load_view_groups_by_the_marker(self) -> None:
        filas = [
            *_rows(False),
            Contraction(n=4, start_s=9.0, end_s=9.8, muscle="FCR", rms_mv=0.3,
                        peak_pct=70.0, mdf_hz=90.0, emd_ms=55.0),
        ]
        fig = Figure()
        draw_contraction_chart(fig, filas, name_1="FCR", view="load",
                               loads=[2.0, 2.0, 3.0, None])
        assert len(fig.axes) == 3
        etiquetas = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert etiquetas == ["2", "3", tr("none")]
        assert fig.axes[0].get_xlabel() == tr("Load (kg)")
        # Amplitude, velocity and delay: what the kinematics practical asks.
        assert fig.axes[1].get_title() == tr("Velocity by load")
        assert fig.axes[2].get_title() == tr("EMD by load")

    def test_views_that_need_what_the_recording_lacks_say_so(self) -> None:
        fig = Figure()
        draw_contraction_chart(fig, _rows(False), name_1="FCR", view="category")
        assert not fig.axes[0].axison
        assert any("two muscles" in t.get_text() or "dos músculos" in t.get_text()
                   for t in fig.axes[0].texts)
        fig = Figure()
        draw_contraction_chart(fig, _rows(False), name_1="FCR", view="load")
        assert not fig.axes[0].axison

    def test_the_report_can_ask_for_panels_side_by_side(self) -> None:
        fig = Figure()
        draw_contraction_chart(fig, _rows(True), name_1="FCR", name_2="ECR",
                               view=("category", "dominance"))
        assert len(fig.axes) == 2
        with pytest.raises(ValueError):
            draw_contraction_chart(fig, _rows(True), name_1="FCR", view="pie")

    def test_too_few_points_for_a_relation_says_so(self) -> None:
        fig = Figure()
        draw_contraction_chart(fig, _rows(False)[:1], name_1="FCR")
        relacion = fig.axes[1]
        assert not relacion.axison
        assert any("MDF" in t.get_text() for t in relacion.texts)

    def test_no_rows_no_axes(self) -> None:
        fig = Figure()
        draw_contraction_chart(fig, [], name_1="FCR")
        assert len(fig.axes) == 1 and not fig.axes[0].axison

    def test_one_window_does_not_become_a_slab(self) -> None:
        """Left to fill the box, a single bar was half the panel high."""
        fig = Figure()
        draw_coactivation_chart(
            fig,
            [CoactivationResult(index=74.0, mean_1=52.0, mean_2=48.0,
                                window_s=(0.0, 20.0), label="Grip")],
            name_1="FCR", name_2="ECR",
        )
        lo, hi = fig.axes[0].get_ylim()
        # The bar is 0.6 units: three lines' worth of room keeps it to a fifth
        # of the panel, and it sits in the middle of them.
        assert hi - lo >= 3.0
        assert (lo + hi) / 2 == pytest.approx(0.0)

    def test_the_co_activation_chart_is_one_line_per_window(self) -> None:
        """A bar with the index, or a gold block and a chip for who worked;
        the name on the left, the seconds on an axis of their own on the
        right, and a legend that says what each colour is."""
        from emgteach.charts import COLOUR_1, COLOUR_2, COLOUR_BOTH

        fig = Figure()
        res = [
            CoactivationResult(index=85.0, mean_1=60.0, mean_2=55.0, window_s=(0.0, 5.0), label="Grip"),
            CoactivationResult(index=None, mean_1=45.0, mean_2=3.0, window_s=(5.0, 9.0),
                               label="Flexion", reason="not reported — x"),
            CoactivationResult(index=None, mean_1=2.0, mean_2=1.0, window_s=(9.0, 12.0),
                               label="Rest", reason="not reported — y"),
        ]
        draw_coactivation_chart(fig, res, name_1="FCR", name_2="ECR")
        ax = fig.axes[0]
        # One bar per window: the index, or the gold block in its place.
        assert len(ax.patches) == 3
        colores = [p.get_facecolor() for p in ax.patches]
        assert colores[0] == pytest.approx(mcolors.to_rgba(COLOUR_BOTH))
        assert colores[1] == colores[2] != colores[0]
        textos = [t.get_text() for t in ax.texts]
        assert "85 %" in textos
        # No means, and no words for «not reported»: that is the legend's job.
        assert not any("FCR 60" in t or "not reported" in t for t in textos)
        etiquetas = [t.get_text() for t in ax.get_legend().get_texts()]
        assert etiquetas == ["FCR", "ECR", tr("Co-activation"), tr("not reported")]
        # The chip: the flexion was the first muscle's alone, the rest nobody's.
        chips = [ln for ln in ax.get_lines() if ln.get_marker() == "s"]
        assert len(chips) == 1
        assert mcolors.to_rgba(chips[0].get_color()) == pytest.approx(mcolors.to_rgba(COLOUR_1))
        assert mcolors.to_rgba(COLOUR_2) != mcolors.to_rgba(COLOUR_1)
        # Names on the left, seconds on the right.
        assert [t.get_text() for t in ax.get_yticklabels()] == ["Grip", "Flexion", "Rest"]
        derecha = [t.get_text() for t in fig.axes[1].get_yticklabels()]
        assert derecha == ["0–5 s", "5–9 s", "9–12 s"]  # noqa: RUF001


@pytest.mark.gui
class TestTheTabShowsChartsFirst:
    @pytest.fixture
    def tab(self, qapp):
        from emgteach.gui.tabs.analysis import AnalysisTab
        from emgteach.gui.widgets.logger import LoggerWidget

        # Cleared first: the view choice is kept across sessions on purpose,
        # and a run that ended on «series» would otherwise open the next
        # one's tab on it.
        ajustes = QSettings("emgteach-test", "charts")
        ajustes.clear()
        t = AnalysisTab(LoggerWidget(), ajustes)
        yield t
        t.deleteLater()
        ajustes.clear()

    def _llenar(self, tab) -> None:
        tab._refresh_contractions({
            "contractions": _rows(True), "channel_name": "FCR",
            "channel_name_2": "ECR", "emd_ms_mean": 42.0,
        })

    def test_the_contraction_box_opens_on_the_relation_and_keeps_the_table(self, tab) -> None:
        """The relation is the panel a conclusion is read off, so it is what
        the box opens on; the series and the numbers are a click away."""
        self._llenar(tab)
        assert tab._sel_contr.vista() == "relation"
        assert tab._stack_contr.currentIndex() == 0
        # One panel fills the box: the activation plane, on its own.
        assert len(tab._fig_contr.axes) == 1
        assert tab._fig_contr.axes[0].get_title() == tr("Who leads each contraction")
        assert tab._tbl_contr.rowCount() == 3

    def test_the_views_rotate_without_re_running_the_analysis(self, tab) -> None:
        self._llenar(tab)
        tab._sel_contr.set_vista("series")
        assert tab._stack_contr.currentIndex() == 0
        # The series alone: its axis and the MDF twinned on it, no relation.
        assert len(tab._fig_contr.axes) == 2
        assert tab._fig_contr.axes[0].get_xlabel() == tr("Contraction")
        tab._sel_contr.set_vista("table")
        assert tab._stack_contr.currentIndex() == 1
        tab._sel_contr.set_vista("relation")
        assert tab._stack_contr.currentIndex() == 0
        assert len(tab._fig_contr.axes) == 1

    def test_the_choice_is_kept_for_the_next_session(self, tab, qapp) -> None:
        from emgteach.gui.tabs.analysis import AnalysisTab
        from emgteach.gui.widgets.logger import LoggerWidget

        tab._sel_contr.set_vista("series")
        tab._sel_coact.set_vista("table")
        otra = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "charts"))
        try:
            assert otra._sel_contr.vista() == "series"
            assert otra._sel_coact.vista() == "table"
            assert otra._stack_coact.currentIndex() == 1
        finally:
            otra.deleteLater()

    def test_the_band_stays_low(self, tab) -> None:
        """The band under the panels is paid for out of the panels' height:
        its height is fixed, and nothing inside it — not a long table's size
        hint — can push it taller."""
        from emgteach.gui.tabs.analysis import _ALTO_BANDA

        assert tab._banda.height() == tab._banda.minimumHeight() == _ALTO_BANDA
        assert tab._banda.maximumHeight() == _ALTO_BANDA
        for caja in (tab._box_coact, tab._box_contr, tab._grp_resumen):
            assert caja.parent() is tab._banda
        # And the view switches live on the title line, not on a row of their own.
        for sel, box in ((tab._sel_contr, tab._box_contr), (tab._sel_coact, tab._box_coact)):
            assert sel.parent() is box
            assert sel.y() == 0

    def test_the_recording_decides_which_views_are_offered(self, tab) -> None:
        """Two muscles for the categories and the dominance, load markers
        for the load; a plain single-muscle recording gets the three."""
        self._llenar(tab)
        assert tab._sel_contr.visibles() == [
            "relation", "category", "dominance", "series", "table"]
        tab._refresh_contractions({"contractions": _rows(False), "channel_name": "FCR"})
        assert tab._sel_contr.visibles() == ["relation", "series", "table"]
        tab._refresh_contractions({
            "contractions": _rows(False), "channel_name": "FCR",
            "fv_loads": [(0.5, 2.0), (4.5, 3.0)],
        })
        assert tab._sel_contr.visibles() == ["relation", "series", "load", "table"]

    def test_a_view_the_next_recording_lacks_falls_back_to_the_relation(self, tab) -> None:
        self._llenar(tab)
        tab._sel_contr.set_vista("dominance")
        tab._refresh_contractions({"contractions": _rows(False), "channel_name": "FCR"})
        assert tab._sel_contr.vista() == "relation"
        assert tab._stack_contr.currentIndex() == 0

    def test_each_chart_fills_its_box(self, tab) -> None:
        """Capped low and pushed up by a trailing stretch, both charts sat in
        the top two thirds of their box with a strip of empty box beneath."""
        for caja in (tab._box_coact, tab._box_contr):
            lay = caja.layout()
            # A caption and the stack, and the stack takes what is left.
            assert lay.count() == 2
            assert lay.stretch(1) == 1

    def test_a_long_series_scrolls_instead_of_shrinking(self, tab) -> None:
        """Thirty contractions on the dominance bars, or a dozen windows of
        co-activation, ask the canvas for more than the box: the box then
        scrolls under the wheel, as the table beside it does."""
        from PySide6.QtWidgets import QScrollArea

        # The canvases sit in scroll areas, and pass the wheel on to them.
        assert isinstance(tab._stack_contr.widget(0), QScrollArea)
        assert isinstance(tab._stack_coact.widget(0), QScrollArea)
        muchas = [
            Contraction(n=k, start_s=float(k), end_s=k + 0.8, muscle="FCR" if k % 2 else "ECR",
                        rms_mv=0.2, peak_pct=50.0, mdf_hz=90.0, channel=1 if k % 2 else 2,
                        rms_mv_other=0.02, peak_pct_other=4.0)
            for k in range(1, 31)
        ]
        tab._refresh_contractions({"contractions": muchas, "channel_name": "FCR",
                                   "channel_name_2": "ECR"})
        tab._sel_contr.set_vista("dominance")
        alto_30 = tab._canvas_contr.minimumHeight()
        tab._sel_contr.set_vista("series")
        ancho_30 = tab._canvas_contr.minimumWidth()
        tab._sel_contr.set_vista("relation")
        assert tab._canvas_contr.minimumHeight() == tab._canvas_contr.minimumWidth() == 0
        self._llenar(tab)
        tab._sel_contr.set_vista("dominance")
        assert alto_30 > tab._canvas_contr.minimumHeight()
        tab._sel_contr.set_vista("series")
        assert ancho_30 > tab._canvas_contr.minimumWidth()
        ventanas = [
            CoactivationResult(index=None, mean_1=40.0, mean_2=2.0, window_s=(2.0 * k, 2.0 * k + 1),
                               label=f"w{k}", reason="x")
            for k in range(12)
        ]
        tab._selected_segments = [(1.0, 2.0)]
        tab._refresh_coactivation({"channel_name": "FCR", "channel_name_2": "ECR",
                                   "coactivation": ventanas, "coactivation_from_markers": True})
        doce = tab._canvas_coact.minimumHeight()
        tab._refresh_coactivation({"channel_name": "FCR", "channel_name_2": "ECR",
                                   "coactivation": ventanas[:3], "coactivation_from_markers": True})
        assert doce > tab._canvas_coact.minimumHeight()

    def test_the_summary_says_calibration_over_its_repetitions(self, tab) -> None:
        from emgteach.phases import FROM_REPS

        tab._actualizar_procedencia_cvm({
            "mvc_ref": 0.834, "mvc_ref_source": FROM_REPS,
            "cal_reps": {0: [1.0, 1.1, 1.2, 1.0, 1.1, 1.2]},
        })
        lineas = tab._lbl_cvm.text().split("\n")
        assert lineas == ["0.834 mV", tr("calibration"), tr("({n} repetitions)").format(n=6)]

    def test_the_long_summary_values_wrap(self, tab) -> None:
        """The fatigue verdict and where the MVC came from are sentences.
        On one line they set the width of the whole panel."""
        for lbl in (tab._lbl_fatiga, tab._lbl_cvm, tab._lbl_pico):
            assert lbl.wordWrap()

    def test_the_co_activation_box_has_chart_and_table(self, tab) -> None:
        assert tab._sel_coact.claves() == ["chart", "table"]
        tab._sel_coact.set_vista("table")
        assert tab._stack_coact.currentIndex() == 1
        tab._sel_coact.set_vista("chart")
        assert tab._stack_coact.currentIndex() == 0
