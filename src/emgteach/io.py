"""EDF+ reading and buffered writing for biopotential streams.

This module provides:

- :class:`BufferedEdfWriter`, a context-manager that implements the
  buffer-then-flush pattern of Agis-Torres (2026) [1]_, which avoids
  the silent file-corruption pitfall that occurs when sub-record device
  blocks are written individually with ``pyedflib.EdfWriter.writeSamples``.
- :class:`RecordingMetadata`, the EDF+ identification header, fitted to
  :data:`EDF_RECORDING_IDENT_BUDGET` before it is written. The same family
  of defect one level up: the header block silently drops whatever runs past
  its budget, and the protocol is the field at the end of the queue.
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

import unicodedata
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

import numpy as np

from emgteach.i18n import tr


def ascii_label(label: str, limit: int = 16) -> str:
    """The channel label as the EDF header can hold it: printable ASCII,
    at most ``limit`` characters.

    EDF stores its labels in the 7-bit ASCII of 1992, and a name with an
    accent does not survive the trip: «Músculo» — the Spanish default for
    the single-muscle practical — came back from the file as «MA sculo».
    Accents are dropped rather than the letters that carry them, so the
    name still reads («Musculo», «Biceps»); what has no ASCII form at all
    becomes «?».
    """
    plano = unicodedata.normalize("NFKD", str(label))
    sin_acentos = "".join(c for c in plano if not unicodedata.combining(c))
    limpio = "".join(c if 32 <= ord(c) < 127 else "?" for c in sin_acentos)
    return limpio.strip()[:limit]

if TYPE_CHECKING:
    import numpy.typing as npt

    PathLike = str | Path
    FloatArray = npt.NDArray[np.float64]
    ArrayLike = npt.ArrayLike


__all__ = [
    "EDF_RECORDING_IDENT_BUDGET",
    "BufferedEdfWriter",
    "ChannelInfo",
    "RecordingMetadata",
    "assess_edf_channels",
    "build_timestamped_path",
    "create_edf_writer",
    "edf_duration",
    "find_edf_acc_channel",
    "list_edf_channels",
    "list_edf_emg_channels",
    "read_edf_metadata",
    "read_edf_mne",
    "read_edf_pyedflib",
    "write_edf_block",
]


# ---------------------------------------------------------------------------
# The EDF+ recording-identification budget
# ---------------------------------------------------------------------------

#: Characters the EDF+ *recording* identification block leaves for
#: ``admincode``, ``technician``, ``equipment`` and ``recording_additional``
#: between them — measured against the writer, not read off the specification.
#:
#: EDF+ gives the block eighty bytes, and pyedflib warns when the four values
#: plus ``"Startdate dd-MMM-yyyy"`` pass that mark. The underlying edflib is
#: stricter: it composes the field as ``Startdate dd-MMM-yyyy <admincode>
#: <technician> <equipment> <recording_additional>`` and stops at sixty-four,
#: leaving thirty-nine characters for the four values and cutting whatever
#: runs past — ``recording_additional`` last in the queue, so first to lose.
#:
#: Measured on ``emg_2026-08-31_19-33.edf`` (pyedflib 0.1.42): equipment
#: ``"BITalino (98:D3:91:FE:44:E4)"`` (28) plus protocol
#: ``"agonist/antagonist"`` (18) is 46 against a budget of 39, and
#: ``getRecordingAdditional()`` returned the 39 - 28 = 11 characters that fit,
#: ``"agonist/ant"``. pyedflib said nothing: its own formula scored that same
#: header at 69 of 80.
#:
#: Which is the failure mode this module already exists to document. The
#: buffered-write pitfall of Agis-Torres (2026) [1]_ corrupts a recording
#: without raising; this truncates a header without raising. Both produce a
#: file that opens cleanly and answers wrongly, and both are found late — a
#: protocol that no longer names the practice is noticed at marking, weeks
#: after the bench is gone.
EDF_RECORDING_IDENT_BUDGET = 39

#: Characters of a device identifier kept when the equipment string has to be
#: shortened. Five is the tail of a MAC address (``"44:E4"``) or of a serial
#: port — enough to tell one bench from the next, which is all the field is
#: read for once the recording is over.
EQUIPMENT_ID_TAIL = 5


def _compact_equipment(equipment: str) -> str:
    """Reduce a device string to its name plus the tail of its identifier.

    ``"BITalino (98:D3:91:FE:44:E4)"`` becomes ``"BITalino 44:E4"``: half the
    characters, and still the answer to "which bench was this?". Device names
    are built as ``"<name> (<identifier>)"`` by every backend
    (:mod:`emgteach.devices`), so the parenthesis is what gets squeezed.
    Returns the string unchanged when there is no parenthesised part to
    squeeze — the caller then falls back to a plain cut.
    """
    head, sep, rest = equipment.partition("(")
    if not sep:
        return equipment
    identifier = rest.rstrip().removesuffix(")").strip()
    return f"{head.strip()} {identifier[-EQUIPMENT_ID_TAIL:]}".strip()


# ---------------------------------------------------------------------------
# Channel metadata
# ---------------------------------------------------------------------------


#: How many EDF+ annotation signals to allocate. Each holds roughly five
#: annotations per second; see BufferedEdfWriter.__post_init__ for why this is
#: not one.
_ANNOTATION_SIGNALS = 4


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
            "label": ascii_label(self.label),
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
        EDF ``recording_additional``. Last in the recording block and so the
        first the writer cuts; :meth:`fit_to_edf_budget` is what stops that.
    technician : str
        Supervisor/technician -> EDF ``technician``.
    equipment : str
        Acquisition device description -> EDF ``equipment``. Shares
        :data:`EDF_RECORDING_IDENT_BUDGET` characters with ``technician`` and
        ``protocol``, and a real device string spends most of them on its own:
        ``"BITalino (98:D3:91:FE:44:E4)"`` is twenty-eight of thirty-nine.
    patient_additional : str
        Free note in the *patient* identification field -> EDF
        ``patient_additional``. A separate block with its own budget, and a
        far roomier one — seventy-one characters shared with
        ``student_name`` and ``student_code``, of which a session uses a
        handful. A note appended to the *recording* block instead would come
        out of the protocol's thirty-nine. This is where a derived file says
        it is derived.
    start_datetime : datetime, optional
        Recording start timestamp -> EDF ``startdatetime``. When ``None``
        pyedflib uses the current time.
    """

    student_name: str = ""
    student_code: str = ""
    protocol: str = ""
    technician: str = ""
    equipment: str = ""
    patient_additional: str = ""
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
                self.patient_additional,
                self.start_datetime is not None,
            )
        )

    def fit_to_edf_budget(self) -> tuple[RecordingMetadata, list[str]]:
        """Return these fields shortened to fit EDF+, and what that cost.

        ``technician``, ``equipment`` and ``protocol`` share
        :data:`EDF_RECORDING_IDENT_BUDGET` characters; past that the writer
        cuts the protocol, silently. So the decision is taken here instead,
        explicitly, and always the same way: **the protocol is never the field
        that gives way.** It is what names the practice, and it is the one
        thing that cannot be recovered from anywhere else — the device is on
        the bench and the supervisor signed the sheet, but "which exercise was
        this?" only the header answers.

        What gives way, in order: the equipment string is compacted to its
        name plus the tail of its identifier, then cut, then the technician is
        cut. Each step is reported. The ``patient_*`` fields are untouched —
        they live in their own eighty-character block, with room to spare.

        Returns
        -------
        (metadata, notices)
            A copy with whatever had to be shortened, and one line per
            shortening, ready for an acquisition log. ``notices`` is empty
            when everything fitted, which is the ordinary case.
        """
        notices: list[str] = []
        technician, equipment = self.technician, self.equipment
        spare = EDF_RECORDING_IDENT_BUDGET - len(self.protocol)

        if spare < 0:
            # Nothing can be given up on the protocol's behalf: it overruns
            # the whole block on its own. Hand it every character there is and
            # say plainly that it will still be cut.
            notices.append(
                tr(
                    "Warning — the protocol is {length} characters and the "
                    "EDF+ header has room for {budget}; it will be saved cut "
                    "short as \"{kept}\". Shorten it to keep it whole."
                ).format(
                    length=len(self.protocol),
                    budget=EDF_RECORDING_IDENT_BUDGET,
                    kept=self.protocol[:EDF_RECORDING_IDENT_BUDGET],
                )
            )
            return replace(self, technician="", equipment=""), notices

        if len(technician) + len(equipment) <= spare:
            return self, notices

        # The equipment goes first: shortened, it still names the bench.
        shortened = _compact_equipment(equipment)
        if len(technician) + len(shortened) > spare:
            shortened = shortened[: max(0, spare - len(technician))]
        if shortened != equipment:
            notices.append(
                tr(
                    "Warning — the EDF+ header shares {budget} characters "
                    "between equipment, supervisor and protocol. Equipment "
                    "shortened from \"{was}\" to \"{now}\" so the protocol "
                    "\"{protocol}\" is saved whole."
                ).format(
                    budget=EDF_RECORDING_IDENT_BUDGET,
                    was=equipment,
                    now=shortened,
                    protocol=self.protocol,
                )
            )
            equipment = shortened

        # Only reachable when the supervisor's name alone overruns what the
        # protocol left: by now the equipment is down to nothing.
        if len(technician) + len(equipment) > spare:
            technician = technician[: max(0, spare - len(equipment))]
            notices.append(
                tr(
                    "Warning — supervisor shortened to \"{now}\" so the "
                    "protocol \"{protocol}\" is saved whole."
                ).format(now=technician, protocol=self.protocol)
            )

        return replace(self, technician=technician, equipment=equipment), notices

    def apply_to(self, writer: Any) -> list[str]:
        """Push the non-empty fields onto a ``pyedflib.EdfWriter``.

        Must be called before any sample is written (header is fixed once
        data records begin). Unknown setters are ignored defensively so a
        pyedflib version lacking one does not abort a recording.

        Fields are fitted to the EDF+ budget first
        (:meth:`fit_to_edf_budget`); the returned lines say what that cost,
        and are meant for the acquisition log. Trimming a header is a fair
        decision to have to make — making it without saying so is the bug.
        """
        fitted, notices = self.fit_to_edf_budget()
        setters = {
            "setPatientName": fitted.student_name,
            "setPatientCode": fitted.student_code,
            "setRecordingAdditional": fitted.protocol,
            "setPatientAdditional": fitted.patient_additional,
            "setTechnician": fitted.technician,
            "setEquipment": fitted.equipment,
        }
        for name, value in setters.items():
            if value and hasattr(writer, name):
                try:
                    getattr(writer, name)(value)
                except Exception:  # pragma: no cover — defensive
                    pass
        if fitted.start_datetime is not None and hasattr(writer, "setStartdatetime"):
            try:
                writer.setStartdatetime(fitted.start_datetime)
            except Exception:  # pragma: no cover — defensive
                pass
        return notices


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
    #: What fitting the identification header to EDF+ cost, one line per
    #: field shortened (see :meth:`RecordingMetadata.fit_to_edf_budget`).
    #: Empty unless something had to give. Callers with a log — the
    #: acquisition worker — are expected to show these: the budget is real,
    #: the trimming is fine, doing it in silence is what is not.
    header_notices: list[str] = field(default_factory=list, init=False)
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
        # EDF+ stores annotations inside the data records, so their capacity is
        # a *rate*, not a total: with the single annotation signal pyedflib
        # allocates by default, roughly five annotations per second survive and
        # the rest are dropped without an error — the same silent-loss family as
        # the buffered-write defect. A two-phase session can put four marks in
        # one second (the end of a calibration repetition, the next start, a
        # phase change), one short of the cliff; a derived file that rewrites
        # them all is well past it. Four signals lift the ceiling to about
        # twenty per second.
        self._writer.set_number_of_annotation_signals(_ANNOTATION_SIGNALS)
        self._writer.setSignalHeaders([ch.to_pyedflib_header() for ch in self.channels])

        # EDF+ identification header (student, protocol, ...) before any data.
        if self.metadata is not None and not self.metadata.is_empty():
            self.header_notices = self.metadata.apply_to(self._writer)

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


def read_edf_markers(path: PathLike) -> list[tuple[float, str]]:
    """Return an EDF+ file's annotations as ``(seconds, text)``.

    Reads the annotation table alone, without loading a single sample: what a
    tab needs when it is asking a file a question about the session — was an
    MVC calibrated? which loads were used? — before deciding what to offer.
    Returns an empty list for a file with no annotations, or one that cannot
    be opened; the caller is asking, not requiring.
    """
    import pyedflib

    try:
        reader = pyedflib.EdfReader(str(path))
    except Exception:
        return []
    try:
        onsets, _, descriptions = reader.readAnnotations()
    except Exception:  # pragma: no cover — defensive
        return []
    finally:
        reader.close()
    return [
        (float(o), str(d)) for o, d in zip(onsets, descriptions, strict=False)
    ]


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


def find_edf_acc_channel(path: PathLike) -> tuple[str, str] | None:
    """Locate the accelerometer channel in an EDF and infer its placement.

    Returns ``(label, placement)`` where ``placement`` is ``"muscle"``,
    ``"limb"`` or ``"unknown"`` (parsed from the label the acquisition tab
    writes, e.g. ``"ACC (muscle)"`` / ``"ACC (limb)"``), or ``None`` if the
    file has no accelerometer channel. The ACC channel is the one whose
    physical dimension is ``"g"`` (falling back to a label starting with
    ``"ACC"``).
    """
    import pyedflib

    try:
        reader = pyedflib.EdfReader(str(path))
    except Exception:  # pragma: no cover — unreadable/missing file
        return None
    try:
        labels = reader.getSignalLabels()
        headers = reader.getSignalHeaders()
        for label, header in zip(labels, headers, strict=False):
            name = str(label).strip()
            dim = str(
                header.get("dimension", header.get("physical_dimension", ""))
            ).strip().lower()
            if dim == "g" or name.upper().startswith("ACC"):
                low = name.lower()
                if "musc" in low or "músc" in low:
                    placement = "muscle"
                elif "limb" in low or "segment" in low or "segmento" in low:
                    placement = "limb"
                else:
                    placement = "unknown"
                return name, placement
        return None
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

    from emgteach.dsp import DEFAULT_PHYSICAL_MAX_MV, assess_channel_quality

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
            pmax = float(
                header.get("physical_max", DEFAULT_PHYSICAL_MAX_MV)
                or DEFAULT_PHYSICAL_MAX_MV
            )
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
            # The getter, not the ``patient_additional`` attribute beside it:
            # that one is the raw eighty-byte field, and it comes back as the
            # repr of a padded bytes object.
            patient_additional=str(reader.getPatientAdditional() or "").strip(),
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
