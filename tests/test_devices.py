"""Unit tests for :mod:`emgteach.devices` using mocks instead of hardware.

These tests run on any machine without a BITalino, an Arduino or even
a serial port. The :class:`AcquisitionDevice` contract is verified by
constructing a minimal subclass; the Arduino backend is tested by
mocking ``serial.Serial``; the BITalino backend is tested by mocking
the ``bitalino`` module's ``BITalino`` class.

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

from emgteach.devices import AcquisitionDevice, ArduinoDevice, BitalinoDevice

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
        assert out.shape == (2,)
        # ADC=1023 → V_in ≈ 5 V → (5 - 2.5)*1000/200 = 12.5 mV
        np.testing.assert_allclose(out[1], 12.5, atol=0.05)
        # ADC=511 ≈ midscale → output close to 0
        assert abs(out[0]) < 0.05

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
# BitalinoDevice — mocked bitalino package
# ---------------------------------------------------------------------------


class _FakeBITalino:
    """Stand-in for ``bitalino.BITalino``.

    Has a ``read_event`` controllable from tests so that we can simulate
    a blocking ``read`` and a ``close`` from another thread.
    """

    def __init__(self, mac: str) -> None:
        self.mac = mac
        self.started = False
        self.closed = False
        self.read_event = threading.Event()
        self.read_should_raise: BaseException | None = None
        self.last_n: int = 0

    def start(self, fs: int, channels: list[int]) -> None:
        self.started = True

    def read(self, n: int) -> np.ndarray:
        self.last_n = n
        # Block until either the test sets read_event, or close() is called.
        # When close() is called, raising mimics what real BITalino does
        # when the underlying socket is yanked from under it.
        self.read_event.wait(timeout=5.0)
        if self.read_should_raise is not None:
            raise self.read_should_raise
        # Default: return n rows by 6 columns (BITalino returns a matrix)
        # with ADC values ~512 (midscale).
        return np.full((n, 6), 512.0)

    def stop(self) -> None:
        self.started = False

    def close(self) -> None:
        self.closed = True
        # Unblock any pending read by signalling the event with an exception
        if not self.read_event.is_set():
            self.read_should_raise = OSError("Connection closed")
            self.read_event.set()


@pytest.fixture
def fake_bitalino_module(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    """Patch the ``bitalino`` module so :class:`BitalinoDevice.open` finds it."""
    fake = MagicMock()
    fake.BITalino.side_effect = lambda mac: _FakeBITalino(mac)
    monkeypatch.setitem(sys.modules, "bitalino", fake)
    yield fake


class TestBitalinoDeviceBasics:
    def test_open_without_extra_raises_helpful_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate the bitalino package not being installed
        monkeypatch.setitem(sys.modules, "bitalino", None)
        device = BitalinoDevice("00:00:00:00:00:00")
        with pytest.raises(ImportError, match='emgteach\\[bitalino\\]'):
            device.open()

    def test_name_includes_mac(self) -> None:
        device = BitalinoDevice("98:D3:91:FE:44:E4")
        assert "98:D3:91:FE:44:E4" in device.name

    def test_fs_property(self) -> None:
        device = BitalinoDevice("00:00:00:00:00:00", fs=500)
        assert device.fs == 500.0

    def test_open_starts_streaming(self, fake_bitalino_module: MagicMock) -> None:
        device = BitalinoDevice("AA:BB:CC:DD:EE:FF", fs=1000, channels=[0, 1])
        device.open()
        assert device.is_connected
        device.close()
        assert not device.is_connected

    def test_open_twice_raises(self, fake_bitalino_module: MagicMock) -> None:
        device = BitalinoDevice("AA:BB:CC:DD:EE:FF")
        device.open()
        with pytest.raises(RuntimeError, match="already active"):
            device.open()
        device.close()

    def test_read_without_open_raises(self) -> None:
        device = BitalinoDevice("AA:BB:CC:DD:EE:FF")
        with pytest.raises(RuntimeError, match="not open"):
            device.read(100)

    def test_close_without_open_is_noop(self) -> None:
        device = BitalinoDevice("AA:BB:CC:DD:EE:FF")
        device.close()  # must not raise


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


class TestBitalinoWatchdog:
    """The pivotal property of :meth:`BitalinoDevice.force_close`.

    Background. ``bitalino.BITalino.read`` can block indefinitely if the
    Bluetooth link drops mid-session. The watchdog protocol releases
    the blocked read by closing the socket from a second thread. The
    test below reproduces the scenario in microcosm: thread A enters
    ``read``; thread B calls ``force_close``; thread A must unblock
    promptly (in much less than the 3-second GUI threshold).
    """

    def test_force_close_releases_blocked_read(
        self, fake_bitalino_module: MagicMock
    ) -> None:
        device = BitalinoDevice("AA:BB:CC:DD:EE:FF")
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
