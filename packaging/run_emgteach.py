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


def _selftest_log_path() -> str:
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    return os.path.join(base, "emgteach_selftest.log")


def _selftest_body() -> None:
    """Import every runtime dependency and build the GUI off-screen."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    # Touch the heavy, dynamically-imported modules so a frozen build that
    # dropped one fails here rather than in front of a tester.
    import matplotlib  # noqa: F401
    import matplotlib.backends.backend_agg  # noqa: F401  (PDF reports)
    import matplotlib.backends.backend_qtagg  # noqa: F401  (Analysis/MVC tabs)
    import mne  # noqa: F401  (Analysis EDF reader)
    import numpy  # noqa: F401
    import pyedflib  # noqa: F401
    import pyqtgraph  # noqa: F401
    import reportlab  # noqa: F401  (PDF reports)
    import scipy.signal  # noqa: F401
    import serial  # noqa: F401  (Arduino + BITalino-over-COM)

    import bitalino  # noqa: F401  (BITalino backend, COM-port path)

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
        print(f"SELFTEST FAILED:\n{tb}", file=sys.stderr)
        return 1

    msg = f"SELFTEST OK: emgteach {_app_version()} (frozen={getattr(sys, 'frozen', False)})"
    try:
        with open(log, "w", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass
    print(msg)
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    from emgteach.__main__ import main as gui_main

    rc = gui_main()
    return 0 if rc is None else int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
