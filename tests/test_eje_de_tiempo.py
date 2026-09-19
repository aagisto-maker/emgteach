"""The live time axis is the recording's clock, not the window's.

The plots drew ``np.arange(n) / FS``: seconds counted from the left edge of
the visible window. A recording two minutes long read 0…5 s for as long as it
lasted, the numbers never moved, and nothing on screen said when anything had
happened — or told a live screen from a stopped one.

The tab already kept the absolute count, and already used it to place the
marker lines inside the window. Now the axis carries it, and the marks are
drawn at the second they happened.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from emgteach.gui.tabs.acquisition import FS, AcquisitionTab
from emgteach.gui.widgets.logger import LoggerWidget


@pytest.fixture
def tab(qapp):
    widget = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "eje-tiempo"))
    widget._n_channels = 1
    yield widget
    widget._watchdog_timer.stop()
    widget._mvc_timer.stop()
    widget._prep_timer.stop()
    widget._load_timer.stop()
    widget.close()


def _llenar(tab: AcquisitionTab, segundos: float, desde: float = 0.0) -> None:
    """Feed the ring buffers as the worker's blocks do."""
    n = int(segundos * FS)
    muestras = np.zeros(n, dtype=float)
    tab._buf_raw[0].extend(muestras)
    tab._buf_env[0].extend(muestras)
    tab._total_samples = int((desde + segundos) * FS)
    tab._n_visible = min(n, tab._n_visible)
    tab._new_data = True


class TestTheAxisAdvances:
    def test_the_window_carries_the_seconds_of_the_recording(self, tab) -> None:
        _llenar(tab, 5.0)
        tab._refresh_plots()
        x_inicio = tab._curves_raw[0].getData()[0]
        assert x_inicio[0] == pytest.approx(0.0, abs=1e-6)
        assert x_inicio[-1] == pytest.approx(5.0 - 1.0 / FS, abs=1e-6)

        # Two minutes in, the same window shows where it is in the recording.
        tab._total_samples = int(125.0 * FS)
        tab._refresh_plots(force=True)
        x_tarde = tab._curves_raw[0].getData()[0]
        assert x_tarde[0] == pytest.approx(120.0, abs=1e-6)
        assert x_tarde[-1] == pytest.approx(125.0 - 1.0 / FS, abs=1e-6)
        assert len(x_tarde) == len(x_inicio)      # the window itself is the same

    def test_a_marker_is_drawn_at_the_second_it_happened(self, tab) -> None:
        _llenar(tab, 5.0)
        tab._total_samples = int(100.0 * FS)
        tab._marker_events.append((97.5, "presa"))
        tab._refresh_plots(force=True)
        visibles = [ln.value() for pool in tab._marker_lines for ln in pool if ln.isVisible()]
        assert visibles and visibles[0] == pytest.approx(97.5, abs=1e-6)

    def test_a_marker_out_of_the_window_is_not_drawn(self, tab) -> None:
        _llenar(tab, 5.0)
        tab._total_samples = int(100.0 * FS)
        tab._marker_events.append((10.0, "vieja"))
        tab._refresh_plots(force=True)
        assert not [ln for pool in tab._marker_lines for ln in pool if ln.isVisible()]

    def test_with_nothing_acquired_the_axis_starts_at_zero(self, tab) -> None:
        """The empty tab keeps 0…window: there is nothing to place in time."""
        tab._total_samples = 0
        tab._refresh_plots(force=True)
        x = tab._curves_raw[0].getData()[0]
        assert x is None or len(x) == 0
        rango = tab._plot_raw.getViewBox().viewRange()[0]
        assert rango[0] == pytest.approx(0.0, abs=0.01)

    def test_the_axes_say_the_unit(self, tab) -> None:
        for plot in (tab._plot_raw, tab._plot_env, tab._plot_acc):
            assert "s" in plot.getAxis("bottom").labelText, plot.windowTitle()
