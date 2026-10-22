"""After a wheel zoom the live view keeps following the signal.

The live plots have no X range of their own: pyqtgraph's auto-range follows
the sliding window for them. A wheel zoom turns that auto-range off, and
until 3.9.0 the axis then stayed where it was while the signal ran out of
sight to the right; the «A» button brought it back. Now the width the wheel
chose is kept and the window slides with the last sample; «A» gives the
whole window back.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from emgteach.gui.tabs.acquisition import FS, MAX_POINTS
from tests.test_marcas_manuales import _until, recording, tab  # noqa: F401


def _wheel(plot, steps: int = 1) -> None:
    """A wheel notch towards the user (zoom in) at the plot's centre."""
    viewport = plot.viewport()
    centre = viewport.rect().center()
    for _ in range(steps):
        wheel = QWheelEvent(QPointF(centre), QPointF(viewport.mapToGlobal(centre)),
                            QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase,
                            False)
        QApplication.sendEvent(viewport, wheel)
    QApplication.instance().processEvents()


def _last_second(acq) -> float:
    return (acq._total_samples - 1) / FS


def _x_range(plot) -> tuple[float, float]:
    x0, x1 = plot.getViewBox().viewRange()[0]
    return float(x0), float(x1)


@pytest.fixture
def live(qapp, request):
    """The tab recording the simulated board, with a second of signal drawn."""
    acq = request.getfixturevalue("recording")
    _until(qapp, lambda: acq._total_samples > FS, 5.0, "a second of signal")
    _until(qapp, lambda: _x_range(acq._plot_raw)[1] > 0.5, 5.0, "the plot to follow")
    return acq


@pytest.mark.gui
def test_the_zoomed_live_view_keeps_the_width_and_follows_the_signal(qapp, live) -> None:
    plot = live._plot_raw
    _wheel(plot, steps=3)
    assert not plot.getViewBox().autoRangeEnabled()[0], "the wheel left auto-range on"
    x0, x1 = _x_range(plot)
    width = x1 - x0
    assert 0 < width < 0.9 * min(live._n_visible, MAX_POINTS) / FS, "the wheel did not zoom in"

    # A second later the window has moved on with the signal…
    then = _last_second(live)
    _until(qapp, lambda: _last_second(live) > then + 1.0, 5.0, "a second more of signal")
    _until(qapp, lambda: _x_range(plot)[1] > then + 0.9, 5.0,
           "the zoomed view to follow the signal")
    x0, x1 = _x_range(plot)
    # …its right edge is the last sample, within a block…
    assert abs(x1 - _last_second(live)) < 0.2, (x1, _last_second(live))
    # …and the width the wheel chose is kept.
    assert abs((x1 - x0) - width) < 0.02 * width, (x1 - x0, width)
    assert not plot.getViewBox().autoRangeEnabled()[0]


@pytest.mark.gui
def test_the_envelope_follows_too(qapp, live) -> None:
    plot = live._plot_env
    _wheel(plot, steps=2)
    x0, x1 = _x_range(plot)
    width = x1 - x0
    then = _last_second(live)
    _until(qapp, lambda: _x_range(plot)[1] > then + 0.5, 5.0, "the envelope to follow")
    x0, x1 = _x_range(plot)
    assert abs(x1 - _last_second(live)) < 0.2
    assert abs((x1 - x0) - width) < 0.02 * width


@pytest.mark.gui
def test_the_a_button_gives_the_whole_window_back(qapp, live) -> None:
    plot = live._plot_raw
    _wheel(plot, steps=3)
    x0, x1 = _x_range(plot)
    window = min(live._n_visible, MAX_POINTS) / FS
    assert x1 - x0 < 0.9 * window
    # What the «A» button in the plot's corner does.
    plot.getPlotItem().autoBtnClicked()
    assert plot.getViewBox().autoRangeEnabled()[0]
    _until(qapp, lambda: _x_range(plot)[1] - _x_range(plot)[0] > 0.9 * window, 5.0,
           "the whole window back")
    x0, x1 = _x_range(plot)
    assert abs(x1 - _last_second(live)) < 0.2
