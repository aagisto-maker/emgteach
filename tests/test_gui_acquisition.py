"""GUI test for the acquisition tab's live muscle-load monitor.

Marked ``gui`` (needs a QApplication). It drives the load monitor directly by
feeding synthetic ``data_ready`` blocks, without a real device.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

pytestmark = pytest.mark.gui


def _block(env_mv: float, n: int = 1000) -> dict:
    z = np.zeros(n)
    return {"raw_mv": [z], "filtered": [z], "envelope": [np.full(n, env_mv)]}


class _FakeWorker:
    def isRunning(self) -> bool:
        return True

    def stop_forced(self) -> None:
        pass

    def wait(self, ms: int = 0) -> bool:
        return True


def test_live_load_calibration_and_zones(qapp) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    tab = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "acq"))
    tab._n_channels = 1
    tab._apply_channel_visibility()
    tab._worker = _FakeWorker()

    # Calibrate with a few seconds of "maximum contraction" (0.5 mV envelope).
    tab._on_calibrar()
    assert tab._calibrating
    for _ in range(math.ceil(tab._calib_target / 1000)):
        tab._on_data_ready(_block(0.5))
    assert not tab._calibrating
    assert tab._mvc_ref[0] == pytest.approx(0.5, abs=1e-6)

    # Moderate load (0.25 mV -> 50 % MVC): warning zone (>= 40 %).
    for _ in range(3):
        tab._on_data_ready(_block(0.25))
    assert 40.0 <= tab._load_bars[0]._value <= 60.0
    assert tab._online[0].status == "warning"

    # Heavy load (0.40 mV -> 80 % MVC): danger zone (>= 70 %).
    for _ in range(3):
        tab._on_data_ready(_block(0.40))
    assert tab._online[0].status == "danger"

    # Stopping the monitor greys the bar out.
    tab._stop_load_monitor()
    assert tab._load_bars[0]._active is False
    tab.cleanup()


def test_load_thresholds_adjustable_after_calibration(qapp) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "acq-thr")
    settings.clear()
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab._n_channels = 1
    tab._apply_channel_visibility()
    tab._worker = _FakeWorker()

    # The threshold spin-boxes are disabled until an MVC is calibrated.
    assert not tab._spin_warning.isEnabled()
    assert not tab._spin_danger.isEnabled()

    tab._on_calibrar()
    for _ in range(math.ceil(tab._calib_target / 1000)):
        tab._on_data_ready(_block(0.5))
    assert tab._spin_warning.isEnabled()
    assert tab._spin_danger.isEnabled()

    # Lower the thresholds: warning 20 %, danger 40 %.
    tab._spin_warning.setValue(20)
    tab._spin_danger.setValue(40)
    assert tab._online[0].warning_limit == 20.0
    assert tab._online[0].danger_limit == 40.0
    assert tab._load_bars[0]._warning == 20.0
    assert tab._load_bars[0]._danger == 40.0
    # Persisted across sessions.
    assert float(settings.value("adquisicion/load_danger")) == 40.0

    # 0.25 mV -> 50 % MVC now lands in the danger zone (>= 40 %).
    for _ in range(3):
        tab._on_data_ready(_block(0.25))
    assert tab._online[0].status == "danger"

    # warning < danger is enforced.
    tab._spin_warning.setValue(80)
    assert tab._spin_danger.value() > tab._spin_warning.value()

    settings.clear()
    tab.cleanup()


def test_reset_clears_acquisition_view(qapp) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "acq-reset")
    settings.clear()
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab._n_channels = 1
    tab._apply_channel_visibility()
    tab._worker = _FakeWorker()

    tab._on_calibrar()
    for _ in range(math.ceil(tab._calib_target / 1000)):
        tab._on_data_ready(_block(0.5))
    tab._marker_events.append((1.0, "x"))
    assert tab._mvc_ref[0] is not None

    # reset() is a no-op while recording…
    assert tab.is_recording()
    tab.reset()
    assert tab._mvc_ref[0] is not None

    # …and clears everything once stopped.
    tab._worker = None
    tab.reset()
    assert tab._mvc_ref[0] is None
    assert tab._marker_events == []
    assert tab._total_samples == 0
    assert not tab._spin_warning.isEnabled()
    tab.cleanup()
