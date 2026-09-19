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

    @property
    def n_channels(self) -> int:
        """Number of channels returned by :meth:`read` (default 1).

        Single-channel backends keep the default. Multi-channel backends
        override this — e.g. a BITalino configured with several analogue
        channels, or an Arduino whose firmware streams several sensors
        (agonist/antagonist montages).
        """
        return 1

    @property
    def physical_min(self) -> float:
        """Lower signal bound in physical units (mV) for the EDF header.

        Backends override this with their true full-scale so the EDF digital
        range maps to the signal without clipping and without wasting ADC
        resolution. The generic default is a conservative ±3.3 mV.
        """
        return -3.3

    @property
    def physical_max(self) -> float:
        """Upper signal bound in physical units (mV) for the EDF header."""
        return 3.3

    # -- optional per-channel metadata ---------------------------------------
    # Backends that mix signal modalities (e.g. a BITalino recording EMG *and*
    # its accelerometer) override these so each channel gets the right EDF unit
    # and physical range and the worker can skip EMG filtering on non-EMG
    # channels. The defaults describe a homogeneous EMG device, so single-
    # modality backends and existing code are unaffected.

    def channel_kinds(self) -> list[str]:
        """Signal kind per channel: ``"EMG"`` (filtered, envelope) or a raw
        modality such as ``"ACC"`` (stored as-is, not EMG-filtered)."""
        return ["EMG"] * self.n_channels

    def channel_units(self) -> list[str]:
        """Physical unit per channel for the EDF header (e.g. ``"mV"``, ``"g"``)."""
        return ["mV"] * self.n_channels

    def channel_physical_ranges(self) -> list[tuple[float, float]]:
        """``(min, max)`` physical range per channel for the EDF header."""
        return [(self.physical_min, self.physical_max)] * self.n_channels

    @abstractmethod
    def open(self) -> None:
        """Establish the connection. Raises on failure."""

    @abstractmethod
    def read(self, n_samples: int) -> FloatArray:
        """Read *n_samples* and return them as float64 millivolts.

        Returns a 2-D array of shape ``(n_samples, n_channels)``; a
        single-channel device returns shape ``(n_samples, 1)``.

        This call blocks until the requested samples are available, or
        raises if the connection is lost. Implementations must release
        any internal lock before the blocking I/O so that
        :meth:`force_close` can interrupt the read from another thread.
        """

    @abstractmethod
    def close(self) -> None:
        """Close the connection in an orderly fashion."""

    # Not abstract: a backend that cannot act on this — every real board —
    # should not have to write an empty method to say so.
    def instruct(  # noqa: B027
        self, channel_index: int, level: float | None,
        *, repeat_s: float | None = None,
    ) -> None:
        """Tell the device what the subject is being asked to do, if it can act.

        The application knows when it is asking for a maximal effort of one
        muscle: the calibration wizard opens a span and closes it. A board
        has no say in what the person attached to it does, so it ignores
        this — which is what this default does. The simulated board obeys,
        so that a rehearsal without hardware calibrates against a real
        maximum instead of against whatever its cycle was doing when the
        span opened, and the task then reads the share of it that the cycle
        says.

        Parameters
        ----------
        channel_index : int
            Which muscle is being asked, in the order :meth:`read` returns.
        level : float or None
            The activation asked of it, 1.0 being its maximum and 0.0 being
            «nothing, stay still» — which is what the calibration asks for
            between one effort and the next — or ``None`` to stop asking
            and let the device do whatever it does.
        repeat_s : float, optional
            When given, *level* is not held but performed as a contraction
            of about a second every *repeat_s* seconds, which is what the
            free manoeuvres of the task are: six of one muscle at the
            student's own pace. Without it the level is held.

        **One instruction per channel.** Asking one muscle says nothing
        about the other, so the caller says what the other is doing too:
        the calibration asks the one for its maximum and the other for
        rest, and the manoeuvre that works both at once asks both. It used
        to be one instruction for the pair, with the muscle not named
        forced to rest, and that could not express a grip at all.
        """

    @abstractmethod
    def force_close(self) -> None:
        """Close the connection immediately, callable from any thread.

        Safe to call when the device is already closed (no-op).
        """
