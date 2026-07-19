"""GUI test for the acquisition tab's live muscle-load monitor.

Marked ``gui`` (needs a QApplication). It drives the load monitor directly by
feeding synthetic ``data_ready`` blocks, without a real device.
"""

from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.gui


def _block(env_mv: float, n: int = 1000) -> dict:
    z = np.zeros(n)
    return {"raw_mv": [z], "filtered": [z], "envelope": [np.full(n, env_mv)]}


class _FakeWorker:
    def __init__(self) -> None:
        self.markers: list[str] = []

    def isRunning(self) -> bool:
        return True

    def add_marker(self, label: str) -> None:
        self.markers.append(label)

    def stop_forced(self) -> None:
        pass

    def wait(self, ms: int = 0) -> bool:
        return True


def _drive_calibration(tab, env_mv: float = 0.5) -> None:
    """Run the guided MVC-calibration wizard to completion headlessly, by
    ticking its state machine and feeding envelope data during each
    contraction phase (the QTimer does not fire in the test event loop)."""
    tab._on_calibrar()
    for _ in range(5000):
        if not tab._mvc_active:
            break
        if tab._mvc_phase == "contract":
            tab._on_data_ready(_block(env_mv))
        tab._mvc_tick()


def test_mmg_placement_locks_to_single_channel(qapp) -> None:
    """ACC on the muscle (MMG) forces a single EMG channel; limb allows two."""
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "acc-lock")
    settings.clear()
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab._set_channel_controls_enabled(True)     # idle, BITalino by default
    tab._combo_n_channels.setCurrentIndex(1)    # 2 channels
    assert tab._combo_n_channels.isEnabled()

    tab._chk_acc.setChecked(True)
    tab._combo_acc_place.setCurrentIndex(0)     # "on the muscle (MMG)"
    assert tab._combo_n_channels.currentIndex() == 0      # forced to 1 channel
    assert not tab._combo_n_channels.isEnabled()          # and locked

    tab._combo_acc_place.setCurrentIndex(1)     # "on the moving segment"
    assert tab._combo_n_channels.isEnabled()              # two channels allowed

    tab._chk_acc.setChecked(False)              # ACC off restores the control
    assert tab._combo_n_channels.isEnabled()
    settings.clear()


def test_live_load_calibration_and_zones(qapp) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    tab = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "acq"))
    tab._n_channels = 1
    tab._apply_channel_visibility()
    tab._worker = _FakeWorker()

    # Run the guided MVC-calibration wizard to completion (0.5 mV envelope).
    _drive_calibration(tab, 0.5)
    assert not tab._mvc_active
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

    _drive_calibration(tab, 0.5)
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


def test_acc_plot_fixed_range_zoom_and_aligned_sidebar(qapp) -> None:
    """The ACC plot has a stable ±1 g range (no auto-range flicker); its ▲▼
    buttons magnify around the trace level; and its sidebar slot is shown/hidden
    with the plot so the raw/envelope buttons stay aligned with their plots."""
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "acq-acc-range")
    settings.clear()
    tab = AcquisitionTab(LoggerWidget(), settings)

    # The ACC sidebar slot tracks the ACC plot's visibility.
    tab._chk_acc.setChecked(True)
    assert tab._acc_sidebar_slot.isVisibleTo(tab)
    tab._chk_acc.setChecked(False)
    assert not tab._acc_sidebar_slot.isVisibleTo(tab)
    tab._chk_acc.setChecked(True)

    # Default range is the full ±1 g, and it does not change with the data
    # (no auto-range): a fresh recording resets it to ±1 g.
    tab._reset_buffers()
    lo, hi = tab._plot_acc.getViewBox().viewRange()[1]
    assert lo == pytest.approx(-1.0, abs=1e-6) and hi == pytest.approx(1.0, abs=1e-6)

    # Zoom in with ▲ magnifies (smaller visible span); zoom out returns toward ±1 g.
    tab._acc_zoom_step(zoom_in=True)
    assert tab._acc_zoom > 1.0
    lo2, hi2 = tab._plot_acc.getViewBox().viewRange()[1]
    assert (hi2 - lo2) < 2.0                     # narrower than the full ±1 g

    # Reset scales returns the ACC plot to ±1 g and zoom 1.
    tab._reset_y_scales()
    assert tab._acc_zoom == 1.0
    lo3, hi3 = tab._plot_acc.getViewBox().viewRange()[1]
    assert lo3 == pytest.approx(-1.0, abs=1e-6) and hi3 == pytest.approx(1.0, abs=1e-6)

    settings.clear()
    tab.cleanup()


def test_guided_force_velocity_marks_each_load(qapp) -> None:
    """The guided F-V wizard walks the load list and writes one EDF marker per
    load at the start of its recording window, with the load encoded."""
    from PySide6.QtCore import QSettings

    from emgteach.force_velocity import fv_load_marker, parse_fv_load_markers
    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "acq-fv")
    settings.clear()
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab._n_channels = 1
    tab._apply_channel_visibility()
    worker = _FakeWorker()
    tab._worker = worker

    loads = [2.0, 4.0, 6.0]
    tab._fv_start(loads, reps=2, prep_s=1.0, window_s=1.0)
    assert tab._fv_active
    assert tab._fv_phase == "mvc_ready"      # an MVC maximum comes first

    # Drive the state machine to completion (the QTimer does not tick in tests),
    # feeding the envelope during the MVC-maximum window so a reference is set.
    for _ in range(8000):
        if not tab._fv_active:
            break
        if tab._fv_phase == "mvc_contract":
            tab._on_data_ready(_block(0.5))
        tab._fv_tick()
    assert not tab._fv_active

    # The MVC maximum set a reference (no load marker for it).
    assert tab._mvc_ref[0] == pytest.approx(0.5, abs=1e-6)

    # One marker per contraction: reps x loads, each carrying its own load.
    fv_markers = parse_fv_load_markers([(0.0, m) for m in worker.markers])
    assert [kg for _onset, kg in fv_markers] == [2.0, 2.0, 4.0, 4.0, 6.0, 6.0]
    assert worker.markers == [fv_load_marker(kg) for kg in [2, 2, 4, 4, 6, 6]]
    tab.cleanup()


def test_guided_fv_button_enabled_when_connected_with_acc(qapp) -> None:
    """The guided F-V button is available once a BITalino is connected with the
    ACC on — before recording and for any placement — so the load dialog can
    always be reached (the wizard starts the recording itself)."""
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "acq-fvbtn")
    settings.clear()
    tab = AcquisitionTab(LoggerWidget(), settings)

    # Not connected yet -> disabled.
    tab._chk_acc.setChecked(True)
    tab._update_fv_button()
    assert not tab._btn_fv_guided.isEnabled()

    # Connected (BITalino) + ACC on -> enabled even while idle (not recording).
    tab._combo_device_type.setCurrentIndex(0)
    tab._btn_conectar.setChecked(True)
    tab._update_fv_button()
    assert tab._btn_fv_guided.isEnabled()

    # Enabled regardless of placement (muscle) — the dialog warns instead.
    tab._combo_acc_place.setCurrentIndex(0)   # muscle
    tab._update_fv_button()
    assert tab._btn_fv_guided.isEnabled()

    # ACC off -> disabled.
    tab._chk_acc.setChecked(False)
    tab._update_fv_button()
    assert not tab._btn_fv_guided.isEnabled()
    settings.clear()
    tab.cleanup()


def test_guided_force_velocity_needs_two_loads(qapp) -> None:
    """A single load is rejected — the F-V study needs at least two points."""
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    settings = QSettings("emgteach-test", "acq-fv1")
    settings.clear()
    tab = AcquisitionTab(LoggerWidget(), settings)
    tab._worker = _FakeWorker()
    tab._fv_start([5.0], reps=1, prep_s=1.0, window_s=1.0)
    assert not tab._fv_active
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

    _drive_calibration(tab, 0.5)
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
