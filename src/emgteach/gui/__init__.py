"""PySide6 graphical user interface for emgteach.

The GUI is a thin layer on top of the Qt-free analytic core. The single
entry point :func:`emgteach.gui.app.main` instantiates the QApplication,
shows a brief splash screen and constructs the QMainWindow with three
tabs (Acquisition, Analysis, MVC).
"""

from __future__ import annotations

from emgteach.gui.app import main

__all__ = ["main"]
