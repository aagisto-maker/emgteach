# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone Windows build of *emgteach*.

Build (from the project root, inside the venv):

    pyinstaller --noconfirm packaging/emgteach.spec

Produces a single windowed executable ``dist/emgteach.exe`` that needs no
Python install on the target machine. Both hardware backends talk over
``pyserial``: the Arduino + MyoWare over USB serial, and the BITalino over
its Windows Bluetooth *virtual COM port* (Bluetooth Classic / SPP). No
PyBluez, no external ``bitalino`` package and no BLE stack are involved.
"""

import os

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# The spec lives in <root>/packaging; resolve the project root and src layout.
ROOT = os.path.dirname(os.path.abspath(SPECPATH))  # noqa: F821  (SPECPATH injected)
SRC = os.path.join(ROOT, "src")
ENTRY = os.path.join(ROOT, "packaging", "run_emgteach.py")

datas = []
binaries = []
hiddenimports = []

# --- mne: lazy_loader-based package; collect code, data and .pyi stubs ------
_mne_datas, _mne_binaries, _mne_hidden = collect_all("mne")
datas += _mne_datas
binaries += _mne_binaries
hiddenimports += _mne_hidden

# --- reportlab: bundles font data files -------------------------------------
datas += collect_data_files("reportlab")
hiddenimports += collect_submodules("reportlab")

# --- pyqtgraph: heavy dynamic imports ---------------------------------------
hiddenimports += collect_submodules("pyqtgraph")

# --- pyedflib: C extension --------------------------------------------------
binaries += collect_dynamic_libs("pyedflib")
hiddenimports += collect_submodules("pyedflib")

# --- classroom broadcast: dashboard page + Qt WebSocket/network modules -----
datas += [
    (os.path.join(SRC, "emgteach", "web", "dashboard.html"), "emgteach/web"),
]

# --- explicit hidden imports ------------------------------------------------
hiddenimports += [
    "matplotlib.backends.backend_qtagg",  # Analysis / MVC live canvases
    "matplotlib.backends.backend_agg",    # PDF report rendering
    "serial",                              # pyserial (Arduino USB + BITalino COM)
    "serial.tools.list_ports",             # COM-port enumeration in the GUI
    "PySide6.QtWebSockets",                # classroom broadcast (WebSocket data)
    "PySide6.QtNetwork",                   # classroom broadcast (HTTP + TCP)
    "segno",                               # classroom join QR code
]

# Trim clearly-unused / conflicting packages to keep the binary smaller and
# avoid pulling a second Qt binding. mne treats the 3-D / ML stack as fully
# optional, and we never import it.
excludes = [
    "PyQt5", "PyQt6", "PySide2", "shiboken2",
    "tkinter",
    "pytest", "_pytest", "pluggy",
    "IPython", "jupyter", "jupyter_client", "notebook", "nbconvert", "nbformat",
    "sphinx", "mkdocs",
    "vtk", "pyvista", "pyvistaqt", "nibabel", "dipy", "numba",
    "sklearn", "torch", "tensorflow",
]

a = Analysis(
    [ENTRY],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="emgteach",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX can corrupt Qt / numpy DLLs — keep it off.
    runtime_tmpdir=None,
    console=False,  # windowed app (no terminal window for testers)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
