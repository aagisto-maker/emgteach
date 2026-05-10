"""Smoke tests that the package is importable and exposes the expected API.

These tests intentionally avoid instantiating any Qt object, so they
run on a headless machine without the libEGL/libGL system libraries
needed by PySide6.QtGui. End-to-end GUI tests live in ``test_workers``
and (eventually) ``test_gui`` and are gated by the ``gui`` marker.
"""

from __future__ import annotations

import importlib

import pytest


def test_version_is_a_string() -> None:
    import emgteach

    assert isinstance(emgteach.__version__, str)
    assert emgteach.__version__.count(".") >= 2


def test_main_module_is_importable() -> None:
    """``python -m emgteach`` must at least be importable.

    ``main()`` itself opens a QApplication, which we cannot run on a
    headless CI runner without a display server, so we only verify
    that the module loads and exposes a callable ``main``.
    """
    mod = importlib.import_module("emgteach.__main__")
    assert callable(mod.main)


def test_gui_module_is_importable() -> None:
    """The ``emgteach.gui`` package must import without instantiating Qt.

    Skipped on systems where the Qt platform plugin is unavailable
    (e.g. a sandbox without libEGL.so.1).
    """
    try:
        importlib.import_module("emgteach.gui")
    except ImportError as exc:
        if "libEGL" in str(exc) or "libGL" in str(exc):
            pytest.skip(f"Qt platform libraries not available: {exc}")
        raise
