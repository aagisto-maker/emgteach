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
