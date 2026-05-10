"""Round-trip and structural tests for :mod:`emgteach.io`.

The tests run on a fully synthetic signal so they are fast and
require no hardware. The buffered writer is the central piece tested
here: a stream-and-write antipattern would inflate the file duration
tenfold; a correct buffered writer must reproduce duration, RMS and
spectral content within tight tolerances.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach import (
    BufferedEdfWriter,
    ChannelInfo,
    build_timestamped_path,
    read_edf_pyedflib,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FS = 1000  # Hz
DURATION_S = 10
N_SAMPLES = FS * DURATION_S
BLOCK = 100  # ms = 100 samples at 1 kHz — same as BITalino / Arduino loops


@pytest.fixture
def synthetic_signal() -> np.ndarray:
    """10 s, 80 Hz carrier (0.3 mV) + Gaussian noise (sigma 0.05 mV).

    Same parameters as the BSPC reproducibility package, modulo the
    seed so results are byte-stable across runs in tests.
    """
    rng = np.random.default_rng(seed=42)
    t = np.arange(N_SAMPLES) / FS
    signal = 0.3 * np.sin(2 * np.pi * 80.0 * t) + 0.05 * rng.standard_normal(N_SAMPLES)
    return signal.astype(np.float64)


@pytest.fixture
def out_path(tmp_path: Path) -> str:
    """Path inside pytest's tmp dir for an EDF file under test."""
    return str(tmp_path / "session.edf")


# ---------------------------------------------------------------------------
# BufferedEdfWriter — single channel
# ---------------------------------------------------------------------------


class TestBufferedWriterSingleChannel:
    """The single-channel case must reproduce duration, amplitude and
    spectrum of the original signal — the property that the antipattern
    silently breaks (Agis-Torres 2026)."""

    def test_round_trip_duration_is_correct(
        self, synthetic_signal: np.ndarray, out_path: str
    ) -> None:
        ch = ChannelInfo("EMG", sample_frequency=FS)
        with BufferedEdfWriter(out_path, channels=[ch]) as writer:
            for i in range(0, N_SAMPLES, BLOCK):
                writer.add_samples(synthetic_signal[i : i + BLOCK])

        result = read_edf_pyedflib(out_path)
        # Reported file duration must match the actual duration to within one record
        assert len(result["emg_raw"]) == N_SAMPLES, (
            f"Expected {N_SAMPLES} samples, got {len(result['emg_raw'])}. "
            "This is the very symptom that the buffered writer is meant to prevent."
        )

    def test_round_trip_rms_is_preserved(
        self, synthetic_signal: np.ndarray, out_path: str
    ) -> None:
        """RMS amplitude after writing+reading must match within tolerance.

        The antipattern attenuates RMS by ~3.2x because 90 % of the
        stored samples are quantised-zero padding.
        """
        ch = ChannelInfo("EMG", sample_frequency=FS)
        with BufferedEdfWriter(out_path, channels=[ch]) as writer:
            for i in range(0, N_SAMPLES, BLOCK):
                writer.add_samples(synthetic_signal[i : i + BLOCK])

        result = read_edf_pyedflib(out_path)
        rms_in = float(np.sqrt(np.mean(synthetic_signal**2)))
        rms_out = float(np.sqrt(np.mean(result["emg_raw"] ** 2)))
        # 5 % tolerance — quantisation through the 10-bit ADC range is the
        # main source of loss; the buffered writer itself is loss-free.
        assert rms_out == pytest.approx(rms_in, rel=0.05), (
            f"RMS mismatch: in={rms_in:.4f} mV, out={rms_out:.4f} mV"
        )

    def test_zero_padding_artifact_is_absent(
        self, synthetic_signal: np.ndarray, out_path: str
    ) -> None:
        """Ratio of samples within ±1 LSB of zero must stay low.

        In an antipattern file 90 % of samples are at quantised zero;
        in a correct buffered file it should be a small fraction
        determined by the natural noise level.
        """
        ch = ChannelInfo("EMG", sample_frequency=FS)
        with BufferedEdfWriter(out_path, channels=[ch]) as writer:
            for i in range(0, N_SAMPLES, BLOCK):
                writer.add_samples(synthetic_signal[i : i + BLOCK])

        result = read_edf_pyedflib(out_path)
        lsb = (3.3 - (-3.3)) / 1024.0  # 10-bit ADC over ±3.3 V
        near_zero = float(np.mean(np.abs(result["emg_raw"]) <= lsb))
        # The synthetic signal spends a tiny fraction within ±1 LSB of zero
        # because it has nonzero amplitude. The antipattern would push this
        # to ~0.9; we accept anything well under 0.5 as evidence that the
        # padding artifact is not present.
        assert near_zero < 0.2, (
            f"Suspiciously high fraction of samples at quantised zero "
            f"({near_zero:.3f}); buffered writer may be silently degenerated."
        )

    def test_close_pads_with_last_value_not_zero(self, out_path: str) -> None:
        """The trailing remainder must be padded with the last sample."""
        ch = ChannelInfo("EMG", sample_frequency=FS)
        n = FS + 250  # one full record plus 250 samples of remainder
        signal = np.full(n, 1.5, dtype=np.float64)
        signal[-1] = 0.7  # set last sample so we can verify it propagates

        with BufferedEdfWriter(out_path, channels=[ch]) as writer:
            writer.add_samples(signal)

        result = read_edf_pyedflib(out_path)
        # File must contain exactly two records (2 * FS samples)
        assert len(result["emg_raw"]) == 2 * FS
        # The padding region (last FS - 250 samples of the second record)
        # should hold the last acquired value (0.7), not zero.
        padded = result["emg_raw"][n:]
        assert np.allclose(padded, 0.7, atol=0.05), (
            f"Padding values look like {padded[:5]}; expected ~0.7."
        )


# ---------------------------------------------------------------------------
# BufferedEdfWriter — multichannel
# ---------------------------------------------------------------------------


class TestBufferedWriterMultiChannel:
    """The multichannel case is what the acquisition GUI actually uses."""

    def test_three_channels_round_trip(
        self, synthetic_signal: np.ndarray, out_path: str
    ) -> None:
        chs = [
            ChannelInfo("EMG", sample_frequency=FS),
            ChannelInfo("EMG_Filtered", sample_frequency=FS),
            ChannelInfo(
                "EMG_Envelope", physical_min=0.0, sample_frequency=FS
            ),
        ]
        envelope = np.abs(synthetic_signal)  # crude envelope for the test

        with BufferedEdfWriter(out_path, channels=chs) as writer:
            for i in range(0, N_SAMPLES, BLOCK):
                end = i + BLOCK
                writer.add_samples(
                    synthetic_signal[i:end],
                    synthetic_signal[i:end],
                    envelope[i:end],
                )

        for idx in range(3):
            result = read_edf_pyedflib(out_path, channel_index=idx)
            assert len(result["emg_raw"]) == N_SAMPLES, (
                f"Channel {idx} length mismatch."
            )

    def test_mismatched_block_lengths_raise(self, out_path: str) -> None:
        chs = [
            ChannelInfo("EMG", sample_frequency=FS),
            ChannelInfo("EMG_Filtered", sample_frequency=FS),
        ]
        with BufferedEdfWriter(out_path, channels=chs) as writer:
            with pytest.raises(ValueError, match="same length"):
                writer.add_samples(np.zeros(100), np.zeros(50))

    def test_wrong_number_of_blocks_raises(self, out_path: str) -> None:
        chs = [
            ChannelInfo("EMG", sample_frequency=FS),
            ChannelInfo("EMG_Filtered", sample_frequency=FS),
        ]
        with BufferedEdfWriter(out_path, channels=chs) as writer:
            with pytest.raises(ValueError, match="2 channel"):
                writer.add_samples(np.zeros(100))


# ---------------------------------------------------------------------------
# Construction validation
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_no_channels_raises(self, out_path: str) -> None:
        with pytest.raises(ValueError, match="at least one channel"):
            BufferedEdfWriter(out_path, channels=[])

    def test_mixed_sample_frequencies_raise(self, out_path: str) -> None:
        chs = [
            ChannelInfo("A", sample_frequency=1000),
            ChannelInfo("B", sample_frequency=500),
        ]
        with pytest.raises(ValueError, match="same sample_frequency"):
            BufferedEdfWriter(out_path, channels=chs)

    def test_double_close_is_safe(
        self, synthetic_signal: np.ndarray, out_path: str
    ) -> None:
        ch = ChannelInfo("EMG", sample_frequency=FS)
        writer = BufferedEdfWriter(out_path, channels=[ch])
        writer.add_samples(synthetic_signal[:1500])
        writer.close()
        writer.close()  # must not raise

    def test_add_after_close_raises(
        self, synthetic_signal: np.ndarray, out_path: str
    ) -> None:
        ch = ChannelInfo("EMG", sample_frequency=FS)
        writer = BufferedEdfWriter(out_path, channels=[ch])
        writer.add_samples(synthetic_signal[:1500])
        writer.close()
        with pytest.raises(RuntimeError, match="closed"):
            writer.add_samples(synthetic_signal[:100])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestBuildTimestampedPath:
    def test_default_directory_and_prefix(self) -> None:
        p = build_timestamped_path()
        # Format: ./emg_YYYY-MM-DD_HH-MM.edf
        name = Path(p).name
        assert name.startswith("emg_") and name.endswith(".edf")
        # YYYY-MM-DD_HH-MM has length 16
        assert len(name) == len("emg_") + 16 + len(".edf")

    def test_custom_directory_prefix_suffix(self, tmp_path: Path) -> None:
        p = build_timestamped_path(tmp_path, prefix="bitalino", suffix=".bdf")
        assert Path(p).parent == tmp_path
        assert Path(p).name.startswith("bitalino_")
        assert p.endswith(".bdf")
