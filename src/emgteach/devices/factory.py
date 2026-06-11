"""Device factory and registry — the extension point for new hardware.

The GUI selects an acquisition backend by an opaque string id
(``"bitalino"``, ``"arduino"``) and builds the device through
:func:`create_device`, *without* importing the concrete device classes.
New hardware is supported by implementing
:class:`~emgteach.devices.base.AcquisitionDevice` and calling
:func:`register_device`; no change to the worker or GUI layers is
needed.

This complements :class:`~emgteach.profiles.SignalProfile`: a profile is
the extension point for new *signal modalities*, while this registry is
the extension point for new *hardware backends*.
"""

from __future__ import annotations

from collections.abc import Callable

from emgteach.devices.arduino import ArduinoDevice
from emgteach.devices.base import AcquisitionDevice
from emgteach.devices.bitalino import BitalinoDevice

__all__ = [
    "BACKEND_ARDUINO",
    "BACKEND_BITALINO",
    "available_backends",
    "create_device",
    "register_device",
]

#: Stable backend identifiers for the built-in hardware.
BACKEND_BITALINO = "bitalino"
BACKEND_ARDUINO = "arduino"

#: A device builder: any callable returning an AcquisitionDevice.
DeviceBuilder = Callable[..., AcquisitionDevice]

_REGISTRY: dict[str, DeviceBuilder] = {}


def register_device(backend_id: str, builder: DeviceBuilder) -> None:
    """Register *builder* under *backend_id*, overwriting any existing one.

    Parameters
    ----------
    backend_id : str
        Opaque identifier used by :func:`create_device` (e.g. ``"arduino"``).
    builder : callable
        Any callable that returns an :class:`AcquisitionDevice`. A device
        class is itself a valid builder.
    """
    _REGISTRY[backend_id] = builder


def available_backends() -> list[str]:
    """Return the registered backend ids, in registration order."""
    return list(_REGISTRY)


def create_device(backend_id: str, **kwargs: object) -> AcquisitionDevice:
    """Instantiate the device registered under *backend_id*.

    Parameters
    ----------
    backend_id : str
        One of :func:`available_backends`.
    **kwargs
        Forwarded verbatim to the registered builder, e.g. ``mac`` and
        ``fs`` for BITalino, or ``port`` and ``fs`` for Arduino.

    Returns
    -------
    AcquisitionDevice
        The constructed backend.

    Raises
    ------
    KeyError
        If *backend_id* is not registered.
    """
    try:
        builder = _REGISTRY[backend_id]
    except KeyError:
        raise KeyError(
            f"Unknown device backend {backend_id!r}. "
            f"Available backends: {available_backends()}."
        ) from None
    return builder(**kwargs)


# -- Built-in backends -------------------------------------------------------
# The device classes are valid builders (calling the class constructs an
# instance). Importing them here does not pull in the optional `bitalino`
# package: BitalinoDevice imports it lazily inside open().
register_device(BACKEND_BITALINO, BitalinoDevice)
register_device(BACKEND_ARDUINO, ArduinoDevice)
