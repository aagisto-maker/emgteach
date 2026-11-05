"""The full scale of each board, pinned before and after `full_scale_mv()`.

Step 0 of the plan to split `AcquisitionTab` (docs/PLAN-partir-AcquisitionTab.md,
Ángel, 5 November 2026): `physical_min`/`physical_max` are to delegate to a
public `full_scale_mv()`, and those two numbers go into the header of every
EDF recorded. These tests pin, as literals taken from the code before the
change, every value that must not move: for each board, each montage and
each channel (EMG, the accelerometer, the Arduino) the physical range, the
fields as they are written into the EDF header, and the scale the raw panel
is drawn to. They compare exactly, not approximately, and **one case per
channel**, so that a change in one value fails the channel it belongs to
and no other: the EMG's gain leaves the accelerometer's cases green, and
the accelerometer's range leaves the EMG's (Ángel, 5 November 2026).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emgteach.devices.arduino import ArduinoDevice
from emgteach.devices.bitalino import BitalinoDevice
from emgteach.io import BufferedEdfWriter, ChannelInfo
from emgteach.profiles import EMG_PROFILE

#: ±(3.3 V / 2) · 1000 / 1009, as the float the code gives.
_BITALINO_MV = 1.635282457879088
#: ±(5 V / 2) · 1000 / 200.
_ARDUINO_MV = 12.5
#: The accelerometer is stored as normalised acceleration, ±1 g, whatever
#: the EMG front end's gain.
_ACC_G = 1.0

_EMG_BIT = ("EMG", "mV", (-_BITALINO_MV, _BITALINO_MV))
_EMG_ARD = ("EMG", "mV", (-_ARDUINO_MV, _ARDUINO_MV))
_ACC = ("ACC", "g", (-_ACC_G, _ACC_G))

#: Each montage as the application builds it, and what each of its channels
#: must give: kind, unit and (min, max) physical range.
_MONTAGES = {
    "bitalino 1 EMG": (
        lambda: BitalinoDevice("simulada", fs=1000, channels=[0]),
        [_EMG_BIT]),
    "bitalino 2 EMG": (
        lambda: BitalinoDevice("simulada", fs=1000, channels=[0, 1]),
        [_EMG_BIT, _EMG_BIT]),
    "bitalino 1 EMG + ACC": (
        lambda: BitalinoDevice("simulada", fs=1000, channels=[0], acc=True, acc_channel=3),
        [_EMG_BIT, _ACC]),
    "bitalino 2 EMG + ACC": (
        lambda: BitalinoDevice("simulada", fs=1000, channels=[0, 1], acc=True, acc_channel=3),
        [_EMG_BIT, _EMG_BIT, _ACC]),
    "bitalino EMG on A2, ACC on A1": (
        lambda: BitalinoDevice("simulada", fs=1000, channels=[1], acc=True, acc_channel=0),
        [_EMG_BIT, _ACC]),
    "arduino 1": (
        lambda: ArduinoDevice("COM9", fs=1000, n_channels=1),
        [_EMG_ARD]),
    "arduino 2": (
        lambda: ArduinoDevice("COM9", fs=1000, n_channels=2),
        [_EMG_ARD, _EMG_ARD]),
}

#: The six fields of each signal in the EDF header, as pyedflib writes them
#: (8 characters, so the BITalino's range is cut to «-1.63528» / «1.635282»):
#: label, unit, physical min, physical max, digital min, digital max.
_HDR_BIT = ("mV", "-1.63528", "1.635282", "0", "1023")
_HDR_ARD = ("mV", "-12.5", "12.5", "0", "1023")
_HDR_ACC = ("g", "-1", "1", "0", "1023")
_HEADER = {
    "bitalino 1 EMG": [_HDR_BIT],
    "bitalino 2 EMG": [_HDR_BIT, _HDR_BIT],
    "bitalino 1 EMG + ACC": [_HDR_BIT, _HDR_ACC],
    "bitalino 2 EMG + ACC": [_HDR_BIT, _HDR_BIT, _HDR_ACC],
    "bitalino EMG on A2, ACC on A1": [_HDR_BIT, _HDR_ACC],
    "arduino 1": [_HDR_ARD],
    "arduino 2": [_HDR_ARD, _HDR_ARD],
}

#: One case per channel of each montage, named by its kind.
_CHANNELS = [
    pytest.param(montage, i, id=f"{montage} / ch{i} {kind}")
    for montage, (_build, channels) in _MONTAGES.items()
    for i, (kind, _unit, _range) in enumerate(channels)
]


@pytest.mark.parametrize("montage", list(_MONTAGES))
def test_each_montage_has_the_channels_it_had(montage: str) -> None:
    build, expected = _MONTAGES[montage]
    device = build()
    assert device.channel_kinds() == [k for k, _u, _r in expected]
    assert device.n_channels == len(expected)


@pytest.mark.parametrize(("montage", "i"), _CHANNELS)
def test_each_channel_s_physical_range_is_exactly_what_it_was(montage: str, i: int) -> None:
    build, expected = _MONTAGES[montage]
    device = build()
    kind, unit, physical = expected[i]
    assert device.channel_kinds()[i] == kind
    assert device.channel_units()[i] == unit
    assert device.channel_physical_ranges()[i] == physical
    if kind == "EMG":
        # The scalar pair the single-modality header is built from.
        assert (device.physical_min, device.physical_max) == physical
    else:
        # The accelerometer's range is its own, not the EMG front end's.
        assert physical == (-_ACC_G, _ACC_G)


def _channels_as_the_worker_builds_them(device, labels: list[str], fs: int = 1000):
    """The EDF channels of a recording, as AcquisitionWorker.run builds them:
    one per column with its own unit and range when the accelerometer is
    there, the profile's with the device's scalar range when it is not."""
    kinds = list(device.channel_kinds())
    if "ACC" in kinds:
        units = list(device.channel_units())
        ranges = list(device.channel_physical_ranges())
        return [
            ChannelInfo(labels[c], dimension=units[c], sample_frequency=fs,
                        physical_min=ranges[c][0], physical_max=ranges[c][1])
            for c in range(len(kinds))
        ]
    return EMG_PROFILE.build_channels(
        labels, fs, physical_min=device.physical_min, physical_max=device.physical_max)


def _signal_fields(path: Path) -> list[tuple[str, ...]]:
    """The per-signal fields of an EDF header, read off the bytes: label,
    unit, physical min, physical max, digital min, digital max. The
    annotations signal is left out."""
    with open(path, "rb") as f:
        header = f.read(256)
        ns = int(header[252:256])
        rest = f.read(ns * (16 + 80 + 8 * 6))
    widths = (16, 80, 8, 8, 8, 8, 8)
    columns = []
    offset = 0
    for w in widths:
        columns.append([rest[offset + w * i:offset + w * (i + 1)].decode().strip()
                        for i in range(ns)])
        offset += w * ns
    label, _transducer, unit, pmin, pmax, dmin, dmax = columns
    return [(label[i], unit[i], pmin[i], pmax[i], dmin[i], dmax[i])
            for i in range(ns) if not label[i].startswith("EDF Annotations")]


class _no_warning:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None


def _recorded_header(montage: str, tmp_path: Path) -> list[tuple[str, ...]]:
    """Write a second of the montage as the worker would and read its header."""
    build, expected = _MONTAGES[montage]
    device = build()
    labels = [f"m{i + 1}" for i in range(len(expected))]
    if "ACC" in device.channel_kinds():
        labels[-1] = "ACC"
    path = tmp_path / "scale.edf"
    warns = pytest.warns(UserWarning, match="8 chars") if "bitalino" in montage else _no_warning()
    with warns, BufferedEdfWriter(
            path, channels=_channels_as_the_worker_builds_them(device, labels),
            metadata=None) as w:
        w.add_samples(*[np.zeros(1000) for _ in labels])
    return _signal_fields(path)


@pytest.mark.parametrize(("montage", "i"), _CHANNELS)
def test_the_edf_header_carries_exactly_the_same_fields(
    montage: str, i: int, tmp_path: Path,
) -> None:
    fields = _recorded_header(montage, tmp_path)
    assert len(fields) == len(_HEADER[montage])
    label = "ACC" if _MONTAGES[montage][1][i][0] == "ACC" else f"m{i + 1}"
    assert fields[i] == (label, *_HEADER[montage][i])


@pytest.mark.gui
class TestTheRawPanelIsDrawnToTheSameScale:
    """The raw panel's range when a board type is chosen, before any device
    is opened (AcquisitionTab._ajustar_rango_bruto_al_dispositivo): the
    BITalino's ±1.635 mV and the Arduino's ±12.5 mV, exactly."""

    def test_bitalino(self, qapp) -> None:
        from tests.test_arreglos_pantalla import _cierra, _ventana

        win = _ventana(qapp, "single")
        try:
            adq = win._tab_adq
            adq._combo_device_type.setCurrentIndex(1)
            adq._combo_device_type.setCurrentIndex(0)
            qapp.processEvents()
            assert adq._y_ranges_init[0] == (-_BITALINO_MV, _BITALINO_MV)
        finally:
            _cierra(qapp, win)

    def test_arduino(self, qapp) -> None:
        from tests.test_arreglos_pantalla import _cierra, _ventana

        win = _ventana(qapp, "single")
        try:
            adq = win._tab_adq
            adq._combo_device_type.setCurrentIndex(1)
            qapp.processEvents()
            assert adq._y_ranges_init[0] == (-_ARDUINO_MV, _ARDUINO_MV)
        finally:
            _cierra(qapp, win)
