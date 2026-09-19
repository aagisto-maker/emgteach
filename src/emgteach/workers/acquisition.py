"""Background worker for real-time EMG acquisition.

This is the on-line counterpart of the offline analysis worker.
:class:`AcquisitionWorker` runs on its own QThread so the GUI never
blocks while data is being read from the device. It accepts any
:class:`emgteach.devices.AcquisitionDevice`, applies the streaming
DSP pipeline (notch + band-pass + envelope) and persists every block
to an EDF+ file using the buffered-write pattern of Agis-Torres
(2026), exposed as :class:`emgteach.io.BufferedEdfWriter`.

The worker exposes two stop commands. :meth:`stop` is the orderly
request; :meth:`stop_forced` adds a call to the device's
``force_close``, which is the watchdog hook used to release a
:meth:`AcquisitionDevice.read` that has blocked due to a silently
dropped Bluetooth link.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QMutex, QThread, Signal, Slot

from emgteach.dsp import OnsetDetector, RealtimeFilterState
from emgteach.i18n import tr
from emgteach.io import (
    BufferedEdfWriter,
    ChannelInfo,
    RecordingMetadata,
    build_timestamped_path,
)
from emgteach.profiles import EMG_PROFILE, SignalProfile
from emgteach.recovery import sidecar_path

if TYPE_CHECKING:
    from emgteach.devices import AcquisitionDevice


def mensaje_fallo_guardado(ruta: str | Path, motivo: object) -> str:
    """What the operator reads when a recording cannot be written.

    The writer's own words — «can not open file, no such file or directory» —
    used to reach the screen as the whole message: no file, no folder and
    nothing to do next, so what got written down was «not found» and the fix
    was found by trying another name. The message now names the file and the
    folder, keeps the system's reason, and says what to do.
    """
    p = Path(str(ruta))
    razon = getattr(motivo, "strerror", None) or str(motivo)
    return tr(
        "The recording «{name}» could not be saved in the folder {folder} "
        "({reason}). Choose another folder — Documents, for example — or "
        "another name, and press record again."
    ).format(name=p.name, folder=str(p.parent), reason=razon)


class AcquisitionWorker(QThread):
    """QThread that streams from an :class:`AcquisitionDevice` to an EDF+ file.

    Signals
    -------
    data_ready : dict
        Emitted on every acquired block with keys ``raw_mv``,
        ``filtered`` and ``envelope``; each value is a list holding one
        1-D NumPy array per channel (length ``device.n_channels``).
    log : str
        Human-readable status updates for the log widget.
    finished_ok : str
        Emitted at the end of a normal run with the EDF file path.
    error : str
        Emitted if the device or the writer raises.
    marker_added : (float, str)
        Emitted whenever :meth:`add_marker` records an event.

    Parameters
    ----------
    device : AcquisitionDevice
        Any concrete backend (Arduino, BITalino, ...). The worker only
        uses the abstract interface, so adding a new backend does not
        require any change here.
    save_dir : str, optional
        Directory in which to create the EDF file (default ``"."``). Used
        only when ``save_path`` is not given.
    save_path : str, optional
        Full path (folder + file name) for the EDF file. When given it takes
        precedence over ``save_dir`` and the timestamped auto-name, so the
        user can choose exactly where and under what name the recording is
        saved (like the "Save as…" dialogs). Its parent folder is created if
        needed.
    n_per_read : int, optional
        Number of samples to request per ``device.read`` call (default
        100, i.e. 100 ms at 1 kHz).
    f_low, f_high, f_notch, f_env : float, optional
        DSP cut-offs forwarded to :class:`RealtimeFilterState`. When left
        as ``None`` they default to the corresponding values of ``profile``.
    profile : SignalProfile, optional
        Biopotential profile providing the default filter cut-offs and
        the derived EDF channel schema (default :data:`EMG_PROFILE`).
    sensor_labels : sequence of str, optional
        One base label per hardware channel (e.g. ``["Agonista",
        "Antagonista"]``). Length must equal ``device.n_channels``. When
        omitted, a single-channel device uses the profile's ``raw_label``
        and a multi-channel device gets auto-generated labels.
    auto_detect : bool, optional
        When ``True``, run per-channel automatic contraction-onset
        detection on the envelope and record each onset as an automatic
        marker (``"Inicio (auto)"``) written to the EDF (default ``False``).
    onset_k : float, optional
        Onset-detection sensitivity in baseline standard deviations.
        Defaults to the profile's ``onset_k`` when ``None``.
    parent : QObject, optional
        Parent in the Qt object tree.
    """

    data_ready = Signal(dict)
    log = Signal(str)
    finished_ok = Signal(str)
    error = Signal(str)
    marker_added = Signal(float, str)
    marker_removed = Signal(float, str)

    def __init__(
        self,
        device: AcquisitionDevice,
        save_dir: str = ".",
        save_path: str | None = None,
        n_per_read: int = 100,
        f_low: float | None = None,
        f_high: float | None = None,
        f_notch: float | None = None,
        f_env: float | None = None,
        profile: SignalProfile = EMG_PROFILE,
        sensor_labels: list[str] | None = None,
        auto_detect: bool = False,
        onset_k: float | None = None,
        metadata: RecordingMetadata | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._device = device
        self._save_dir = save_dir
        self._save_path = save_path
        self._metadata = metadata
        self._n_per_read = int(n_per_read)
        self._profile = profile
        self._sensor_labels = list(sensor_labels) if sensor_labels else None
        self._f_low = float(f_low) if f_low is not None else profile.f_low
        self._f_high = float(f_high) if f_high is not None else profile.f_high
        self._f_notch = float(f_notch) if f_notch is not None else profile.f_notch
        self._f_env = float(f_env) if f_env is not None else profile.f_env
        self._auto_detect = bool(auto_detect)
        self._onset_k = float(onset_k) if onset_k is not None else profile.onset_k

        self._running = False
        self._opening = False
        self._streaming = False
        self._n_samples_total: int = 0
        self._markers: list[tuple[float, str]] = []
        self._markers_mutex = QMutex()
        self._last_sample_time: float | None = None
        self._write_failed = False
        self._rearm_onsets = False
        # The marks' mirror on disk, open while a recording is (see
        # emgteach.recovery). Guarded by the markers' mutex.
        self._sidecar = None

    # -- public control ------------------------------------------------------

    def stop(self) -> None:
        """Request a clean stop; the thread finishes the current block."""
        self._running = False

    @Slot()
    def rearm_onsets(self) -> None:
        """Measure the onset detectors' resting level again, from the next block.

        Called by the tab at the start of the recording phase, whose first
        second — after the countdown — is rest; the stream's first second,
        which set the threshold until now, is the start of the warm-up.
        """
        self._rearm_onsets = True

    def stop_forced(self) -> None:
        """Emergency stop: also closes the device socket from this thread.

        This is the watchdog hook: if :meth:`AcquisitionDevice.read` is
        blocked due to a dropped link, calling
        :meth:`AcquisitionDevice.force_close` releases the read with
        an exception, allowing the worker to finish.
        """
        self._running = False
        self._device.force_close()

    def is_opening(self) -> bool:
        """``True`` while the device is being opened (no samples yet)."""
        return self._opening

    def is_streaming(self) -> bool:
        """``True`` once the first ``read`` has succeeded."""
        return self._streaming

    def time_since_last_sample(self) -> float:
        """Seconds elapsed since the last successful ``device.read``.

        Returns ``+inf`` before the first read, so the GUI watchdog
        does not fire during the (potentially long) connection phase.
        """
        t = self._last_sample_time
        if t is None:
            return float("inf")
        return time.monotonic() - t

    @Slot(str)
    def instruct(self, channel_index: int, level: float | None) -> None:
        """Tell the device what is being asked of a muscle right now.

        Thread-safe in the same way as :meth:`add_marker`: called from the
        Qt thread while the worker reads. A device that can act on it does
        so by writing one attribute, which the next block reads; one that
        cannot — a board — does nothing (:meth:`AcquisitionDevice.instruct`).
        """
        self._device.instruct(channel_index, level)

    def add_marker(self, label: str) -> None:
        """Record an event marker at the current acquisition time.

        Thread-safe: callable from the Qt main thread while the worker
        is running. The marker is appended to an internal list and also
        emitted via :attr:`marker_added` for the log/UI; the list is
        written to the EDF file when the recording closes (see
        :meth:`remove_marker`).
        """
        time_s = self._n_samples_total / self._device.fs
        self._record_marker(time_s, label)

    def _record_marker(self, time_s: float, label: str) -> None:
        """Append a marker and emit it (shared by manual and automatic).

        Thread-safe: the internal list is guarded by a mutex so the Qt
        main thread (manual :meth:`add_marker`) and the worker thread
        (automatic onset detection) can record markers concurrently.
        """
        time_s = float(time_s)
        self._markers_mutex.lock()
        try:
            self._markers.append((time_s, label))
            self._mirror_marker(time_s, label)
        finally:
            self._markers_mutex.unlock()
        self.marker_added.emit(time_s, label)

    def _mirror_marker(self, time_s: float, label: str) -> None:
        """Append one mark to the side-car and push it to disk at once.

        The EDF holds its annotations in memory until it closes, so a
        process that dies in mid-recording loses every mark of the session
        with the signal safely on disk. This line survives that: flushed
        and synced mark by mark, at most a few times a second.
        """
        if self._sidecar is None:
            return
        try:
            self._sidecar.write(f"{time_s:.4f}\t{label}\n")
            self._sidecar.flush()
            os.fsync(self._sidecar.fileno())
        except OSError:
            pass

    def _close_sidecar(self, keep: bool) -> None:
        """Close the marks' mirror; keep it only for a file that did not close well."""
        self._markers_mutex.lock()
        try:
            f, self._sidecar = self._sidecar, None
        finally:
            self._markers_mutex.unlock()
        if f is None:
            return
        try:
            f.close()
        except OSError:
            pass
        if keep:
            self.log.emit(tr(
                "The marks are also in {path}; «python -m emgteach.recovery» "
                "rebuilds a readable file."
            ).format(path=f.name))
            return
        try:
            Path(f.name).unlink()
        except OSError:
            pass

    @Slot(float, str)
    def remove_marker(self, time_s: float, label: str) -> bool:
        """Remove a pending marker before it is written to the EDF.

        Markers are flushed to the file only on :meth:`run`'s cleanup, so a
        marker deleted while recording never reaches the EDF. Removes the
        entry whose time matches ``time_s`` (to the sample) and whose label
        matches ``label``; returns ``True`` if one was removed. Thread-safe.
        """
        time_s = float(time_s)
        removed = False
        self._markers_mutex.lock()
        try:
            for i, (t, lbl) in enumerate(self._markers):
                if lbl == label and abs(t - time_s) < 0.5 / self._device.fs:
                    del self._markers[i]
                    removed = True
                    break
        finally:
            self._markers_mutex.unlock()
        if removed:
            self.marker_removed.emit(time_s, label)
        return removed

    def _resolve_sensor_labels(self, n_channels: int) -> list[str] | None:
        """Return one base label per channel, or ``None`` on a mismatch.

        On mismatch the :attr:`error` signal is emitted so the caller can
        abort the run cleanly.
        """
        if self._sensor_labels is not None:
            labels = list(self._sensor_labels)
        elif n_channels == 1:
            labels = [self._profile.raw_label]
        else:
            labels = [
                f"{self._profile.raw_label}{i + 1}" for i in range(n_channels)
            ]
        if len(labels) != n_channels:
            self.error.emit(
                tr(
                    "sensor_labels has {n} entries but the device reports "
                    "{m} channel(s)."
                ).format(n=len(labels), m=n_channels)
            )
            return None
        return labels

    # -- thread body ---------------------------------------------------------

    def run(self) -> None:
        device = self._device
        fs = int(device.fs)
        n_ch = int(device.n_channels)
        labels = self._resolve_sensor_labels(n_ch)
        if labels is None:
            self.finished_ok.emit("")
            return
        # Per-channel signal kind: "EMG" channels get the notch+band-pass+
        # envelope chain and onset detection; non-EMG channels (e.g. the
        # BITalino accelerometer, kind "ACC") are stored and displayed raw.
        kinds = list(device.channel_kinds())
        edf_path = ""
        writer: BufferedEdfWriter | None = None

        try:
            self._opening = True
            self._streaming = False
            self.log.emit(tr("Connecting to {name}…").format(name=device.name))
            device.open()
            self._opening = False
            self.log.emit(tr("Connection established. Starting acquisition."))

            # One independent filter chain per EMG channel; ACC channels get
            # no filter (None) — they are stored/displayed raw.
            filter_states: list[RealtimeFilterState | None] = [
                RealtimeFilterState(
                    fs=fs,
                    f_low=self._f_low,
                    f_high=self._f_high,
                    f_notch=self._f_notch,
                    f_env=self._f_env,
                )
                if kinds[c] == "EMG"
                else None
                for c in range(n_ch)
            ]

            # Optional automatic onset detection on the envelope (EMG only).
            onset_detectors: list[OnsetDetector | None] | None = None
            if self._auto_detect:
                onset_kwargs = dict(self._profile.onset_kwargs())
                onset_kwargs["k"] = self._onset_k
                onset_detectors = [
                    OnsetDetector(fs, **onset_kwargs) if kinds[c] == "EMG" else None
                    for c in range(n_ch)
                ]
                self.log.emit(
                    tr("Automatic onset detection enabled (k={k:.1f}).").format(
                        k=self._onset_k
                    )
                )

            if self._save_path:
                edf_path = self._save_path
                Path(edf_path).parent.mkdir(parents=True, exist_ok=True)
            else:
                edf_path = build_timestamped_path(self._save_dir)
            if "ACC" in kinds:
                # Mixed modalities: build one EDF channel per column with its own
                # unit and physical range (mV for EMG, g for the accelerometer).
                units = list(device.channel_units())
                ranges = list(device.channel_physical_ranges())
                channels = [
                    ChannelInfo(
                        labels[c],
                        dimension=units[c],
                        sample_frequency=fs,
                        physical_min=ranges[c][0],
                        physical_max=ranges[c][1],
                    )
                    for c in range(n_ch)
                ]
            else:
                channels = self._profile.build_channels(
                    labels,
                    fs,
                    physical_min=device.physical_min,
                    physical_max=device.physical_max,
                )
            try:
                writer = BufferedEdfWriter(
                    edf_path, channels=channels, metadata=self._metadata
                )
            except OSError as exc:
                raise OSError(mensaje_fallo_guardado(edf_path, exc)) from exc
            self.log.emit(tr("Recording to: {path}").format(path=edf_path))
            # What the EDF+ identification block could not hold. Said here,
            # while the bench can still act on it, rather than discovered at
            # marking from a protocol that names half a practice.
            for notice in writer.header_notices:
                self.log.emit(notice)
            # The marks' mirror: each one goes to this text file as it is
            # made, so a process that dies before the EDF closes leaves
            # them behind for emgteach.recovery. Removed on a normal close.
            self._markers_mutex.lock()
            try:
                self._sidecar = open(sidecar_path(edf_path), "w", encoding="utf-8")
                self._sidecar.write(
                    f"# emgteach marks for {Path(edf_path).name}: seconds\tlabel\n")
                self._sidecar.flush()
            except OSError:
                self._sidecar = None
            finally:
                self._markers_mutex.unlock()

            sleep_ms = max(1, int(self._n_per_read / fs * 500))
            self._running = True

            while self._running:
                try:
                    block = device.read(self._n_per_read)
                    self._last_sample_time = time.monotonic()
                    if not self._streaming:
                        self._streaming = True
                except Exception as exc:
                    if not self._running:
                        # force_close() was called from another thread
                        break
                    self.error.emit(
                        tr("Connection to {name} lost: {error}").format(
                            name=device.name, error=exc
                        )
                    )
                    break

                if block.ndim == 1:
                    block = block.reshape(-1, 1)
                self._n_samples_total += len(block)

                # Process each channel through its own filter chain. Only
                # the raw signal is written to the EDF (one channel per
                # sensor); the filtered signal and envelope are computed
                # here for the live display and recomputed on analysis.
                if self._rearm_onsets:
                    self._rearm_onsets = False
                    if onset_detectors is not None:
                        for detector in onset_detectors:
                            if detector is not None:
                                detector.rearm()
                        self.log.emit(tr(
                            "Onset detection re-armed: the resting level is measured "
                            "again from here."
                        ))

                raw_list = []
                filt_list = []
                env_list = []
                for c in range(n_ch):
                    raw_c = block[:, c]
                    fstate = filter_states[c]
                    if fstate is not None:
                        filt_c, env_c = fstate.process_block(raw_c)
                    else:
                        # ACC (non-EMG): no filtering; stored/shown as-is.
                        filt_c = raw_c
                        env_c = raw_c
                    raw_list.append(raw_c.copy())
                    filt_list.append(filt_c.copy())
                    env_list.append(env_c.copy())
                    detector = (
                        onset_detectors[c] if onset_detectors is not None else None
                    )
                    if detector is not None:
                        auto_label = (
                            tr("Onset (auto)")
                            if n_ch == 1
                            else tr("Onset (auto) — {label}").format(label=labels[c])
                        )
                        for t_onset in detector.process(env_c):
                            self._record_marker(t_onset, auto_label)

                # One raw block per sensor, in the same order as the EDF
                # channels built from the profile. The buffered writer
                # handles record alignment internally.
                try:
                    writer.add_samples(*raw_list)
                except Exception as exc:
                    # Said once, as an error, and the recording stops: a
                    # file that goes on losing blocks while the screen says
                    # «Signal OK» is worse than one that ends here. What was
                    # written stays on disk; the cleanup says how much.
                    self._write_failed = True
                    self.error.emit(mensaje_fallo_guardado(edf_path, exc))
                    break

                self.data_ready.emit(
                    {
                        "raw_mv": raw_list,
                        "filtered": filt_list,
                        "envelope": env_list,
                    }
                )

                self.msleep(sleep_ms)

        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self._opening = False
            self._streaming = False
            try:
                device.close()
            except Exception:
                pass
            self.log.emit(tr("{name} disconnected.").format(name=device.name))

            # What the tab is told the recording left behind: the path of a
            # file worth opening, or nothing.
            saved = ""
            if writer is not None:
                # Write annotations before close so the EDF file holds
                # the markers; then close flushes the trailing remainder
                # padded with the last sample value (no zero padding).
                self._markers_mutex.lock()
                try:
                    pending = list(self._markers)
                finally:
                    self._markers_mutex.unlock()
                for t_marker, label in pending:
                    try:
                        writer.add_annotation(t_marker, label)
                    except Exception as exc:
                        self.log.emit(tr("Warning — annotation error: {error}").format(error=exc))

                try:
                    writer.close()
                except Exception as exc:
                    self.log.emit(tr("Warning — EDF close error: {error}").format(error=exc))
                    self._write_failed = True

                if self._n_samples_total == 0:
                    # Opened, and not one sample arrived: the header says
                    # zero records and no reader accepts it. Not a recording.
                    try:
                        Path(edf_path).unlink()
                    except OSError:
                        pass
                    self.log.emit(tr(
                        "No samples arrived: the empty file {path} was removed."
                    ).format(path=edf_path))
                elif self._write_failed:
                    self.log.emit(tr(
                        "The file {path} holds the {seconds:.1f} s written before "
                        "the failure and is incomplete; it is not opened for analysis."
                    ).format(path=edf_path, seconds=self._n_samples_total / fs))
                else:
                    self.log.emit(tr("EDF file saved: {path}").format(path=edf_path))
                    saved = edf_path
                self._close_sidecar(keep=bool(self._n_samples_total) and not saved)

            self.finished_ok.emit(saved)
