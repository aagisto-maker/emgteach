"""The BITalino in software: the board's protocol, without the board.

Writing ``simulada`` as the address has to make the application run exactly
as with the board above the serial port, so these tests drive the real
``BitalinoDevice`` — its frame decoder, its CRC check, its close and its
watchdog — against the simulated port, never a copy of them.
"""

from __future__ import annotations

import random
import threading
import time
from unittest.mock import patch

import numpy as np
import pytest

from emgteach.devices.bitalino import BitalinoDevice
from emgteach.devices.bitalino_sim import (
    SIMULATED_PORT,
    SimulatedBitalinoPort,
    crc4,
    encode_frame,
    frame_size,
    is_simulated_address,
)


@pytest.mark.parametrize("n", range(1, 7))
def test_every_frame_decodes_as_the_board_s(n: int) -> None:
    """Encoded by the simulator, decoded and CRC-checked by the application."""
    rng = random.Random(n)
    for _ in range(500):
        values = [rng.randrange(1024) if pos < 4 else rng.randrange(64) for pos in range(n)]
        seq = rng.randrange(16)
        frame = list(encode_frame(values, seq))
        assert len(frame) == frame_size(n)
        assert (frame[-1] >> 4) == seq
        assert BitalinoDevice._crc_ok(frame)
        assert [BitalinoDevice._extract_channel(frame, c) for c in range(n)] == values


def test_a_flipped_bit_fails_the_crc() -> None:
    frame = bytearray(encode_frame([300, 700], 5))
    frame[0] ^= 0x10
    assert not BitalinoDevice._crc_ok(list(frame))
    assert crc4(bytearray(4)) == 0


@pytest.mark.parametrize("address", ["simulada", "Simulada", " SIMULATED "])
def test_the_address_selects_the_simulated_board(address: str) -> None:
    assert is_simulated_address(address)
    device = BitalinoDevice(address)
    assert device.is_simulated
    # No COM port is consulted: there is no Bluetooth involved at all.
    with patch("serial.tools.list_ports.comports", side_effect=AssertionError):
        assert device._resolve_port() == SIMULATED_PORT


@pytest.mark.parametrize("address", ["COM5", "", "98:D3:91:FE:44:E4", "sim"])
def test_other_addresses_are_the_board(address: str) -> None:
    assert not BitalinoDevice(address).is_simulated


CONFIGS = [
    ("single", dict(channels=[0])),
    ("pair", dict(channels=[0, 1])),
    ("kinematics", dict(channels=[0], acc=True, acc_channel=1)),
    ("channel diagnostic", dict(channels=[0, 1, 2, 3, 4, 5])),
]


@pytest.mark.parametrize(("name", "kwargs"), CONFIGS, ids=[c[0] for c in CONFIGS])
def test_the_application_opens_reads_and_closes_it(name: str, kwargs: dict) -> None:
    device = BitalinoDevice("simulada", fs=1000, **kwargs)
    device.open()
    try:
        assert "simulated" in device.name
        assert "BITalino" in device.firmware_version
        start = time.perf_counter()
        data = np.vstack([device.read(100) for _ in range(12)])   # 1.2 s
        elapsed = time.perf_counter() - start
    finally:
        device.close()
    assert not device.is_connected
    assert data.shape == (1200, device.n_channels)
    # Delivered at the real sampling rate, not all at once.
    assert 0.9 < elapsed < 1.8, elapsed
    kinds = device.channel_kinds()
    for i, kind in enumerate(kinds):
        lo, hi = device.channel_physical_ranges()[i]
        assert np.all((data[:, i] >= lo) & (data[:, i] <= hi)), (name, kind)
    # The cycle starts at rest and the first muscle contracts from 0.5 s.
    first = kinds.index("EMG")
    assert np.std(data[700:1200, first]) > 5 * np.std(data[:400, first])


def test_the_accelerometer_follows_the_first_muscle() -> None:
    device = BitalinoDevice("simulada", fs=1000, channels=[0], acc=True, acc_channel=1)
    device.open()
    try:
        data = np.vstack([device.read(200) for _ in range(12)])    # 2.4 s
    finally:
        device.close()
    acc = data[:, device.channel_kinds().index("ACC")]
    assert acc[1800:2400].mean() > acc[:400].mean() + 0.1


def test_close_releases_a_blocked_read() -> None:
    """The watchdog closes the port from another thread; the read must end."""
    device = BitalinoDevice("simulada", fs=1000, channels=[0])
    device.open()
    outcome: list[BaseException | None] = []

    def reader() -> None:
        try:
            device.read(20_000)            # 20 s: far longer than the test
            outcome.append(None)
        except BaseException as exc:       # the point is that it ends, however
            outcome.append(exc)

    thread = threading.Thread(target=reader)
    thread.start()
    time.sleep(0.2)
    device.force_close()
    thread.join(2.0)
    assert not thread.is_alive()
    assert outcome and outcome[0] is not None


def test_a_new_session_without_a_stop_answers_the_version_again() -> None:
    """A dropped link leaves no stop byte behind: the board returns to idle."""
    port = SimulatedBitalinoPort(timeout=0.5)
    port.write(bytes([0xC3, 0x05]))        # 1000 Hz, start A1
    time.sleep(0.05)
    assert port.in_waiting > 0
    port.write(bytes([0x07]))
    port.reset_input_buffer()
    port.write(bytes([0x07]))
    assert port.read(64).startswith(b"BITalino")
    port.close()
