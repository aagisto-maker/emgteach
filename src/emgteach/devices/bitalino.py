"""BITalino *(revolution)* acquisition backend over a Bluetooth virtual COM port.

The BITalino *(revolution)* communicates over Bluetooth **Classic**
(SPP / RFCOMM), not Bluetooth Low Energy. On Windows the paired device is
exposed as an outgoing **virtual COM port**, so this backend speaks the
BITalino wire protocol directly through :mod:`pyserial`. There is therefore

* no dependency on PyBluez (whose C extension needs Microsoft C++ Build
  Tools and is abandoned since 2020),
* no dependency on the external ``bitalino`` package, and
* no Bluetooth Low Energy stack (``bleak`` cannot reach a Classic device).

``pyserial`` is already a hard dependency of the package (the Arduino
backend uses it), it imports cleanly on every supported Python (3.10-3.14)
and freezes without C-toolchain gymnastics, so the standalone executable
keeps working across Windows updates.

Wire protocol *(BITalino (revolution), live-acquisition mode)*
--------------------------------------------------------------
All commands are single bytes; the device must be idle to accept the
sampling-rate, version and start commands. ``_send`` spaces consecutive
command bytes by 100 ms, which the firmware requires.

==========  =================================================  ==================
Direction   Byte                                               Meaning
==========  =================================================  ==================
PC→BITalino ``0000 0111`` (``0x07``)                           Request version
BITalino→PC ``"BITalino..._vX.Y\\n"``                          ASCII version string
PC→BITalino ``<Fs:2> 0000 11``                                 Set sampling rate
PC→BITalino ``A6 A5 A4 A3 A2 A1 0 1``                          Start live mode
BITalino→PC ``N`` bytes per sample (CRC4 + digital + analog)   Acquisition frame
PC→BITalino ``0000 0000`` (``0x00``)                           Stop → idle
==========  =================================================  ==================

The ``<Fs>`` field encodes 1000/100/10/1 Hz as ``3/2/1/0``. Each analog
sample is packed into ``N`` bytes (10 bits for channels A1-A4, 6 bits for
A5-A6) together with a 4-bit sequence number and four digital states; a
4-bit CRC closes every frame and is validated on read.

Watchdog
--------
Because the per-frame serial read can block forever when the Bluetooth
link is silently dropped mid-session, this class implements the watchdog
protocol described in Agis-Torres (2026):

1. :meth:`read` releases the connection lock **before** the blocking
   serial read, so a second thread can acquire the lock and close the
   underlying port.
2. :meth:`force_close` closes the serial port from any thread; the
   blocked :meth:`read` then unblocks immediately and raises.
3. The GUI's ``QTimer`` polls a separate ``time_since_last_sample``
   property (implemented in the worker thread, not here) and triggers
   :meth:`force_close` when no samples have been produced for several
   seconds.
"""

from __future__ import annotations

import math
import re
import threading
import time
from typing import TYPE_CHECKING, ClassVar

import numpy as np

from emgteach.devices.base import AcquisitionDevice
from emgteach.i18n import tr

if TYPE_CHECKING:
    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]


class BitalinoDevice(AcquisitionDevice):
    """Acquisition backend for BITalino *(revolution)* over a virtual COM port.

    Parameters
    ----------
    port : str
        Windows Bluetooth **virtual COM port** of the paired BITalino,
        e.g. ``"COM5"`` (``/dev/...`` on POSIX). Pair the device in the
        operating system's Bluetooth settings first; the COM port it
        assigns is what goes here. A MAC address is **not** accepted —
        direct MAC/RFCOMM needed PyBluez and is no longer supported.
    fs : int, optional
        Sampling frequency in Hz (default 1000). Must be one of the rates
        supported by the BITalino firmware: 1, 10, 100 or 1000.
    channels : sequence of int, optional
        Channel indices to record (default ``[0]``). The BITalino
        revolution exposes 6 analogue channels indexed 0..5.

    Raises
    ------
    RuntimeError
        From :meth:`open` if a MAC address is supplied instead of a COM
        port, if a connection is already active, or if the device on the
        port does not identify itself as a BITalino.

    Examples
    --------
    >>> from emgteach.devices import BitalinoDevice
    >>> device = BitalinoDevice("COM5")    # doctest: +SKIP
    >>> device.open()                      # doctest: +SKIP
    >>> samples_mv = device.read(1000)     # doctest: +SKIP
    >>> device.close()                     # doctest: +SKIP
    """

    # ADC and analogue-front-end constants (BITalino EMG: 10-bit ADC,
    # 3.3 V supply, unity gain, +/-1.65 mV referred to the input).
    _ADC_MAX = 2**10 - 1  # 1023
    _V_REF = 3.3

    # Serial-link constants.
    _BAUD = 115_200
    _TIMEOUT_OPEN_S = 5.0  # max wait for the version reply on open
    _TIMEOUT_READ_S = 5.0  # serial read timeout per chunk while streaming
    _CMD_GAP_S = 0.1  # spacing the firmware requires between command bytes

    # Sampling-rate byte encoding accepted by the firmware.
    _SRATE_CODE: ClassVar[dict[int, int]] = {1000: 3, 100: 2, 10: 1, 1: 0}

    # MAC address (rejected): 6 hex pairs separated by ':' or '-'.
    _MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")

    def __init__(
        self,
        port: str,
        fs: int = 1000,
        channels: list[int] | None = None,
    ) -> None:
        self._port = str(port)
        self._fs = int(fs)
        self._channels = list(channels) if channels is not None else [0]
        self._serial = None  # type: ignore[var-annotated]
        self._conn_lock = threading.Lock()

    # -- AcquisitionDevice properties ----------------------------------------

    @property
    def fs(self) -> float:
        return float(self._fs)

    @property
    def name(self) -> str:
        return f"BITalino ({self._port})" if self._port else "BITalino"

    @property
    def n_channels(self) -> int:
        return len(self._channels)

    @property
    def is_connected(self) -> bool:
        """``True`` while the underlying serial port is open."""
        with self._conn_lock:
            return self._serial is not None

    # -- AcquisitionDevice interface -----------------------------------------

    def open(self) -> None:
        """Open the virtual COM port and start streaming.

        Raises
        ------
        RuntimeError
            If a MAC address is supplied instead of a COM port, if a
            connection is already active, if the sampling rate or channel
            list is invalid, or if the device does not identify itself as
            a BITalino.
        """
        import serial  # lazy — keeps import time low when device is not used

        self._validate_address()
        self._validate_config()

        with self._conn_lock:
            if self._serial is not None:
                raise RuntimeError(
                    tr(
                        "A BITalino connection is already active. "
                        "Close it before opening another."
                    )
                )
            ser = serial.Serial(
                port=self._port,
                baudrate=self._BAUD,
                timeout=self._TIMEOUT_OPEN_S,
            )
            try:
                # Confirm we are actually talking to a BITalino before
                # streaming, so a wrong COM port fails fast and clearly.
                version = self._read_version(ser)
                if "BITalino" not in version:
                    raise RuntimeError(
                        tr(
                            "The device on {port} did not identify itself as a "
                            "BITalino. Check that you entered its Bluetooth "
                            "virtual COM port."
                        ).format(port=self._port)
                    )
                self._set_sampling_rate(ser)
                self._start_streaming(ser)
            except Exception:
                try:
                    ser.close()
                except Exception:
                    pass
                raise
            ser.timeout = self._TIMEOUT_READ_S
            self._serial = ser

    def read(self, n_samples: int) -> FloatArray:
        """Read *n_samples* and return the active channels as float64 mV.

        Returns shape ``(n_samples, n_channels)``. The analogue channels
        are returned in the order given to the constructor.

        The connection lock is released **before** the blocking serial
        read, allowing :meth:`force_close` to release a stuck read from
        another thread without dead-locking.
        """
        with self._conn_lock:
            ser = self._serial
        if ser is None:
            raise RuntimeError(tr("The BITalino device is not open."))

        n = int(n_samples)
        frame_bytes = self._frame_size()
        raw_buf = self._receive_exact(ser, n * frame_bytes)  # blocking; no lock
        adc = self._decode_frames(raw_buf, n)
        return self._raw_to_mv(adc)

    def close(self) -> None:
        """Stop streaming and close the COM port.

        Safe to call when already closed (no-op).
        """
        with self._conn_lock:
            ser = self._serial
            if ser is None:
                return
            try:
                if ser.is_open:
                    self._send(ser, 0x00)  # stop → idle
            except Exception:
                pass
            finally:
                try:
                    ser.close()
                except Exception:
                    pass
                self._serial = None

    def force_close(self) -> None:
        """Close the COM port immediately from any thread.

        Used by the watchdog described in this module's docstring.
        """
        with self._conn_lock:
            ser = self._serial
            if ser is None:
                return
            try:
                ser.close()
            except Exception:
                pass
            self._serial = None

    # -- protocol helpers ----------------------------------------------------

    def _validate_address(self) -> None:
        """Reject a MAC address with an actionable message."""
        addr = self._port.strip()
        if not addr:
            raise RuntimeError(tr("No BITalino COM port given. Enter e.g. COM5."))
        if self._MAC_RE.match(addr):
            raise RuntimeError(
                tr(
                    "BITalino now connects through its Bluetooth virtual COM port "
                    "(e.g. COM5), not a MAC address. Pair the device in the "
                    "operating system's Bluetooth settings and enter the COM port "
                    "it assigns. Direct MAC/RFCOMM (PyBluez) is no longer supported."
                )
            )

    def _validate_config(self) -> None:
        """Validate sampling rate and channel list before opening the port."""
        if self._fs not in self._SRATE_CODE:
            raise RuntimeError(
                tr(
                    "Unsupported BITalino sampling rate {fs} Hz. "
                    "Use one of 1, 10, 100 or 1000."
                ).format(fs=self._fs)
            )
        if not self._channels or any(c not in range(6) for c in self._channels):
            raise RuntimeError(
                tr("Invalid BITalino channel list; channels must be in 0..5.")
            )

    def _send(self, ser: object, byte: int) -> None:
        """Send a single command byte, spaced as the firmware requires."""
        time.sleep(self._CMD_GAP_S)
        ser.write(bytes([byte]))  # type: ignore[attr-defined]

    def _read_version(self, ser: object) -> str:
        """Request and return the firmware version string."""
        self._send(ser, 0x07)
        chars: list[str] = []
        deadline = time.monotonic() + self._TIMEOUT_OPEN_S
        while time.monotonic() < deadline:
            chunk = ser.read(1)  # type: ignore[attr-defined]
            if not chunk:
                break
            chars.append(chunk.decode("ascii", errors="ignore"))
            text = "".join(chars)
            if text.endswith("\n") and "BITalino" in text:
                return text[text.index("BITalino") : -1]
        return "".join(chars)

    def _set_sampling_rate(self, ser: object) -> None:
        """Send the set-sampling-rate command for ``self._fs``."""
        code = self._SRATE_CODE[self._fs]
        self._send(ser, (code << 6) | 0x03)

    def _start_streaming(self, ser: object) -> None:
        """Send the live-acquisition start command for the active channels."""
        command = 0x01  # low two bits: 01 = live mode
        for ch in self._channels:
            command |= 1 << (2 + ch)
        self._send(ser, command)

    def _frame_size(self) -> int:
        """Bytes per acquisition frame for the active channel count."""
        n = self.n_channels
        if n <= 4:
            return math.ceil((12.0 + 10.0 * n) / 8.0)
        return math.ceil((52.0 + 6.0 * (n - 4)) / 8.0)

    def _receive_exact(self, ser: object, nbytes: int) -> bytes:
        """Read exactly *nbytes* from the port or raise on timeout/closure."""
        buf = bytearray()
        while len(buf) < nbytes:
            chunk = ser.read(nbytes - len(buf))  # type: ignore[attr-defined]
            if not chunk:
                raise RuntimeError(
                    tr("Timeout while reading from the BITalino — connection lost.")
                )
            buf.extend(chunk)
        return bytes(buf)

    def _decode_frames(self, raw: bytes, n_samples: int) -> FloatArray:
        """Decode *n_samples* BITalino frames into ``(n_samples, n_channels)`` ADC.

        Each frame carries a 4-bit CRC that is validated; a mismatch means
        the serial stream lost framing and is reported so the watchdog and
        worker can react.
        """
        n_ch = self.n_channels
        frame_bytes = self._frame_size()
        out = np.empty((n_samples, n_ch), dtype=np.float64)
        for s in range(n_samples):
            frame = list(raw[s * frame_bytes : (s + 1) * frame_bytes])
            if not self._crc_ok(frame):
                raise RuntimeError(
                    tr("Corrupted BITalino frame (CRC mismatch) — connection lost.")
                )
            for ch in range(n_ch):
                out[s, ch] = self._extract_channel(frame, ch)
        return out

    @staticmethod
    def _crc_ok(frame: list[int]) -> bool:
        """Validate the trailing 4-bit CRC of a decoded frame in place."""
        crc = frame[-1] & 0x0F
        frame[-1] = frame[-1] & 0xF0
        x = 0
        for byte in frame:
            for bit in range(7, -1, -1):
                x = x << 1
                if x & 0x10:
                    x = x ^ 0x03
                x = x ^ ((byte >> bit) & 0x01)
        return crc == (x & 0x0F)

    @staticmethod
    def _extract_channel(frame: list[int], ch: int) -> int:
        """Extract the 10-bit (A1-A4) or 6-bit (A5-A6) analogue value of *ch*.

        ``frame`` must already have its CRC nibble cleared (see
        :meth:`_crc_ok`). The bit packing follows the BITalino frame layout,
        where analogue channels occupy the trailing bytes.
        """
        if ch == 0:
            return ((frame[-2] & 0x0F) << 6) | (frame[-3] >> 2)
        if ch == 1:
            return ((frame[-3] & 0x03) << 8) | frame[-4]
        if ch == 2:
            return (frame[-5] << 2) | (frame[-6] >> 6)
        if ch == 3:
            return ((frame[-6] & 0x3F) << 4) | (frame[-7] >> 4)
        if ch == 4:
            return ((frame[-7] & 0x0F) << 2) | (frame[-8] >> 6)
        return frame[-8] & 0x3F

    # -- ADC ↔ mV conversion -------------------------------------------------

    @classmethod
    def _raw_to_mv(cls, raw_adc: FloatArray | np.ndarray) -> FloatArray:
        """Convert 10-bit BITalino ADC values to millivolts.

        BITalino EMG channels expose ±1.65 mV across the full ADC
        excursion at 3.3 V supply with unity gain.
        """
        return ((np.asarray(raw_adc, dtype=np.float64) / cls._ADC_MAX) - 0.5) * cls._V_REF

    @staticmethod
    def raw_to_mv(raw_adc: FloatArray | np.ndarray) -> FloatArray:
        """Public alias of the internal ADC to mV conversion."""
        return BitalinoDevice._raw_to_mv(raw_adc)
