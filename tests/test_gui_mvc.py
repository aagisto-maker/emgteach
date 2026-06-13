"""GUI regression tests for the MVC tab.

Marked ``gui`` because they build real widgets, so they need a
``QApplication`` (provided by the shared ``qapp`` fixture) and run on a
headless runner thanks to the offscreen Qt platform set in ``conftest.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QElapsedTimer

from emgteach.io import BufferedEdfWriter, ChannelInfo

pytestmark = pytest.mark.gui


def _make_edf(path: Path, fs: int = 1000, secs: int = 12) -> str:
    n = fs * secs
    t = np.arange(n) / fs
    emg = 0.2 * np.sin(2 * np.pi * 80 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.3 * t))
    ch = ChannelInfo("EMG", dimension="mV", sample_frequency=fs)
    with BufferedEdfWriter(str(path), channels=[ch]) as writer:
        writer.add_samples(emg.reshape(-1, 1).astype(float))
    return str(path)


def test_compute_does_not_hang_and_fills_load_panel(qapp, tmp_path: Path) -> None:
    """Computing the MVC must start the worker (no stale-attribute crash in
    ``_iniciar_calculo``) and the worker -> ``_on_result`` path must hide the
    progress bar and fill the muscle-load data panel.

    Regression for the bug where ``_iniciar_calculo`` still referenced the
    removed summary labels, so the click raised before the worker started and
    the progress bar span forever ("se queda pensando").
    """
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.mvc import MvcTab
    from emgteach.gui.widgets.logger import LoggerWidget

    edf = _make_edf(tmp_path / "test.edf")
    tab = MvcTab(LoggerWidget(), QSettings("emgteach-test", "mvc"))
    tab._edit_path.setText(edf)
    tab._populate_channels(edf)

    done: list = []
    orig = tab._on_result
    tab._on_result = lambda r: (orig(r), done.append(r))

    tab._iniciar_calculo()  # must not raise

    timer = QElapsedTimer()
    timer.start()
    while not done and timer.elapsed() < 20000:
        qapp.processEvents()

    assert done, "MvcWorker did not produce a result"
    assert not tab._progress.isVisible()        # not stuck 'thinking'
    assert len(tab._axes_list) == 3             # three time-series panels
    assert tab._d_static.text() != "—"          # load data panel filled
    assert "apdf" in tab._last_result
    tab.cleanup()
