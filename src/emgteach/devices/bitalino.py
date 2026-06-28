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

Addressing
----------
COM-port numbers vary per PC, which is awkward in a teaching lab. To keep
configuration minimal and stable across machines, the constructor accepts
three forms of address and :meth:`open` resolves them to a concrete port:

* a **MAC address** (e.g. ``"98:D3:91:FE:44:E4"``) — the stable identifier
  used historically. Windows exposes the paired device's MAC inside the COM
  port's ``hwid``, so the MAC is resolved to whatever ``COMx`` the local PC
  assigned. This is the recommended, same-on-every-PC form.
* a **COM port** (e.g. ``"COM5"``) — used verbatim, as an explicit override.
* **empty / ``"auto"``** — autodetect: probe the Bluetooth serial ports and
  pick the first that answers the version handshake as a BITalino.

No PyBluez is involved in any case: resolution only reads the COM-port list
and the transport is always ``pyserial``.

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
from typing import TYPE_CHECKING, Any, ClassVar

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
        Device address, resolved by :meth:`open` to a concrete COM port:
        a **MAC address** (recommended, stable across PCs — resolved to the
        local virtual COM port via its ``hwid``), an explicit **COM port**
        (``"COM5"``, ``/dev/...``), or **empty/``"auto"``** to autodetect the
        BITalino among the paired Bluetooth serial ports. The device must be
        paired in the operating system's Bluetooth settings beforehand.
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
    _PROBE_TIMEOUT_S = 1.5  # max wait for the version reply while autodetecting
    _CMD_GAP_S = 0.1  # spacing the firmware requires between command bytes
    # Windows releases a Bluetooth SPP virtual COM port a little after close, so
    # a reopen (after autodetect probing, or a quick reconnect) can transiently
    # fail with WinError 1168. Retry the open a few times before giving up.
    _OPEN_RETRIES = 4
    _OPEN_RETRY_GAP_S = 0.4

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
        self._resolved_port: str | None = None
        self._conn_lock = threading.Lock()

    # -- AcquisitionDevice properties ----------------------------------------

    @property
    def fs(self) -> float:
        return float(self._fs)

    @property
    def name(self) -> str:
        if self._resolved_port and self._resolved_port != self._port.strip():
            label = self._port.strip() or "auto"
            return f"BITalino ({label} -> {self._resolved_port})"
        if self._port.strip():
            return f"BITalino ({self._port})"
        return "BITalino (auto)"

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
            If a connection is already active, if the sampling rate or channel
            list is invalid, if the address cannot be resolved to a COM port
            (MAC not paired / no BITalino autodetected), or if the device on
            the resolved port does not identify itself as a BITalino.
        """
        import serial  # lazy — keeps import time low when device is not used

        self._validate_config()
        resolved = self._resolve_port()  # MAC -> COM, autodetect, or direct COM

        with self._conn_lock:
            if self._serial is not None:
                raise RuntimeError(
                    tr(
                        "A BITalino connection is already active. "
                        "Close it before opening another."
                    )
                )
            ser = self._open_serial(serial, resolved)
            try:
                # Confirm we are actually talking to a BITalino before
                # streaming, so a wrong COM port fails fast and clearly.
                version = self._read_version(ser)
                if "BITalino" not in version:
                    raise RuntimeError(
                        tr(
                            "The device on {port} did not identify itself as a "
                            "BITalino. Check that the BITalino is paired and "
                            "switched on."
                        ).format(port=resolved)
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
            self._resolved_port = resolved
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

    def _resolve_port(self) -> str:
        """Resolve the configured address to a concrete serial port.

        A MAC address is mapped to the local COM port whose ``hwid`` carries
        that MAC; an explicit ``COMx`` / ``/dev/...`` is used verbatim; an
        empty address (or ``"auto"``) triggers autodetection by handshake.
        Never imports PyBluez — only reads the COM-port list.
        """
        addr = self._port.strip()
        if addr and not self._MAC_RE.match(addr) and addr.lower() != "auto":
            return addr  # explicit serial port

        from serial.tools import list_ports

        ports = list(list_ports.comports())
        if self._MAC_RE.match(addr):
            wanted = self._norm_hex(addr)
            for p in ports:
                if wanted in self._norm_hex(p.hwid or ""):
                    return p.device
            raise RuntimeError(
                tr(
                    "BITalino {mac} was not found among the paired Bluetooth COM "
                    "ports. Pair it in the operating system's Bluetooth settings "
                    "and switch it on."
                ).format(mac=addr)
            )
        return self._autodetect(ports)

    def _autodetect(self, ports: list) -> str:
        """Probe the Bluetooth serial ports and return the first BITalino."""
        for p in self._bluetooth_ports(ports):
            if self._probe(p):
                return p
        raise RuntimeError(
            tr(
                "No BITalino was found on the Bluetooth COM ports. Pair the "
                "BITalino in the operating system's Bluetooth settings and switch "
                "it on, or enter its MAC address or COM port explicitly."
            )
        )

    @classmethod
    def _bluetooth_ports(cls, ports: list) -> list[str]:
        """Candidate outgoing Bluetooth serial ports, in enumeration order.

        Keeps ports that look like a Bluetooth serial link and drops the
        "incoming" port whose ``hwid`` carries the all-zero address, which
        never answers a handshake.
        """
        out: list[str] = []
        for p in ports:
            hwid = (p.hwid or "").upper()
            desc = (p.description or "").lower()
            is_bt = "BTHENUM" in hwid or "bluetooth" in desc
            if is_bt and "000000000000" not in cls._norm_hex(hwid):
                out.append(p.device)
        return out

    def _probe(self, port: str) -> bool:
        """Open *port* briefly and return ``True`` if it answers as a BITalino."""
        import serial

        try:
            ser = serial.Serial(
                port=port, baudrate=self._BAUD, timeout=self._PROBE_TIMEOUT_S
            )
        except Exception:
            return False
        try:
            return "BITalino" in self._read_version(ser, timeout_s=self._PROBE_TIMEOUT_S)
        except Exception:
            return False
        finally:
            try:
                ser.close()
            except Exception:
                pass

    @staticmethod
    def _norm_hex(s: str) -> str:
        """Uppercase a string and strip ``:`` / ``-`` so MACs compare cleanly."""
        return s.upper().replace(":", "").replace("-", "")

    def _open_serial(self, serial_mod: Any, port: str) -> Any:
        """Open *port*, retrying briefly to ride over Bluetooth SPP release lag."""
        last_exc: Exception | None = None
        for attempt in range(self._OPEN_RETRIES):
            try:
                return serial_mod.Serial(
                    port=port, baudrate=self._BAUD, timeout=self._TIMEOUT_OPEN_S
                )
            except Exception as exc:  # pyserial: SerialException — retry transient lock
                last_exc = exc
                if attempt < self._OPEN_RETRIES - 1:
                    time.sleep(self._OPEN_RETRY_GAP_S)
        raise RuntimeError(
            tr("Could not open the BITalino port {port}: {err}").format(
                port=port, err=last_exc
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

    def _read_version(self, ser: object, timeout_s: float | None = None) -> str:
        """Request and return the firmware version string."""
        self._send(ser, 0x07)
        chars: list[str] = []
        deadline = time.monotonic() + (timeout_s or self._TIMEOUT_OPEN_S)
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
