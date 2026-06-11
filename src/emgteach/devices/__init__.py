"""Hardware backends for biopotential acquisition.

Two interchangeable backends are provided:

- :class:`ArduinoDevice` — Arduino RedBoard Plus + MyoWare 2.0 over USB serial
- :class:`BitalinoDevice` — BITalino *(revolution)* over Bluetooth (optional;
  requires the ``bitalino`` extra)

Both implement the :class:`AcquisitionDevice` interface so the rest of
the package (workers, GUI tabs) is hardware-agnostic.
"""

from __future__ import annotations

from emgteach.devices.arduino import ArduinoDevice
from emgteach.devices.base import AcquisitionDevice
from emgteach.devices.bitalino import BitalinoDevice
from emgteach.devices.factory import (
    BACKEND_ARDUINO,
    BACKEND_BITALINO,
    available_backends,
    create_device,
    register_device,
)

__all__ = [
    "BACKEND_ARDUINO",
    "BACKEND_BITALINO",
    "AcquisitionDevice",
    "ArduinoDevice",
    "BitalinoDevice",
    "available_backends",
    "create_device",
    "register_device",
]
