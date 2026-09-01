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
    RecordingMetadata,
    build_timestamped_path,
    create_edf_writer,
    edf_duration,
    list_edf_channels,
    read_edf_metadata,
    read_edf_pyedflib,
    write_edf_block,
)
from emgteach.io import EDF_RECORDING_IDENT_BUDGET

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

    Same parameters as the buffered-write reproducibility package, modulo the
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


# ---------------------------------------------------------------------------
# Deprecated legacy helpers
# ---------------------------------------------------------------------------


class TestDeprecatedHelpers:
    """The unsafe per-block writers are kept but must warn (Agis-Torres 2026)."""

    def test_create_edf_writer_warns(self, out_path: str) -> None:
        with pytest.warns(DeprecationWarning, match="create_edf_writer"):
            writer = create_edf_writer(out_path, fs=FS)
        writer.close()

    def test_write_edf_block_warns(self, out_path: str) -> None:
        with pytest.warns(DeprecationWarning, match="create_edf_writer"):
            writer = create_edf_writer(out_path, fs=FS)
        block = np.zeros(FS, dtype=np.float64)
        try:
            with pytest.warns(DeprecationWarning, match="write_edf_block"):
                write_edf_block(writer, block, block, block)
        finally:
            writer.close()


# ---------------------------------------------------------------------------
# Channel listing (header-only)
# ---------------------------------------------------------------------------


class TestListEdfChannels:
    def test_lists_channel_labels_in_order(self, out_path: str) -> None:
        chs = [
            ChannelInfo("Agonista", sample_frequency=FS),
            ChannelInfo("Antagonista", sample_frequency=FS),
        ]
        with BufferedEdfWriter(out_path, channels=chs) as writer:
            writer.add_samples(np.zeros(FS), np.zeros(FS))
        assert list_edf_channels(out_path) == ["Agonista", "Antagonista"]

    def test_missing_file_returns_empty_list(self, tmp_path: Path) -> None:
        assert list_edf_channels(str(tmp_path / "does_not_exist.edf")) == []


# ---------------------------------------------------------------------------
# Annotation round-trip
# ---------------------------------------------------------------------------


class TestAnnotationRoundTrip:
    """Annotations written to an EDF must be readable again on reload."""

    def test_mne_reader_recovers_annotation(self, out_path: str) -> None:
        pytest.importorskip("mne")
        from emgteach import read_edf_mne

        ch = ChannelInfo("EMG", sample_frequency=FS)
        with BufferedEdfWriter(out_path, channels=[ch]) as writer:
            writer.add_samples(np.zeros(2 * FS, dtype=np.float64))
            writer.add_annotation(0.5, "inicio contracción")

        edf = read_edf_mne(out_path, "EMG")
        labels = [desc for _onset, desc in edf["markers"]]
        assert "inicio contracción" in labels

    def test_pyedflib_reader_recovers_annotation(self, out_path: str) -> None:
        ch = ChannelInfo("EMG", sample_frequency=FS)
        with BufferedEdfWriter(out_path, channels=[ch]) as writer:
            writer.add_samples(np.zeros(2 * FS, dtype=np.float64))
            writer.add_annotation(0.5, "inicio contracción")

        result = read_edf_pyedflib(out_path)
        labels = [desc for _onset, desc in result["markers"]]
        assert "inicio contracción" in labels

    def test_a_crowded_second_keeps_every_annotation(self, out_path: str) -> None:
        """Twelve marks inside one second must all come back.

        EDF+ keeps annotations inside the data records, so their capacity is a
        rate: with pyedflib's default single annotation signal only about five
        per second survive and the rest vanish without an error. A real session
        crossed that line — the derived file lost ``PREP start`` and
        ``REC start`` — which is the same silent loss as the buffered-write
        defect, in a different header field.
        """
        ch = ChannelInfo("EMG", sample_frequency=FS)
        escritas = [f"m{i:02d}" for i in range(12)]
        with BufferedEdfWriter(out_path, channels=[ch]) as writer:
            writer.add_samples(np.zeros(3 * FS, dtype=np.float64))
            for i, texto in enumerate(escritas):
                writer.add_annotation(1.0 + i * 0.05, texto)

        leidas = [desc for _onset, desc in read_edf_pyedflib(out_path)["markers"]]
        assert [t for t in escritas if t not in leidas] == []


class TestPhysicalRangeNoClipping:
    """The device-aware physical range must let a wide Arduino signal survive
    the EDF round-trip, whereas the narrow BITalino default clips it — exactly
    the data-loss bug the per-device range fixes."""

    def _roundtrip_peak(self, out_path: str, pmax: float) -> float:
        n = 2 * FS
        sig = np.zeros(n, dtype=np.float64)
        sig[n // 2] = 10.0  # a +10 mV peak, inside the Arduino ±12.5 mV range
        ch = ChannelInfo(
            "EMG", sample_frequency=FS, physical_min=-pmax, physical_max=pmax
        )
        with BufferedEdfWriter(out_path, channels=[ch]) as writer:
            writer.add_samples(sig)
        return float(np.max(read_edf_pyedflib(out_path)["emg_raw"]))

    def test_arduino_range_preserves_the_peak(self, out_path: str) -> None:
        assert self._roundtrip_peak(out_path, 12.5) == pytest.approx(10.0, abs=0.1)

    def test_narrow_default_range_clips_the_peak(self, out_path: str) -> None:
        # With the old ±3.3 mV default the +10 mV peak is silently clipped.
        assert self._roundtrip_peak(out_path, 3.3) < 3.5


# ---------------------------------------------------------------------------
# EDF+ recording metadata (student / protocol header)
# ---------------------------------------------------------------------------


class TestRecordingMetadata:
    """Student/protocol identification round-trips through the EDF+ header."""

    def _write(self, out_path: str, metadata: RecordingMetadata) -> None:
        ch = ChannelInfo("EMG", sample_frequency=FS)
        sig = np.zeros(2 * FS, dtype=np.float64)
        with BufferedEdfWriter(out_path, channels=[ch], metadata=metadata) as writer:
            writer.add_samples(sig)

    def test_metadata_round_trips(self, out_path: str) -> None:
        self._write(
            out_path,
            RecordingMetadata(
                student_name="Ada Lovelace",
                student_code="A123",
                protocol="Isometric biceps 30 s",
            ),
        )
        meta = read_edf_metadata(out_path)
        assert meta.student_name == "Ada Lovelace"
        assert meta.student_code == "A123"
        assert meta.protocol == "Isometric biceps 30 s"

    def test_no_metadata_is_valid(self, out_path: str) -> None:
        # Writing without metadata must still produce a readable file.
        self._write(out_path, RecordingMetadata())
        assert edf_duration(out_path) == pytest.approx(2.0, abs=0.01)

    def test_is_empty(self) -> None:
        assert RecordingMetadata().is_empty()
        assert not RecordingMetadata(student_name="x").is_empty()


# ---------------------------------------------------------------------------
# The recording-identification budget
# ---------------------------------------------------------------------------


class TestTheProtocolIsNeverTheFieldThatGivesWay:
    """What the EDF+ recording block does when four fields want eighty chars.

    Measured on ``C:\\Records\\emg_2026-08-31_19-33.edf``: the app wrote the
    protocol ``"agonist/antagonist"`` and ``getRecordingAdditional()`` gave
    back ``"agonist/ant"``. The device string, twenty-eight characters of
    ``"BITalino (98:D3:91:FE:44:E4)"``, had eaten the budget, and pyedflib —
    whose guard scores that header at 69 of 80 and stays quiet — never said
    so. Same family as the buffered-write corruption the module documents
    (Agis-Torres 2026): the file is valid, the loss is silent, and nobody
    finds out until a marking pile has protocols that name no practice.
    """

    #: The header as the bench actually wrote it.
    EQUIPMENT = "BITalino (98:D3:91:FE:44:E4)"
    PROTOCOL = "agonist/antagonist"

    def _write(self, out_path: str, metadata: RecordingMetadata) -> list[str]:
        ch = ChannelInfo("EMG", sample_frequency=FS)
        sig = np.zeros(2 * FS, dtype=np.float64)
        with BufferedEdfWriter(out_path, channels=[ch], metadata=metadata) as w:
            w.add_samples(sig)
            notices = list(w.header_notices)
        return notices

    def test_the_protocol_comes_back_whole(self, out_path: str) -> None:
        """The regression itself: write the measured header, read it back."""
        self._write(
            out_path,
            RecordingMetadata(
                student_name="Ada Lovelace",
                student_code="A123",
                protocol=self.PROTOCOL,
                equipment=self.EQUIPMENT,
            ),
        )
        assert read_edf_metadata(out_path).protocol == self.PROTOCOL

    def test_the_equipment_still_names_the_bench(self, out_path: str) -> None:
        """Shortened, not dropped: the device and the tail of its MAC stay,
        which is what tells one bench from the next one along."""
        self._write(
            out_path,
            RecordingMetadata(protocol=self.PROTOCOL, equipment=self.EQUIPMENT),
        )
        equipment = read_edf_metadata(out_path).equipment
        assert equipment.startswith("BITalino")
        assert equipment.endswith("44:E4")

    def test_the_shortening_is_said_out_loud(self, out_path: str) -> None:
        """Trimming is a decision; making it in silence is the bug."""
        notices = self._write(
            out_path,
            RecordingMetadata(protocol=self.PROTOCOL, equipment=self.EQUIPMENT),
        )
        assert notices, "the header was trimmed and nothing was logged"
        assert any("BITalino" in n for n in notices), notices

    def test_a_header_that_fits_is_left_alone(self, out_path: str) -> None:
        """No shortening, and nothing logged, when there is room for all."""
        notices = self._write(
            out_path,
            RecordingMetadata(protocol="iso 30 s", equipment="BITalino"),
        )
        meta = read_edf_metadata(out_path)
        assert meta.equipment == "BITalino"
        assert meta.protocol == "iso 30 s"
        assert notices == []

    def test_a_protocol_too_long_on_its_own_is_reported(
        self, out_path: str
    ) -> None:
        """The one case nothing can save. It still must not pass in silence."""
        protocol = "agonist/antagonist co-activation, elbow, three loads"
        notices = self._write(
            out_path,
            RecordingMetadata(protocol=protocol, equipment=self.EQUIPMENT),
        )
        assert notices, "the protocol was truncated and nothing was logged"
        assert any(str(len(protocol)) in n for n in notices), notices
        # Everything that could be given up, was: the protocol keeps the
        # whole budget, so what survives is as much of it as EDF+ allows.
        assert read_edf_metadata(out_path).protocol == protocol[
            :EDF_RECORDING_IDENT_BUDGET
        ]

    def test_the_budget_is_what_the_writer_actually_enforces(
        self, out_path: str
    ) -> None:
        """The constant is measured, not read off the specification, so it is
        pinned here: a pyedflib that changes the arithmetic fails this test
        rather than quietly starting to truncate protocols again."""
        equipment = "E" * EDF_RECORDING_IDENT_BUDGET
        protocol = "P"
        self._write(
            out_path,
            # Straight to the writer, past the fitting step, to ask edflib
            # itself where it cuts.
            RecordingMetadata(protocol="", equipment=equipment),
        )
        assert read_edf_metadata(out_path).equipment == equipment
        self._write(out_path, RecordingMetadata(protocol=protocol, equipment=equipment))
        meta = read_edf_metadata(out_path)
        assert len(meta.equipment) + len(meta.protocol) <= (
            EDF_RECORDING_IDENT_BUDGET
        )


@pytest.mark.parametrize("campo", ["student_name", "student_code"])
def test_the_recording_carries_the_code_and_not_the_name(tmp_path, campo) -> None:
    """What the acquisition tab writes, checked at the file.

    The student's name used to go into ``patientname``, so every recording
    carried it out of the laboratory — into the marking pile, into whatever
    gets shared with a colleague, into an archive. The tab no longer asks for
    it; both header fields carry the code, because EDF+ writes 'X' into an
    empty patientname and a patient block reading 'X' beside a code says less
    than one that says the code twice.
    """
    pytest.importorskip("pyedflib")
    import numpy as np

    from emgteach.io import (
        BufferedEdfWriter,
        ChannelInfo,
        RecordingMetadata,
        read_edf_metadata,
    )

    destino = tmp_path / "sesion.edf"
    meta = RecordingMetadata(student_name="A1", student_code="A1")
    with BufferedEdfWriter(
        str(destino),
        channels=[ChannelInfo("Muscle", dimension="mV", sample_frequency=1000)],
        metadata=meta,
    ) as w:
        w.add_samples(np.zeros(2000))
    leido = read_edf_metadata(destino)
    assert getattr(leido, campo) == "A1"
