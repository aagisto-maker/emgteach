"""Panel 1: the raw trace of each muscle, one vertical axis each, in its colour.

Two muscles in millivolts on one axis invite the comparison of heights that
surface EMG cannot support — the amplitude depends on the skin and fat between
muscle and electrode — so in the pair each trace gets its own axis, painted in
the muscle's colour and named after it, as the EMG and the accelerometer are in
panels 10 and 12. What must never happen is an axis in one colour over a trace
in the other: the reading of the whole tab rests on the colours.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest
from matplotlib.colors import to_hex
from matplotlib.figure import Figure

from emgteach.charts import COLOUR_1, COLOUR_2
from emgteach.figures import draw_raw_panel

SRC = Path(__file__).resolve().parents[1] / "src" / "emgteach"


def _result(two: bool = True) -> dict:
    """Two muscles of very different size, as an agonist and an antagonist."""
    fs = 1000
    t = np.arange(4 * fs) / fs
    rng = np.random.default_rng(3)
    r = {"times": t, "emg_raw": rng.normal(0.0, 0.5, t.size),
         "channel_name": "FCR"}
    if two:
        r["emg_raw_2"] = rng.normal(0.0, 0.05, t.size)
        r["channel_name_2"] = "ECR"
    return r


def _hex(colour) -> str:
    return to_hex(colour).lower()


def _panel(two: bool = True):
    fig = Figure()
    ax = fig.subplots()
    twin = draw_raw_panel(ax, _result(two))
    return fig, ax, twin


def test_two_muscles_get_an_axis_each() -> None:
    fig, _ax, twin = _panel()
    assert twin is not None
    assert len(fig.axes) == 2


def test_each_axis_wears_the_colour_and_the_name_of_its_trace() -> None:
    _fig, ax, twin = _panel()
    for axis, colour, name in ((ax, COLOUR_1, "FCR"), (twin, COLOUR_2, "ECR")):
        (line,) = axis.get_lines()
        assert _hex(line.get_color()) == _hex(colour)
        assert _hex(axis.yaxis.label.get_color()) == _hex(colour)
        assert name in axis.get_ylabel()
        for tick in axis.yaxis.get_major_ticks():
            assert _hex(tick.label1.get_color()) == _hex(colour)
            assert _hex(tick.label2.get_color()) == _hex(colour)


def test_the_two_zero_lines_are_one() -> None:
    """Both axes symmetric about zero: the rest of each muscle sits at the
    same height, whatever their sizes."""
    _fig, ax, twin = _panel()
    for axis in (ax, twin):
        lo, hi = axis.get_ylim()
        assert lo == pytest.approx(-hi)
        assert hi > 0


def test_one_muscle_is_one_axis_as_before() -> None:
    fig, ax, twin = _panel(two=False)
    assert twin is None
    assert len(fig.axes) == 1
    (line,) = ax.get_lines()
    assert _hex(line.get_color()) == "#333333"


def test_the_report_draws_panel_one_as_the_screen_does() -> None:
    from emgteach.reports import _draw_analysis_panel

    fig = Figure()
    ax = fig.subplots()
    _draw_analysis_panel(fig, ax, 0, _result())
    assert len(fig.axes) == 2
    assert ax.get_title().startswith("1. ")


def test_the_muscle_colours_are_never_typed() -> None:
    """Imported from charts.py wherever something is drawn: a colour
    convention copied by hand drifts. (A stylesheet accent that happens to
    share the blue is not a muscle, and is not a bare literal.)"""
    literal = re.compile(r"""["']#(?:4169e1|d62728)["']""", re.IGNORECASE)
    for rel in ("figures.py", "reports.py", "gui/tabs/analysis.py",
                "gui/tabs/acquisition.py"):
        found = literal.findall((SRC / rel).read_text(encoding="utf-8"))
        assert not found, (rel, found)


def test_the_panels_are_numbered_one_to_twelve() -> None:
    """No letters, no gaps: the second raw trace no longer takes a number."""
    from emgteach.gui.tabs.analysis import _PANEL_LAYOUT

    assert [num for _pid, num in _PANEL_LAYOUT] == [str(n) for n in range(1, 13)]


# ── on screen ───────────────────────────────────────────────────────────


def _pair_edf(path: Path, fs: int = 1000, secs: int = 8) -> str:
    from emgteach.io import BufferedEdfWriter, ChannelInfo

    n = fs * secs
    t = np.arange(n) / fs
    rng = np.random.default_rng(11)
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
def test_in_the_pair_panel_one_draws_both_and_zooms_both(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    from PySide6.QtCore import QElapsedTimer, QSettings
    from PySide6.QtWidgets import QMessageBox

    from emgteach.gui.tabs.analysis import AnalysisTab
    from emgteach.gui.widgets.logger import LoggerWidget
    from emgteach.modes import MODE_PAIR

    monkeypatch.setattr(
        QMessageBox, "exec", lambda self: QMessageBox.StandardButton.NoButton
    )
    tab = AnalysisTab(LoggerWidget(), QSettings("emgteach-test", "panel-bruto"))
    tab.apply_mode(MODE_PAIR, False)
    tab.adopt_recording(_pair_edf(tmp_path / "par.edf"))
    tab._combo_canal.setCurrentIndex(tab._combo_canal.findText("Biceps"))
    tab._chk_compare2.setChecked(True)
    tab._combo_canal2.setCurrentIndex(tab._combo_canal2.findText("Triceps"))

    done: list = []
    original = tab._on_result
    tab._on_result = lambda r: (original(r), done.append(r))
    tab._iniciar_analisis()
    timer = QElapsedTimer()
    timer.start()
    while not done and timer.elapsed() < 30000:
        qapp.processEvents()
    assert done, "the analysis worker produced no result"

    # Panel 1 comes first in display order and is ticked by default.
    ax = tab._axes_list[0]
    twin = tab._y_twins[0]
    assert "Biceps" in ax.get_ylabel()
    assert "Triceps" in twin.get_ylabel()
    assert ax.get_title().startswith("1. ")

    before = [ax.get_ylim(), twin.get_ylim()]
    tab._y_zoom(0, ax, True)
    for (lo0, hi0), axis in zip(before, (ax, twin), strict=True):
        lo1, hi1 = axis.get_ylim()
        assert lo1 == pytest.approx(lo0 / 1.5)
        assert hi1 == pytest.approx(hi0 / 1.5)
