# emgteach Arduino firmware

Streaming firmware for the **Arduino + MyoWare 2.0** acquisition backend
(`emgteach.devices.ArduinoDevice`). It samples one or more analogue EMG
channels and streams raw 10-bit ADC values over USB serial.

## Requirements

- Arduino IDE (or `arduino-cli`).
- An ATmega328P board (Arduino Uno / SparkFun RedBoard Plus) at a **5 V**
  logic level.
- One MyoWare 2.0 sensor per channel.

## Wiring

| Signal              | Arduino pin |
|---------------------|-------------|
| MyoWare #1 `ENV`/`RAW` output | `A0` |
| MyoWare #2 output (2-channel only) | `A1` |
| MyoWare `+`         | `5V`  |
| MyoWare `-`         | `GND` |

The firmware reads the analogue pin directly, so connect the MyoWare
output you want to digitise (the `RAW` output if you intend to apply the
emgteach DSP pipeline, which expects a raw EMG signal).

## Flashing

1. Open `emgteach_arduino.ino` in the Arduino IDE.
2. For **two channels**, set `N_CHANNELS` to `2` near the top of the
   sketch (it is `1` by default). Leave it at `1` for a single channel.
3. Select your board and port, then upload.

Re-flashing replaces whatever sketch is currently on the board.

## Using it from emgteach

The `N_CHANNELS` value in the firmware **must match** the device:

```python
from emgteach.devices import ArduinoDevice

device = ArduinoDevice(port="COM4", fs=1000)               # 1 channel
device = ArduinoDevice(port="COM4", fs=1000, n_channels=2) # 2 channels
```

In the GUI, the channel count is selected on the acquisition tab.

## Protocol

```
Arduino -> PC : "READY\n"     once, after reset
PC -> Arduino : "START\n"     begin streaming at SAMPLE_RATE_HZ
PC -> Arduino : "STOP\n"      stop streaming
Arduino -> PC : "STOPPED\n"   acknowledge STOP
PC -> Arduino : "PING\n"      liveness check
Arduino -> PC : "PONG\n"      reply to PING
Arduino -> PC : N_CHANNELS x uint16 little-endian per sample tick,
                channels frame-interleaved (ch0, ch1, ...)
```

Baud rate **115200**, sample rate **1000 Hz** by default
(`SAMPLE_RATE_HZ`). At 1 kHz with two channels each tick transmits 4
bytes (~0.35 ms) and performs two `analogRead`s (~0.2 ms), comfortably
within the 1 ms budget.

> ⚠️ This firmware has not been validated end-to-end on hardware in this
> repository's CI (there is no Arduino in the loop). Verify a real
> acquisition after flashing before relying on it for teaching.
