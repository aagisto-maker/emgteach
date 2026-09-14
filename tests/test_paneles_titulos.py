"""Every panel says what it is, whose it is and how to read it.

A panel that has to be explained aloud is badly drawn. Each title carries its
number, its name, the muscle when it shows only one, and on a second line its
reading — what it means that the curve rises or falls. The titles come from
one table, ``emgteach.panels``, on screen and in the report alike.

Panel 8 is a path through time, not a fitted function; and choosing another
muscle re-runs the analysis, so no panel goes on showing the previous one.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from matplotlib.figure import Figure
from matplotlib.text import Annotation

from emgteach import i18n
from emgteach.panels import BY_PID, OVERLAY_READING_MV, PANELS, panel_title


def _one() -> dict:
    return {"channel_name": "FCR"}


def _two() -> dict:
    return {"channel_name": "FCR", "channel_name_2": "ECR", "emg_raw_2": [0.0],
            "psd_2": [0.0], "rms_seg_2": [0.0], "mdf_seg_2": [0.0]}


def test_the_numbers_run_from_one_to_twelve() -> None:
    assert sorted(p.number for p in PANELS) == list(range(1, 13))
    assert len(BY_PID) == len(PANELS)


def test_the_numbers_are_the_tabs() -> None:
    from emgteach.gui.tabs.analysis import _PANEL_LAYOUT

    assert {pid: str(BY_PID[pid].number) for pid, _ in _PANEL_LAYOUT} == dict(
        _PANEL_LAYOUT
    )


def test_every_title_carries_its_number_and_a_reading() -> None:
    for p in PANELS:
        head, reading = panel_title(p.pid, _one()).split("\n")
        assert head.startswith(f"{p.number}. "), head
        assert reading.startswith("(") and reading.endswith(")"), reading
        assert len(reading) > 20, reading


def test_a_panel_of_one_muscle_names_it() -> None:
    for p in PANELS:
        head = panel_title(p.pid, _one()).split("\n")[0]
        assert ("FCR" in head) == p.per_muscle, head


def test_with_two_muscles_the_names_go_on_the_axes() -> None:
    """Panels that draw both muscles name them on their axes or legend."""
    for p in PANELS:
        if p.two_key:
            head = panel_title(p.pid, _two()).split("\n")[0]
            assert "FCR" not in head and "ECR" not in head, head


def test_no_other_title_says_agonist() -> None:
    """Panel 9 is found by that word, here and in the tests of its units."""
    for p in PANELS:
        if p.pid != 8:
            assert "agonist" not in panel_title(p.pid, _one()).lower()


def test_every_word_of_the_table_is_translated() -> None:
    """The table reaches tr() as data, which the scan of literals cannot see."""
    texts = [s for p in PANELS for s in (p.name, p.reading, p.reading_two) if s]
    texts.append(OVERLAY_READING_MV)
    missing = [s for s in texts if s not in i18n._ES]
    assert not missing, missing


def test_panel_nine_says_its_unit_and_its_reading() -> None:
    from emgteach.mvc import overlay_curves

    base = {"emg_envelope": np.ones(5), "emg_envelope_2": np.ones(5),
            "channel_name": "FCR", "channel_name_2": "ECR"}
    pct, _ = overlay_curves({**base, "mvc_ref": 1.0, "mvc_ref_2": 1.0})
    mv, _ = overlay_curves(base)
    assert pct.title.startswith("9. ")
    assert "% MVC" in pct.title
    assert mv.title.startswith("9. ")
    assert "% MVC" not in mv.title
    assert i18n.tr(OVERLAY_READING_MV) in mv.title


# ── panel 8: a path through time ────────────────────────────────────────


def _windows() -> dict:
    t = np.arange(0.5, 12.0, 1.0)
    active = np.ones(t.size, dtype=bool)
    active[:3] = False
    return {"t_seg": t, "mdf_seg": np.linspace(110.0, 80.0, t.size),
            "rms_seg": np.linspace(0.10, 0.30, t.size), "fat_active": active,
            "channel_name": "FCR",
            "rms_mdf_range": np.linspace(80.0, 110.0, 50),
            "rms_mdf_fitted": np.linspace(0.10, 0.30, 50)}


def _panel_eight(r: dict):
    from emgteach.figures import draw_amplitude_frequency_panel

    fig = Figure()
    ax = fig.subplots()
    draw_amplitude_frequency_panel(ax, r)
    return ax


def test_panel_eight_joins_the_working_windows_in_time_order() -> None:
    """A resting window's median frequency is the amplifier's: the path is
    drawn over the windows the fatigue trend is fitted on."""
    r = _windows()
    ax = _panel_eight(r)
    (line,) = ax.get_lines()
    assert np.array_equal(np.asarray(line.get_xdata()), r["mdf_seg"][r["fat_active"]])
    assert np.array_equal(np.asarray(line.get_ydata()), r["rms_seg"][r["fat_active"]])


def test_panel_eight_ends_in_an_arrow() -> None:
    r = _windows()
    ax = _panel_eight(r)
    arrows = [c for c in ax.get_children()
              if isinstance(c, Annotation) and c.arrow_patch is not None]
    assert len(arrows) == 1
    x_end = r["mdf_seg"][r["fat_active"]][-1]
    y_end = r["rms_seg"][r["fat_active"]][-1]
    assert arrows[0].xy == pytest.approx((x_end, y_end))


def test_panel_eight_draws_no_fitted_curve() -> None:
    """The fit read as panel 7's time trend, and time is on no axis here."""
    ax = _panel_eight(_windows())
    assert len(ax.get_lines()) == 1


def test_panel_eight_without_the_mask_draws_every_window() -> None:
    r = _windows()
    del r["fat_active"]
    (line,) = _panel_eight(r).get_lines()
    assert len(line.get_xdata()) == len(r["t_seg"])


# ── another muscle, analysed at once ────────────────────────────────────


def _two_muscles(path: Path, fs: int = 1000, secs: int = 8) -> str:
    from emgteach.io import BufferedEdfWriter, ChannelInfo

    n = fs * secs
    t = np.arange(n) / fs
    rng = np.random.default_rng(5)
    quiet = (t >= 1.5).astype(float)
    burst = (np.sin(2 * np.pi * 0.25 * (t - 1.5)) ** 2) * quiet
    chans = [
        ChannelInfo("Biceps", dimension="mV", sample_frequency=fs),
        ChannelInfo("Triceps", dimension="mV", sample_frequency=fs),
    ]
    a = rng.normal(0.0, 0.60, n) * burst
    b = rng.normal(0.0, 0.06, n) * (1.0 - burst) * quiet
    with BufferedEdfWriter(str(path), channels=chans) as w:
        for i in range(0, n, fs):
            w.add_samples(a[i:i + fs], b[i:i + fs])
    return str(path)


@pytest.mark.gui
def test_choosing_another_muscle_reanalyses_it(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    """Left pending, the panels went on showing the previous muscle until
    Analyse was pressed, and none of them said whose it was."""
    from PySide6.QtCore import QElapsedTimer, QSettings
    from PySide6.QtWidgets import QMessageBox

    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.logger import LoggerWidget
    from emgteach.modes import MODE_SINGLE

    monkeypatch.setattr(
        QMessageBox, "exec", lambda self: QMessageBox.StandardButton.NoButton
    )
    tab = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "canal-elegido"))
    tab.apply_mode(MODE_SINGLE, False)
    tab.adopt_recording(_two_muscles(tmp_path / "dos.edf"))

    def settle(until) -> bool:
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < 30000:
            qapp.processEvents()
            running = tab._worker is not None and tab._worker.isRunning()
            if not running and until():
                return True
        return False

    try:
        if not settle(lambda: tab._last_result is not None):
            tab._iniciar_analisis()
            assert settle(lambda: tab._last_result is not None)
        first = tab._last_result["channel_name"]
        other = "Triceps" if first == "Biceps" else "Biceps"
        idx = tab._combo_canal.findText(other)
        tab._combo_canal.setCurrentIndex(idx)
        tab._combo_canal.activated.emit(idx)
        assert settle(lambda: tab._last_result.get("channel_name") == other)
        assert any(other in ax.get_title() for ax in tab._fig.axes)
    finally:
        tab.cleanup()
