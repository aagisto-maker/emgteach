/*
 * emgteach_arduino — EMG streaming firmware for Arduino + MyoWare 2.0
 *
 * Companion firmware for emgteach.devices.ArduinoDevice. Streams one or
 * more analogue EMG channels as raw 10-bit ADC samples over USB serial.
 *
 * Wire protocol (must match ArduinoDevice):
 *   Arduino -> PC : "READY\n"      once, after reset
 *   PC -> Arduino : "START\n"      begin streaming at SAMPLE_RATE_HZ
 *   PC -> Arduino : "STOP\n"       stop streaming
 *   Arduino -> PC : "STOPPED\n"    acknowledge STOP
 *   PC -> Arduino : "PING\n"       liveness check
 *   Arduino -> PC : "PONG\n"       reply to PING
 *   Arduino -> PC : N_CHANNELS x uint16 little-endian per sample tick,
 *                   channels frame-interleaved (ch0, ch1, ...). The host
 *                   reshapes the flat stream into (sample, channel).
 *
 * Baud rate is 115200 (the CH340 driver on many RedBoard Plus boards
 * silently drops bytes at higher rates; 115200 keeps a wide margin over
 * the useful 20000 bps of a single 1 kHz channel).
 *
 * Two channels (e.g. agonist/antagonist):
 *   1. Set N_CHANNELS to 2 below and re-flash.
 *   2. Wire the second MyoWare 2.0 sensor output to A1 (see README.md).
 *   3. Construct the device as ArduinoDevice(port, n_channels=2).
 */

const uint8_t  N_CHANNELS     = 1;          // 1 or 2 (add pins for more)
const uint8_t  CHANNEL_PINS[] = {A0, A1};   // analogue input per channel
const uint32_t SAMPLE_RATE_HZ = 1000;       // must match ArduinoDevice fs
const uint32_t BAUD           = 115200;

const uint32_t SAMPLE_PERIOD_US = 1000000UL / SAMPLE_RATE_HZ;

bool     streaming      = false;
uint32_t next_sample_us = 0;
String   cmd            = "";

void setup() {
  Serial.begin(BAUD);
  analogReference(DEFAULT);   // 5 V reference (matches ArduinoDevice _V_REF)
  delay(50);                  // let the USB-serial reset preamble settle
  Serial.println("READY");
}

void handleCommand(const String& c) {
  if (c == "START") {
    streaming = true;
    next_sample_us = micros();
  } else if (c == "STOP") {
    streaming = false;
    Serial.println("STOPPED");
  } else if (c == "PING") {
    Serial.println("PONG");
  }
}

void loop() {
  // -- Parse incoming line-delimited commands --
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    if (ch == '\n') {
      cmd.trim();
      handleCommand(cmd);
      cmd = "";
    } else if (ch != '\r') {
      cmd += ch;
      if (cmd.length() > 16) {
        cmd = "";   // guard against runaway input
      }
    }
  }

  // -- Stream samples on a fixed-rate tick --
  if (streaming) {
    uint32_t now = micros();
    // The (int32_t) cast makes the comparison robust to micros() wraparound.
    if ((int32_t)(now - next_sample_us) >= 0) {
      for (uint8_t i = 0; i < N_CHANNELS; i++) {
        uint16_t v = (uint16_t)analogRead(CHANNEL_PINS[i]);
        Serial.write((uint8_t)(v & 0xFF));         // low byte
        Serial.write((uint8_t)((v >> 8) & 0xFF));  // high byte
      }
      next_sample_us += SAMPLE_PERIOD_US;
    }
  }
}
