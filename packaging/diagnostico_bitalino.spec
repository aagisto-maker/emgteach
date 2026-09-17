# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the BITalino connection diagnostic.

Build (from the project root, inside the venv):

    pyinstaller --noconfirm packaging/diagnostico_bitalino.spec

Produces ``dist/diagnostico_bitalino.exe``, a one-file *console* program: it
prints the checks as it goes and keeps the window open at the end. It uses
the application's own BITalino backend (``emgteach.devices.bitalino``) over
``pyserial``, and no Qt — which keeps it far smaller than the application.
"""

import os

ROOT = os.path.dirname(os.path.abspath(SPECPATH))  # noqa: F821  (SPECPATH injected)
SRC = os.path.join(ROOT, "src")
ENTRY = os.path.join(ROOT, "packaging", "run_diagnostico.py")

a = Analysis(  # noqa: F821  (injected by PyInstaller)
    [ENTRY],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=["serial", "serial.tools.list_ports"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # ``import emgteach`` leaves Qt out (its workers are imported when first
    # asked for) and the diagnostic imports no GUI module, so the Qt and
    # plotting stacks stay out. Nor does it filter a signal, read or write an
    # EDF or make a report, so scipy, mne, pyedflib and reportlab stay out too:
    # PyInstaller follows every import statement it finds, including the ones
    # the package only runs when asked, and scipy alone was most of a 61 MB
    # program. tests/test_diagnostico.py runs a whole diagnosis and checks
    # that nothing listed here is imported.
    excludes=[
        "PySide6", "shiboken6", "PyQt5", "PyQt6", "PySide2", "pyqtgraph",
        "matplotlib", "tkinter", "pytest", "_pytest", "IPython",
        "scipy", "mne", "pyedflib", "reportlab", "segno", "pandas",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="diagnostico_bitalino",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
