"""Shared pytest fixtures and Qt setup.

The Qt offscreen platform plugin is selected at import time so the
GUI-touching tests (workers and, eventually, tabs) can run on a
headless CI runner without a display server.
"""

from __future__ import annotations

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
