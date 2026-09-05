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

## Notes / limitations

- PyInstaller does not cross-compile: build on Windows for Windows. A macOS or
  Linux build must be produced on that OS with the same spec.
- The build is unsigned. For wider distribution, sign `emgteach.exe` with an
  authenticode certificate.
- `git`, if present on a tester's PC, is not required; the PDF-report footer
  simply omits the commit hash when git is unavailable.
