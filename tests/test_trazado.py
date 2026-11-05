"""The live plots as a piece of their own (step 3 of
docs/PLAN-partir-AcquisitionTab.md): `LivePlots` is built with the sampling
rate, the channels' colours, the profile's ranges, the channel count, the
accelerometer and a way to ask for the channels' names — and nothing else.
The tab feeds it blocks and events and calls its methods; what it has to
say goes out through ``logged``. The tab's side — when a recording starts,
stops or is reviewed — is covered by the tests that record
(tests/test_gui_acquisition.py, tests/test_gui_session_review.py and others).
"""

from __future__ import annotations

import numpy as np
import pytest

from emgteach.gui.acquisition.plots import MAX_POINTS, LivePlots
from emgteach.i18n import tr

pytestmark = pytest.mark.gui

_COLORES = [(65, 105, 225), (214, 39, 40)]
_HEX = ["#4169E1", "#D62728"]


@pytest.fixture
def trazado(qapp):
    nombres = {"lista": ["FCR"]}
    piece = LivePlots(
        fs=1000, colours=_COLORES, colour_hex=_HEX,
        ylim_raw=(-3.3, 3.3), ylim_envelope=(-0.05, 1.0),
        n_channels=1, acc_enabled=False, labels=lambda: list(nombres["lista"]),
    )
    piece.nombres = nombres
    piece.registro: list[str] = []
    piece.logged.connect(piece.registro.append)
    piece.update_legend()
    yield piece
    piece.stop_live()
    piece.close()
    piece.deleteLater()
    qapp.processEvents()


def _bloque(n_ch: int, valor: float, n: int = 100) -> tuple[list, list]:
    return ([np.full(n, valor) for _ in range(n_ch)],
            [np.full(n, abs(valor)) for _ in range(n_ch)])


def test_it_is_built_with_what_it_is_given(trazado) -> None:
    assert trazado.title() == tr("Real-time EMG signal")
    assert trazado.objectName() == "plotsBox"          # stays white
    assert len(trazado._curves_raw) == len(trazado._curves_env) == len(_COLORES)
    assert trazado.plot_widgets() == [trazado._plot_raw, trazado._plot_env, trazado._plot_acc]
    assert trazado._plot_acc.isHidden()                # no accelerometer
    assert trazado._n_visible == 5 * 1000              # five seconds on screen
    assert trazado._lbl_legend.isHidden()              # one channel: no key


def test_two_channels_get_a_key_and_two_lanes(trazado) -> None:
    trazado.nombres["lista"] = ["FCR", "ECR"]
    trazado.set_channels(2)
    trazado.update_legend()
    trazado.restack()
    assert not trazado._lbl_legend.isHidden()
    assert "FCR" in trazado._lbl_legend.text() and "ECR" in trazado._lbl_legend.text()
    assert trazado._curves_raw[1].isVisible() and trazado._curves_env[1].isVisible()
    lo, hi = trazado._plot_raw.getViewBox().viewRange()[1]
    assert (lo, hi) == pytest.approx((-6.6, 6.6))      # two lanes of ±3.3
    assert [t.toPlainText().strip() for t in trazado._lane_labels[0]] == ["FCR", "ECR"]
    # The names are asked for when drawn: renamed, the lanes say so.
    trazado.nombres["lista"] = ["FDS", "EDC"]
    trazado.restack()
    assert [t.toPlainText().strip() for t in trazado._lane_labels[0]] == ["FDS", "EDC"]


def test_blocks_fill_the_buffers_and_the_axis_counts_seconds(trazado) -> None:
    for _ in range(20):
        trazado.append(*_bloque(1, 0.5))
    assert trazado._total_samples == 2000 and trazado._new_data
    trazado.redraw()
    x, y = trazado._curves_raw[0].getData()
    assert x[-1] == pytest.approx(1.999) and y[-1] == pytest.approx(0.5)
    assert len(trazado._buf_raw[0]) == MAX_POINTS


def test_the_accelerometer_column_goes_to_its_own_buffer(trazado) -> None:
    trazado.set_acc_enabled(True)
    assert not trazado._plot_acc.isHidden() and not trazado._acc_sidebar_slot.isHidden()
    raw, env = _bloque(1, 0.2)
    raw.append(np.full(100, 0.9))                       # the trailing ACC column
    trazado.append(raw, env)
    assert list(trazado._buf_acc)[-1] == pytest.approx(0.9)
    assert list(trazado._buf_raw[0])[-1] == pytest.approx(0.2)
    trazado.set_acc_enabled(False)
    assert trazado._plot_acc.isHidden() and trazado._acc_sidebar_slot.isHidden()


def test_markers_are_drawn_where_they_happened_and_cleared(trazado) -> None:
    for _ in range(30):
        trazado.append(*_bloque(1, 0.1))
    trazado.add_marker(1.5, "Fatigue")
    trazado.redraw()
    visibles = [ln.value() for ln in trazado._marker_lines[0] if ln.isVisible()]
    assert visibles == [pytest.approx(1.5)]
    trazado.clear()
    assert trazado._marker_events == [] and trazado._total_samples == 0
    assert not any(ln.isVisible() for pool in trazado._marker_lines for ln in pool)
    assert set(trazado._buf_raw[0]) == {0.0}


def test_the_raw_plot_takes_the_device_s_own_full_scale(trazado) -> None:
    trazado.follow_device(0, recording=False)           # BITalino
    lo, hi = trazado._plot_raw.getViewBox().viewRange()[1]
    assert hi == pytest.approx(1.635282457879088) and lo == pytest.approx(-hi)
    # While recording the scale is noted, not imposed on the plot.
    trazado._plot_raw.setYRange(-9.0, 9.0, padding=0)
    trazado.follow_device(1, recording=True)            # Arduino
    assert trazado._y_ranges_init[0] == (-12.5, 12.5)
    assert trazado._plot_raw.getViewBox().viewRange()[1] == pytest.approx([-9.0, 9.0])


def test_a_calibration_scales_the_plots_never_below_the_profile(trazado) -> None:
    trazado.autoscale([0.8], [4.0])
    assert trazado._y_ranges_init[1] == pytest.approx((-0.06, 1.2))   # 0.8 times 1.5
    assert trazado._y_ranges_init[0] == pytest.approx((-5.0, 5.0))    # 4.0 times 1.25
    trazado.autoscale([0.1], [0.5])                     # a weak calibration
    assert trazado._y_ranges_init[1] == pytest.approx((-0.05, 1.0))   # the profile's
    assert trazado._y_ranges_init[0] == pytest.approx((-3.3, 3.3))


def test_a_review_that_cannot_be_read_is_said_and_changes_nothing(trazado, monkeypatch) -> None:
    """A file with no EMG channel is passed over without a word; one that lists
    its channels and then cannot be read says so, through ``logged``."""
    from emgteach.gui.acquisition import plots as mod

    monkeypatch.setattr(mod, "list_edf_emg_channels", lambda path: [])
    trazado.show_recording("vacio.edf", lambda span: "")
    assert trazado.registro == [] and not trazado._revisando

    def no_se_lee(path, channel):
        raise OSError("the stick was taken out")

    monkeypatch.setattr(mod, "list_edf_emg_channels", lambda path: ["FCR"])
    monkeypatch.setattr(mod, "read_edf_mne", no_se_lee)
    trazado.show_recording("roto.edf", lambda span: "")
    assert trazado.registro == [tr("The recording could not be shown for review: {err}")
                                .format(err="the stick was taken out")]
    assert not trazado._revisando and trazado._revision_items == []
    trazado.leave_review()
    assert trazado._plot_raw.plotItem.titleLabel.text == tr("Raw EMG signal (mV)")


def test_the_fine_controls_can_be_hidden(trazado) -> None:
    trazado.set_scale_controls_visible(False)
    assert trazado._sidebar.isHidden() and trazado._btn_reset_escala.isHidden()
    trazado.set_scale_controls_visible(True)
    assert not trazado._sidebar.isHidden() and not trazado._btn_reset_escala.isHidden()


def test_the_tab_lays_it_out_where_the_box_was(qapp) -> None:
    from tests.test_arreglos_pantalla import _cierra, _ventana

    win = _ventana(qapp, "single")
    try:
        adq = win._tab_adq
        assert isinstance(adq._trazado, LivePlots)
        assert adq._trazado.parentWidget() is adq
        # Last in the tab's column, taking the height that is left.
        raiz = adq.layout()
        assert raiz.itemAt(raiz.count() - 1).widget() is adq._trazado
        assert raiz.stretch(raiz.count() - 1) == 1
        # The practicals hide the fine controls.
        assert adq._trazado._sidebar.isHidden()
    finally:
        _cierra(qapp, win)
