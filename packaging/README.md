# Standalone Windows build

This folder packages `emgteach` into a single Windows executable
(`emgteach.exe`) that runs on any Windows 10/11 PC **without** a Python
installation. It is meant for the critical-testing phase: hand the `.exe`
to testers, they double-click it, no setup.

## Files

| File | Purpose |
|------|---------|
| `emgteach.spec` | PyInstaller recipe (one-file, windowed). |
| `run_emgteach.py` | Frozen entry point. Normal launch starts the GUI; `--selftest` runs a headless integrity check. |
| `build.log` | Last build output (git-ignored). |

## Build (developer machine)

From the **project root**, inside the project venv (Python 3.10–3.12):

```powershell
pip install -e ".[build]"        # installs PyInstaller
pip install reportlab            # hard runtime dep, needed in the bundle
pyinstaller --noconfirm --clean packaging\emgteach.spec
```

The executable is written to `dist\emgteach.exe`. The build is large
(~several hundred MB on disk before one-file compression) because it bundles
PySide6, mne, scipy, matplotlib and numpy.

### Verify the frozen build (headless)

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
dist\emgteach.exe --selftest      # exit code 0 = OK
Get-Content dist\emgteach_selftest.log
```

`--selftest` imports the full runtime surface and builds the main window
off-screen. Because the app is windowed (no console), the outcome is written
to `emgteach_selftest.log` next to the executable.

### The connection diagnostic

```powershell
pyinstaller --noconfirm --clean packaging\diagnostico_bitalino.spec
```

writes `dist\diagnostico_bitalino.exe`, a console program that uses the
application's own BITalino backend and no Qt. Put it next to `emgteach.exe`:
double-clicked, it takes the address from `bitalino.txt` (or autodetects the
board), checks the Bluetooth adapter, the pairing, the COM port, the
handshake and ten seconds of acquisition, keeps its window open, and saves
`diagnostico_bitalino_<date>.txt` beside it. From a console,
`diagnostico_bitalino.exe simulada` checks the tool itself without the board,
and `diagnostico_bitalino.exe COM5` tries a given port.

### Recovering a recording that did not close

A recording the process did not get to close — a power cut, a forced
close — leaves an EDF with all its signal on disk that no reader accepts
(its header says `-1` records) and without the session's marks, which
pyedflib writes only on close. The worker mirrors every mark to
`<name>.marcas.txt` beside the EDF as it is made, and removes that file on
a normal close. To rebuild a readable file:

```powershell
python -m emgteach.recovery C:\Records\P07_2026-09-10_16-32.edf
```

writes `P07_2026-09-10_16-32_recuperado.edf` with the signal and the marks;
the original is never modified.

### Build in CI

The *Build Windows exe* workflow (`.github/workflows/build-windows-exe.yml`)
builds the same executable and runs the self-test on Windows: on demand
(*Actions → Build Windows exe → Run workflow*), on a pushed `exe-*` tag and
on pull requests that touch `packaging/`. The executable is kept as a
workflow artifact named `emgteach-windows-exe`.

It is not attached to releases, which carry the source only: an unsigned
build meets the antivirus false positive described below as soon as it is
downloaded. To attach it again, give the workflow back its
`release: types: [published]` trigger, `permissions: contents: write` and a
last step that runs
`gh release upload "$TAG" "emgteach-$TAG-windows-x64.exe" --clobber`.
Reverting the commit that removed them
(`git log -- .github/workflows/build-windows-exe.yml`) restores all three.

## Run (tester machine)

Double-click `emgteach.exe`. The first launch is a few seconds slower (the
one-file bundle self-extracts to a temp folder). No install, no admin rights.

> **Antivirus note.** Unsigned one-file PyInstaller executables occasionally
> trigger a SmartScreen / antivirus false positive. If Windows SmartScreen
> appears, choose *More info → Run anyway*. Code-signing would remove this but
> is out of scope for the test build.

### Hardware backends in the .exe

- **Arduino + MyoWare** — over USB serial (`pyserial`). Works out of the box.
- **BITalino (revolution)** — over the **Windows Bluetooth virtual COM port**
  (e.g. `COM5`), using `pyserial`. The backend speaks the BITalino protocol
  itself, so no external `bitalino` module and no PyBluez are bundled.

  **How to connect:** pair the BITalino in Windows Bluetooth settings first;
  Windows then exposes an outgoing COM port for it. In the acquisition tab,
  prefer the device's **MAC address** — it is the same on every PC, whereas
  the COM number is assigned per machine and can change. The app resolves the
  MAC to the current COM port by reading the port list. An explicit `COMx` is
  also accepted, and an empty field autodetects.
- **Once per station** — put a text file `bitalino.txt` next to
  `emgteach.exe` with the address on its first line (lines starting with `#`
  are comments; `simulada` works too, and an empty file means autodetect).
  The acquisition tab starts with it and «Default» returns to it.
- **Without the board** — write `simulada` in the address field: the
  application connects a BITalino simulated in software
  (`emgteach.devices.bitalino_sim`) that speaks the same protocol, so the
  recording, the calibration and the classroom broadcast can be tried on
  any PC. The Bluetooth link is what it leaves out.

## Notes / limitations

- PyInstaller does not cross-compile: build on Windows for Windows. A macOS or
  Linux build must be produced on that OS with the same spec.
- The build is unsigned. For wider distribution, sign `emgteach.exe` with an
  authenticode certificate.
- `git`, if present on a tester's PC, is not required; the PDF-report footer
  simply omits the commit hash when git is unavailable.
