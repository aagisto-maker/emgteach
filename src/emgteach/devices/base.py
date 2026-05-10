"""Abstract base class shared by every acquisition backend.

The rest of the package (workers, GUI tabs) operates exclusively
against :class:`AcquisitionDevice`. New hardware can be supported by
implementing this interface; no changes to the worker or GUI layers
are required.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]


class AcquisitionDevice(ABC):
    """Common interface for every EMG acquisition backend.

    Concrete subclasses encapsulate connection details and the ADC →
    physical-units conversion. The worker thread interacts with the
    device only through this contract.

    The split between :meth:`close` (orderly shutdown, may block) and
    :meth:`force_close` (immediate, callable from any thread) is what
    enables the watchdog implemented in :class:`BitalinoDevice`: a
    second thread can release a stuck :meth:`read` by calling
    :meth:`force_close` without dead-locking against the lock that
    protects the device handle.
    """

    @property
    @abstractmethod
    def fs(self) -> float:
        """Sampling frequency in hertz."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for log output (e.g. ``'Arduino MyoWare (COM4)'``)."""

    @abstractmethod
    def open(self) -> None:
        """Establish the connection. Raises on failure."""

    @abstractmethod
    def read(self, n_samples: int) -> FloatArray:
        """Read *n_samples* and return them as float64 in millivolts.

        This call blocks until the requested samples are available, or
        raises if the connection is lost. Implementations must release
        any internal lock before the blocking I/O so that
        :meth:`force_close` can interrupt the read from another thread.
        """

    @abstractmethod
    def close(self) -> None:
        """Close the connection in an orderly fashion."""

    @abstractmethod
    def force_close(self) -> None:
        """Close the connection immediately, callable from any thread.

        Safe to call when the device is already closed (no-op).
        """
