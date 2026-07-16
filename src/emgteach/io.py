"""EDF+ reading and buffered writing for biopotential streams.

This module provides:

- :class:`BufferedEdfWriter`, a context-manager that implements the
  buffer-then-flush pattern of Agis-Torres (2026) [1]_, which avoids
  the silent file-corruption pitfall that occurs when sub-record device
  blocks are written individually with ``pyedflib.EdfWriter.writeSamples``.
- Two reader functions (:func:`read_edf_mne` and
  :func:`read_edf_pyedflib`) that return a uniform dictionary so the
  rest of the package does not depend on which reader is used.
- Lower-level helpers (:func:`build_timestamped_path`,
  :func:`create_edf_writer`, :func:`write_edf_block`) kept for
  backward compatibility with the prototype acquisition tab.

References
----------
.. [1] Agis-Torres Á. (2026). Silent corruption of EDF recordings during
   real-time biopotential streaming: a buffered-write solution.
   Reproducibility package: https://doi.org/10.5281/zenodo.20042878
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

    PathLike = str | Path
    FloatArray = npt.NDArray[np.float64]
    ArrayLike = npt.ArrayLike


__all__ = [
    "BufferedEdfWriter",
    "ChannelInfo",
    "RecordingMetadata",
    "assess_edf_channels",
    "build_timestamped_path",
    "create_edf_writer",
    "edf_duration",
    "list_edf_channels",
    "list_edf_emg_channels",
    "read_edf_metadata",
    "read_edf_mne",
    "read_edf_pyedflib",
    "write_edf_block",
]


# ---------------------------------------------------------------------------
# Channel metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChannelInfo:
    """Metadata for a single EDF+ channel.

    Defaults match the BITalino-compatible 3.3 V, 10-bit ADC range used
    in the prototype acquisition app. Override :attr:`physical_min` /
    :attr:`physical_max` for the Arduino + MyoWare backend (5 V range)
    or any other hardware.

    Attributes
    ----------
    label : str
        Channel name written to the EDF header (e.g. ``"EMG"``).
    dimension : str
        Physical units, e.g. ``"mV"``.
    physical_min, physical_max : float
        Range of the analogue signal in physical units.
    digital_min, digital_max : int
        Range of the raw ADC integer values.
    sample_frequency : int
        Sampling rate in Hz. Must equal samples-per-record so that one
        EDF data record matches one second of signal.
    """

    label: str
    dimension: str = "mV"
    physical_min: float = -3.3
    physical_max: float = 3.3
    digital_min: int = 0
    digital_max: int = 1023
    sample_frequency: int = 1000

    def to_pyedflib_header(self) -> dict[str, Any]:
        """Return the header dict expected by ``pyedflib.EdfWriter.setSignalHeader``."""
        return {
            "label": self.label,
            "dimension": self.dimension,
            "sample_frequency": self.sample_frequency,
            "physical_min": self.physical_min,
            "physical_max": self.physical_max,
            "digital_min": self.digital_min,
            "digital_max": self.digital_max,
        }


@dataclass(frozen=True)
class RecordingMetadata:
    """Optional EDF+ header identification for a teaching session.

    Maps the lab's real-world fields (who recorded, which protocol, when)
    onto the standard EDF+ patient/recording header so a saved ``.edf`` is
    self-describing and a report can name the student and protocol without
    a side-car file.

    Attributes
    ----------
    student_name : str
        Student's name -> EDF ``patientname``.
    student_code : str
        Student's code/ID -> EDF ``patientcode``.
    protocol : str
        Protocol description (e.g. "Isometric biceps, 30 s") ->
        EDF ``recording_additional``.
    technician : str
        Supervisor/technician -> EDF ``technician``.
    equipment : str
        Acquisition device description -> EDF ``equipment``.
    start_datetime : datetime, optional
        Recording start timestamp -> EDF ``startdatetime``. When ``None``
        pyedflib uses the current time.
    """

    student_name: str = ""
    student_code: str = ""
    protocol: str = ""
    technician: str = ""
    equipment: str = ""
    start_datetime: datetime | None = None

    def is_empty(self) -> bool:
        """``True`` if no field carries information worth writing."""
        return not any(
            (
                self.student_name,
                self.student_code,
                self.protocol,
                self.technician,
                self.equipment,
                self.start_datetime is not None,
            )
        )

    def apply_to(self, writer: Any) -> None:
        """Push the non-empty fields onto a ``pyedflib.EdfWriter``.

        Must be called before any sample is written (header is fixed once
        data records begin). Unknown setters are ignored defensively so a
        pyedflib version lacking one does not abort a recording.
        """
        setters = {
            "setPatientName": self.student_name,
            "setPatientCode": self.student_code,
            "setRecordingAdditional": self.protocol,
            "setTechnician": self.technician,
            "setEquipment": self.equipment,
        }
        for name, value in setters.items():
            if value and hasattr(writer, name):
                try:
                    getattr(writer, name)(value)
                except Exception:  # pragma: no cover — defensive
                    pass
        if self.start_datetime is not None and hasattr(writer, "setStartdatetime"):
            try:
                writer.setStartdatetime(self.start_datetime)
            except Exception:  # pragma: no cover — defensive
                pass


# ---------------------------------------------------------------------------
# Buffered EDF+ writer (the central contribution)
# ---------------------------------------------------------------------------


@dataclass
class BufferedEdfWriter:
    """Context-manager EDF+ writer using the buffer-then-flush pattern.

    The writer is intended for **real-time acquisition** where the
    hardware delivers blocks shorter than the EDF data record. It
    accumulates samples in per-channel NumPy buffers and flushes one
    full record (``sample_frequency`` samples per channel) at a time.
    On close it pads any trailing remainder with the **last acquired
    value** (not zero) to avoid introducing a spectral discontinuity
    at the end of the recording.

    This pattern is the reference implementation of Agis-Torres (2026)
    [1]_ and is the safe alternative to calling
    ``pyedflib.EdfWriter.writeSamples`` once per device read with
    blocks shorter than ``fs`` samples.

    Parameters
    ----------
    path : str or pathlib.Path
        Output file path. Parent directory must exist.
    channels : sequence of ChannelInfo
        One ChannelInfo per channel to record. All channels must share
        the same ``sample_frequency``.

    Examples
    --------
    Single-channel acquisition at 1 kHz with 100 ms device blocks:

    >>> import numpy as np
    >>> from emgteach.io import BufferedEdfWriter, ChannelInfo
    >>> samples = np.random.randn(10_000) * 0.05  # 10 s of synthetic noise
    >>> ch = ChannelInfo(label="EMG", sample_frequency=1000)
    >>> with BufferedEdfWriter("session.edf", channels=[ch]) as writer:
    ...     for i in range(0, len(samples), 100):  # 100-sample blocks
    ...         writer.add_samples(samples[i : i + 100])

    Multi-channel acquisition (raw + filtered + envelope):

    >>> chs = [
    ...     ChannelInfo("EMG"),
    ...     ChannelInfo("EMG_Filtered"),
    ...     ChannelInfo("EMG_Envelope", physical_min=0.0),
    ... ]
    >>> with BufferedEdfWriter("session.edf", channels=chs) as writer:
    ...     writer.add_samples(raw_block, filtered_block, envelope_block)

    References
    ----------
    .. [1] Agis-Torres Á. (2026). Silent corruption of EDF recordings
       during real-time biopotential streaming: a buffered-write
       solution. Reproducibility package:
       https://doi.org/10.5281/zenodo.20042878
    """

    path: PathLike
    channels: Sequence[ChannelInfo]
    metadata: RecordingMetadata | None = None
    _writer: Any = field(default=None, init=False, repr=False)
    _buffers: list[FloatArray] = field(default_factory=list, init=False, repr=False)
    _fs: int = field(default=0, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        import pyedflib  # lazy import — keeps test collection fast

        if not self.channels:
            raise ValueError("BufferedEdfWriter requires at least one channel.")
        fss = {ch.sample_frequency for ch in self.channels}
        if len(fss) != 1:
            raise ValueError(
                "All channels must share the same sample_frequency; "
                f"got {sorted(fss)}."
            )
        self._fs = fss.pop()

        n = len(self.channels)
        self._writer = pyedflib.EdfWriter(
            str(self.path), n, file_type=pyedflib.FILETYPE_EDFPLUS
        )
        self._writer.setSignalHeaders([ch.to_pyedflib_header() for ch in self.channels])

        # EDF+ identification header (student, protocol, ...) before any data.
        if self.metadata is not None and not self.metadata.is_empty():
            self.metadata.apply_to(self._writer)

        # One pending-samples buffer per channel
        self._buffers = [np.array([], dtype=np.float64) for _ in self.channels]

    # -- context-manager protocol --------------------------------------------

    def __enter__(self) -> BufferedEdfWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- public API -----------------------------------------------------------

    @property
    def sample_frequency(self) -> int:
        """Sampling frequency shared by every channel (Hz)."""
        return self._fs

    def add_samples(self, *blocks: ArrayLike) -> None:
        """Append a device block to each channel buffer and flush full records.

        Parameters
        ----------
        *blocks : array-like
            One 1-D array per channel, in the same order as
            ``channels`` was passed to the constructor. All blocks must
            have the same length.

        Raises
        ------
        RuntimeError
            If the writer has been closed.
        ValueError
            If the number of blocks does not match the number of
            channels, or if the blocks have different lengths.
        """
        if self._closed:
            raise RuntimeError("Cannot add samples after the writer has been closed.")
        if len(blocks) != len(self.channels):
            raise ValueError(
                f"Got {len(blocks)} blocks but writer has "
                f"{len(self.channels)} channel(s)."
            )

        arrays = [np.asarray(b, dtype=np.float64).ravel() for b in blocks]
        sizes = {a.size for a in arrays}
        if len(sizes) != 1:
            raise ValueError(
                f"All channel blocks must have the same length; got sizes {sorted(sizes)}."
            )

        for i, incoming in enumerate(arrays):
            self._buffers[i] = np.concatenate([self._buffers[i], incoming])

        # Flush as many complete records as the buffer can supply, in lockstep
        while all(buf.size >= self._fs for buf in self._buffers):
            record = [buf[: self._fs] for buf in self._buffers]
            self._writer.writeSamples(record)
            self._buffers = [buf[self._fs :] for buf in self._buffers]

    def add_annotation(self, onset_s: float, description: str) -> None:
        """Write an EDF+ annotation (event marker) at *onset_s* seconds.

        Annotations are written immediately to the underlying file with
        a duration of ``-1`` (instantaneous event), as is conventional
        for EMG event markers (contraction onset, fatigue, rest).

        Parameters
        ----------
        onset_s : float
            Time of the event in seconds from the start of the recording.
        description : str
            Free-text label, e.g. ``"contraction_onset"``.

        Raises
        ------
        RuntimeError
            If the writer has already been closed.
        """
        if self._closed:
            raise RuntimeError("Cannot add annotations after close().")
        self._writer.writeAnnotation(float(onset_s), -1, str(description))

    def close(self) -> None:
        """Flush the trailing remainder and close the underlying file.

        The trailing samples (fewer than ``sample_frequency`` per
        channel) are padded with the **last acquired value** of each
        channel, never with zero, to avoid introducing a step
        discontinuity in the final record.

        Calling :meth:`close` more than once is safe (a no-op after
        the first call).
        """
        if self._closed:
            return
        try:
            remainder = self._buffers[0].size  # all buffers have the same size
            if remainder > 0:
                pad_n = self._fs - remainder
                tail_records: list[FloatArray] = []
                for buf in self._buffers:
                    last_value = float(buf[-1])
                    pad = np.full(pad_n, last_value, dtype=np.float64)
                    tail_records.append(np.concatenate([buf, pad]))
                self._writer.writeSamples(tail_records)
        finally:
            self._writer.close()
            self._closed = True


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------


def read_edf_mne(path: PathLike, channel_name: str) -> dict[str, Any]:
    """Read one channel from an EDF+ file using MNE.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the EDF+ file.
    channel_name : str
        Label of the channel to extract (must match the EDF header).

    Returns
    -------
    dict
        Dictionary with keys ``emg_raw`` (1-D array of mV),
        ``sfreq`` (float), ``times`` (1-D array of seconds),
        ``ch_names`` (list of strings) and ``markers``
        (list of (onset_s, description) tuples).

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If ``channel_name`` is not present in the file.
    RuntimeError
        For any other error raised by MNE while reading.
    """
    import mne  # lazy import — keeps test collection fast

    spath = str(path)
    try:
        raw = mne.io.read_raw_edf(spath, preload=True, verbose=False)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"EDF file not found: '{spath}'") from exc
    except Exception as exc:  # pragma: no cover — defensive
        raise RuntimeError(f"MNE failed to read the EDF file: {exc}") from exc

    if channel_name not in raw.ch_names:
        raise ValueError(
            f"Channel '{channel_name}' not found. "
            f"Available channels: {raw.ch_names}"
        )

    emg_raw = raw.get_data(picks=channel_name)[0] * 1e3  # MNE returns V; convert to mV
    markers: list[tuple[float, str]] = []
    try:
        markers = [
            (float(ann["onset"]), str(ann["description"])) for ann in raw.annotations
        ]
    except Exception:  # pragma: no cover — empty annotations
        pass

    return {
        "emg_raw": emg_raw,
        "sfreq": float(raw.info["sfreq"]),
        "times": raw.times,
        "ch_names": raw.ch_names,
        "markers": markers,
    }


def read_edf_pyedflib(path: PathLike, channel_index: int = 0) -> dict[str, Any]:
    """Read one channel from an EDF+ file using ``pyedflib``'s highlevel API.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the EDF+ file.
    channel_index : int, optional
        Index of the channel to extract (default 0).

    Returns
    -------
    dict
        Dictionary with keys ``emg_raw`` (1-D array in physical units),
        ``sfreq`` (float), ``dimension`` (str, e.g. ``"mV"``),
        ``tiempo`` (1-D array of seconds) and ``markers``.
    """
    import pyedflib
    from pyedflib import highlevel

    spath = str(path)
    try:
        signals, headers, _ = highlevel.read_edf(spath)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"EDF file not found: '{spath}'") from exc
    except Exception as exc:  # pragma: no cover — defensive
        raise RuntimeError(f"pyedflib failed to read the EDF file: {exc}") from exc

    if channel_index >= len(signals):
        raise ValueError(
            f"Channel index {channel_index} out of range "
            f"(file has {len(signals)} channel(s))."
        )

    emg_raw = signals[channel_index]
    sfreq = float(headers[channel_index].get("sample_frequency", 1000))
    dimension = headers[channel_index].get("physical_dimension", "mV")
    tiempo = np.arange(len(emg_raw)) / sfreq

    markers: list[tuple[float, str]] = []
    try:
        reader = pyedflib.EdfReader(spath)
        onsets, _, descriptions = reader.readAnnotations()
        reader.close()
        markers = [
            (float(o), str(d)) for o, d in zip(onsets, descriptions, strict=False)
        ]
    except Exception:  # pragma: no cover — files without annotations
        pass

    return {
        "emg_raw": emg_raw,
        "sfreq": sfreq,
        "dimension": dimension,
        "tiempo": tiempo,
        "markers": markers,
    }


def list_edf_channels(path: PathLike) -> list[str]:
    """Return the channel labels of an EDF file (reads the header only).

    Fast: it opens the file just long enough to read the signal headers,
    so it is suitable for populating a channel picker in the GUI.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the EDF+ file.

    Returns
    -------
    list of str
        The channel labels in file order, or an empty list if the file
        cannot be read.
    """
    import pyedflib

    try:
        reader = pyedflib.EdfReader(str(path))
    except Exception:  # pragma: no cover — unreadable/missing file
        return []
    try:
        return [str(label) for label in reader.getSignalLabels()]
    finally:
        reader.close()


def list_edf_emg_channels(path: PathLike) -> list[str]:
    """Return only the EMG channel labels of an EDF file.

    Non-biopotential channels — currently the accelerometer, written with the
    physical dimension ``"g"`` (or the label ``"ACC"``) — are excluded, so a
    channel picker offers only the muscle channels (e.g. EMG1/EMG2) and the
    "one or two channels" logic is not confused by an extra movement channel.
    Falls back to an empty list if the file cannot be read.
    """
    import pyedflib

    try:
        reader = pyedflib.EdfReader(str(path))
    except Exception:  # pragma: no cover — unreadable/missing file
        return []
    try:
        labels = reader.getSignalLabels()
        headers = reader.getSignalHeaders()
        out: list[str] = []
        for label, header in zip(labels, headers, strict=False):
            dim = str(
                header.get("dimension", header.get("physical_dimension", ""))
            ).strip().lower()
            if dim == "g" or str(label).strip().upper() == "ACC":
                continue
            out.append(str(label))
        return out
    finally:
        reader.close()


def assess_edf_channels(path: PathLike) -> list[tuple[str, str]]:
    """Per-EMG-channel quality verdict for a file, for a warning on load.

    Returns ``[(label, status), ...]`` where ``status`` is one of ``"ok"``,
    ``"flat"``, ``"weak"`` or ``"saturated"`` (see
    :func:`emgteach.dsp.assess_channel_quality`). Non-biopotential channels
    (the accelerometer, dimension ``"g"``/label ``"ACC"``) and the annotation
    channel are skipped. Returns an empty list if the file cannot be read.
    """
    import pyedflib

    from emgteach.dsp import assess_channel_quality

    try:
        reader = pyedflib.EdfReader(str(path))
    except Exception:  # pragma: no cover — unreadable/missing file
        return []
    try:
        labels = reader.getSignalLabels()
        headers = reader.getSignalHeaders()
        out: list[tuple[str, str]] = []
        for i, (label, header) in enumerate(zip(labels, headers, strict=False)):
            name = str(label).strip()
            dim = str(
                header.get("dimension", header.get("physical_dimension", ""))
            ).strip().lower()
            if dim == "g" or name.upper() in ("ACC", "EDF ANNOTATIONS"):
                continue
            fs = float(header.get("sample_frequency", 1000) or 1000)
            pmax = float(header.get("physical_max", 1.65) or 1.65)
            status = assess_channel_quality(reader.readSignal(i), fs, pmax)
            out.append((str(label), status))
        return out
    finally:
        reader.close()


def read_edf_metadata(path: PathLike) -> RecordingMetadata:
    """Read the EDF+ identification header (student, protocol, ...).

    Header-only and defensive: returns an empty :class:`RecordingMetadata`
    if the file cannot be read, so callers can show whatever is present
    without special-casing missing fields.
    """
    import pyedflib

    try:
        reader = pyedflib.EdfReader(str(path))
    except Exception:  # pragma: no cover — unreadable/missing file
        return RecordingMetadata()
    try:
        try:
            start_dt: datetime | None = reader.getStartdatetime()
        except Exception:  # pragma: no cover — reader without the getter
            start_dt = None
        return RecordingMetadata(
            student_name=str(reader.getPatientName() or ""),
            student_code=str(reader.getPatientCode() or ""),
            protocol=str(reader.getRecordingAdditional() or ""),
            technician=str(reader.getTechnician() or ""),
            equipment=str(reader.getEquipment() or ""),
            start_datetime=start_dt,
        )
    finally:
        reader.close()


def edf_duration(path: PathLike) -> float:
    """Return the recording duration in seconds (reads the header only).

    Fast enough for GUI use (e.g. to bound a region-of-interest control):
    it opens the file only to read ``getFileDuration``. Returns ``0.0`` if
    the file cannot be read.
    """
    import pyedflib

    try:
        reader = pyedflib.EdfReader(str(path))
    except Exception:  # pragma: no cover — unreadable/missing file
        return 0.0
    try:
        return float(reader.getFileDuration())
    finally:
        reader.close()


# ---------------------------------------------------------------------------
# Lower-level helpers (kept for backward compatibility with the prototype)
# ---------------------------------------------------------------------------


def build_timestamped_path(
    directory: PathLike = ".",
    *,
    prefix: str = "emg",
    suffix: str = ".edf",
) -> str:
    """Generate a timestamped filename inside ``directory``.

    The timestamp uses the ``%Y-%m-%d_%H-%M`` format. Useful for the
    acquisition tab to avoid overwriting previous sessions.

    Parameters
    ----------
    directory : str or pathlib.Path, optional
        Target directory (default ``"."``).
    prefix : str, optional
        Filename prefix (default ``"emg"``).
    suffix : str, optional
        File extension including the dot (default ``".edf"``).

    Returns
    -------
    str
        Path of the form ``<directory>/<prefix>_YYYY-MM-DD_HH-MM<suffix>``.
    """
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return str(Path(directory) / f"{prefix}_{ts}{suffix}")


def create_edf_writer(path: PathLike, fs: int) -> Any:
    """Create a 3-channel ``pyedflib.EdfWriter`` for the EMG schema.

    Channels are: ``EMG`` (raw mV), ``EMG_Filtered`` (mV, after notch +
    band-pass), ``EMG_Envelope`` (mV, rectified + low-pass).

    The caller is responsible for closing the writer.

    .. deprecated::
        Use :class:`BufferedEdfWriter` instead. This helper returns a
        raw ``pyedflib.EdfWriter`` whose per-block ``writeSamples`` use
        is the very stream-and-write antipattern that silently corrupts
        recordings (Agis-Torres 2026); :class:`BufferedEdfWriter`
        implements the safe buffer-then-flush pattern. Kept only for
        backward compatibility with the original prototype.

    Parameters
    ----------
    path : str or pathlib.Path
        Output path.
    fs : int
        Sampling rate in Hz (samples per record).

    Returns
    -------
    pyedflib.EdfWriter
        Configured writer ready for ``writeSamples`` calls.
    """
    warnings.warn(
        "create_edf_writer() is deprecated; use BufferedEdfWriter, which "
        "implements the safe buffer-then-flush pattern (Agis-Torres 2026).",
        DeprecationWarning,
        stacklevel=2,
    )
    import pyedflib

    writer = pyedflib.EdfWriter(str(path), 3, file_type=pyedflib.FILETYPE_EDFPLUS)
    channel_info = [
        ChannelInfo("EMG", sample_frequency=fs).to_pyedflib_header(),
        ChannelInfo("EMG_Filtered", sample_frequency=fs).to_pyedflib_header(),
        ChannelInfo(
            "EMG_Envelope", physical_min=0.0, sample_frequency=fs
        ).to_pyedflib_header(),
    ]
    writer.setSignalHeaders(channel_info)
    return writer


def write_edf_block(
    writer: Any,
    emg_mv: ArrayLike,
    emg_filtered: ArrayLike,
    emg_envelope: ArrayLike,
) -> None:
    """Write one block of samples to an open ``pyedflib.EdfWriter``.

    Caller must guarantee that ``len(emg_mv) == len(emg_filtered) ==
    len(emg_envelope)`` and is a multiple of the writer's
    samples-per-record.

    .. deprecated::
        Use :class:`BufferedEdfWriter` instead. Calling ``writeSamples``
        with blocks shorter than one data record is the stream-and-write
        antipattern that silently corrupts EDF recordings (Agis-Torres
        2026). Kept only for backward compatibility with the prototype.
    """
    warnings.warn(
        "write_edf_block() is deprecated; use BufferedEdfWriter, which "
        "implements the safe buffer-then-flush pattern (Agis-Torres 2026).",
        DeprecationWarning,
        stacklevel=2,
    )
    writer.writeSamples(
        [
            np.asarray(emg_mv, dtype=np.float64),
            np.asarray(emg_filtered, dtype=np.float64),
            np.asarray(emg_envelope, dtype=np.float64),
        ]
    )
