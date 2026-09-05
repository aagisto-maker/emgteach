"""PyInstaller entry point for the standalone *emgteach* build.

A normal launch delegates to :func:`emgteach.__main__.main` (the PySide6
GUI). Invoked with ``--selftest`` it instead imports the full runtime
surface, builds the main window off-screen, pumps the event loop once and
exits ``0`` — a headless integrity check used to validate the frozen
executable (a missing bundled module then fails loudly with a non-zero
exit code instead of only crashing on the testers' machines).
"""

from __future__ import annotations

import os
import sys


def _app_version() -> str:
    try:
        import emgteach

        return getattr(emgteach, "__version__", "?")
    except Exception:  # pragma: no cover - defensive
        return "?"


def _di(mensaje: str, salida) -> None:
    """Say it on the console, if this launch has one. Never raises."""
    if salida is None:
        return
    try:
        salida.write(mensaje + "\n")
        salida.flush()
    except Exception:  # pragma: no cover - a closed or unwritable stream
        pass


def _selftest_log_path() -> str:
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    return os.path.join(base, "emgteach_selftest.log")


# Runtime modules the frozen build must contain. Importing each one both
# validates it was bundled and exercises mne's lazy loader.
_RUNTIME_MODULES = (
    "matplotlib",
    "matplotlib.backends.backend_agg",     # PDF reports
    "matplotlib.backends.backend_qtagg",   # Analysis / MVC tabs
    "mne",                                 # Analysis EDF reader
    "numpy",
    "pyedflib",
    "pyqtgraph",
    "reportlab",                           # PDF reports
    "scipy.signal",
    "serial",                              # Arduino USB + BITalino over Bluetooth COM
    "serial.tools.list_ports",             # MAC->COM resolution + autodetect
)


def _selftest_body() -> None:
    """Import every runtime dependency and build the GUI off-screen."""
    import importlib

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    for _name in _RUNTIME_MODULES:
        importlib.import_module(_name)

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from emgteach.gui.app import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    settings = QSettings("Bioinstrumentacion", "EMGApp_selftest")
    window = MainWindow(settings)
    window.show()
    app.processEvents()
    window.close()


def _selftest() -> int:
    """Run the integrity check, recording the outcome to a log file.

    The frozen build is *windowed* (no console), so the result is written
    to ``emgteach_selftest.log`` next to the executable and mirrored to
    stdout for source runs.

    "Mirrored" and not "printed": a windowed build started without a console
    of its own has ``sys.stdout`` set to None, and printing to it raises —
    which turned a passing self-test into a non-zero exit and would have
    hidden the traceback of a failing one behind a second, unrelated error.
    The log file is the report; the console is a convenience when there is
    one.
    """
    import traceback

    log = _selftest_log_path()
    try:
        _selftest_body()
    except Exception:
        tb = traceback.format_exc()
        try:
            with open(log, "w", encoding="utf-8") as fh:
                fh.write(f"SELFTEST FAILED: emgteach {_app_version()}\n\n{tb}")
        except OSError:
            pass
        _di(f"SELFTEST FAILED:\n{tb}", sys.stderr)
        return 1

    msg = f"SELFTEST OK: emgteach {_app_version()} (frozen={getattr(sys, 'frozen', False)})"
    try:
        with open(log, "w", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass
    _di(msg, sys.stdout)
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    from emgteach.__main__ import main as gui_main

    rc = gui_main()
    return 0 if rc is None else int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
