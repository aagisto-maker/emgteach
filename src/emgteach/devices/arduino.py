"""Arduino RedBoard Plus + MyoWare 2.0 acquisition backend over USB serial.

Wire protocol (see ``arduino/emg_streamer.ino`` for the firmware side):

==========  =================================  ============================
Direction   Message                            Description
==========  =================================  ============================
Arduino→PC  ``READY\\n``                        Emitted once after reset
PC→Arduino  ``START\\n``                        Begins streaming at *fs* Hz
PC→Arduino  ``STOP\\n``                         Stops streaming
Arduino→PC  ``STOPPED\\n``                      Confirmation of STOP
PC→Arduino  ``PING\\n``                         Connection test
Arduino→PC  ``PONG\\n``                         Reply to PING
Arduino→PC  2 bytes little-endian uint16        One ADC sample (0..1023)
==========  =================================  ============================

ADC → mV conversion (MyoWare 2.0 RAW mode, V_ref = 5 V, gain ≈ 200):

.. math::

    \\text{mV} = \\bigl(\\text{adc} \\cdot 5 / 1023 - 2.5\\bigr) \\cdot 1000 / 200

The baud rate is **115 200**, not 500 000 as one might choose for
maximum throughput. Reason: the CH340 driver shipped with most
RedBoard Plus boards on Windows has been observed to silently drop
bytes at higher baud rates. 115 200 bps offers a 5.7x margin over
the useful 20 000 bps (1 kHz x 2 bytes/sample).
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

import numpy as np

from emgteach.devices.base import AcquisitionDevice
from emgteach.i18n import tr

if TYPE_CHECKING:
    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]


class ArduinoDevice(AcquisitionDevice):
    """Acquisition backend for Arduino RedBoard Plus + MyoWare 2.0.

    Parameters
    ----------
    port : str
        Serial port path (``"COM4"`` on Windows, ``"/dev/ttyUSB0"`` on
        Linux, etc.).
    fs : int, optional
        Sampling frequency in Hz (default 1000). Must match the value
        configured in the Arduino firmware.
    n_channels : int, optional
        Number of analogue channels streamed by the firmware (default 1).
        Must match the firmware's ``N_CHANNELS``. When greater than 1 the
        firmware sends the channels frame-interleaved (all channels of one
        sample, then the next sample), and :meth:`read` de-interleaves
        them into the trailing axis.

    Examples
    --------
    >>> from emgteach.devices import ArduinoDevice
    >>> device = ArduinoDevice("COM4")
    >>> device.open()  # waits for "READY", then sends "START"  # doctest: +SKIP
    >>> samples_mv = device.read(1000)  # one second of data    # doctest: +SKIP
    >>> device.close()                                          # doctest: +SKIP
    """

    _BAUD = 115_200
    _TIMEOUT_OPEN_S = 5.0  # max wait for the "READY" handshake
    _TIMEOUT_READ_S = 3.0  # serial read timeout per chunk
    _STOP_TIMEOUT_S = 0.5  # max wait for the "STOPPED" reply on close

    # ADC and analogue-front-end constants for MyoWare 2.0 in RAW mode
    _ADC_MAX = 1023.0  # 10-bit ADC
    _V_REF = 5.0  # V_ref of the Arduino board (5 V via shield jumper)
    _GAIN = 200.0  # MyoWare 2.0 nominal gain in RAW mode

    def __init__(self, port: str, fs: int = 1000, n_channels: int = 1) -> None:
        self._port = port
        self._fs = int(fs)
        self._n_channels = int(n_channels)
        self._serial = None  # type: ignore[var-annotated]
        self._lock = threading.Lock()

    # -- AcquisitionDevice properties ----------------------------------------

    @property
    def fs(self) -> float:
        return float(self._fs)

    @property
    def name(self) -> str:
        return f"Arduino MyoWare ({self._port})"

    @property
    def n_channels(self) -> int:
        return self._n_channels

    # -- AcquisitionDevice interface -----------------------------------------

    def open(self) -> None:
        """Open the serial port, wait for ``READY``, send ``START``.

        Raises
        ------
        RuntimeError
            If the port is already open, or if the Arduino does not
            reply ``READY`` within :attr:`_TIMEOUT_OPEN_S`.
        """
        import serial  # lazy — keeps import time low when device is not used

        with self._lock:
            if self._serial is not None:
                raise RuntimeError(tr("The serial port is already open."))

            ser = serial.Serial(
                port=self._port,
                baudrate=self._BAUD,
                timeout=self._TIMEOUT_OPEN_S,
            )
            # The Arduino resets when the port is opened; wait for READY.
            deadline = time.monotonic() + self._TIMEOUT_OPEN_S
            while time.monotonic() < deadline:
                line = ser.readline().decode("ascii", errors="ignore").strip()
                if line == "READY":
                    break
            else:
                ser.close()
                raise RuntimeError(
                    tr(
                        "The Arduino on {port} did not reply READY within {timeout:.0f} s."
                    ).format(port=self._port, timeout=self._TIMEOUT_OPEN_S)
                )

            ser.timeout = self._TIMEOUT_READ_S
            ser.write(b"START\n")
            ser.flush()
            self._serial = ser

    def read(self, n_samples: int) -> FloatArray:
        """Read *n_samples* binary samples per channel and convert to mV.

        Parameters
        ----------
        n_samples : int
            Number of ADC samples to read per channel.

        Returns
        -------
        numpy.ndarray
            float64 array of shape ``(n_samples, n_channels)`` in
            millivolts referred to the MyoWare 2.0 input.

        Raises
        ------
        RuntimeError
            If the port is not open, or if the read times out.
        """
        with self._lock:
            ser = self._serial
        if ser is None:
            raise RuntimeError(tr("The Arduino device is not open."))

        n = int(n_samples)
        n_bytes = n * 2 * self._n_channels
        buf = bytearray()
        while len(buf) < n_bytes:
            chunk = ser.read(n_bytes - len(buf))
            if not chunk:
                raise RuntimeError(
                    tr("Timeout while reading from the Arduino — connection lost.")
                )
            buf.extend(chunk)

        adc = np.frombuffer(bytes(buf), dtype="<u2").astype(np.float64)
        mv = (adc * self._V_REF / self._ADC_MAX - self._V_REF / 2.0) * 1000.0 / self._GAIN
        # The firmware streams channels frame-interleaved, so a C-order
        # reshape recovers (sample, channel).
        return mv.reshape(n, self._n_channels)

    def close(self) -> None:
        """Send ``STOP``, wait briefly for ``STOPPED``, then close the port.

        If the Arduino does not reply ``STOPPED`` within
        :attr:`_STOP_TIMEOUT_S`, the port is closed anyway so the user
        never gets stuck. Calling :meth:`close` when already closed is
        a no-op.
        """
        with self._lock:
            ser = self._serial
            if ser is None or not ser.is_open:
                self._serial = None
                return

            try:
                old_timeout = ser.timeout
                ser.timeout = 0.1
                try:
                    ser.write(b"STOP\n")
                    ser.flush()
                except Exception:
                    pass
                deadline = time.monotonic() + self._STOP_TIMEOUT_S
                while time.monotonic() < deadline:
                    try:
                        line = ser.readline()
                        if b"STOPPED" in line:
                            break
                    except Exception:
                        break
                ser.timeout = old_timeout
            finally:
                try:
                    ser.close()
                except Exception:
                    pass
                self._serial = None

    def force_close(self) -> None:
        """Close the serial port immediately, from any thread."""
        with self._lock:
            ser = self._serial
            if ser is None:
                return
            try:
                ser.close()
            except Exception:
                pass
            self._serial = None

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def list_ports() -> list[str]:
        """Return the device names of all serial ports currently available."""
        try:
            from serial.tools import list_ports

            return [p.device for p in list_ports.comports()]
        except Exception:
            return []

