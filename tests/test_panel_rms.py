"""Panel 6: the RMS of each window; in the pair, each muscle against its own axis.

RMS is in millivolts, and two muscles' millivolts do not share a yardstick —
the same reason panel 1 gives each raw trace an axis of its own. With one
muscle the panel is what it was.
"""

from __future__ import annotations

import numpy as np
from matplotlib.colors import to_hex
from matplotlib.figure import Figure

from emgteach.charts import COLOUR_1, COLOUR_2
from emgteach.figures import draw_rms_panel


def _result(two: bool = True) -> dict:
    t = np.arange(0.5, 20.0, 1.0)
    r = {"times": np.arange(0.0, 20.0, 0.001), "t_seg": t,
         "rms_seg": 0.30 + 0.01 * t, "channel_name": "FCR"}
    if two:
        r["t_seg_2"] = t
        r["rms_seg_2"] = 0.03 + 0.002 * t
        r["channel_name_2"] = "ECR"
    return r


def _hex(colour) -> str:
    return to_hex(colour).lower()


def test_two_muscles_get_an_axis_each_in_their_colours() -> None:
    fig = Figure()
    ax = fig.subplots()
    twin = draw_rms_panel(ax, _result())
    assert twin is not None
    assert len(fig.axes) == 2
    for axis, colour, name in ((ax, COLOUR_1, "FCR"), (twin, COLOUR_2, "ECR")):
        (line,) = axis.get_lines()
        assert _hex(line.get_color()) == _hex(colour)
        assert _hex(axis.yaxis.label.get_color()) == _hex(colour)
        assert name in axis.get_ylabel()
        for tick in axis.yaxis.get_major_ticks():
            assert _hex(tick.label2.get_color()) == _hex(colour)


def test_both_axes_start_at_zero() -> None:
    """The two floors are one, so neither muscle looks at rest by scale."""
    fig = Figure()
    ax = fig.subplots()
    twin = draw_rms_panel(ax, _result())
    for axis in (ax, twin):
        lo, hi = axis.get_ylim()
        assert lo == 0.0
        assert hi > 0.0


def test_one_muscle_is_drawn_as_before() -> None:
    fig = Figure()
    ax = fig.subplots()
    assert draw_rms_panel(ax, _result(two=False)) is None
    assert len(fig.axes) == 1
    (line,) = ax.get_lines()
    assert _hex(line.get_color()) == "#2ca02c"
    assert ax.get_ylabel() == "RMS (mV)"


def test_the_report_draws_panel_six_as_the_screen_does() -> None:
    from emgteach.reports import _draw_analysis_panel

    fig = Figure()
    ax = fig.subplots()
    _draw_analysis_panel(fig, ax, 5, _result())
    assert len(fig.axes) == 2
