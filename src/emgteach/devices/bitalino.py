"""BITalino *(revolution)* acquisition backend over Bluetooth.

Requires the optional ``bitalino`` extra: ``pip install "emgteach[bitalino]"``.
On Windows + Python 3.12 the ``bitalino`` package transitively depends
on ``PyBluez-bitalino`` which has no precompiled wheel and needs
Microsoft C++ Build Tools. Users who only have an Arduino backend
should not install this extra.

Watchdog
--------
Because :meth:`bitalino.BITalino.read` can block forever when the
Bluetooth link is silently dropped mid-session, this class implements
a watchdog protocol described in Agis-Torres (2026):

1. :meth:`read` releases the connection lock **before** the blocking
   call to the device's ``read``, so a second thread can acquire the
   lock and close the underlying socket.
2. :meth:`force_close` closes the device handle from any thread; the
   blocked :meth:`read` then unblocks immediately by raising.
3. The GUI's ``QTimer`` polls a separate ``time_since_last_sample``
   property (implemented in the worker thread, not here) and triggers
   :meth:`force_close` when no samples have been produced for several
   seconds.

The contract here is just the device side: provide a ``force_close``
that does not deadlock against a blocked ``read``.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import numpy as np

from emgteach.devices.base import AcquisitionDevice

if TYPE_CHECKING:
    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]


class BitalinoDevice(AcquisitionDevice):
    """Acquisition backend for BITalino *(revolution)* over Bluetooth.

    Parameters
    ----------
    mac : str
        MAC address of the BITalino, e.g. ``"98:D3:91:FE:44:E4"``.
    fs : int, optional
        Sampling frequency in Hz (default 1000). Must be supported by
        the BITalino firmware (typically 1, 10, 100, 1000).
    channels : sequence of int, optional
        Channel indices to record (default ``[0]``). The BITalino
        revolution exposes 6 analogue channels indexed 0..5.

    Raises
    ------
    ImportError
        If the optional ``bitalino`` extra is not installed.

    Examples
    --------
    >>> from emgteach.devices import BitalinoDevice
    >>> device = BitalinoDevice("98:D3:91:FE:44:E4")  # doctest: +SKIP
    >>> device.open()                                  # doctest: +SKIP
    >>> samples_mv = device.read(1000)                 # doctest: +SKIP
    >>> device.close()                                 # doctest: +SKIP
    """

    # ADC and analogue-front-end constants (BITalino EMG: 10-bit ADC,
    # 3.3 V supply, unity gain, +/-1.65 mV referred to the input).
    _ADC_MAX = 2**10 - 1  # 1023
    _V_REF = 3.3

    def __init__(
        self,
        mac: str,
        fs: int = 1000,
        channels: list[int] | None = None,
    ) -> None:
        self._mac = mac
        self._fs = int(fs)
        self._channels = list(channels) if channels is not None else [0]
        self._device = None  # type: ignore[var-annotated]
        self._conn_lock = threading.Lock()

    # -- AcquisitionDevice properties ----------------------------------------

    @property
    def fs(self) -> float:
        return float(self._fs)

    @property
    def name(self) -> str:
        return f"BITalino {self._mac}" if self._mac else "BITalino"

    @property
    def is_connected(self) -> bool:
        """``True`` while the underlying handle is open."""
        with self._conn_lock:
            return self._device is not None

    # -- AcquisitionDevice interface -----------------------------------------

    def open(self) -> None:
        """Open the Bluetooth connection and start streaming.

        Raises
        ------
        ImportError
            If the optional ``bitalino`` extra is not installed.
        RuntimeError
            If a connection is already active on this object.
        """
        try:
            import bitalino  # lazy — only required when actually opening
        except ImportError as exc:
            raise ImportError(
                "BitalinoDevice requires the optional 'bitalino' extra. "
                'Install with: pip install "emgteach[bitalino]"'
            ) from exc

        with self._conn_lock:
            if self._device is not None:
                raise RuntimeError(
                    "A BITalino connection is already active. "
                    "Close it before opening another."
                )
            device = bitalino.BITalino(self._mac)
            device.start(self._fs, self._channels)
            self._device = device

    def read(self, n_samples: int) -> FloatArray:
        """Read *n_samples* and return the active channel as float64 mV.

        The connection lock is released **before** the blocking call to
        the underlying device, allowing :meth:`force_close` to release
        a stuck read from another thread without dead-locking.
        """
        with self._conn_lock:
            device = self._device
        if device is None:
            raise RuntimeError("BitalinoDevice is not open.")

        raw = device.read(n_samples)  # blocking; lock NOT held here
        return self._raw_to_mv(raw[:, -1])

    def close(self) -> None:
        """Stop streaming and close the Bluetooth connection.

        Safe to call when already closed (no-op).
        """
        with self._conn_lock:
            if self._device is not None:
                try:
                    self._device.stop()
                    self._device.close()
                except Exception:
                    pass
                finally:
                    self._device = None

    def force_close(self) -> None:
        """Close the device handle immediately from any thread.

        Used by the watchdog described in this module's docstring.
        """
        with self._conn_lock:
            if self._device is not None:
                try:
                    self._device.close()
                except Exception:
                    pass
                self._device = None

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
