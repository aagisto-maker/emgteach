"""Connection diagnostic for the BITalino: is this station ready to record?

Run on the laboratory PC before a practical — with the board switched on, or
with the address ``simulada`` to check the tool and the application without
it — it answers, in order, the questions a failed connection leaves open:

1. Which address it tries, and where that came from: the command line,
   ``bitalino.txt`` next to the application, or autodetection.
2. Whether Windows sees a Bluetooth adapter, and whether it works.
3. Whether a BITalino is paired, and which COM port Windows gave it.
4. Whether the board answers the version handshake, and how fast.
5. Some seconds of acquisition: how many frames arrived, at what rate,
   whether any failed its CRC, and whether each channel carries a signal.

It connects exactly as the acquisition tab does — the same
:class:`~emgteach.devices.bitalino.BitalinoDevice`, the same address forms —
so a station that passes here connects in the application. The answers are
also written to a text file next to the application, to be sent to whoever
helps.

Qt-free: it runs as its own small console program.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from emgteach.devices.bitalino import BitalinoDevice
from emgteach.devices.bitalino_sim import is_simulated_address
from emgteach.i18n import set_language, tr
from emgteach.station import ADDRESS_FILE, app_folder, read_station_address

#: Seconds of acquisition the diagnostic records by default.
DEFAULT_SECONDS = 10.0
#: The inputs it opens: A1 and A2, the pair's two muscles (one muscle uses A1).
DEFAULT_CHANNELS = (0, 1)
#: Below this standard deviation (1 µV) an input carries no signal at all.
_FLAT_MV = 0.001
#: A channel with more than this share of samples at the rails is saturated.
_SATURATED_SHARE = 0.01
#: The sampling rate the application records at, and the tolerance around it.
_FS = 1000
_RATE_TOLERANCE = 0.05
#: How an adapter's instance id starts; paired devices start with BTHENUM.
_RADIO_PREFIXES = ("USB\\", "PCI\\", "ACPI\\", "UART\\", "SD\\")
_MAC_IN_HWID = re.compile(r"&([0-9A-F]{12})_")
_MAC_IN_ID = re.compile(r"DEV_([0-9A-F]{12})")


@dataclass
class Check:
    """One question and its answer; ``ok`` is ``None`` when it could not be
    asked or does not apply."""

    title: str
    ok: bool | None
    lines: list[str] = field(default_factory=list)


@dataclass
class Diagnosis:
    address: str
    source: str
    checks: list[Check] = field(default_factory=list)
    report_path: Path | None = None

    @property
    def ok(self) -> bool:
        """Ready to record: nothing failed, and the acquisition passed."""
        acquired = any(c.title == tr("Acquisition") and c.ok for c in self.checks)
        return acquired and all(c.ok is not False for c in self.checks)


# -- what Windows knows ----------------------------------------------------------

def bluetooth_devices() -> list[dict] | None:
    """Windows' Bluetooth devices — adapters and paired devices — or ``None``
    when Windows cannot be asked (another system, or PowerShell refused)."""
    if platform.system() != "Windows":
        return None
    command = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        "Get-PnpDevice -Class Bluetooth | "
        "Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Compress"
    )
    try:
        run = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(run.stdout) if run.returncode == 0 and run.stdout.strip() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if data is None:
        return None
    if isinstance(data, dict):
        data = [data]
    return [
        {"name": str(d.get("FriendlyName") or ""), "status": str(d.get("Status") or ""),
         "id": str(d.get("InstanceId") or "")}
        for d in data
    ]


def classify_bluetooth(devices: list[dict]) -> tuple[list[dict], list[dict]]:
    """(adapters, paired BITalinos) among Windows' Bluetooth devices."""
    radios = [d for d in devices if d["id"].upper().startswith(_RADIO_PREFIXES)]
    boards = [d for d in devices if "bitalino" in d["name"].lower()]
    return radios, boards


def _mac(hex12: str) -> str:
    return ":".join(hex12[i:i + 2] for i in range(0, 12, 2))


def bluetooth_com_ports() -> list[tuple[str, str, str]]:
    """(port, "outgoing" or "incoming", remote MAC) for each Bluetooth COM port."""
    from serial.tools import list_ports

    ports = []
    for p in list_ports.comports():
        hwid = (p.hwid or "").upper()
        if "BTHENUM" not in hwid and "bluetooth" not in (p.description or "").lower():
            continue
        m = _MAC_IN_HWID.search(hwid)
        hex12 = m.group(1) if m else ""
        if hex12 and hex12 != "000000000000":
            ports.append((p.device, "outgoing", _mac(hex12)))
        else:
            ports.append((p.device, "incoming", ""))
    return ports


# -- the checks ------------------------------------------------------------------

def _check_bluetooth(checks: list[Check], say: Callable[[str], None]) -> None:
    devices = bluetooth_devices()
    if devices is None:
        _add(checks, Check(tr("Bluetooth adapter"), None,
                           [tr("Windows could not be asked; the connection below says the rest.")]), say)
        return
    radios, boards = classify_bluetooth(devices)
    working = [r for r in radios if r["status"].upper() == "OK"]
    lines = [f"{r['name']} — {r['status']}" for r in radios]
    if not working:
        lines.append(tr("No working Bluetooth adapter: plug in the dongle, or switch Bluetooth "
                        "on in Windows settings."))
    _add(checks, Check(tr("Bluetooth adapter"), bool(working), lines), say)
    lines = []
    for b in boards:
        m = _MAC_IN_ID.search(b["id"].upper())
        lines.append(f"{b['name']}" + (f" ({_mac(m.group(1))})" if m else ""))
    if not boards:
        lines.append(tr("No BITalino is paired. Settings > Bluetooth & devices > Add device, "
                        "with the board switched on; its PIN is 1234. If it is not listed, set "
                        "Bluetooth devices discovery to Advanced (Settings > Bluetooth & "
                        "devices > Devices)."))
    _add(checks, Check(tr("BITalino paired"), bool(boards), lines), say)


def _check_port(address: str, checks: list[Check], say: Callable[[str], None]) -> None:
    ports = bluetooth_com_ports()
    outgoing = [(dev, mac) for dev, kind, mac in ports if kind == "outgoing"]
    lines = [f"{dev} → {mac}" for dev, mac in outgoing]
    if BitalinoDevice._MAC_RE.match(address):
        wanted = BitalinoDevice._norm_hex(address)
        found = [dev for dev, mac in outgoing if BitalinoDevice._norm_hex(mac) == wanted]
        if found:
            lines = [tr("{mac} is on {port}").format(mac=address, port=found[0])]
        else:
            lines.append(tr("No Bluetooth COM port leads to {mac}: pair that BITalino, or check "
                            "the address in {file}.").format(mac=address, file=ADDRESS_FILE))
        _add(checks, Check(tr("COM port"), bool(found), lines), say)
        return
    if address:                                  # an explicit COM port
        from serial.tools import list_ports

        exists = any(p.device.upper() == address.upper() for p in list_ports.comports())
        if not exists:
            lines.append(tr("There is no {port} on this PC.").format(port=address))
        _add(checks, Check(tr("COM port"), exists, lines), say)
        return
    if not outgoing:                             # autodetect
        lines.append(tr("No outgoing Bluetooth COM port: no BITalino is paired with this PC."))
    _add(checks, Check(tr("COM port"), bool(outgoing), lines), say)


def _check_acquisition(address: str, seconds: float, channels: tuple[int, ...],
                       checks: list[Check], say: Callable[[str], None]) -> None:
    device = BitalinoDevice(address, fs=_FS, channels=list(channels))
    start = time.perf_counter()
    try:
        device.open()
    except Exception as exc:
        _add(checks, Check(tr("Connection"), False, [str(exc)]), say)
        return
    opened = time.perf_counter() - start
    _add(checks, Check(tr("Connection"), True, [
        tr("{name} answered «{version}» in {s:.1f} s").format(
            name=device.name, version=device.firmware_version, s=opened)]), say)

    blocks: list[np.ndarray] = []
    error = ""
    start = time.perf_counter()
    try:
        while time.perf_counter() - start < seconds:
            blocks.append(device.read(100))
    except Exception as exc:
        error = str(exc)
    finally:
        elapsed = time.perf_counter() - start
        device.close()
    data = np.vstack(blocks) if blocks else np.empty((0, len(channels)))
    rate = data.shape[0] / elapsed if elapsed > 0 else 0.0
    ok = not error and data.shape[0] > 0 and abs(rate - _FS) <= _RATE_TOLERANCE * _FS
    lines = [tr("{n} frames in {s:.1f} s: {hz:.0f} Hz (the board sends {fs})").format(
        n=data.shape[0], s=elapsed, hz=rate, fs=_FS)]
    if error:
        lines.append(tr("It stopped: {error}").format(error=error))
    else:
        lines.append(tr("No frame failed its CRC."))
    top = device.physical_max
    for i, ch in enumerate(channels):
        col = data[:, i] if data.shape[0] else np.zeros(1)
        sd = float(np.std(col))
        at_rails = float(np.mean(np.abs(col) >= 0.99 * top))
        note = ""
        if sd < _FLAT_MV:
            note = " — " + tr("flat: nothing reaches this input")
        elif at_rails > _SATURATED_SHARE:
            note = " — " + tr("saturated in {pct:.0f} % of the samples").format(pct=100 * at_rails)
        lines.append(tr("A{n}: standard deviation {sd:.3f} mV").format(n=ch + 1, sd=sd) + note)
    _add(checks, Check(tr("Acquisition"), ok, lines), say)


def _add(checks: list[Check], check: Check, say: Callable[[str], None]) -> None:
    checks.append(check)
    say(_render_check(check))


def _render_check(check: Check) -> str:
    mark = {True: "[OK]", False: f"[{tr('FAIL')}]", None: "[--]"}[check.ok]
    return "\n".join([f"{mark:7s} {check.title}"] + [f"        {line}" for line in check.lines])


# -- the diagnosis -----------------------------------------------------------------

def run_diagnosis(address: str | None = None, *, seconds: float = DEFAULT_SECONDS,
                  channels: tuple[int, ...] = DEFAULT_CHANNELS,
                  folder: Path | None = None,
                  say: Callable[[str], None] = print) -> Diagnosis:
    """Ask every question in order, print the answers and write the report.

    *address* is what the acquisition field takes; ``None`` reads it from
    ``bitalino.txt`` in *folder* (the application's), and without the file
    the board is autodetected.
    """
    folder = app_folder() if folder is None else Path(folder)
    if address is None:
        written = read_station_address(folder)
        if written is None:
            address, source = "", tr("no {file}: autodetected").format(file=ADDRESS_FILE)
        else:
            address, source = written, tr("from {file}").format(file=ADDRESS_FILE)
    else:
        address, source = address.strip(), tr("given on the command line")
    diagnosis = Diagnosis(address, source)
    when = datetime.now()
    say(_header(diagnosis, when))

    if is_simulated_address(address):
        _add(diagnosis.checks, Check(tr("Bluetooth"), None,
                                     [tr("Does not apply: the BITalino is simulated.")]), say)
    else:
        _check_bluetooth(diagnosis.checks, say)
        _check_port(address, diagnosis.checks, say)
    _check_acquisition(address, seconds, channels, diagnosis.checks, say)

    verdict = (tr("Result: ready to record.") if diagnosis.ok
               else tr("Result: not ready. The first check that failed says why."))
    say(verdict)
    report = "\n\n".join([_header(diagnosis, when)]
                         + [_render_check(c) for c in diagnosis.checks] + [verdict]) + "\n"
    path = folder / f"diagnostico_bitalino_{when:%Y%m%d_%H%M%S}.txt"
    try:
        path.write_text(report, encoding="utf-8")
        diagnosis.report_path = path
        say(tr("Report saved in {path}").format(path=path))
    except OSError as exc:
        say(tr("The report could not be saved: {error}").format(error=exc))
    return diagnosis


def _header(diagnosis: Diagnosis, when: datetime) -> str:
    try:
        from emgteach import __version__
    except Exception:  # pragma: no cover - defensive
        __version__ = "?"
    shown = diagnosis.address or tr("empty: autodetect")
    return "\n".join([
        tr("emgteach {version} — BITalino connection diagnostic — {when}").format(
            version=__version__, when=f"{when:%Y-%m-%d %H:%M}"),
        tr("Address: {address} ({source})").format(address=shown, source=diagnosis.source),
    ])


def system_language() -> str:
    """The Windows interface language, as the application would pick it."""
    try:
        import ctypes

        return "es" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x0A else "en"
    except Exception:
        import locale

        name = (locale.getlocale()[0] or "").lower()
        return "es" if name.startswith(("es", "spanish")) else "en"


def main(argv: list[str] | None = None) -> int:
    set_language(system_language())
    parser = argparse.ArgumentParser(description=tr("BITalino connection diagnostic."))
    parser.add_argument(
        "address", nargs="?", default=None,
        help=tr("MAC address, COM port or «simulada»; without it, the one in "
                "bitalino.txt, or autodetection."))
    parser.add_argument("--seconds", type=float, default=DEFAULT_SECONDS,
                        help=tr("seconds of acquisition (10 by default)"))
    args = parser.parse_args(argv)
    return 0 if run_diagnosis(args.address, seconds=args.seconds).ok else 1
