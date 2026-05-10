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

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QMutex, QThread, Signal, Slot

from emgteach.dsp import RealtimeFilterState
from emgteach.io import BufferedEdfWriter, ChannelInfo, build_timestamped_path

if TYPE_CHECKING:
    from emgteach.devices import AcquisitionDevice


class AcquisitionWorker(QThread):
    """QThread that streams from an :class:`AcquisitionDevice` to an EDF+ file.

    Signals
    -------
    data_ready : dict
        Emitted on every acquired block with keys ``raw_mv``,
        ``filtered`` and ``envelope`` (each a 1-D NumPy array).
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
        Directory in which to create the EDF file (default ``"."``).
    n_per_read : int, optional
        Number of samples to request per ``device.read`` call (default
        100, i.e. 100 ms at 1 kHz).
    f_low, f_high, f_notch, f_env : float, optional
        DSP cut-offs forwarded to :class:`RealtimeFilterState`.
    parent : QObject, optional
        Parent in the Qt object tree.
    """

    data_ready = Signal(dict)
    log = Signal(str)
    finished_ok = Signal(str)
    error = Signal(str)
    marker_added = Signal(float, str)

    def __init__(
        self,
        device: AcquisitionDevice,
        save_dir: str = ".",
        n_per_read: int = 100,
        f_low: float = 20.0,
        f_high: float = 450.0,
        f_notch: float = 50.0,
        f_env: float = 5.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._device = device
        self._save_dir = save_dir
        self._n_per_read = int(n_per_read)
        self._f_low = float(f_low)
        self._f_high = float(f_high)
        self._f_notch = float(f_notch)
        self._f_env = float(f_env)

        self._running = False
        self._opening = False
        self._streaming = False
        self._n_samples_total: int = 0
        self._markers: list[tuple[float, str]] = []
        self._markers_mutex = QMutex()
        self._last_sample_time: float | None = None

    # -- public control ------------------------------------------------------

    def stop(self) -> None:
        """Request a clean stop; the thread finishes the current block."""
        self._running = False

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
    def add_marker(self, label: str) -> None:
        """Record an event marker at the current acquisition time.

        Thread-safe: callable from the Qt main thread while the worker
        is running. The marker is appended to an internal list and also
        emitted via :attr:`marker_added` for the log/UI; it is written
        to the EDF file in real time via
        :meth:`BufferedEdfWriter.add_annotation`.
        """
        fs = self._device.fs
        time_s = self._n_samples_total / fs
        self._markers_mutex.lock()
        try:
            self._markers.append((time_s, label))
        finally:
            self._markers_mutex.unlock()
        self.marker_added.emit(time_s, label)

    # -- thread body ---------------------------------------------------------

    def run(self) -> None:
        device = self._device
        fs = int(device.fs)
        edf_path = ""
        writer: BufferedEdfWriter | None = None

        try:
            self._opening = True
            self._streaming = False
            self.log.emit(f"Connecting to {device.name}...")
            device.open()
            self._opening = False
            self.log.emit("Connection established. Starting acquisition.")

            filter_state = RealtimeFilterState(
                fs=fs,
                f_low=self._f_low,
                f_high=self._f_high,
                f_notch=self._f_notch,
                f_env=self._f_env,
            )

            edf_path = build_timestamped_path(self._save_dir)
            channels = [
                ChannelInfo("EMG", sample_frequency=fs),
                ChannelInfo("EMG_Filtered", sample_frequency=fs),
                ChannelInfo("EMG_Envelope", physical_min=0.0, sample_frequency=fs),
            ]
            writer = BufferedEdfWriter(edf_path, channels=channels)
            self.log.emit(f"Recording to: {edf_path}")

            sleep_ms = max(1, int(self._n_per_read / fs * 500))
            self._running = True

            while self._running:
                try:
                    emg_mv = device.read(self._n_per_read)
                    self._last_sample_time = time.monotonic()
                    if not self._streaming:
                        self._streaming = True
                except Exception as exc:
                    if not self._running:
                        # force_close() was called from another thread
                        break
                    self.error.emit(f"Connection to {device.name} lost: {exc}")
                    break

                self._n_samples_total += len(emg_mv)
                emg_filtered, emg_envelope = filter_state.process_block(emg_mv)

                # The buffered writer handles record alignment internally,
                # so we just feed it the same blocks the device produces.
                try:
                    writer.add_samples(emg_mv, emg_filtered, emg_envelope)
                except Exception as exc:
                    self.log.emit(f"Warning - EDF write error: {exc}")

                self.data_ready.emit(
                    {
                        "raw_mv": emg_mv.copy(),
                        "filtered": emg_filtered.copy(),
                        "envelope": emg_envelope.copy(),
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
            self.log.emit(f"{device.name} disconnected.")

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
                        self.log.emit(f"Warning - annotation error: {exc}")

                try:
                    writer.close()
                    self.log.emit(f"EDF file saved: {edf_path}")
                except Exception as exc:
                    self.log.emit(f"Warning - EDF close error: {exc}")

            self.finished_ok.emit(edf_path)
