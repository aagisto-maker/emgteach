"""Tests for the QThread workers using a synthetic AcquisitionDevice.

The acquisition worker is the most important one to test because it
hosts the buffered-write integration -- the central claim of the BSPC
short communication, now wired through :class:`BufferedEdfWriter`. A
round-trip test (synthetic device -> worker -> EDF -> read back -> check
duration and markers) verifies that the integration is correct end to
end.

Tests are marked ``gui`` because they instantiate QThread, hence need
a QApplication. They run on a headless runner thanks to the
offscreen Qt platform set in ``conftest.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from emgteach.devices import AcquisitionDevice
from emgteach.io import read_edf_pyedflib
from emgteach.workers import AcquisitionWorker, AnalysisWorker, MvcWorker

pytestmark = pytest.mark.gui


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp() -> QCoreApplication:
    """Single QCoreApplication shared by every test in the session."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


class _FakeDevice(AcquisitionDevice):
    """In-memory device that produces a deterministic 80 Hz sinusoid.

    The sampling cursor advances on every :meth:`read` so consecutive
    blocks form a continuous waveform, which is what we need to verify
    that the worker writes a continuous EDF.
    """

    def __init__(self, fs: int = 1000) -> None:
        self._fs = int(fs)
        self._cursor = 0
        self._opened = False

    @property
    def fs(self) -> float:
        return float(self._fs)

    @property
    def name(self) -> str:
        return "FakeDevice"

    def open(self) -> None:
        self._opened = True

    def read(self, n_samples: int) -> np.ndarray:
        n = int(n_samples)
        t = (self._cursor + np.arange(n)) / self._fs
        sig = 0.3 * np.sin(2 * np.pi * 80.0 * t)
        self._cursor += n
        return sig.astype(np.float64)

    def close(self) -> None:
        self._opened = False

    def force_close(self) -> None:
        self._opened = False


def _wait_for_signal(qapp: QCoreApplication, signal, timeout_ms: int = 5000) -> None:
    """Spin a Qt event loop until *signal* fires or the timeout expires."""
    loop = QEventLoop()

    def on_emit(*_args, **_kwargs) -> None:
        loop.quit()

    signal.connect(on_emit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


# ---------------------------------------------------------------------------
# AcquisitionWorker
# ---------------------------------------------------------------------------


class TestAcquisitionWorker:
    """End-to-end test of the acquisition worker on a fake device."""

    def test_round_trip_edf_has_correct_duration(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        """The worker must produce an EDF whose duration matches the
        real samples it received from the device, with no antipattern
        zero-padding (Agis-Torres 2026).
        """
        device = _FakeDevice(fs=1000)
        worker = AcquisitionWorker(
            device=device, save_dir=str(tmp_path), n_per_read=100
        )

        edf_path_holder: list[str] = []

        def on_finished(path: str) -> None:
            edf_path_holder.append(path)

        worker.finished_ok.connect(on_finished)
        worker.start()

        # Let the worker read for ~1.5 s of fake data, then request stop
        QTimer.singleShot(150, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=8000)
        worker.wait(8000)

        assert edf_path_holder, "Worker did not emit finished_ok"
        edf_path = edf_path_holder[0]
        assert Path(edf_path).exists(), f"EDF file not created at {edf_path}"

        result = read_edf_pyedflib(edf_path, channel_index=0)
        n_edf = len(result["emg_raw"])
        n_acquired = device._cursor
        fs = int(device.fs)

        # The buffered writer pads the trailing remainder with the last
        # acquired value up to a complete data record. So the EDF
        # contains at least n_acquired samples and at most one extra
        # record's worth of last-value padding. The antipattern would
        # have inflated this 10x (one full record per 100-sample block).
        assert n_acquired <= n_edf, (
            f"EDF has fewer samples ({n_edf}) than the device produced "
            f"({n_acquired}); writer dropped data."
        )
        assert n_edf < n_acquired + fs, (
            f"EDF has {n_edf} samples for {n_acquired} acquired "
            f"({n_edf / max(1, n_acquired):.1f}x). The buffered writer "
            "should pad at most one record beyond real data; the "
            "antipattern would 10x-inflate."
        )

    def test_marker_is_persisted_as_edf_annotation(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        device = _FakeDevice(fs=1000)
        worker = AcquisitionWorker(
            device=device, save_dir=str(tmp_path), n_per_read=100
        )

        edf_path_holder: list[str] = []
        worker.finished_ok.connect(edf_path_holder.append)

        # Synchronise the marker call with the first data_ready, so the
        # worker is guaranteed to have entered its read loop and have a
        # nonzero acquisition cursor.
        added = {"done": False}

        def add_when_streaming(_block: dict) -> None:
            if not added["done"]:
                added["done"] = True
                worker.add_marker("contraction_onset")

        worker.data_ready.connect(add_when_streaming)
        worker.start()
        QTimer.singleShot(800, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=8000)
        worker.wait(8000)

        assert edf_path_holder, "Worker did not emit finished_ok"
        result = read_edf_pyedflib(edf_path_holder[0])
        labels = [label for _t, label in result["markers"]]
        assert "contraction_onset" in labels, (
            f"Marker did not survive to EDF; got markers {result['markers']}"
        )

    def test_data_ready_signal_is_emitted(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        device = _FakeDevice(fs=1000)
        worker = AcquisitionWorker(
            device=device, save_dir=str(tmp_path), n_per_read=100
        )

        blocks: list[dict] = []
        worker.data_ready.connect(blocks.append)

        worker.start()
        QTimer.singleShot(120, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=8000)
        worker.wait(8000)

        assert len(blocks) >= 1, "data_ready was never emitted"
        first = blocks[0]
        assert set(first.keys()) == {"raw_mv", "filtered", "envelope"}
        assert first["raw_mv"].shape == first["filtered"].shape == first["envelope"].shape


# ---------------------------------------------------------------------------
# AnalysisWorker
# ---------------------------------------------------------------------------


class TestAnalysisWorker:
    """Run the analysis worker on an EDF produced by AcquisitionWorker."""

    def _generate_edf(self, qapp: QCoreApplication, tmp_path: Path) -> str:
        device = _FakeDevice(fs=1000)
        worker = AcquisitionWorker(
            device=device, save_dir=str(tmp_path), n_per_read=100
        )
        edf_paths: list[str] = []
        worker.finished_ok.connect(edf_paths.append)
        worker.start()
        # Long enough for compute_segments to find at least one segment
        QTimer.singleShot(2200, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=10000)
        worker.wait(10000)
        return edf_paths[0]

    def test_result_ready_has_expected_keys(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        pytest.importorskip("mne")

        edf_path = self._generate_edf(qapp, tmp_path)

        analysis = AnalysisWorker(edf_path=edf_path, channel_name="EMG")
        results: list[dict] = []
        errors: list[str] = []
        analysis.result_ready.connect(results.append)
        analysis.error.connect(errors.append)

        analysis.start()
        _wait_for_signal(qapp, analysis.result_ready, timeout_ms=15000)
        analysis.wait(15000)

        assert not errors, f"Analysis emitted errors: {errors}"
        assert len(results) == 1
        keys = set(results[0].keys())
        for required in (
            "emg_raw",
            "emg_filtered",
            "emg_envelope",
            "rms_sliding",
            "frequencies",
            "psd",
            "mnf",
            "mdf",
            "t_seg",
            "rms_seg",
            "mdf_seg",
            "fat_fitted",
            "fat_slope_sign",
            "rms_global",
            "duration",
            "iemg",
            "fs",
        ):
            assert required in keys, f"Missing key: {required}"


# ---------------------------------------------------------------------------
# MvcWorker
# ---------------------------------------------------------------------------


class TestMvcWorker:
    def _generate_edf(self, qapp: QCoreApplication, tmp_path: Path) -> str:
        device = _FakeDevice(fs=1000)
        worker = AcquisitionWorker(
            device=device, save_dir=str(tmp_path), n_per_read=100
        )
        edf_paths: list[str] = []
        worker.finished_ok.connect(edf_paths.append)
        worker.start()
        QTimer.singleShot(1200, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=8000)
        worker.wait(8000)
        return edf_paths[0]

    def test_auto_normalisation_emits_result(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        edf_path = self._generate_edf(qapp, tmp_path)

        mvc = MvcWorker(edf_path=edf_path)
        results: list[dict] = []
        errors: list[str] = []
        mvc.result_ready.connect(results.append)
        mvc.error.connect(errors.append)

        mvc.start()
        _wait_for_signal(qapp, mvc.result_ready, timeout_ms=15000)
