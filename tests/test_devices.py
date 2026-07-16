"""Unit tests for :mod:`emgteach.devices` using mocks instead of hardware.

These tests run on any machine without a BITalino, an Arduino or even
a serial port. The :class:`AcquisitionDevice` contract is verified by
constructing a minimal subclass; both hardware backends are tested by
mocking ``serial.Serial`` — the BITalino backend now speaks its wire
protocol directly over ``pyserial`` (Bluetooth virtual COM port), so the
tests feed it hand-encoded BITalino frames.

The watchdog property of the BITalino device — the most novel piece
in the package, exposed in the GUI's ``QTimer`` poll — is verified by
launching :meth:`force_close` from a second thread while the first is
blocked inside :meth:`read`, and checking that the read unblocks.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from emgteach.devices import (
    BACKEND_ARDUINO,
    BACKEND_BITALINO,
    AcquisitionDevice,
    ArduinoDevice,
    BitalinoDevice,
    available_backends,
    create_device,
    register_device,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


# ---------------------------------------------------------------------------
# AcquisitionDevice — abstract contract
# ---------------------------------------------------------------------------


class TestAcquisitionDeviceABC:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            AcquisitionDevice()  # type: ignore[abstract]

    def test_minimal_concrete_subclass_works(self) -> None:
        class Dummy(AcquisitionDevice):
            @property
            def fs(self) -> float:
                return 1000.0

            @property
            def name(self) -> str:
                return "dummy"

            def open(self) -> None:
                pass

            def read(self, n_samples: int) -> np.ndarray:
                return np.zeros(n_samples, dtype=np.float64)

            def close(self) -> None:
                pass

            def force_close(self) -> None:
                pass

        d = Dummy()
        assert d.fs == 1000.0
        assert d.name == "dummy"
        assert d.read(5).shape == (5,)
        assert d.n_channels == 1  # default from the ABC


# ---------------------------------------------------------------------------
# ArduinoDevice — mocked pyserial
# ---------------------------------------------------------------------------


class _FakeSerial:
    """Minimal pyserial.Serial replacement for unit tests.

    Records every byte written, and replies to ``readline`` /
    ``read`` from a queue of pre-canned responses.
    """

    def __init__(self, *args, **kwargs) -> None:
        self.timeout = kwargs.get("timeout")
        self.is_open = True
        self.written = bytearray()
        self.readline_queue: list[bytes] = []
        self.binary_queue: bytearray = bytearray()

    def write(self, data: bytes) -> int:
        self.written += data
        return len(data)

    def flush(self) -> None:
        pass

    def readline(self) -> bytes:
        if not self.readline_queue:
            return b""
        return self.readline_queue.pop(0)

    def read(self, n: int) -> bytes:
        if not self.binary_queue:
            return b""
        head = bytes(self.binary_queue[:n])
        del self.binary_queue[:n]
        return head

    def close(self) -> None:
        self.is_open = False


@pytest.fixture
def fake_serial_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[_FakeSerial]]:
    """Patch ``serial.Serial`` to record every constructor call and return
    a list of the :class:`_FakeSerial` instances created during the test."""
    fakes: list[_FakeSerial] = []

    fake_serial_module = MagicMock()

    def factory(*args, **kwargs):
        s = _FakeSerial(*args, **kwargs)
        fakes.append(s)
        return s

    fake_serial_module.Serial.side_effect = factory
    monkeypatch.setitem(sys.modules, "serial", fake_serial_module)
    yield fakes


class TestArduinoDevice:
    def test_open_waits_ready_then_sends_start(
        self, fake_serial_factory: list[_FakeSerial]
    ) -> None:
        device = ArduinoDevice("COM4")
        # Simulate the firmware: returns "READY" first, nothing afterwards
        with patch.object(_FakeSerial, "readline", side_effect=[b"READY\n"]):
            device.open()

        assert len(fake_serial_factory) == 1
        ser = fake_serial_factory[0]
        assert b"START\n" in ser.written

    def test_open_raises_if_no_ready(
        self, monkeypatch: pytest.MonkeyPatch, fake_serial_factory: list[_FakeSerial]
    ) -> None:
        # Speed the test up by making the timeout ~zero
        monkeypatch.setattr(ArduinoDevice, "_TIMEOUT_OPEN_S", 0.05)
        device = ArduinoDevice("COM4")
        with pytest.raises(RuntimeError, match="READY"):
            device.open()

    def test_open_twice_raises(self, fake_serial_factory: list[_FakeSerial]) -> None:
        device = ArduinoDevice("COM4")
        with patch.object(_FakeSerial, "readline", side_effect=[b"READY\n"]):
            device.open()
        with pytest.raises(RuntimeError, match="already open"):
            device.open()

    def test_read_converts_adc_to_mv(
        self, fake_serial_factory: list[_FakeSerial]
    ) -> None:
        device = ArduinoDevice("COM4")
        with patch.object(_FakeSerial, "readline", side_effect=[b"READY\n"]):
            device.open()

        ser = fake_serial_factory[0]
        # ADC value 511 (≈ midscale) → 5*511/1023 ≈ 2.498 V → -0.002 V → -10 µV ≈ 0 mV
        # Two samples: ADC=511 and ADC=1023
        ser.binary_queue = bytearray(np.array([511, 1023], dtype="<u2").tobytes())

        out = device.read(2)
        assert out.shape == (2, 1)
        # ADC=1023 → V_in ≈ 5 V → (5 - 2.5)*1000/200 = 12.5 mV
        np.testing.assert_allclose(out[1, 0], 12.5, atol=0.05)
        # ADC=511 ≈ midscale → output close to 0
        assert abs(out[0, 0]) < 0.05

    def test_read_two_channels_deinterleaves(
        self, fake_serial_factory: list[_FakeSerial]
    ) -> None:
        device = ArduinoDevice("COM4", n_channels=2)
        with patch.object(_FakeSerial, "readline", side_effect=[b"READY\n"]):
            device.open()

        ser = fake_serial_factory[0]
        # Frame-interleaved: sample0=[ch0=1023, ch1=511], sample1=[ch0=511, ch1=1023]
        ser.binary_queue = bytearray(
            np.array([1023, 511, 511, 1023], dtype="<u2").tobytes()
        )

        out = device.read(2)
        assert out.shape == (2, 2)
        np.testing.assert_allclose(out[0, 0], 12.5, atol=0.05)  # ch0, sample0
        assert abs(out[0, 1]) < 0.05  # ch1, sample0
        assert abs(out[1, 0]) < 0.05  # ch0, sample1
        np.testing.assert_allclose(out[1, 1], 12.5, atol=0.05)  # ch1, sample1

    def test_n_channels_default_and_custom(self) -> None:
        assert ArduinoDevice("COM4").n_channels == 1
        assert ArduinoDevice("COM4", n_channels=2).n_channels == 2

    def test_read_timeout_raises(self, fake_serial_factory: list[_FakeSerial]) -> None:
        device = ArduinoDevice("COM4")
        with patch.object(_FakeSerial, "readline", side_effect=[b"READY\n"]):
            device.open()

        # Empty binary_queue → ser.read returns b"" → timeout path
        with pytest.raises(RuntimeError, match="Timeout"):
            device.read(1)

    def test_read_without_open_raises(self) -> None:
        device = ArduinoDevice("COM4")
        with pytest.raises(RuntimeError, match="not open"):
            device.read(10)

    def test_close_sends_stop_and_closes_port(
        self, fake_serial_factory: list[_FakeSerial]
    ) -> None:
        device = ArduinoDevice("COM4")
        with patch.object(_FakeSerial, "readline", side_effect=[b"READY\n"]):
            device.open()

        ser = fake_serial_factory[0]
        # On close, readline() will be called repeatedly until "STOPPED" is seen
        with patch.object(_FakeSerial, "readline", side_effect=[b"STOPPED\n"]):
            device.close()

        assert b"STOP\n" in ser.written
        assert ser.is_open is False

    def test_close_when_never_opened_is_noop(self) -> None:
        device = ArduinoDevice("COM4")
        device.close()  # must not raise

    def test_force_close_closes_port(
        self, fake_serial_factory: list[_FakeSerial]
    ) -> None:
        device = ArduinoDevice("COM4")
        with patch.object(_FakeSerial, "readline", side_effect=[b"READY\n"]):
            device.open()

        ser = fake_serial_factory[0]
        device.force_close()
        assert ser.is_open is False

    def test_force_close_when_never_opened_is_noop(self) -> None:
        device = ArduinoDevice("COM4")
        device.force_close()  # must not raise

    def test_name_property(self) -> None:
        device = ArduinoDevice("COM4")
        assert device.name == "Arduino MyoWare (COM4)"

    def test_fs_property(self) -> None:
        device = ArduinoDevice("COM4", fs=2000)
        assert device.fs == 2000.0


# ---------------------------------------------------------------------------
# BitalinoDevice — mocked pyserial (Bluetooth virtual COM port)
# ---------------------------------------------------------------------------
#
# The backend speaks the BITalino wire protocol over pyserial directly, so
# the helpers below encode valid BITalino acquisition frames (with the 4-bit
# CRC the device validates on read) to exercise the real decoder.


def _bitalino_crc4(frame: list[int]) -> int:
    """Reference CRC-4 over a frame whose CRC nibble is already zeroed."""
    x = 0
    for byte in frame:
        for bit in range(7, -1, -1):
            x = x << 1
            if x & 0x10:
                x = x ^ 0x03
            x = x ^ ((byte >> bit) & 0x01)
    return x & 0x0F


def _encode_frame_1ch(adc: int, seq: int = 0, digital: int = 0) -> bytes:
    """Encode a single-channel (3-byte) BITalino acquisition frame."""
    b0 = (adc & 0x3F) << 2  # A1[5:0] in the top 6 bits, 2 pad bits
    b1 = ((digital & 0x0F) << 4) | ((adc >> 6) & 0x0F)  # 4 digital | A1[9:6]
    b2 = (seq & 0x0F) << 4  # seq in high nibble, CRC nibble starts at 0
    frame = [b0, b1, b2]
    frame[2] |= _bitalino_crc4(frame)
    return bytes(frame)


def _encode_frame_2ch(a1: int, a2: int, seq: int = 0, digital: int = 0) -> bytes:
    """Encode a two-channel (4-byte) BITalino acquisition frame."""
    b0 = a2 & 0xFF  # A2[7:0]
    b1 = ((a1 & 0x3F) << 2) | ((a2 >> 8) & 0x03)  # A1[5:0] | A2[9:8]
    b2 = ((digital & 0x0F) << 4) | ((a1 >> 6) & 0x0F)  # 4 digital | A1[9:6]
    b3 = (seq & 0x0F) << 4
    frame = [b0, b1, b2, b3]
    frame[3] |= _bitalino_crc4(frame)
    return bytes(frame)


def _encode_frame_5ch(
    a1: int, a2: int, a3: int, a4: int, a5: int, seq: int = 0
) -> bytes:
    """Encode a five-channel (8-byte) BITalino frame: A1-A4 10-bit, A5 6-bit.

    This is the layout used when the accelerometer (A5) is recorded alongside
    the EMG: the contiguous block A1..A5 is enabled so A5 lands in the 6-bit
    position. Inverts the decoder's per-position bit extraction.
    """
    frame = [0] * 8
    frame[0] = (a5 & 0x03) << 6
    frame[1] = ((a4 & 0x0F) << 4) | ((a5 >> 2) & 0x0F)
    frame[2] = ((a3 & 0x03) << 6) | ((a4 >> 4) & 0x3F)
    frame[3] = (a3 >> 2) & 0xFF
    frame[4] = a2 & 0xFF
    frame[5] = ((a1 & 0x3F) << 2) | ((a2 >> 8) & 0x03)
    frame[6] = (a1 >> 6) & 0x0F
    frame[7] = (seq & 0x0F) << 4
    frame[7] |= _bitalino_crc4(frame)
    return bytes(frame)


_VERSION_REPLY = b"BITalino_v5.2\n"


@pytest.fixture
def fast_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the 100 ms inter-command spacing so tests run instantly."""
    monkeypatch.setattr(BitalinoDevice, "_CMD_GAP_S", 0.0)


class _FakePortInfo:
    """Stand-in for ``serial.tools.list_ports_common.ListPortInfo``."""

    def __init__(self, device: str, hwid: str, description: str = "") -> None:
        self.device = device
        self.hwid = hwid
        self.description = description


def _version_serial(*args, **kwargs) -> _FakeSerial:
    """A ``_FakeSerial`` already primed with the BITalino version reply."""
    s = _FakeSerial(*args, **kwargs)
    s.binary_queue = bytearray(_VERSION_REPLY)
    return s


# A Bluetooth SPP port whose hwid carries the lab BITalino's MAC, the matching
# "incoming" port with the all-zero address, and the Arduino's USB port.
_BT_OUT = _FakePortInfo(
    "COM3",
    r"BTHENUM\{00001101-0000-1000-8000-00805F9B34FB}_LOCALMFG&0046\8&x&0&98D391FE44E4_C0",
    "Standard Serial over Bluetooth link (COM3)",
)
_BT_IN = _FakePortInfo(
    "COM4",
    r"BTHENUM\{00001101-0000-1000-8000-00805F9B34FB}_LOCALMFG&0000\8&x&0&000000000000_00",
    "Standard Serial over Bluetooth link (COM4)",
)
_USB = _FakePortInfo("COM6", "USB VID:PID=10C4:EA60", "Silicon Labs CP210x USB to UART Bridge")


class TestBitalinoAddressing:
    """MAC -> COM resolution and autodetection, all PyBluez-free."""

    def test_mac_resolves_to_com_port(self, fast_commands: None) -> None:
        device = BitalinoDevice("98:D3:91:FE:44:E4", channels=[0])
        with patch(
            "serial.tools.list_ports.comports", return_value=[_BT_IN, _BT_OUT, _USB]
        ), patch("serial.Serial", side_effect=_version_serial):
            device.open()
        assert device._resolved_port == "COM3"  # matched by the MAC in the hwid
        assert "COM3" in device.name
        device.close()

    def test_mac_accepts_dash_separators(self, fast_commands: None) -> None:
        device = BitalinoDevice("98-D3-91-FE-44-E4", channels=[0])
        with patch(
            "serial.tools.list_ports.comports", return_value=[_BT_OUT]
        ), patch("serial.Serial", side_effect=_version_serial):
            device.open()
        assert device._resolved_port == "COM3"
        device.close()

    def test_mac_not_paired_raises(self, fast_commands: None) -> None:
        device = BitalinoDevice("AA:BB:CC:DD:EE:FF")
        with patch(
            "serial.tools.list_ports.comports", return_value=[_BT_IN, _USB]
        ), pytest.raises(RuntimeError, match="was not found"):
            device.open()

    def test_autodetect_empty_address(self, fast_commands: None) -> None:
        device = BitalinoDevice("", channels=[0])
        with patch(
            "serial.tools.list_ports.comports", return_value=[_BT_OUT, _USB]
        ), patch("serial.Serial", side_effect=_version_serial):
            device.open()
        assert device._resolved_port == "COM3"
        device.close()

    def test_autodetect_skips_incoming_zero_port(self, fast_commands: None) -> None:
        # The all-zero "incoming" port must be filtered out as a candidate.
        assert BitalinoDevice._bluetooth_ports([_BT_IN, _BT_OUT, _USB]) == ["COM3"]

    def test_autodetect_none_found_raises(self, fast_commands: None) -> None:
        device = BitalinoDevice("")
        with patch(
            "serial.tools.list_ports.comports", return_value=[_USB]
        ), pytest.raises(RuntimeError, match="No BITalino"):
            device.open()

    def test_name_auto_when_empty(self) -> None:
        assert BitalinoDevice("").name == "BITalino (auto)"


class TestBitalinoDeviceBasics:
    def test_name_includes_port(self) -> None:
        device = BitalinoDevice("COM5")
        assert "COM5" in device.name

    def test_fs_property(self) -> None:
        device = BitalinoDevice("COM5", fs=500)
        assert device.fs == 500.0

    def test_n_channels_matches_channels(self) -> None:
        assert BitalinoDevice("COM5").n_channels == 1
        assert BitalinoDevice("COM5", channels=[0, 1]).n_channels == 2

    def test_accelerometer_channel_layout_and_metadata(self) -> None:
        # 1 EMG + ACC: exposes A1 (EMG/mV) + A5 (ACC/g); decodes A1..A5.
        d = BitalinoDevice("COM5", channels=[0], acc=True)
        assert d.n_channels == 2
        assert d.channel_kinds() == ["EMG", "ACC"]
        assert d.channel_units() == ["mV", "g"]
        ranges = d.channel_physical_ranges()
        assert ranges[0] == (-1.65, 1.65)
        assert ranges[1] == (-1.0, 1.0)
        assert d._decode_channels == [0, 1, 2, 3, 4]   # contiguous A1..A5
        # 2 EMG + ACC exposes three channels; ACC last.
        d2 = BitalinoDevice("COM5", channels=[0, 1], acc=True)
        assert d2.n_channels == 3
        assert d2.channel_kinds() == ["EMG", "EMG", "ACC"]

    def test_no_accelerometer_is_unchanged(self) -> None:
        d = BitalinoDevice("COM5", channels=[0, 1])
        assert d.channel_kinds() == ["EMG", "EMG"]
        assert d.channel_units() == ["mV", "mV"]
        assert d._decode_channels == [0, 1]

    def test_raw_to_acc_maps_full_scale_to_pm1(self) -> None:
        np.testing.assert_allclose(BitalinoDevice.raw_to_acc(0), -1.0)
        np.testing.assert_allclose(BitalinoDevice.raw_to_acc(63), 1.0)
        np.testing.assert_allclose(
            BitalinoDevice.raw_to_acc(np.array([0, 63])), [-1.0, 1.0]
        )

    def test_open_rejects_bad_sampling_rate(self, fast_commands: None) -> None:
        device = BitalinoDevice("COM5", fs=42)
        with pytest.raises(RuntimeError, match="sampling rate"):
            device.open()

    def test_open_sends_rate_and_start_commands(
        self, fast_commands: None, fake_serial_factory: list[_FakeSerial]
    ) -> None:
        device = BitalinoDevice("COM5", fs=1000, channels=[0])
        ser = _FakeSerial()
        ser.binary_queue = bytearray(_VERSION_REPLY)
        with patch("serial.Serial", return_value=ser):
            device.open()
        assert device.is_connected
        # set-rate for 1000 Hz: (3 << 6) | 0x03 = 0xC3; start live, ch0: 0x01 | 1<<2 = 0x05
        assert 0xC3 in ser.written
        assert 0x05 in ser.written
        device.close()
        assert not device.is_connected
        # close() must send the stop/idle byte (0x00)
        assert 0x00 in ser.written

    def test_open_wrong_device_raises_and_closes_port(
        self, fast_commands: None
    ) -> None:
        device = BitalinoDevice("COM5")
        ser = _FakeSerial()
        ser.binary_queue = bytearray(b"not-a-bitalino\n")
        with patch("serial.Serial", return_value=ser), pytest.raises(
            RuntimeError, match="did not identify"
        ):
            device.open()
        assert ser.is_open is False  # the port must be closed again on failure

    def test_open_twice_raises(
        self, fast_commands: None, fake_serial_factory: list[_FakeSerial]
    ) -> None:
        device = BitalinoDevice("COM5")
        ser = _FakeSerial()
        ser.binary_queue = bytearray(_VERSION_REPLY)
        with patch("serial.Serial", return_value=ser):
            device.open()
            with pytest.raises(RuntimeError, match="already active"):
                device.open()
        device.close()

    def test_open_busy_port_raises_actionable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A busy / access-denied port must yield an actionable message that
        # tells the user to power-cycle the BITalino, after the retries.
        monkeypatch.setattr(BitalinoDevice, "_OPEN_RETRY_GAP_S", 0.0)
        monkeypatch.setattr(BitalinoDevice, "_OPEN_RETRIES", 2)
        device = BitalinoDevice("COM5")

        def denied(*args, **kwargs):
            raise PermissionError(13, "Access is denied")

        with patch("serial.Serial", side_effect=denied), pytest.raises(
            RuntimeError, match="off and on"
        ):
            device.open()

    def test_read_without_open_raises(self) -> None:
        device = BitalinoDevice("COM5")
        with pytest.raises(RuntimeError, match="not open"):
            device.read(100)

    def test_close_without_open_is_noop(self) -> None:
        device = BitalinoDevice("COM5")
        device.close()  # must not raise

    def test_read_one_channel_decodes_to_mv(self, fast_commands: None) -> None:
        device = BitalinoDevice("COM5", fs=1000, channels=[0])
        ser = _FakeSerial()
        # version reply, then two frames: ADC=1023 (full scale) and ADC=0
        ser.binary_queue = bytearray(
            _VERSION_REPLY + _encode_frame_1ch(1023) + _encode_frame_1ch(0)
        )
        with patch("serial.Serial", return_value=ser):
            device.open()
        out = device.read(2)
        assert out.shape == (2, 1)
        np.testing.assert_allclose(out[0, 0], 1.65, atol=0.01)  # ADC max → +1.65 mV
        np.testing.assert_allclose(out[1, 0], -1.65, atol=0.01)  # ADC 0  → -1.65 mV
        device.close()

    def test_read_two_channels_returns_two_columns(self, fast_commands: None) -> None:
        device = BitalinoDevice("COM5", fs=1000, channels=[0, 1])
        ser = _FakeSerial()
        # one frame: A1=1023 (+1.65 mV), A2=512 (≈ midscale → ≈0 mV)
        ser.binary_queue = bytearray(_VERSION_REPLY + _encode_frame_2ch(1023, 512))
        with patch("serial.Serial", return_value=ser):
            device.open()
        out = device.read(1)
        assert out.shape == (1, 2)
        np.testing.assert_allclose(out[0, 0], 1.65, atol=0.01)
        assert abs(out[0, 1]) < 0.02
        device.close()

    def test_read_two_channels_plus_accelerometer(self, fast_commands: None) -> None:
        """acc=True exposes EMG + a normalised ACC column, decoded from A1..A5."""
        device = BitalinoDevice("COM5", fs=1000, channels=[0, 1], acc=True)
        # A1=1023 (+1.65 mV), A2=512 (~0 mV), A3/A4 ignored, A5=63 (+1.0 g).
        frame = _encode_frame_5ch(a1=1023, a2=512, a3=0, a4=0, a5=63)
        ser = _FakeSerial()
        ser.binary_queue = bytearray(_VERSION_REPLY + frame)
        with patch("serial.Serial", return_value=ser):
            device.open()
        out = device.read(1)
        # Three exposed columns: EMG A1, EMG A2, ACC A5 (A3/A4 dropped).
        assert out.shape == (1, 3)
        np.testing.assert_allclose(out[0, 0], 1.65, atol=0.01)   # A1 in mV
        assert abs(out[0, 1]) < 0.02                             # A2 ~0 mV
        np.testing.assert_allclose(out[0, 2], 1.0, atol=0.01)    # A5 = +1 g
        device.close()

    def test_read_timeout_raises(self, fast_commands: None) -> None:
        device = BitalinoDevice("COM5")
        ser = _FakeSerial()
        ser.binary_queue = bytearray(_VERSION_REPLY)  # no frames follow
        with patch("serial.Serial", return_value=ser):
            device.open()
        with pytest.raises(RuntimeError, match="Timeout"):
            device.read(1)
        device.close()

    def test_read_crc_mismatch_raises(self, fast_commands: None) -> None:
        device = BitalinoDevice("COM5", channels=[0])
        frame = bytearray(_encode_frame_1ch(500))
        frame[-1] ^= 0x01  # corrupt the CRC nibble
        ser = _FakeSerial()
        ser.binary_queue = bytearray(_VERSION_REPLY + bytes(frame))
        with patch("serial.Serial", return_value=ser):
            device.open()
        with pytest.raises(RuntimeError, match="CRC"):
            device.read(1)
        device.close()


class TestBitalinoConversion:
    def test_raw_to_mv_midscale_is_zero(self) -> None:
        # ADC midscale (511.5) → 0 mV
        result = BitalinoDevice.raw_to_mv(np.array([511.5]))
        np.testing.assert_allclose(result, 0.0, atol=1e-6)

    def test_raw_to_mv_full_scale(self) -> None:
        # ADC max → +1.65 V (+1.65 mV in BITalino convention from prototype)
        # The conversion is ((adc/1023) - 0.5) * 3.3
        result = BitalinoDevice.raw_to_mv(np.array([1023.0]))
        np.testing.assert_allclose(result, 1.65, atol=0.01)

    def test_raw_to_mv_zero_adc(self) -> None:
        # ADC=0 → -1.65 V (full negative excursion)
        result = BitalinoDevice.raw_to_mv(np.array([0.0]))
        np.testing.assert_allclose(result, -1.65, atol=0.01)


class _BlockingFakeSerial:
    """Fake serial whose streaming read blocks until :meth:`close`.

    During ``open`` it returns the version reply byte-by-byte; once that is
    exhausted, any further ``read`` blocks on an event until ``close`` is
    called from another thread — mimicking a real serial read that the
    operating system releases when the port is yanked shut.
    """

    def __init__(self, *args, **kwargs) -> None:
        self.timeout = kwargs.get("timeout")
        self.is_open = True
        self.written = bytearray()
        self._version = bytearray(_VERSION_REPLY)
        self._closed = threading.Event()

    def write(self, data: bytes) -> int:
        self.written += data
        return len(data)

    def read(self, n: int) -> bytes:
        if self._version:
            head = bytes(self._version[:n])
            del self._version[:n]
            return head
        # Block as a real read would, until the port is closed.
        self._closed.wait(timeout=5.0)
        return b""

    def close(self) -> None:
        self.is_open = False
        self._closed.set()


class TestBitalinoWatchdog:
    """The pivotal property of :meth:`BitalinoDevice.force_close`.

    Background. The per-frame serial read can block indefinitely if the
    Bluetooth link drops mid-session. The watchdog protocol releases the
    blocked read by closing the port from a second thread. The test below
    reproduces the scenario: thread A enters ``read``; thread B calls
    ``force_close``; thread A must unblock promptly (well under the 3-second
    GUI threshold).
    """

    def test_force_close_releases_blocked_read(self, fast_commands: None) -> None:
        device = BitalinoDevice("COM5", channels=[0])
        ser = _BlockingFakeSerial()
        with patch("serial.Serial", return_value=ser):
            device.open()

        elapsed_ms: list[float] = []
        exceptions: list[BaseException] = []

        def reader() -> None:
            t0 = time.monotonic()
            try:
                device.read(1000)
            except BaseException as exc:
                exceptions.append(exc)
            elapsed_ms.append((time.monotonic() - t0) * 1000.0)

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        # Give thread A a chance to enter the blocking read
        time.sleep(0.05)
        # Trigger the watchdog from this thread
        device.force_close()
        t.join(timeout=2.0)

        assert not t.is_alive(), "Reader thread did not unblock after force_close()"
        assert len(elapsed_ms) == 1
        assert elapsed_ms[0] < 500, (
            f"Reader took {elapsed_ms[0]:.0f} ms to unblock; expected well "
            "under the 3-second GUI watchdog threshold."
        )
        assert exceptions, "Reader did not see the close-induced exception."


# ---------------------------------------------------------------------------
# Device factory / registry
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_registry() -> Iterator[None]:
    """Snapshot and restore the factory registry around a test."""
    from emgteach.devices import factory

    snapshot = dict(factory._REGISTRY)
    try:
        yield
    finally:
        factory._REGISTRY.clear()
        factory._REGISTRY.update(snapshot)


class TestDeviceFactory:
    def test_builtin_backends_are_registered(self) -> None:
        backends = available_backends()
        assert BACKEND_BITALINO in backends
        assert BACKEND_ARDUINO in backends

    def test_create_arduino_returns_arduino_device(self) -> None:
        device = create_device(BACKEND_ARDUINO, port="COM9", fs=1000)
        assert isinstance(device, ArduinoDevice)
        assert device.fs == 1000.0
        assert "COM9" in device.name

    def test_create_bitalino_returns_bitalino_device(self) -> None:
        # Construction must not touch the serial port; it is opened lazily
        # inside open(), not here.
        device = create_device(BACKEND_BITALINO, port="COM5", fs=1000)
        assert isinstance(device, BitalinoDevice)
        assert device.fs == 1000.0
        assert "COM5" in device.name

    def test_unknown_backend_raises_keyerror(self) -> None:
        with pytest.raises(KeyError, match="Unknown device backend"):
            create_device("not-a-backend")

    def test_register_new_backend(self, clean_registry: None) -> None:
        class _DummyDevice(AcquisitionDevice):
            def __init__(self, label: str = "x") -> None:
                self._label = label

            @property
            def fs(self) -> float:
                return 500.0

            @property
            def name(self) -> str:
                return f"dummy:{self._label}"

            def open(self) -> None:
                pass

            def read(self, n_samples: int) -> np.ndarray:
                return np.zeros(n_samples, dtype=np.float64)

            def close(self) -> None:
                pass

            def force_close(self) -> None:
                pass

        register_device("dummy", _DummyDevice)
        assert "dummy" in available_backends()
        device = create_device("dummy", label="abc")
        assert isinstance(device, _DummyDevice)
        assert device.name == "dummy:abc"


class TestDevicePhysicalRange:
    """Each backend reports its true full-scale (mV) for the EDF header, so
    strong contractions are not silently clipped (Arduino spans ±12.5 mV,
    well beyond the BITalino default ±3.3 mV)."""

    def test_arduino_full_scale_is_pm_12_5_mv(self) -> None:
        device = ArduinoDevice("COM4")
        assert device.physical_max == pytest.approx(12.5)
        assert device.physical_min == pytest.approx(-12.5)

    def test_bitalino_full_scale_is_pm_1_65_mv(self) -> None:
        device = BitalinoDevice("COM5")
        assert device.physical_max == pytest.approx(1.65)
        assert device.physical_min == pytest.approx(-1.65)
