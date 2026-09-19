"""A BITalino (revolution) in software, to try the application without the board.

Writing ``simulada`` (or ``simulated``) as the BITalino address makes
:class:`~emgteach.devices.bitalino.BitalinoDevice` open
:class:`SimulatedBitalinoPort` instead of a Bluetooth virtual COM port. The
port speaks the board's wire protocol byte for byte — the version reply, the
sampling-rate and start commands, frames with their sequence number and 4-bit
CRC — so everything above the serial port runs as it does with the board: the
frame decoder and its CRC check, the acquisition worker and its watchdog, the
calibration wizard, the recording and the classroom broadcast. Only the
Bluetooth link and the electrodes are left out, which is what makes it useful
in a laboratory where the board is not at hand.

The signal is synthetic: Gaussian noise whose amplitude follows a 12-second
cycle that starts with every connection — rest, a flexion of the first muscle
at 0.5 s, an extension of the second at 4.5 s and a grip with both at 8.5 s —
converted to ADC counts with the inverse of the application's own conversion.
An accelerometer channel, when one is enabled, follows the first muscle's
contraction with a short delay. It is nobody's recording and measures nothing;
the device calls itself "BITalino (simulated)", and that name goes into the
EDF header of anything recorded with it.
"""

from __future__ import annotations

import math
import random
import threading
import time

#: Addresses that select the simulated board (compared case-insensitively).
SIMULATED_ADDRESSES = ("simulada", "simulated")
#: The port name the address resolves to.
SIMULATED_PORT = "simulada"
#: What the simulated board answers to the version request.
VERSION_REPLY = b"BITalino_v5.2 SIMULATED\n"

_VCC = 3.3
_GAIN = 1009.0
_ADC_MAX = 1023
_FS_BY_CODE = {3: 1000, 2: 100, 1: 10, 0: 1}

#: The activity cycle: (start s, end s, level of muscle 1, level of muscle 2).
CYCLE_S = 12.0
_CYCLE = (
    (0.5, 2.5, 0.50, 0.05),     # flexion
    (4.5, 6.5, 0.05, 0.50),     # extension
    (8.5, 10.5, 0.40, 0.40),    # grip: both at once
)
_RAMP_S = 0.25
#: How long one of the task's free contractions lasts, when the
#: application asks for them repeated. The practical guide asks for six
#: of about a second each, with a couple of seconds between them.
_BURST_S = 1.0
#: Standard deviation of the EMG in mV: at rest, and at full activation.
_REST_MV = 0.006
_MAX_MV = (0.30, 0.20)


def is_simulated_address(address: str) -> bool:
    """Whether *address* selects the simulated board."""
    return str(address).strip().lower() in SIMULATED_ADDRESSES


# -- the frame, as the board packs it -------------------------------------------

def frame_size(n_channels: int) -> int:
    """Bytes per frame with *n_channels* enabled (the board's own arithmetic)."""
    if n_channels <= 4:
        return math.ceil((12.0 + 10.0 * n_channels) / 8.0)
    return math.ceil((52.0 + 6.0 * (n_channels - 4)) / 8.0)


def crc4(frame: bytes | bytearray) -> int:
    """The board's 4-bit CRC, over a frame whose last nibble is still zero."""
    x = 0
    for byte in frame:
        for bit in range(7, -1, -1):
            x <<= 1
            if x & 0x10:
                x ^= 0x03
            x ^= (byte >> bit) & 0x01
    return x & 0x0F


def encode_frame(values: list[int], seq: int, digital: int = 0) -> bytes:
    """One frame: the enabled channels in order (10 bits for the first four
    positions, 6 bits for the fifth and sixth), the sequence number and the
    CRC — the inverse of ``BitalinoDevice._extract_channel``."""
    n = len(values)
    size = frame_size(n)
    a = [int(v) for v in values] + [0] * (6 - n)
    f = bytearray(size)

    def put(from_end: int, value: int) -> None:
        if from_end <= size:
            f[-from_end] = value & 0xFF

    put(1, (seq & 0x0F) << 4)
    put(2, ((digital & 0x0F) << 4) | ((a[0] >> 6) & 0x0F))
    put(3, ((a[0] & 0x3F) << 2) | ((a[1] >> 8) & 0x03))
    put(4, a[1] & 0xFF)
    put(5, (a[2] >> 2) & 0xFF)
    put(6, ((a[2] & 0x03) << 6) | ((a[3] >> 4) & 0x3F))
    put(7, ((a[3] & 0x0F) << 4) | ((a[4] >> 2) & 0x0F))
    put(8, ((a[4] & 0x03) << 6) | (a[5] & 0x3F))
    f[-1] |= crc4(f)
    return bytes(f)


def mv_to_adc(mv: float) -> int:
    """Inverse of the application's EMG conversion (gain 1009, 3.3 V, 10 bits)."""
    adc = round((mv * _GAIN / (_VCC * 1000.0) + 0.5) * _ADC_MAX)
    return min(_ADC_MAX, max(0, adc))


def g_to_adc(g: float) -> int:
    """Inverse of the application's accelerometer conversion (±1 g, 10 bits)."""
    return min(_ADC_MAX, max(0, round((g + 1.0) / 2.0 * _ADC_MAX)))


# -- the synthetic subject ------------------------------------------------------

def _ramp(t: float, start: float, end: float, ramp: float) -> float:
    """0 outside [start, end], 1 inside, with raised-cosine edges."""
    if t <= start or t >= end:
        return 0.0
    x = min(1.0, (t - start) / ramp, (end - t) / ramp)
    return 0.5 - 0.5 * math.cos(math.pi * x)


class _SyntheticSubject:
    """Two muscles on the first two EMG inputs enabled, and an accelerometer."""

    def __init__(self, acc_channel: int | None, seed: int | None) -> None:
        self.acc_channel = acc_channel
        self._rng = random.Random(seed)
        self._movement = 0.0
        self._delay: list[float] = []
        #: ``{muscle: (level, repeat_s)}`` while the application is asking
        #: for something of that muscle, and the muscles missing from it
        #: follow the cycle. Empty the rest of the time. Replaced whole,
        #: never mutated: written from the interface thread and read in
        #: the worker's, so one assignment and no state in between to
        #: catch half done.
        self._asked: dict[int, tuple[float, float | None]] = {}

    def instruct(self, channel_index: int, level: float | None,
                 *, repeat_s: float | None = None) -> None:
        """Ask this muscle for *level*, or stop asking it with ``None``.

        ``0.0`` is an instruction like any other — «do nothing» — and
        ``None`` is the absence of one, which gives this muscle back to
        the cycle. **Per muscle**: what the other is doing is whatever it
        was last told, or the cycle. Asking muscle 0 used to force muscle
        1 to rest, which was right for the calibration and made the
        manoeuvre that works both at once impossible to ask for.

        With *repeat_s* the level is not held: the muscle contracts for
        about a second every *repeat_s* seconds, which is what the free
        manoeuvres of the task look like. A rehearsal without hardware
        then shows the six contractions the screen is asking for instead
        of the one every twelve seconds the cycle happens to give.
        """
        pedido = dict(self._asked)
        if level is None:
            pedido.pop(int(channel_index), None)
        else:
            pedido[int(channel_index)] = (
                float(level), None if repeat_s is None else float(repeat_s))
        self._asked = pedido

    def activation(self, t: float) -> tuple[float, float]:
        """What each muscle is doing at *t*: what was asked, or the cycle.

        While an effort is asked of one muscle the other is at rest: the
        instruction of the calibration is a jerk of that muscle, and a
        maximum measured with the other one firing would be a maximum of
        something else. Nothing here touches the clock, so the cycle is
        where it was when the asking stops.
        """
        asked = self._asked
        phase = t % CYCLE_S
        ciclo = [0.0, 0.0]
        for start, end, l1, l2 in _CYCLE:
            r = _ramp(phase, start, end, _RAMP_S)
            ciclo[0], ciclo[1] = max(ciclo[0], l1 * r), max(ciclo[1], l2 * r)
        fuera = []
        for c in (0, 1):
            pedido = asked.get(c)
            if pedido is None:
                fuera.append(ciclo[c])
                continue
            level, repeat_s = pedido
            if repeat_s is None or repeat_s <= 0:
                fuera.append(level)
                continue
            # One contraction of about a second per period, ramped like
            # the cycle's so the onset detector sees the same edge it
            # would see on a real one.
            fuera.append(level * _ramp(t % repeat_s, 0.0, _BURST_S, _RAMP_S))
        return (fuera[0], fuera[1])

    def sample(self, t: float, fs: float, channels: list[int]) -> list[int]:
        """ADC counts for the enabled *channels*, in ascending order."""
        a1, a2 = self.activation(t)
        gauss = self._rng.gauss
        emg = [c for c in channels if c != self.acc_channel]
        out = []
        for c in channels:
            if c == self.acc_channel:
                # Movement follows the first muscle about 60 ms later and is
                # smoothed like a limb with inertia; a small 9.5 Hz tremor on top.
                self._delay.append(a1)
                late = self._delay.pop(0) if len(self._delay) > max(1, round(0.06 * fs)) else 0.0
                alpha = 1.0 - math.exp(-1.0 / (0.15 * fs))
                self._movement += alpha * (late - self._movement)
                g = (0.30 + 0.60 * self._movement
                     + 0.01 * math.sin(2.0 * math.pi * 9.5 * t) + gauss(0.0, 0.004))
                out.append(g_to_adc(g))
                continue
            k = emg.index(c)
            level = (a1, a2)[k] if k < 2 else 0.0
            mv_sd = _REST_MV + (_MAX_MV[k] if k < 2 else 0.0) * level
            out.append(mv_to_adc(gauss(0.0, mv_sd)))
        return out


# -- the port -------------------------------------------------------------------

class SimulatedBitalinoPort:
    """Stands in for ``serial.Serial`` with a BITalino at the other end.

    ``write`` takes the one-byte commands; ``read`` returns the replies and,
    while the board is streaming, its frames at the real sampling rate —
    blocking as a serial read does, and giving up after ``timeout`` seconds.
    ``close`` from another thread releases a blocked ``read`` at once, as the
    watchdog needs.
    """

    def __init__(self, acc_channel: int | None = None, timeout: float = 5.0,
                 seed: int | None = None) -> None:
        self.port = SIMULATED_PORT
        self.timeout = timeout
        self.is_open = True
        self._subject = _SyntheticSubject(acc_channel, seed)
        self._out = bytearray()
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._fs = 1000
        self._channels: list[int] = []
        self._streaming = False
        self._t0 = 0.0
        self._sent = 0
        self._seq = 0

    def instruct(self, channel_index: int, level: float | None,
                 *, repeat_s: float | None = None) -> None:
        """Pass the application's instruction on to the synthetic subject."""
        self._subject.instruct(channel_index, level, repeat_s=repeat_s)

    # -- the commands
    def write(self, data: bytes) -> int:
        with self._lock:
            for byte in bytes(data):
                self._command(byte)
        return len(data)

    def _command(self, byte: int) -> None:
        if byte == 0x00:
            self._streaming = False
        elif byte == 0x07:
            self._streaming = False
            self._out += VERSION_REPLY
        elif self._streaming:
            return                          # the board ignores the rest while live
        elif byte & 0x03 == 0x03:
            self._fs = _FS_BY_CODE[byte >> 6]
        elif byte & 0x03 in (0x01, 0x02):  # live (and the board's simulation mode)
            mask = byte >> 2
            self._channels = [c for c in range(6) if mask >> c & 1]
            self._streaming = True
            self._t0 = time.perf_counter()
            self._sent = 0
            self._seq = 0

    # -- the frames
    def _fill(self) -> None:
        if not self._streaming or not self._channels:
            return
        due = int((time.perf_counter() - self._t0) * self._fs) - self._sent
        for _ in range(min(due, 2000)):
            t = self._sent / self._fs
            values = self._subject.sample(t, self._fs, self._channels)
            values = [v >> 4 if pos >= 4 else v for pos, v in enumerate(values)]
            self._out += encode_frame(values, self._seq)
            self._seq = (self._seq + 1) & 0x0F
            self._sent += 1

    @property
    def in_waiting(self) -> int:
        with self._lock:
            self._fill()
            return len(self._out)

    def read(self, size: int = 1) -> bytes:
        deadline = time.monotonic() + (self.timeout or 0.0)
        while True:
            if self._closed.is_set():
                import serial

                raise serial.SerialException("the simulated BITalino port is closed")
            with self._lock:
                self._fill()
                if len(self._out) >= size or time.monotonic() >= deadline:
                    data = bytes(self._out[:size])
                    del self._out[:size]
                    return data
                if self._streaming and self._channels:
                    missing = size - len(self._out)
                    frames = math.ceil(missing / frame_size(len(self._channels)))
                    wait = frames / self._fs
                else:
                    wait = 0.01
            self._closed.wait(max(0.001, min(wait, deadline - time.monotonic())))

    def reset_input_buffer(self) -> None:
        with self._lock:
            self._out.clear()

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False
        self._streaming = False
        self._closed.set()
