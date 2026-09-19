"""The recording phase starts from rest, and the live monitor knows it.

The onset detector sets its threshold from the stream's first second and
never again; in a guided session that second is the start of the warm-up.
At ``REC start`` — after a countdown that is rest by construction — the
detector is re-armed and the live Jonsson levels start counting, and both
keep going during the lifts of the force-velocity study. The levels come
from a histogram, so they cost the same after an hour as after a second.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from emgteach.apda import OnlineLoad
from emgteach.dsp import OnsetDetector
from emgteach.phases import rec_start_marker

FS = 1000


def test_rearm_measures_the_threshold_again_and_keeps_the_time_base() -> None:
    rng = np.random.default_rng(3)
    warmup = 0.20 + 0.05 * rng.standard_normal(FS)      # the stream's first second: contractions
    rest = 0.005 + 0.001 * rng.standard_normal(FS)
    task = np.full(FS, 0.10)                             # a gentle lift, a fifth of the warm-up

    stale = OnsetDetector(FS)
    rearmed = OnsetDetector(FS)
    for det in (stale, rearmed):
        assert det.process(warmup) == []
        assert det.threshold is not None and det.threshold > 0.15
        det.process(rest)                                # 1 to 2 s: the countdown
    rearmed.rearm()
    assert rearmed.threshold is None
    for det in (stale, rearmed):
        assert det.process(rest) == []                   # 2 to 3 s: rest again
    assert rearmed.threshold is not None and rearmed.threshold < 0.02
    assert stale.threshold > 0.15, "the old detector keeps the warm-up's threshold"

    assert stale.process(task) == [], "against the warm-up's threshold the lift is invisible"
    onsets = rearmed.process(task)                       # 3 to 4 s
    assert len(onsets) == 1
    assert onsets[0] == pytest.approx(3.0, abs=0.005), "onset times stay in the file's time base"


def test_the_histogram_levels_match_numpy_to_a_tenth_of_a_percent() -> None:
    rng = np.random.default_rng(5)
    x = rng.uniform(0.0, 80.0, 20_000)
    ol = OnlineLoad()
    for i in range(0, x.size, 100):
        ol.add(x[i:i + 100])
    assert ol.n == x.size
    for level, p in ((ol.static, 10), (ol.median, 50), (ol.peak, 90)):
        assert level == pytest.approx(float(np.percentile(x, p)), abs=0.2)
    assert ol.static == round(ol.static, 1)


def test_the_histogram_counts_resets_and_caps_at_its_top() -> None:
    ol = OnlineLoad()
    ol.add(np.full(200_000, 12.34))                      # twenty minutes at 166 Hz, one array
    ol.add(np.full(10, 1e6))
    assert ol.n == 200_010
    assert ol.median == pytest.approx(12.3, abs=1e-9)
    assert ol.peak == pytest.approx(12.3, abs=1e-9)
    assert ol._hist.size == int(OnlineLoad.TOP_PCT * OnlineLoad.BINS_PER_PCT) + 1
    assert not hasattr(ol, "_buf"), "no per-sample buffer any more"
    ol.reset()
    assert ol.n == 0
    assert (ol.static, ol.median, ol.peak) == (0.0, 0.0, 0.0)
    ol.add(np.full(3, 1e6))
    assert ol.static == OnlineLoad.TOP_PCT, "anything above the top lands in the last bin"


class _FakeWorker:
    """Collects the marks and the re-arm requests the tab makes, in order."""

    def __init__(self, can_rearm: bool = True) -> None:
        self.events: list[str] = []
        if can_rearm:
            self.rearm_onsets = lambda: self.events.append("rearm")

    def isRunning(self) -> bool:      # Qt's spelling, matched on purpose
        return True

    def add_marker(self, label: str) -> None:
        self.events.append(str(label))

    def instruct(self, channel_index: int, level: float | None, **_k) -> None:
        self.events.append(f"instruct ch={channel_index} level={level}")

    def stop(self) -> None:
        """The tab stops the worker when the recording ends; nothing to do here."""

    def is_streaming(self) -> bool:
        return True


@pytest.fixture
def tab(qapp):
    from PySide6.QtCore import QSettings

    from emgteach.gui.tabs.acquisition import AcquisitionTab
    from emgteach.gui.widgets.logger import LoggerWidget

    widget = AcquisitionTab(LoggerWidget(), QSettings("emgteach-test", "rearme"))
    widget._n_channels = 1
    widget._worker = _FakeWorker()
    yield widget
    widget._watchdog_timer.stop()
    widget._mvc_timer.stop()
    widget._prep_timer.stop()
    widget._load_timer.stop()
    widget.close()


def _terminar_la_cuenta_atras(tab) -> None:
    """The last tick of the preparation countdown: the one that writes REC start."""
    tab._prep_elapsed = tab._profile.prep_countdown_s
    tab._prep_tick()


@pytest.mark.gui
def test_rec_start_rearms_the_worker_and_restarts_the_live_levels(tab) -> None:
    tab._mvc_ref[0] = 0.5
    tab._online[0].add(np.full(500, 20.0))               # the countdown's rest, as counted until now
    tab._update_load_readout()
    assert "P50 20" in tab._load_readouts[0].text()

    _terminar_la_cuenta_atras(tab)
    assert tab._worker.events == [rec_start_marker(), "rearm"], "the mark first, then the re-arm"
    assert tab._online[0].n == 0
    assert "P50 0" in tab._load_readouts[0].text()

    # A worker without the slot (an older fake, a kinematics-only stream) is left alone.
    tab._worker = _FakeWorker(can_rearm=False)
    _terminar_la_cuenta_atras(tab)
    assert tab._worker.events == [rec_start_marker()]


@pytest.mark.gui
def test_the_bars_follow_the_lifts_of_the_force_velocity_study(tab) -> None:
    tab._mvc_ref[0] = 0.5
    fed: list = []
    tab._fv_mvc_feed = fed.append
    env = [np.full(100, 0.25)]                           # half the reference
    tab._fv_active = True

    tab._fv_phase = "mvc_contract"                       # the study's own maximum: the wizard's
    tab._process_load(env)
    assert len(fed) == 1 and tab._online[0].n == 0

    for phase in ("intro", "ready", "contract", "rest"):  # the cued lifts: the monitor's
        tab._fv_phase = phase
        tab._process_load(env)
    assert len(fed) == 1
    assert tab._online[0].n == 400
    assert tab._load_bars[0]._value == pytest.approx(50.0)


@pytest.mark.gui
def test_the_worker_rearms_its_detectors_at_the_next_block_and_says_so(qapp, tmp_path) -> None:
    from emgteach.devices import BitalinoDevice
    from emgteach.workers.acquisition import AcquisitionWorker

    worker = AcquisitionWorker(BitalinoDevice("simulada", fs=1000, channels=[0]),
                               save_path=str(tmp_path / "sim.edf"), sensor_labels=["FCR"],
                               auto_detect=True)
    lines: list[str] = []
    worker.log.connect(lines.append)
    worker.start()
    end = time.monotonic() + 8
    while time.monotonic() < end and not worker.is_streaming():
        qapp.processEvents()
        time.sleep(0.02)
    assert worker.is_streaming()

    def rearmed() -> bool:
        return any("re-armed" in s or "rearmada" in s for s in lines)

    assert not rearmed()
    worker.rearm_onsets()
    end = time.monotonic() + 3
    while time.monotonic() < end and not rearmed():
        qapp.processEvents()
        time.sleep(0.02)
    worker.stop()
    assert worker.wait(5000)
    assert rearmed()
