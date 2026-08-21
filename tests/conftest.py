"""Shared pytest fixtures and Qt setup.

The Qt offscreen platform plugin is selected at import time so the
GUI-touching tests (workers and, eventually, tabs) can run on a
headless CI runner without a display server.
"""

from __future__ import annotations

import gc
import os

import pytest

# Must be set before any PySide6 import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """Session-wide QApplication shared by the GUI and worker tests.

    A full ``QApplication`` (not just ``QCoreApplication``) so widget tests
    can create real widgets; it doubles as the event loop for the QThread
    worker tests. PySide6 is imported lazily so the Qt-free smoke tests still
    run on machines without the Qt platform libraries.
    """
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # pragma: no cover — headless without Qt
        pytest.skip(f"PySide6/Qt unavailable: {exc}")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window(qapp):
    """A shown MainWindow on throwaway settings, closed afterwards.

    Shown rather than merely constructed because the mode and tour tests ask
    what is visible, and Qt only gives real geometry to a window on screen
    (offscreen still counts). The saved port stands in for a machine that has
    been set up already, so the first-run exception does not fire.
    """
    from PySide6.QtCore import QSettings

    from emgteach.gui.app import MainWindow

    settings = QSettings("emgteach-test", "gui-window")
    settings.clear()
    settings.setValue("adquisicion/port", "COM5")
    win = MainWindow(settings)
    win.resize(1400, 900)
    win.show()
    qapp.processEvents()
    try:
        yield win
    finally:
        settings.clear()
        qapp.processEvents()   # flush deferred canvas draws before teardown
        win.close()
        # Destroy this window deterministically before the next test builds
        # one. Left to the garbage collector, the C++ side of a discarded
        # window gets freed at an arbitrary moment — including part-way
        # through the construction of its successor, which crashes inside
        # pyqtgraph with an access violation on Windows.
        win.deleteLater()
        qapp.processEvents()
        qapp.processEvents()
        gc.collect()
