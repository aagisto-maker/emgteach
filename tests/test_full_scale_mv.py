"""`full_scale_mv()`: the device's full scale as a public method.

Step 0 of the plan to split `AcquisitionTab` (docs/PLAN-partir-AcquisitionTab.md,
Ángel, 5 November 2026). The acquisition tab drew its raw panel to the
board's scale by importing the two device classes and reading their private
`_V_REF` and `_GAIN_EMG`/`_GAIN`. The scale is now asked of the device
class, through the factory, and the EDF header's `physical_min`/`physical_max`
come from the same number. What each value must be is pinned apart, in
tests/test_escala_del_dispositivo.py.
"""

from __future__ import annotations

import inspect

import pytest

from emgteach.devices import (
    BACKEND_ARDUINO,
    BACKEND_BITALINO,
    AcquisitionDevice,
    ArduinoDevice,
    BitalinoDevice,
    device_class,
    factory,
)


class _Bare(AcquisitionDevice):
    """A backend that says nothing about its scale: the generic rail."""

    @property
    def fs(self) -> float:
        return 1000.0

    @property
    def name(self) -> str:
        return "bare"

    def open(self) -> None:
        pass

    def read(self, n_samples: int):
        raise NotImplementedError

    def close(self) -> None:
        pass

    def force_close(self) -> None:
        pass


def test_a_backend_that_says_nothing_has_the_generic_rail() -> None:
    assert _Bare.full_scale_mv() == 3.3
    d = _Bare()
    assert (d.physical_min, d.physical_max) == (-3.3, 3.3)
    assert _Bare.list_ports() == []


def test_each_board_s_full_scale_is_its_rail_over_its_gain() -> None:
    # Class-level: no device has to exist for the tab to scale its panel.
    assert BitalinoDevice.full_scale_mv() == 3.3 / 2.0 * 1000.0 / 1009.0
    assert ArduinoDevice.full_scale_mv() == 5.0 / 2.0 * 1000.0 / 200.0
    # A profile may supply the gain of the sensor it describes.
    assert BitalinoDevice.full_scale_mv(sensor_gain=1100.0) == 3.3 / 2.0 * 1000.0 / 1100.0
    assert ArduinoDevice.full_scale_mv(sensor_gain=400.0) == 5.0 / 2.0 * 1000.0 / 400.0


def test_the_header_s_range_is_the_same_number() -> None:
    """physical_min/max delegate to full_scale_mv(): one source for the EDF
    header and the panel."""
    for device in (BitalinoDevice("simulada", fs=1000, channels=[0, 1], acc=True),
                   ArduinoDevice("COM9", fs=1000, n_channels=2)):
        scale = type(device).full_scale_mv()
        assert device.physical_max == scale
        assert device.physical_min == -scale
        emg = [r for r, k in zip(device.channel_physical_ranges(), device.channel_kinds(),
                                 strict=True) if k == "EMG"]
        assert emg and all(r == (-scale, scale) for r in emg)


def test_the_factory_gives_the_class_behind_a_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    assert device_class(BACKEND_BITALINO) is BitalinoDevice
    assert device_class(BACKEND_ARDUINO) is ArduinoDevice
    with pytest.raises(KeyError, match="Unknown device backend"):
        device_class("no-such-board")
    # A builder function is a valid backend for create_device, but it has no
    # class to ask a scale of.
    monkeypatch.setitem(factory._REGISTRY, "built", lambda **kw: _Bare())
    with pytest.raises(TypeError, match="builder function"):
        device_class("built")


def test_the_arduino_lists_serial_ports_and_the_bitalino_does_not() -> None:
    assert isinstance(ArduinoDevice.list_ports(), list)
    assert BitalinoDevice.list_ports() == []


def test_the_tab_names_no_device_class_and_reads_no_private_constant() -> None:
    from emgteach.gui.tabs import acquisition

    source = inspect.getsource(acquisition)
    assert "_GAIN" not in source and "_V_REF" not in source
    assert not hasattr(acquisition, "BitalinoDevice")
    assert not hasattr(acquisition, "ArduinoDevice")
