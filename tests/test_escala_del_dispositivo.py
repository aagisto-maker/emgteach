"""The full scale of each board, pinned before and after `full_scale_mv()`.

Step 0 of the plan to split `AcquisitionTab` (docs/PLAN-partir-AcquisitionTab.md,
Ángel, 5 November 2026): `physical_min`/`physical_max` are to delegate to a
public `full_scale_mv()`, and those two numbers go into the header of every
EDF recorded. These tests pin, as literals taken from the code before the
change, every value that must not move: for each board and each channel
(EMG, the accelerometer, the Arduino) the physical range, the fields as they
are written into the EDF header, and the scale the raw panel is drawn to.
They compare exactly, not approximately: a change of one value in any of
them fails here.
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
#: The accelerometer is stored as normalised acceleration.
_ACC_G = 1.0

#: Each board as the application builds it, and what each channel must give:
#: kind, unit and (min, max) physical range.
_CASES = {
    "bitalino 1 EMG": (
        lambda: BitalinoDevice("simulada", fs=1000, channels=[0]),
        [("EMG", "mV", (-_BITALINO_MV, _BITALINO_MV))]),
    "bitalino 2 EMG": (
        lambda: BitalinoDevice("simulada", fs=1000, channels=[0, 1]),
        [("EMG", "mV", (-_BITALINO_MV, _BITALINO_MV))] * 2),
    "bitalino 1 EMG + ACC": (
        lambda: BitalinoDevice("simulada", fs=1000, channels=[0], acc=True, acc_channel=3),
        [("EMG", "mV", (-_BITALINO_MV, _BITALINO_MV)), ("ACC", "g", (-_ACC_G, _ACC_G))]),
    "bitalino 2 EMG + ACC": (
        lambda: BitalinoDevice("simulada", fs=1000, channels=[0, 1], acc=True, acc_channel=3),
        [("EMG", "mV", (-_BITALINO_MV, _BITALINO_MV))] * 2 + [("ACC", "g", (-_ACC_G, _ACC_G))]),
    "bitalino EMG on A2, ACC on A1": (
        lambda: BitalinoDevice("simulada", fs=1000, channels=[1], acc=True, acc_channel=0),
        [("EMG", "mV", (-_BITALINO_MV, _BITALINO_MV)), ("ACC", "g", (-_ACC_G, _ACC_G))]),
    "arduino 1": (
        lambda: ArduinoDevice("COM9", fs=1000, n_channels=1),
        [("EMG", "mV", (-_ARDUINO_MV, _ARDUINO_MV))]),
    "arduino 2": (
        lambda: ArduinoDevice("COM9", fs=1000, n_channels=2),
        [("EMG", "mV", (-_ARDUINO_MV, _ARDUINO_MV))] * 2),
}

#: The six fields of each signal in the EDF header, as pyedflib writes them
#: (8 characters, so the BITalino's range is cut to «-1.63528» / «1.635282»):
#: label, unit, physical min, physical max, digital min, digital max.
_HEADER = {
    "bitalino 1 EMG": [("m1", "mV", "-1.63528", "1.635282", "0", "1023")],
    "bitalino 2 EMG": [("m1", "mV", "-1.63528", "1.635282", "0", "1023"),
                       ("m2", "mV", "-1.63528", "1.635282", "0", "1023")],
    "bitalino 1 EMG + ACC": [("m1", "mV", "-1.63528", "1.635282", "0", "1023"),
                             ("ACC", "g", "-1", "1", "0", "1023")],
    "bitalino 2 EMG + ACC": [("m1", "mV", "-1.63528", "1.635282", "0", "1023"),
                             ("m2", "mV", "-1.63528", "1.635282", "0", "1023"),
                             ("ACC", "g", "-1", "1", "0", "1023")],
    "bitalino EMG on A2, ACC on A1": [("m1", "mV", "-1.63528", "1.635282", "0", "1023"),
                                      ("ACC", "g", "-1", "1", "0", "1023")],
    "arduino 1": [("m1", "mV", "-12.5", "12.5", "0", "1023")],
    "arduino 2": [("m1", "mV", "-12.5", "12.5", "0", "1023"),
                  ("m2", "mV", "-12.5", "12.5", "0", "1023")],
}


@pytest.mark.parametrize("case", list(_CASES))
def test_each_channel_s_physical_range_is_exactly_what_it_was(case: str) -> None:
    build, expected = _CASES[case]
    device = build()
    assert device.channel_kinds() == [k for k, _u, _r in expected]
    assert device.channel_units() == [u for _k, u, _r in expected]
    assert device.channel_physical_ranges() == [r for _k, _u, r in expected]
    emg = next(r for k, _u, r in expected if k == "EMG")
    # The scalar pair the single-modality header is built from.
    assert (device.physical_min, device.physical_max) == emg


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


@pytest.mark.parametrize("case", list(_HEADER))
def test_the_edf_header_carries_exactly_the_same_fields(case: str, tmp_path: Path) -> None:
    build, expected = _CASES[case]
    device = build()
    labels = [f"m{i + 1}" for i in range(len(expected))]
    if "ACC" in device.channel_kinds():
        labels[-1] = "ACC"
    path = tmp_path / "scale.edf"
    with pytest.warns(UserWarning, match="8 chars") if "bitalino" in case else _no_warning():
        with BufferedEdfWriter(path, channels=_channels_as_the_worker_builds_them(
                device, labels), metadata=None) as w:
            w.add_samples(*[np.zeros(1000) for _ in labels])
    assert _signal_fields(path) == _HEADER[case]


class _no_warning:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None


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
