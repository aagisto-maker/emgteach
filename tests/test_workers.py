"""Tests for the QThread workers using a synthetic AcquisitionDevice.

The acquisition worker is the most important one to test because it
hosts the buffered-write integration -- the central claim of the
buffered-write short communication, now wired through
:class:`BufferedEdfWriter`. A
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

from emgteach import SignalProfile
from emgteach.devices import AcquisitionDevice
from emgteach.io import read_edf_pyedflib
from emgteach.workers import AcquisitionWorker, AnalysisWorker, MvcWorker

pytestmark = pytest.mark.gui


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeDevice(AcquisitionDevice):
    """In-memory device that produces a deterministic 80 Hz sinusoid.

    The sampling cursor advances on every :meth:`read` so consecutive
    blocks form a continuous waveform, which is what we need to verify
    that the worker writes a continuous EDF.
    """

    def __init__(self, fs: int = 1000, n_channels: int = 1) -> None:
        self._fs = int(fs)
        self._cursor = 0
        self._opened = False
        self._n_channels = int(n_channels)

    @property
    def fs(self) -> float:
        return float(self._fs)

    @property
    def name(self) -> str:
        return "FakeDevice"

    @property
    def n_channels(self) -> int:
        return self._n_channels

    def open(self) -> None:
        self._opened = True

    def read(self, n_samples: int) -> np.ndarray:
        n = int(n_samples)
        t = (self._cursor + np.arange(n)) / self._fs
        sig = 0.3 * np.sin(2 * np.pi * 80.0 * t)
        self._cursor += n
        # One column per channel (shape (n, n_channels)), per the new
        # AcquisitionDevice contract.
        return np.column_stack([sig] * self._n_channels).astype(np.float64)

    def close(self) -> None:
        self._opened = False

    def force_close(self) -> None:
        self._opened = False


class _FakeEmgAccDevice(_FakeDevice):
    """Fake device exposing one EMG channel (mV) + one ACC channel (g).

    The EMG column is the base 80 Hz sinusoid; the ACC column is a slow ramp so
    a test can tell the two apart and check the ACC is stored raw (unfiltered).
    """

    def __init__(self, fs: int = 1000) -> None:
        super().__init__(fs=fs, n_channels=2)

    def read(self, n_samples: int) -> np.ndarray:
        n = int(n_samples)
        t = (self._cursor + np.arange(n)) / self._fs
        emg = 0.3 * np.sin(2 * np.pi * 80.0 * t)
        acc = np.linspace(-0.5, 0.5, n)          # slow, low-frequency "movement"
        self._cursor += n
        return np.column_stack([emg, acc]).astype(np.float64)

    def channel_kinds(self) -> list[str]:
        return ["EMG", "ACC"]

    def channel_units(self) -> list[str]:
        return ["mV", "g"]

    def channel_physical_ranges(self) -> list[tuple[float, float]]:
        return [(-1.65, 1.65), (-1.0, 1.0)]


class _RestThenBurstDevice(AcquisitionDevice):
    """Low-amplitude rest, then a sustained high-amplitude 80 Hz burst.

    Drives the automatic onset detector: the envelope stays low during
    the rest baseline and then crosses the threshold when the burst
    starts.
    """

    def __init__(self, fs: int = 1000, rest_s: float = 1.5) -> None:
        self._fs = int(fs)
        self._cursor = 0
        self._rest_n = int(rest_s * fs)

    @property
    def fs(self) -> float:
        return float(self._fs)

    @property
    def name(self) -> str:
        return "RestThenBurstDevice"

    def open(self) -> None:
        pass

    def read(self, n_samples: int) -> np.ndarray:
        n = int(n_samples)
        idx = self._cursor + np.arange(n)
        amp = np.where(idx < self._rest_n, 0.02, 0.5)
        sig = amp * np.sin(2 * np.pi * 80.0 * (idx / self._fs))
        self._cursor += n
        return sig.astype(np.float64).reshape(n, 1)

    def close(self) -> None:
        pass

    def force_close(self) -> None:
        pass


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

    def test_deleted_marker_is_not_persisted(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        device = _FakeDevice(fs=1000)
        worker = AcquisitionWorker(
            device=device, save_dir=str(tmp_path), n_per_read=100
        )
        edf_path_holder: list[str] = []
        worker.finished_ok.connect(edf_path_holder.append)

        # Add two markers, then delete the first one before the recording
        # stops. Only the second must survive to the EDF.
        added_times: list[float] = []
        worker.marker_added.connect(lambda t, _l: added_times.append(t))
        state = {"n": 0}

        def add_two(_block: dict) -> None:
            state["n"] += 1
            if state["n"] == 1:
                worker.add_marker("keep")
                worker.add_marker("undo_me")

        worker.data_ready.connect(add_two)
        worker.start()

        def delete_and_stop() -> None:
            # Remove the mistaken marker using its emitted time.
            assert worker.remove_marker(added_times[1], "undo_me")
            worker.stop()

        QTimer.singleShot(800, delete_and_stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=8000)
        worker.wait(8000)

        result = read_edf_pyedflib(edf_path_holder[0])
        labels = [label for _t, label in result["markers"]]
        assert "keep" in labels
        assert "undo_me" not in labels

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
        # Each value is a list with one 1-D array per channel.
        assert len(first["raw_mv"]) == device.n_channels == 1
        assert (
            first["raw_mv"][0].shape
            == first["filtered"][0].shape
            == first["envelope"][0].shape
        )

    def test_custom_profile_sets_edf_channel_labels(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        """A non-EMG profile must flow through to the EDF channel schema.

        This is the end-to-end check that ``SignalProfile`` is a real
        extension point: swapping the profile changes the recorded channel
        labels with no other code change in the worker.
        """
        from pyedflib import highlevel

        ecg = SignalProfile(
            name="ECG",
            f_low=0.5,
            f_high=100.0,
            raw_label="ECG",
        )
        device = _FakeDevice(fs=1000)
        worker = AcquisitionWorker(
            device=device, save_dir=str(tmp_path), n_per_read=100, profile=ecg
        )
        edf_paths: list[str] = []
        worker.finished_ok.connect(edf_paths.append)
        worker.start()
        QTimer.singleShot(150, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=8000)
        worker.wait(8000)

        assert edf_paths, "Worker did not emit finished_ok"
        _signals, headers, _ = highlevel.read_edf(edf_paths[0])
        labels = [h["label"] for h in headers]
        assert labels == ["ECG"]

    def test_two_channel_acquisition_writes_one_raw_channel_per_sensor(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        """Two sensors produce two raw EDF channels, labelled per sensor."""
        from pyedflib import highlevel

        device = _FakeDevice(fs=1000, n_channels=2)
        worker = AcquisitionWorker(
            device=device,
            save_dir=str(tmp_path),
            n_per_read=100,
            sensor_labels=["Agonista", "Antagonista"],
        )
        edf_paths: list[str] = []
        worker.finished_ok.connect(edf_paths.append)
        worker.start()
        QTimer.singleShot(200, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=8000)
        worker.wait(8000)

        assert edf_paths and edf_paths[0], "Worker did not emit finished_ok"
        signals, headers, _ = highlevel.read_edf(edf_paths[0])
        labels = [h["label"] for h in headers]
        assert labels == ["Agonista", "Antagonista"]
        assert len(signals) == 2

    def test_accelerometer_channel_written_with_own_unit_and_unfiltered(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        """An ACC channel is stored raw with unit 'g'; EMG keeps its own chain."""
        from pyedflib import highlevel

        device = _FakeEmgAccDevice(fs=1000)
        worker = AcquisitionWorker(
            device=device, save_dir=str(tmp_path), n_per_read=100,
            sensor_labels=["EMG", "ACC"],
        )
        captured: list[dict] = []
        worker.data_ready.connect(captured.append)
        edf_paths: list[str] = []
        worker.finished_ok.connect(edf_paths.append)
        worker.start()
        QTimer.singleShot(400, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=8000)
        worker.wait(8000)

        assert edf_paths and edf_paths[0]
        _signals, headers, _ = highlevel.read_edf(edf_paths[0])
        labels = [h["label"] for h in headers]
        dims = [h["dimension"] for h in headers]
        assert labels == ["EMG", "ACC"]
        assert dims == ["mV", "g"]                 # ACC keeps its own unit
        # The ACC block is emitted unfiltered: envelope == raw for that channel.
        acc_blocks = [b for b in captured if len(b["raw_mv"]) == 2]
        assert acc_blocks, "no two-channel blocks captured"
        b = acc_blocks[0]
        np.testing.assert_allclose(b["envelope"][1], b["raw_mv"][1])
        # ...whereas the EMG channel is filtered, so its envelope differs from raw.
        assert not np.allclose(b["envelope"][0], b["raw_mv"][0])

    def test_auto_detection_writes_an_automatic_marker(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        """With auto_detect on, a contraction onset is written to the EDF."""
        device = _RestThenBurstDevice(fs=1000, rest_s=1.5)
        worker = AcquisitionWorker(
            device=device,
            save_dir=str(tmp_path),
            n_per_read=100,
            auto_detect=True,
        )
        edf_paths: list[str] = []
        worker.finished_ok.connect(edf_paths.append)
        worker.start()
        # Acquire well past the 1.5 s rest so the burst onset is detected.
        QTimer.singleShot(2500, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=12000)
        worker.wait(12000)

        assert edf_paths and edf_paths[0], "Worker did not emit finished_ok"
        result = read_edf_pyedflib(edf_paths[0])
        labels = [label for _t, label in result["markers"]]
        assert any("auto" in label.lower() for label in labels), (
            f"No automatic onset marker found; got {result['markers']}"
        )

    def test_manual_and_auto_markers_coexist_in_edf(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        """Acceptance criterion: a session with both a manual marker and an
        automatic onset persists both to the EDF.
        """
        device = _RestThenBurstDevice(fs=1000, rest_s=1.5)
        worker = AcquisitionWorker(
            device=device,
            save_dir=str(tmp_path),
            n_per_read=100,
            auto_detect=True,
        )
        edf_paths: list[str] = []
        worker.finished_ok.connect(edf_paths.append)

        added = {"done": False}

        def add_manual(_block: dict) -> None:
            if not added["done"]:
                added["done"] = True
                worker.add_marker("fatiga aparente")

        worker.data_ready.connect(add_manual)
        worker.start()
        QTimer.singleShot(2500, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=12000)
        worker.wait(12000)

        assert edf_paths and edf_paths[0], "Worker did not emit finished_ok"
        result = read_edf_pyedflib(edf_paths[0])
        labels = [label for _t, label in result["markers"]]
        assert "fatiga aparente" in labels, f"manual marker missing; got {labels}"
        assert any("auto" in label.lower() for label in labels), (
            f"automatic marker missing; got {labels}"
        )


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

    def _generate_two_channel_edf(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> str:
        device = _FakeDevice(fs=1000, n_channels=2)
        worker = AcquisitionWorker(
            device=device, save_dir=str(tmp_path), n_per_read=100,
            sensor_labels=["Agonista", "Antagonista"],
        )
        edf_paths: list[str] = []
        worker.finished_ok.connect(edf_paths.append)
        worker.start()
        QTimer.singleShot(2200, worker.stop)
        _wait_for_signal(qapp, worker.finished_ok, timeout_ms=10000)
        worker.wait(10000)
        return edf_paths[0]

    def test_second_channel_envelope_is_overlaid(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        """channel_name_2 adds the antagonist envelope aligned with the first."""
        pytest.importorskip("mne")
        edf_path = self._generate_two_channel_edf(qapp, tmp_path)

        analysis = AnalysisWorker(
            edf_path=edf_path, channel_name="Agonista",
            channel_name_2="Antagonista",
        )
        results: list[dict] = []
        errors: list[str] = []
        analysis.result_ready.connect(results.append)
        analysis.error.connect(errors.append)
        analysis.start()
        _wait_for_signal(qapp, analysis.result_ready, timeout_ms=15000)
        analysis.wait(15000)

        assert not errors, f"Analysis emitted errors: {errors}"
        assert len(results) == 1
        r = results[0]
        assert r["channel_name_2"] == "Antagonista"
        assert "emg_envelope_2" in r
        # The overlaid envelope is aligned with the primary one.
        assert len(r["emg_envelope_2"]) == len(r["emg_envelope"])

    def test_no_second_channel_leaves_result_single(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        """Without channel_name_2 the result carries no overlay keys."""
        pytest.importorskip("mne")
        edf_path = self._generate_edf(qapp, tmp_path)
        analysis = AnalysisWorker(edf_path=edf_path, channel_name="EMG")
        results: list[dict] = []
        analysis.result_ready.connect(results.append)
        analysis.start()
        _wait_for_signal(qapp, analysis.result_ready, timeout_ms=15000)
        analysis.wait(15000)
        assert results and "emg_envelope_2" not in results[0]

    def test_resolve_roi_full_recording(self, qapp: QCoreApplication) -> None:
        # No ROI requested -> the whole recording, bounds (0, n).
        w = AnalysisWorker(edf_path="x.edf")
        assert w._resolve_roi(10_000, 1000.0, 10.0) == (0, 10_000, 0.0, 10.0)

    def test_resolve_roi_window_and_clamp(self, qapp: QCoreApplication) -> None:
        w = AnalysisWorker(edf_path="x.edf", roi_start_s=2.0, roi_end_s=5.0)
        assert w._resolve_roi(10_000, 1000.0, 10.0) == (2000, 5000, 2.0, 5.0)
        # An end beyond the recording is clamped to the full duration.
        w2 = AnalysisWorker(edf_path="x.edf", roi_start_s=8.0, roi_end_s=99.0)
        i0, i1, _a, b = w2._resolve_roi(10_000, 1000.0, 10.0)
        assert (i0, i1) == (8000, 10_000)
        assert b == 10.0

    def test_resolve_roi_too_short_errors(self, qapp: QCoreApplication) -> None:
        w = AnalysisWorker(edf_path="x.edf", roi_start_s=1.0, roi_end_s=1.5)
        errors: list[str] = []
        w.error.connect(errors.append)
        assert w._resolve_roi(10_000, 1000.0, 10.0) is None
        assert errors and "region" in errors[0].lower()

    def test_roi_analysis_restricts_duration(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        pytest.importorskip("mne")
        edf_path = self._generate_edf(qapp, tmp_path)

        analysis = AnalysisWorker(
            edf_path=edf_path, channel_name="EMG", roi_start_s=0.5, roi_end_s=1.8
        )
        results: list[dict] = []
        errors: list[str] = []
        analysis.result_ready.connect(results.append)
        analysis.error.connect(errors.append)
        analysis.start()
        _wait_for_signal(qapp, analysis.result_ready, timeout_ms=15000)
        analysis.wait(15000)

        assert not errors, f"Analysis emitted errors: {errors}"
        assert len(results) == 1
        r = results[0]
        assert r["roi_start_s"] == 0.5
        assert r["roi_end_s"] == 1.8
        # Cropped analysis runs on ~1.3 s, not the full ~2.2 s recording.
        assert abs(r["duration"] - 1.3) < 0.15
        assert r["full_duration_s"] > 2.0

    def test_multi_fragment_analysis_concatenates(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        pytest.importorskip("mne")
        edf_path = self._generate_edf(qapp, tmp_path)  # ~2.2 s recording

        # Keep two disjoint 0.7 s fragments -> ~1.4 s of concatenated signal.
        analysis = AnalysisWorker(
            edf_path=edf_path,
            channel_name="EMG",
            roi_segments=[(0.2, 0.9), (1.3, 2.0)],
        )
        results: list[dict] = []
        errors: list[str] = []
        analysis.result_ready.connect(results.append)
        analysis.error.connect(errors.append)
        analysis.start()
        _wait_for_signal(qapp, analysis.result_ready, timeout_ms=15000)
        analysis.wait(15000)

        assert not errors, f"Analysis emitted errors: {errors}"
        r = results[0]
        assert r["roi_segments"] == [(0.2, 0.9), (1.3, 2.0)]
        # Duration is the sum of the kept fragments, not the whole file.
        assert abs(r["duration"] - 1.4) < 0.15

    def test_too_short_selection_emits_error(
        self, qapp: QCoreApplication, tmp_path: Path
    ) -> None:
        pytest.importorskip("mne")
        edf_path = self._generate_edf(qapp, tmp_path)
        analysis = AnalysisWorker(
            edf_path=edf_path, channel_name="EMG", roi_segments=[(0.1, 0.5)]
        )
        results: list[dict] = []
        errors: list[str] = []
        analysis.result_ready.connect(results.append)
        analysis.error.connect(errors.append)
        analysis.start()
        _wait_for_signal(qapp, analysis.error, timeout_ms=15000)
        analysis.wait(15000)

        assert not results
        assert errors and "minimum" in errors[0].lower()


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
